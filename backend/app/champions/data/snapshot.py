"""Champions League snapshot building, Elo replay and calibration."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np

from app.champions.config import ChampionsSettings, get_champions_settings
from app.champions.data.api_football import (
    DataSourceError,
    load_history_matches,
    load_source_matches,
)
from app.champions.models import ChampionsMatch, ChampionsSnapshot, ChampionsTeam
from app.champions.names import (
    TEAM_POTS,
    TEAM_SEEDS,
    fallback_identity,
    normalize_team_key,
    team_seed,
)
from app.data.clubelo import fetch_clubelo_ratings
from app.data.history import evaluate_predictions
from app.data.names import normalize_name
from app.domain.davidson import DavidsonParams, fit_davidson, outcome_probabilities
from app.domain.elo import DEFAULT_HOME_ADVANTAGE, DEFAULT_K, update_ratings
from app.domain.scoreline import (
    ScorelineParams,
    expected_goals,
    fit_scoreline,
    sample_scores_batch,
)

DEFAULT_START_RATING = 1500.0
MIN_SCORELINE_SAMPLES = 30
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@dataclass
class ReplayResult:
    ratings: dict[str, float]
    start_ratings: dict[str, float]
    applied: int = 0
    without_score: int = 0
    timeline: list[dict] = field(default_factory=list)


@dataclass
class HistoryReplayResult:
    ratings: dict[str, float]
    start_ratings: dict[str, float]
    season_starts: dict[str, dict[str, float]]
    season_ends: dict[str, dict[str, float]]
    applied: int = 0
    without_score: int = 0
    timeline: list[dict] = field(default_factory=list)
    seasons: list[str] = field(default_factory=list)
    regression: float = 0.0


def _side_country(raw: dict, side: str) -> str:
    return str(raw.get(f"{side}_country") or "")


def make_team(
    name: str,
    *,
    country: str = "",
    elo: float = DEFAULT_START_RATING,
) -> ChampionsTeam:
    key = normalize_team_key(name)
    if key is not None:
        seed = team_seed(key)
        if seed is not None:
            return ChampionsTeam(
                id=seed.id,
                name=seed.name,
                short_name=seed.short_name,
                color=seed.color,
                country=seed.country,
                elo=elo,
                pot=TEAM_POTS.get(seed.id),
            )
        _, short_name, color = fallback_identity(name)
        return ChampionsTeam(
            id=key,
            name=name,
            short_name=short_name,
            color=color,
            country=country or "—",
            elo=elo,
            pot=TEAM_POTS.get(key),
        )
    team_id, short_name, color = fallback_identity(name)
    return ChampionsTeam(
        id=team_id,
        name=name,
        short_name=short_name,
        color=color,
        country=country or "—",
        elo=elo,
        pot=TEAM_POTS.get(team_id),
    )


def resolve_teams(
    matches: Iterable[dict], ratings: dict[str, float] | None = None
) -> dict[str, ChampionsTeam]:
    """Resolve every provider team name to a canonical ``ChampionsTeam``."""
    ratings = ratings or {}
    teams: dict[str, ChampionsTeam] = {}
    for raw in matches:
        for side in ("home", "away"):
            name = raw.get(side)
            if not name:
                continue
            country = _side_country(raw, side) or ""
            team = make_team(name, country=country)
            team = team.with_elo(ratings.get(team.id, team.elo))
            teams.setdefault(team.id, team)
    return teams


def with_match_ids(
    raw_matches: Iterable[dict], teams: dict[str, ChampionsTeam]
) -> list[ChampionsMatch]:
    """Convert provider dictionaries into domain matches."""
    matches: list[ChampionsMatch] = []
    for index, raw in enumerate(raw_matches):
        home = make_team(raw["home"], country=_side_country(raw, "home"))
        away = make_team(raw["away"], country=_side_country(raw, "away"))
        if home.id not in teams or away.id not in teams:
            continue
        phase = raw.get("phase") or "league"
        matches.append(
            ChampionsMatch(
                id=str(raw.get("fixture_id") or f"ucl-{phase}-{index}-{home.id}-{away.id}"),
                phase=phase,
                matchday=int(raw.get("matchday") or 0),
                leg=int(raw.get("leg") or 0),
                home_id=home.id,
                away_id=away.id,
                home_goals=raw.get("home_goals"),
                away_goals=raw.get("away_goals"),
                kickoff=raw.get("kickoff"),
                neutral=bool(raw.get("neutral")),
            )
        )
    matches.sort(key=lambda match: (match.kickoff or "", match.id))
    return matches


def _ordered_raw_matches(matches: Iterable[dict]) -> list[dict]:
    return sorted(
        matches,
        key=lambda raw: (
            raw.get("kickoff") or "",
            raw.get("phase") or "",
            str(raw.get("fixture_id") or ""),
        ),
    )


def replay_matches(
    matches: Iterable[dict],
    teams: Iterable[ChampionsTeam],
    params: dict,
) -> ReplayResult:
    """Replay matches in chronological order and return Elo ratings."""
    team_list = list(teams)
    known = {team.id: team for team in team_list}
    start_ratings = {team.id: float(team.elo) for team in team_list}
    ratings = dict(start_ratings)
    k = float(params.get("k", DEFAULT_K))
    home_advantage = float(params.get("home_advantage", DEFAULT_HOME_ADVANTAGE))

    result = ReplayResult(ratings=ratings, start_ratings=start_ratings)
    ordered = _ordered_raw_matches(matches)
    if not ordered:
        return result

    first_date = (ordered[0].get("kickoff") or "")[:10]
    result.timeline.append(
        {
            "date": first_date,
            "ratings": {team_id: round(value, 2) for team_id, value in ratings.items()},
        }
    )
    current_month = first_date[:7]
    last_date = first_date

    for raw in ordered:
        home_id = make_team(raw["home"], country=_side_country(raw, "home")).id
        away_id = make_team(raw["away"], country=_side_country(raw, "away")).id
        if home_id not in known or away_id not in known:
            continue
        if raw.get("home_goals") is None or raw.get("away_goals") is None:
            result.without_score += 1
            continue

        date = (raw.get("kickoff") or "")[:10]
        if date[:7] != current_month:
            result.timeline.append(
                {
                    "date": last_date,
                    "ratings": {
                        team_id: round(value, 2) for team_id, value in ratings.items()
                    },
                }
            )
            current_month = date[:7]

        advantage = 0.0 if raw.get("neutral") else home_advantage
        home_after, away_after = update_ratings(
            ratings[home_id],
            ratings[away_id],
            int(raw["home_goals"]),
            int(raw["away_goals"]),
            k=k,
            home_advantage=advantage,
        )
        ratings[home_id] = home_after
        ratings[away_id] = away_after
        result.applied += 1
        last_date = date or last_date

    if result.timeline:
        result.timeline.append(
            {
                "date": last_date,
                "ratings": {team_id: round(value, 2) for team_id, value in ratings.items()},
            }
        )
    return result


def _timeline_point(
    date: str, season: str, ratings: dict[str, float]
) -> dict:
    return {
        "date": date,
        "season": season,
        "ratings": {
            team_id: round(value, 2) for team_id, value in ratings.items()
        },
    }


def replay_history(
    seasons: list[tuple[str, list[dict]]],
    teams: Iterable[ChampionsTeam],
    params: dict,
    *,
    regression: float = 0.0,
    season_priors: dict[str, dict[str, float]] | None = None,
    prior_weight: float = 0.0,
) -> HistoryReplayResult:
    team_list = list(teams)
    start_ratings = {team.id: float(team.elo) for team in team_list}
    ratings = dict(start_ratings)
    k = float(params.get("k", DEFAULT_K))
    home_advantage = float(params.get("home_advantage", DEFAULT_HOME_ADVANTAGE))
    result = HistoryReplayResult(
        ratings=ratings,
        start_ratings=start_ratings,
        season_starts={},
        season_ends={},
        regression=regression,
    )

    for index, (label, raw_matches) in enumerate(seasons):
        if index > 0 and regression:
            ratings = {
                team_id: value + regression * (DEFAULT_START_RATING - value)
                for team_id, value in ratings.items()
            }

        prior = (season_priors or {}).get(label)
        if prior and prior_weight:
            ratings = {
                team_id: (1.0 - prior_weight) * value
                + prior_weight * prior.get(team_id, value)
                for team_id, value in ratings.items()
            }

        result.seasons.append(label)
        result.season_starts[label] = dict(ratings)
        ordered = sorted(
            raw_matches,
            key=lambda raw: (
                raw.get("kickoff") or "",
                int(raw.get("sequence") or 0),
            ),
        )
        if not ordered:
            result.season_ends[label] = dict(ratings)
            continue

        first_date = (ordered[0].get("kickoff") or "")[:10]
        last_date = first_date
        current_month = first_date[:7]
        result.timeline.append(_timeline_point(first_date, label, ratings))

        for raw in ordered:
            home_id = make_team(
                raw["home"], country=_side_country(raw, "home")
            ).id
            away_id = make_team(
                raw["away"], country=_side_country(raw, "away")
            ).id
            if home_id not in ratings or away_id not in ratings:
                continue
            if raw.get("home_goals") is None or raw.get("away_goals") is None:
                result.without_score += 1
                continue

            date = (raw.get("kickoff") or "")[:10]
            if date[:7] != current_month:
                result.timeline.append(_timeline_point(last_date, label, ratings))
                current_month = date[:7]

            advantage = 0.0 if raw.get("neutral") else home_advantage
            home_after, away_after = update_ratings(
                ratings[home_id],
                ratings[away_id],
                int(raw["home_goals"]),
                int(raw["away_goals"]),
                k=k,
                home_advantage=advantage,
            )
            ratings[home_id] = home_after
            ratings[away_id] = away_after
            result.applied += 1
            last_date = date or last_date

        result.season_ends[label] = dict(ratings)
        result.timeline.append(_timeline_point(last_date, label, ratings))

    result.ratings = ratings
    return result


def calibration_samples(
    matches: Iterable[dict],
    teams: Iterable[ChampionsTeam],
    params: dict,
) -> list[tuple[float, str, str, int]]:
    """Return ``(delta, outcome, phase, matchday)`` using pre-match ratings."""
    team_list = list(teams)
    ratings = {team.id: float(team.elo) for team in team_list}
    k = float(params.get("k", DEFAULT_K))
    home_advantage = float(params.get("home_advantage", DEFAULT_HOME_ADVANTAGE))
    samples: list[tuple[float, str, str, int]] = []

    for raw in _ordered_raw_matches(matches):
        home_id = make_team(raw["home"], country=_side_country(raw, "home")).id
        away_id = make_team(raw["away"], country=_side_country(raw, "away")).id
        if home_id not in ratings or away_id not in ratings:
            continue
        if raw.get("home_goals") is None or raw.get("away_goals") is None:
            continue
        home_goals = int(raw["home_goals"])
        away_goals = int(raw["away_goals"])
        outcome = "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D"
        advantage = 0.0 if raw.get("neutral") else home_advantage
        samples.append(
            (
                ratings[home_id] + advantage - ratings[away_id],
                outcome,
                str(raw.get("phase") or "league"),
                int(raw.get("matchday") or 0),
            )
        )
        home_after, away_after = update_ratings(
            ratings[home_id],
            ratings[away_id],
            home_goals,
            away_goals,
            k=k,
            home_advantage=advantage,
        )
        ratings[home_id] = home_after
        ratings[away_id] = away_after

    return samples


def calibration_score_samples(
    matches: Iterable[dict],
    teams: Iterable[ChampionsTeam],
    params: dict,
) -> list[tuple[float, int, int, str, int]]:
    """Return ``(delta, home_goals, away_goals, phase, matchday)``."""
    team_list = list(teams)
    ratings = {team.id: float(team.elo) for team in team_list}
    k = float(params.get("k", DEFAULT_K))
    home_advantage = float(params.get("home_advantage", DEFAULT_HOME_ADVANTAGE))
    samples: list[tuple[float, int, int, str, int]] = []

    for raw in _ordered_raw_matches(matches):
        home_id = make_team(raw["home"], country=_side_country(raw, "home")).id
        away_id = make_team(raw["away"], country=_side_country(raw, "away")).id
        if home_id not in ratings or away_id not in ratings:
            continue
        if raw.get("home_goals") is None or raw.get("away_goals") is None:
            continue
        home_goals = int(raw["home_goals"])
        away_goals = int(raw["away_goals"])
        if not raw.get("neutral"):
            samples.append(
                (
                    ratings[home_id] - ratings[away_id],
                    home_goals,
                    away_goals,
                    str(raw.get("phase") or "league"),
                    int(raw.get("matchday") or 0),
                )
            )
        advantage = 0.0 if raw.get("neutral") else home_advantage
        home_after, away_after = update_ratings(
            ratings[home_id],
            ratings[away_id],
            home_goals,
            away_goals,
            k=k,
            home_advantage=advantage,
        )
        ratings[home_id] = home_after
        ratings[away_id] = away_after

    return samples


def scoreline_samples_from_matchdays(
    matches: Iterable[ChampionsMatch],
    elo_by_matchday: dict[int, dict[str, float]],
) -> list[tuple[float, int, int]]:
    """Return pre-match Elo deltas and actual goals for league matches."""
    samples: list[tuple[float, int, int]] = []
    for match in matches:
        if match.phase != "league" or not match.is_played or match.neutral:
            continue
        ratings = elo_by_matchday.get(match.matchday)
        if not ratings:
            continue
        if match.home_goals is None or match.away_goals is None:
            continue
        if match.home_id not in ratings or match.away_id not in ratings:
            continue
        samples.append(
            (
                ratings[match.home_id] - ratings[match.away_id],
                int(match.home_goals),
                int(match.away_goals),
            )
        )
    return samples


def calibrate_params(
    matches: Iterable[dict],
    teams: Iterable[ChampionsTeam],
    params: dict | None = None,
) -> dict:
    params = params or {}
    samples = calibration_samples(matches, teams, params)
    if not samples:
        raise ValueError("no samples available to calibrate Davidson")

    def is_train(sample: tuple[float, str, str, int]) -> bool:
        return sample[2] == "league" and sample[3] <= 6

    train = [sample for sample in samples if is_train(sample)]
    validation = [sample for sample in samples if not is_train(sample)]
    if not train:
        train = samples
    if not validation:
        validation = samples

    train_params = fit_davidson([sample[0] for sample in train], [sample[1] for sample in train])
    probabilities = [
        outcome_probabilities(sample[0], train_params).as_tuple() for sample in validation
    ]
    metrics = evaluate_predictions(probabilities, [sample[1] for sample in validation])

    final_params = fit_davidson([sample[0] for sample in samples], [sample[1] for sample in samples])
    return {
        "home_advantage": round(final_params.home_advantage, 4),
        "nu": round(final_params.nu, 4),
        "elo_scale": final_params.elo_scale,
        "validation": {
            "matches": metrics["matches"],
            "accuracy": round(metrics["accuracy"], 6),
            "log_loss": round(metrics["log_loss"], 6),
            "brier": round(metrics["brier"], 6),
            "train_home_advantage": round(train_params.home_advantage, 4),
            "train_nu": round(train_params.nu, 4),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_history_payload(
    replay: HistoryReplayResult,
    *,
    seed_source: str,
    demo_team_ids: Iterable[str],
) -> dict:
    return {
        "season": replay.seasons[-1] if replay.seasons else "",
        "seasons": list(replay.seasons),
        "start_ratings": {
            team_id: round(value, 2)
            for team_id, value in replay.start_ratings.items()
        },
        "final_ratings": {
            team_id: round(value, 2)
            for team_id, value in replay.ratings.items()
        },
        "season_start_ratings": {
            label: {
                team_id: round(value, 2)
                for team_id, value in values.items()
            }
            for label, values in replay.season_starts.items()
        },
        "season_end_ratings": {
            label: {
                team_id: round(value, 2)
                for team_id, value in values.items()
            }
            for label, values in replay.season_ends.items()
        },
        "teams": sorted(demo_team_ids),
        "timeline": replay.timeline,
        "matches_total": replay.applied + replay.without_score,
        "matches_applied": replay.applied,
        "matches_without_score": replay.without_score,
        "seed_source": seed_source,
        "season_regression": replay.regression,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def load_historical_payload() -> dict:
    path = DATA_DIR / "champions_historical.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_params() -> dict:
    path = DATA_DIR / "champions_params.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    fallback = DATA_DIR / "calibrated_params.json"
    if fallback.exists():
        try:
            data = json.loads(fallback.read_text(encoding="utf-8"))
            return {
                "home_advantage": float(data.get("home_advantage", 60.0)),
                "nu": float(data.get("nu", 0.9)),
                "elo_scale": 400,
                "fallback": "laliga",
            }
        except (OSError, ValueError):
            pass
    return {"home_advantage": 60.0, "nu": 0.9, "elo_scale": 400}


def scoreline_params_from_dict(data: dict | None) -> ScorelineParams:
    data = data or {}
    return ScorelineParams(
        home_base=float(data.get("home_base", 1.45)),
        away_base=float(data.get("away_base", 1.15)),
        elo_slope=float(data.get("elo_slope", 0.0018)),
        home_advantage=float(data.get("home_advantage", 60.0)),
        rho=float(data.get("rho", -0.05)),
        max_goals=int(data.get("max_goals", 10)),
    )


def scoreline_params_to_dict(params: ScorelineParams) -> dict:
    return {
        "home_base": round(params.home_base, 3),
        "away_base": round(params.away_base, 3),
        "elo_slope": round(params.elo_slope, 5),
        "home_advantage": round(params.home_advantage, 2),
        "rho": round(params.rho, 4),
        "max_goals": params.max_goals,
    }


_SNAPSHOT: ChampionsSnapshot | None = None
_SNAPSHOT_LOADED_AT = 0.0
_SNAPSHOT_LOCK = threading.Lock()


def _season_label(season: int) -> str:
    return f"{season}/{(season + 1) % 100:02d}"


CLUBELO_ALIASES: dict[str, str] = {
    "Man City": "manchester-city",
    "Man United": "manchester-united",
    "Ein Frankfurt": "eintracht",
    "M'gladbach": "bor-monchengladbach",
    "Bor. Mönchengladbach": "bor-monchengladbach",
    "Sp Lisbon": "sporting",
    "Sp Braga": "braga",
    "St. Gilloise": "union-saint-gilloise",
    "Paris SG": "psg",
    "PSG": "psg",
}

_CLUBELO_HISTORY: dict | None = None


def _load_clubelo_history() -> dict:
    global _CLUBELO_HISTORY
    if _CLUBELO_HISTORY is None:
        path = DATA_DIR / "clubelo_snapshots.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _CLUBELO_HISTORY = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            _CLUBELO_HISTORY = {}
    return _CLUBELO_HISTORY


def _clubelo_history_snapshot(
    settings: ChampionsSettings, date: str
) -> dict[str, float]:
    if not settings.clubelo_enabled or settings.data_source.lower() == "demo":
        return {}
    data = _load_clubelo_history()
    ratings = data.get("ratings", {})
    if not isinstance(ratings, dict):
        return {}
    value = ratings.get(date, {})
    return value if isinstance(value, dict) else {}


def _clubelo_snapshot(settings: ChampionsSettings, date: str) -> dict[str, float]:
    if not settings.clubelo_enabled or settings.data_source.lower() == "demo":
        return {}
    compact = _clubelo_history_snapshot(settings, date)
    if compact:
        return compact
    marker = Path(settings.cache_dir) / f"clubelo_unavailable_{date}"
    if marker.exists() and time.time() - marker.stat().st_mtime < settings.cache_ttl_seconds:
        return {}
    try:
        ratings = fetch_clubelo_ratings(date, settings.cache_dir)
    except Exception:  # noqa: BLE001 - ClubElo is an optional seed
        ratings = {}
    if not ratings:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("unavailable", encoding="utf-8")
    return ratings


def _resolve_known_id(
    name: str,
    known_ids: set[str],
    known_by_norm: dict[str, str],
) -> str | None:
    key = normalize_team_key(name)
    if key in known_ids:
        return key
    alias = CLUBELO_ALIASES.get(name)
    if alias in known_ids:
        return alias
    normalized = normalize_name(name)
    if normalized in known_by_norm:
        return known_by_norm[normalized]
    tokens = set(normalized.split())
    candidates = {
        team_id
        for norm, team_id in known_by_norm.items()
        if tokens and tokens.issubset(set(norm.split()))
    }
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _clubelo_by_known_teams(
    clubelo: dict[str, float],
    teams: dict[str, ChampionsTeam],
) -> dict[str, float]:
    known_ids = set(teams)
    known_by_norm: dict[str, str] = {}
    for team_id, team in teams.items():
        known_by_norm.setdefault(normalize_name(team.name), team_id)
        known_by_norm.setdefault(normalize_name(team_id), team_id)
    ratings: dict[str, float] = {}
    for name, elo in clubelo.items():
        team_id = _resolve_known_id(name, known_ids, known_by_norm)
        if team_id is not None:
            ratings[team_id] = max(
                ratings.get(team_id, float("-inf")), float(elo)
            )
    return ratings


def _clubelo_by_id(clubelo: dict[str, float]) -> dict[str, float]:
    ratings: dict[str, float] = {}
    for name, elo in clubelo.items():
        key = normalize_team_key(name)
        if key is not None:
            ratings[key] = float(elo)
        normalized = normalize_name(name)
        key = normalize_team_key(normalized)
        if key is not None:
            ratings[key] = float(elo)
    return ratings


def clubelo_priors_for_seasons(
    settings: ChampionsSettings,
    labels: Iterable[str],
    teams: dict[str, ChampionsTeam],
) -> dict[str, dict[str, float]]:
    priors: dict[str, dict[str, float]] = {}
    for label in labels:
        date = f"{label[:4]}-08-01"
        raw = _clubelo_snapshot(settings, date)
        if not raw:
            continue
        mapped = _clubelo_by_known_teams(raw, teams)
        if mapped:
            priors[label] = mapped
    return priors


def seed_history_ratings(
    teams: dict[str, ChampionsTeam],
    first_season_matches: Iterable[dict],
    clubelo: dict[str, float],
) -> tuple[dict[str, float], str]:
    by_id = _clubelo_by_known_teams(clubelo, teams)
    ratings = {
        team_id: by_id.get(team_id, DEFAULT_START_RATING)
        for team_id in teams
    }
    return ratings, "clubelo" if by_id else "fallback_1500"


def _apply_matchdays(
    matches: Iterable[ChampionsMatch],
    start_ratings: dict[str, float],
    params: dict,
    *,
    max_matchday: int | None = None,
) -> tuple[dict[str, float], dict[int, dict[str, float]]]:
    ratings = dict(start_ratings)
    elo_by_matchday: dict[int, dict[str, float]] = {1: dict(ratings)}
    match_list = [match for match in matches if match.phase == "league"]
    matchdays = sorted({match.matchday for match in match_list})
    for matchday in matchdays:
        if max_matchday is not None and matchday > max_matchday:
            break
        played = [
            match
            for match in match_list
            if match.matchday == matchday and match.is_played
        ]
        if not played:
            continue
        for match in played:
            assert match.home_goals is not None and match.away_goals is not None
            home_after, away_after = update_ratings(
                ratings[match.home_id],
                ratings[match.away_id],
                match.home_goals,
                match.away_goals,
                k=float(params.get("k", DEFAULT_K)),
                home_advantage=0.0 if match.neutral else float(params.get("home_advantage", DEFAULT_HOME_ADVANTAGE)),
            )
            ratings[match.home_id] = home_after
            ratings[match.away_id] = away_after
        elo_by_matchday[matchday + 1] = dict(ratings)
    return ratings, {
        matchday: {team_id: round(value, 2) for team_id, value in values.items()}
        for matchday, values in elo_by_matchday.items()
    }


def _timeline_points(
    matches: Iterable[ChampionsMatch],
    elo_by_matchday: dict[int, dict[str, float]],
    label: str,
) -> list[dict]:
    points: list[dict] = []
    played = [match for match in matches if match.phase == "league" and match.is_played]
    for matchday in sorted({match.matchday for match in played}):
        ratings = elo_by_matchday.get(matchday + 1)
        if not ratings:
            continue
        dates = [
            (match.kickoff or "")[:10]
            for match in played
            if match.matchday == matchday and match.kickoff
        ]
        points.append(
            {
                "date": max(dates) if dates else "",
                "season": label,
                "matchday": matchday,
                "ratings": ratings,
            }
        )
    return points


def build_snapshot_from_matches(
    history_matches: list[dict],
    current_matches: list[dict],
    settings: ChampionsSettings,
    *,
    source: str,
    history_labels: list[str],
    current_label: str,
    history_sources: list[str] | None = None,
) -> ChampionsSnapshot:
    if not history_labels:
        raise ValueError("history_labels must not be empty")

    history_start = int(history_labels[0].split("/")[0])
    history_teams = resolve_teams(history_matches)
    by_season: dict[str, list[dict]] = {}
    for raw in history_matches:
        by_season.setdefault(
            str(raw.get("season") or history_labels[-1]), []
        ).append(raw)
    clubelo_history = _clubelo_snapshot(
        settings, f"{history_start}-08-01"
    )
    clubelo_priors = clubelo_priors_for_seasons(
        settings, history_labels, history_teams
    )
    seeded_ratings, seed_source = seed_history_ratings(
        history_teams,
        by_season.get(history_labels[0], []),
        clubelo_history,
    )
    history_teams = {
        team_id: team.with_elo(seeded_ratings[team_id])
        for team_id, team in history_teams.items()
    }
    season_groups = [
        (label, by_season.get(label, [])) for label in history_labels
    ]

    base_params = {"k": DEFAULT_K, "home_advantage": DEFAULT_HOME_ADVANTAGE}
    prior_weight = float(settings.clubelo_prior_weight)
    replay = replay_history(
        season_groups,
        history_teams.values(),
        base_params,
        regression=float(settings.season_regression),
        season_priors=clubelo_priors,
        prior_weight=prior_weight,
    )

    previous_label = history_labels[-1]
    previous_matches = by_season.get(previous_label, [])
    previous_matches_total = len(previous_matches)
    previous_matches_applied = sum(
        1
        for raw in previous_matches
        if raw.get("home_goals") is not None
        and raw.get("away_goals") is not None
    )
    previous_teams = resolve_teams(previous_matches)

    calibration_start = replay.season_starts.get(previous_label, {})
    calibration_teams = [
        team.with_elo(calibration_start.get(team.id, team.elo))
        for team in previous_teams.values()
    ]
    try:
        calibrated = calibrate_params(previous_matches, calibration_teams)
    except Exception:  # noqa: BLE001 - parameters are optional
        calibrated = load_params()

    clubelo_current: dict[str, float] = {}
    fallback = not current_matches
    if fallback:
        start_ratings = {
            team_id: calibration_start.get(team_id, team.elo)
            for team_id, team in previous_teams.items()
        }
        active_teams = {
            team_id: team.with_elo(start_ratings[team_id])
            for team_id, team in previous_teams.items()
        }
        raw_active = [
            match
            for match in previous_matches
            if match.get("phase") == "league"
        ]
        active_label = previous_label
        max_matchday = settings.fallback_rewind_matchday
        model_params = calibrated
        current_source = source
    else:
        clubelo_current_raw = _clubelo_snapshot(
            settings, settings.clubelo_date_2026
        )
        active_teams = resolve_teams(current_matches)
        clubelo_current = _clubelo_by_known_teams(
            clubelo_current_raw, active_teams
        )
        regressed = {
            team_id: value
            + float(settings.season_regression)
            * (DEFAULT_START_RATING - value)
            for team_id, value in replay.ratings.items()
        }
        ratings: dict[str, float] = {}
        unresolved: list[str] = []
        for team_id in active_teams:
            base = regressed.get(team_id, DEFAULT_START_RATING)
            prior = clubelo_current.get(team_id)
            if prior is not None:
                ratings[team_id] = (
                    (1.0 - prior_weight) * base
                    + prior_weight * prior
                )
            elif team_id in regressed:
                ratings[team_id] = base
            else:
                unresolved.append(team_id)
        if unresolved:
            known = [
                ratings[team_id]
                for team_id in active_teams
                if team_id in ratings
            ]
            baseline = (
                sum(known) / len(known) if known else DEFAULT_START_RATING
            )
            for team_id in unresolved:
                ratings[team_id] = baseline
        active_teams = {
            team_id: team.with_elo(ratings[team_id])
            for team_id, team in active_teams.items()
        }
        start_ratings = dict(ratings)
        raw_active = current_matches
        active_label = current_label
        max_matchday = None
        model_params = calibrated
        current_source = source

    active_matches = with_match_ids(raw_active, active_teams)
    if fallback:
        active_matches = [
            match
            if match.matchday <= settings.fallback_rewind_matchday
            else match.as_pending()
            for match in active_matches
        ]

    current_ratings, elo_by_matchday = _apply_matchdays(
        active_matches,
        start_ratings,
        model_params,
        max_matchday=max_matchday,
    )

    scoreline_params = scoreline_params_from_dict(
        {
            **load_params().get("scoreline", {}),
            "home_advantage": float(calibrated.get("home_advantage", 60.0)),
        }
    )
    scoreline_sample_count = 0
    try:
        scoreline_samples = calibration_score_samples(
            previous_matches, calibration_teams, base_params
        )
        if not fallback:
            scoreline_samples.extend(
                scoreline_samples_from_matchdays(
                    active_matches, elo_by_matchday
                )
            )
        scoreline_sample_count = len(scoreline_samples)
        if scoreline_sample_count >= MIN_SCORELINE_SAMPLES:
            scoreline_params = fit_scoreline(
                [sample[0] for sample in scoreline_samples],
                [sample[1] for sample in scoreline_samples],
                [sample[2] for sample in scoreline_samples],
                home_advantage=float(calibrated.get("home_advantage", 60.0)),
                max_goals=10,
            )
    except Exception:  # noqa: BLE001 - keep the stored scoreline params
        pass
    calibrated["scoreline"] = scoreline_params_to_dict(scoreline_params)
    calibrated["scoreline_samples"] = scoreline_sample_count

    updated_teams = [
        team.with_elo(round(current_ratings.get(team.id, team.elo), 2))
        for team in active_teams.values()
    ]

    if fallback:
        seasons = list(history_labels)
        history_values = {
            team.id: [
                round(
                    replay.season_starts.get(label, {}).get(
                        team.id, team.elo
                    ),
                    2,
                )
                for label in history_labels
            ]
            for team in updated_teams
        }
    else:
        seasons = [*history_labels, current_label]
        history_values = {
            team.id: [
                *[
                    round(
                        replay.season_starts.get(label, {}).get(
                            team.id, team.elo
                        ),
                        2,
                    )
                    for label in history_labels
                ],
                round(start_ratings.get(team.id, team.elo), 2),
            ]
            for team in updated_teams
        }

    timeline_current = _timeline_points(
        active_matches, elo_by_matchday, active_label
    )
    timeline = sorted(
        [*replay.timeline, *timeline_current],
        key=lambda point: (
            point.get("date") or "",
            point.get("season") or "",
        ),
    )
    timeline_series = {
        team.id: [
            point.get("ratings", {}).get(team.id) for point in timeline
        ]
        for team in updated_teams
    }

    played_current = sum(
        1 for match in active_matches if match.is_played
    )
    total_current = len(active_matches)
    if fallback:
        note = (
            f"{current_label} no disponible todavía; mostrando "
            f"{previous_label} con las "
            f"{settings.fallback_rewind_matchday} primeras jornadas "
            "reales y el resto simulado"
        )
    else:
        note = (
            f"Datos reales {active_label} · {played_current}/"
            f"{total_current} partidos jugados"
        )

    verification = {
        "available": bool(history_matches),
        "previous_season": previous_label,
        "history_seasons": len(history_labels),
        "history_start": history_labels[0],
        "history_end": history_labels[-1],
        "previous_matches_total": previous_matches_total,
        "previous_matches_applied": previous_matches_applied,
        "history_seasons_loaded": list(history_labels),
        "history_complete": len(history_labels)
        == int(settings.history_seasons),
        "season_regression": float(settings.season_regression),
        "history_matches_total": replay.applied + replay.without_score,
        "history_matches_applied": replay.applied,
        "history_matches_without_score": replay.without_score,
        "matches_total": replay.applied + replay.without_score,
        "matches_applied": replay.applied,
        "matches_without_score": replay.without_score,
        "teams_total": len(history_teams),
        "teams_resolved": len(history_teams),
        "seed_source": seed_source,
        "clubelo_prior": bool(clubelo_priors or clubelo_current),
        "clubelo_prior_weight": (
            prior_weight if (clubelo_priors or clubelo_current) else 0.0
        ),
        "clubelo_source": (
            "xgabora_clubelo"
            if (clubelo_priors or clubelo_current)
            else "unavailable"
        ),
        "clubelo_dates": [
            label for label in history_labels if label in clubelo_priors
        ]
        + ([current_label] if clubelo_current else []),
        "clubelo_teams_matched": len(
            clubelo_priors.get(previous_label, {})
        ),
        "sources": sorted({*(history_sources or []), source}),
        "fallback": fallback,
        "fallback_season": previous_label if fallback else None,
        "current_matches_total": total_current,
        "current_matches_played": played_current,
        "params": calibrated,
    }

    model = {
        "davidson": {
            "home_advantage": round(float(calibrated.get("home_advantage", 60.0)), 2),
            "nu": round(float(calibrated.get("nu", 0.9)), 4),
            "elo_scale": 400.0,
        },
        "scoreline": scoreline_params_to_dict(scoreline_params),
    }

    return ChampionsSnapshot(
        competition="Champions League",
        season=active_label,
        source=current_source,
        updated_at=datetime.now(timezone.utc).isoformat(),
        teams=sorted(updated_teams, key=lambda team: (-team.elo, team.name)),
        matches=active_matches,
        data_version=_version(updated_teams, active_matches, current_source),
        demo=False,
        data_note=note,
        elo_by_matchday=elo_by_matchday,
        elo_history={
            "seasons": seasons,
            "series": [
                {"team_id": team_id, "values": values}
                for team_id, values in history_values.items()
            ],
            "origin": 1500.0,
        },
        elo_verification=verification,
        elo_timeline={
            "dates": [point.get("date") or "" for point in timeline],
            "series": [
                {"team_id": team_id, "values": values}
                for team_id, values in timeline_series.items()
            ],
        },
        model=model,
        target_season=current_label,
        fallback=fallback,
    )


def build_demo_snapshot(settings: ChampionsSettings | None = None) -> ChampionsSnapshot:
    settings = settings or get_champions_settings()
    payload = load_historical_payload()
    final_ratings = payload.get("final_ratings", {})
    teams: dict[str, ChampionsTeam] = {}
    if payload.get("teams"):
        for team_id in payload["teams"]:
            seed = team_seed(team_id)
            if seed is not None:
                teams[team_id] = ChampionsTeam(
                    id=seed.id,
                    name=seed.name,
                    short_name=seed.short_name,
                    color=seed.color,
                    country=seed.country,
                    elo=float(final_ratings.get(team_id, 1500.0)),
                )
    if not teams:
        for seed in TEAM_SEEDS:
            teams[seed.id] = ChampionsTeam(
                id=seed.id,
                name=seed.name,
                short_name=seed.short_name,
                color=seed.color,
                country=seed.country,
                elo=1500.0,
            )

    demo_path = DATA_DIR / "champions_demo_matches.json"
    raw_matches: list[dict] = []
    if demo_path.exists():
        try:
            raw_matches = json.loads(demo_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw_matches = []
    if not raw_matches:
        raw_matches = _generate_demo_matches(list(teams.values()), settings.fallback_rewind_matchday)

    matches = with_match_ids(raw_matches, teams)
    ratings = {team_id: team.elo for team_id, team in teams.items()}
    params = load_params()
    _, elo_by_matchday = _apply_matchdays(matches, ratings, params)
    model_params = {
        "home_advantage": float(params.get("home_advantage", 60.0)),
        "nu": float(params.get("nu", 0.9)),
    }
    scoreline_params = scoreline_params_from_dict(
        {
            **params.get("scoreline", {}),
            "home_advantage": model_params["home_advantage"],
        }
    )
    updated_teams = [team.with_elo(round(ratings[team.id], 2)) for team in teams.values()]
    return ChampionsSnapshot(
        competition="Champions League",
        season=_season_label(settings.season),
        source="demo",
        updated_at=datetime.now(timezone.utc).isoformat(),
        teams=sorted(updated_teams, key=lambda team: (-team.elo, team.name)),
        matches=matches,
        data_version=_version(updated_teams, matches, "demo"),
        demo=True,
        data_note="Datos de demostración: calendario generado y resultados simulados",
        elo_by_matchday=elo_by_matchday,
        elo_history={"seasons": [], "series": [], "origin": 1500.0},
        elo_verification={"available": False, "seed_source": "demo"},
        elo_timeline={"dates": [], "series": []},
        model={
            "davidson": {
                "home_advantage": round(model_params["home_advantage"], 2),
                "nu": round(model_params["nu"], 4),
                "elo_scale": 400.0,
            },
            "scoreline": scoreline_params_to_dict(scoreline_params),
        },
        target_season=_season_label(settings.season),
    )


def _generate_demo_matches(
    teams: list[ChampionsTeam], rewind_matchday: int
) -> list[dict]:
    team_ids = [team.id for team in teams]
    rotation = list(team_ids)
    raw: list[dict] = []
    for round_index in range(8):
        for pair_index in range(len(team_ids) // 2):
            first = rotation[pair_index]
            second = rotation[len(rotation) - 1 - pair_index]
            home, away = (first, second) if (round_index + pair_index) % 2 == 0 else (second, first)
            raw.append(
                {
                    "phase": "league",
                    "matchday": round_index + 1,
                    "leg": 0,
                    "home": home,
                    "away": away,
                    "home_goals": None,
                    "away_goals": None,
                    "kickoff": None,
                    "neutral": False,
                }
            )
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]

    _balance_home_away(raw)
    ratings = {team.id: team.elo for team in teams}
    params = ScorelineParams()
    rng = np.random.default_rng(20_262_027)
    for match in raw:
        if match["matchday"] > rewind_matchday:
            break
        home_lambda, away_lambda = expected_goals(
            ratings[match["home"]], ratings[match["away"]], params
        )
        home_goals, away_goals = sample_scores_batch(
            home_lambda, away_lambda, 1, rng, params
        )
        match["home_goals"] = int(home_goals[0])
        match["away_goals"] = int(away_goals[0])
    return raw


def _balance_home_away(matches: list[dict]) -> None:
    counts: dict[str, int] = {}
    for match in matches:
        counts[match["home"]] = counts.get(match["home"], 0) + 1
        counts.setdefault(match["away"], 0)
    for _ in range(500):
        over = [team for team, count in counts.items() if count > 4]
        under = [team for team, count in counts.items() if count < 4]
        if not over:
            break
        changed = False
        for team in over:
            for match in matches:
                if match["home"] == team and match["away"] in under:
                    match["home"], match["away"] = match["away"], match["home"]
                    counts[team] -= 1
                    counts[match["away"]] += 1
                    changed = True
                    break
            if changed:
                break
        if not changed:
            break


def _version(
    teams: Iterable[ChampionsTeam], matches: Iterable[ChampionsMatch], source: str
) -> str:
    payload = {
        "source": source,
        "teams": [[team.id, round(team.elo, 4)] for team in teams],
        "matches": [
            [
                match.id,
                match.phase,
                match.matchday,
                match.home_id,
                match.away_id,
                match.home_goals,
                match.away_goals,
            ]
            for match in matches
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def _load_snapshot(settings: ChampionsSettings) -> ChampionsSnapshot:
    source = settings.data_source.lower()
    if source == "demo":
        return build_demo_snapshot(settings)

    current_label = _season_label(settings.season)
    try:
        history_matches, history_labels, history_sources = (
            load_history_matches(settings)
        )
        if not history_matches:
            raise DataSourceError("no history matches")
        try:
            current_matches, current_source = load_source_matches(
                settings, settings.season
            )
        except Exception:  # noqa: BLE001 - fallback season is valid
            current_matches = []
            current_source = (
                history_sources[-1] if history_sources else "openfootball"
            )
        return build_snapshot_from_matches(
            history_matches,
            current_matches,
            settings,
            source=current_source,
            history_labels=history_labels,
            current_label=current_label,
            history_sources=history_sources,
        )
    except Exception as error:  # noqa: BLE001 - demo keeps app usable
        snapshot = build_demo_snapshot(settings)
        return ChampionsSnapshot(
            **{
                **snapshot.__dict__,
                "data_note": f"Modo demo ({type(error).__name__}: {error})",
            }
        )


def get_champions_snapshot(
    force: bool = False, settings: ChampionsSettings | None = None
) -> ChampionsSnapshot:
    global _SNAPSHOT, _SNAPSHOT_LOADED_AT
    settings = settings or get_champions_settings()
    with _SNAPSHOT_LOCK:
        fresh = time.time() - _SNAPSHOT_LOADED_AT < settings.snapshot_ttl_seconds
        if _SNAPSHOT is not None and not force and fresh:
            return _SNAPSHOT
        snapshot = _load_snapshot(settings)
        _SNAPSHOT = snapshot
        _SNAPSHOT_LOADED_AT = time.time()
        return snapshot
