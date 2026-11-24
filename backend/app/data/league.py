"""Competition snapshots: demo seed, API refresh and versioning."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from app.config import Settings, get_settings
from app.data.schedule import generate_double_round_robin
from app.data.teams import seed_teams
from app.domain.elo import update_ratings
from app.domain.models import Match, Team
from app.domain.scoreline import ScorelineParams, expected_goals, sample_scores_batch

DEMO_SEASON = "2026/27"
DEMO_UPDATED_AT = "2026-10-20T08:00:00+00:00"
DEMO_SEED = 20_262_027


@dataclass(frozen=True)
class LeagueSnapshot:
    competition: str
    season: str
    source: str
    updated_at: str
    teams: list[Team]
    matches: list[Match]
    fair_play: dict[str, int]
    data_version: str
    demo: bool
    data_note: str | None = None
    elo_by_matchday: dict[int, dict[str, float]] = field(default_factory=dict)
    elo_history: dict = field(default_factory=dict)
    elo_verification: dict = field(default_factory=dict)
    elo_timeline: dict = field(default_factory=dict)


def build_demo_snapshot(settings: Settings | None = None) -> LeagueSnapshot:
    settings = settings or get_settings()
    teams = seed_teams()
    team_ids = [team.id for team in teams]
    ratings = {team.id: team.elo for team in teams}
    params = ScorelineParams()
    rng = np.random.default_rng(DEMO_SEED)

    played_matchdays = max(0, min(settings.demo_played_matchdays, 38))
    matches = generate_double_round_robin(team_ids)
    finished: list[Match] = []
    elo_by_matchday: dict[int, dict[str, float]] = {1: dict(ratings)}
    current_matchday: int | None = None
    for match in sorted(matches, key=lambda item: (item.matchday, item.home_id)):
        if current_matchday is not None and match.matchday != current_matchday:
            if current_matchday <= played_matchdays:
                elo_by_matchday[current_matchday + 1] = dict(ratings)
            current_matchday = match.matchday
        elif current_matchday is None:
            current_matchday = match.matchday

        if match.matchday <= played_matchdays:
            home_lambda, away_lambda = expected_goals(
                ratings[match.home_id], ratings[match.away_id], params
            )
            home_goals, away_goals = sample_scores_batch(
                home_lambda, away_lambda, 1, rng, params
            )
            home_score = int(home_goals[0])
            away_score = int(away_goals[0])
            finished.append(match.with_score(home_score, away_score))
            new_home, new_away = update_ratings(
                ratings[match.home_id],
                ratings[match.away_id],
                home_score,
                away_score,
                home_advantage=params.home_advantage,
            )
            ratings[match.home_id] = new_home
            ratings[match.away_id] = new_away
        else:
            finished.append(match)
    if current_matchday is not None and current_matchday <= played_matchdays:
        elo_by_matchday[current_matchday + 1] = dict(ratings)

    updated_teams = [team.with_elo(round(ratings[team.id], 2)) for team in teams]
    elo_by_matchday = {
        matchday: {team_id: round(value, 2) for team_id, value in values.items()}
        for matchday, values in elo_by_matchday.items()
    }
    version = _version(updated_teams, finished, "demo")
    return LeagueSnapshot(
        competition="LaLiga",
        season=DEMO_SEASON,
        source="demo",
        updated_at=DEMO_UPDATED_AT,
        teams=updated_teams,
        matches=finished,
        fair_play={},
        data_version=version,
        demo=True,
        elo_by_matchday=elo_by_matchday,
    )


def _version(
    teams: list[Team],
    matches: list[Match],
    source: str,
    *,
    fair_play: dict[str, int] | None = None,
) -> str:
    payload = {
        "source": source,
        "fair_play": fair_play or {},
        "teams": [[team.id, round(team.elo, 4)] for team in teams],
        "matches": [
            [
                match.id,
                match.matchday,
                match.home_id,
                match.away_id,
                match.home_goals,
                match.away_goals,
                match.outcome,
            ]
            for match in matches
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


_SNAPSHOT: LeagueSnapshot | None = None
_SNAPSHOT_LOADED_AT = 0.0
_LOCK = threading.Lock()


def get_snapshot(force: bool = False, settings: Settings | None = None) -> LeagueSnapshot:
    global _SNAPSHOT, _SNAPSHOT_LOADED_AT
    settings = settings or get_settings()
    with _LOCK:
        fresh = time.time() - _SNAPSHOT_LOADED_AT < settings.snapshot_ttl_seconds
        if _SNAPSHOT is not None and not force and fresh:
            return _SNAPSHOT
        snapshot = _load_snapshot(settings)
        _SNAPSHOT = snapshot
        _SNAPSHOT_LOADED_AT = time.time()
        return snapshot


def _load_snapshot(settings: Settings) -> LeagueSnapshot:
    source = settings.data_source.lower()
    if source == "demo":
        return build_demo_snapshot(settings)

    errors: list[str] = []
    if source in ("auto", "openfootball"):
        try:
            from app.data.real_league import fetch_real_snapshot

            return fetch_real_snapshot(settings)
        except Exception as error:  # noqa: BLE001 - fall back to another source
            errors.append(f"openfootball: {type(error).__name__}")

    if source in ("auto", "api-football") and settings.api_football_key:
        try:
            from app.data.api_football import fetch_api_snapshot

            return fetch_api_snapshot(settings)
        except Exception as error:  # noqa: BLE001 - the demo must keep the app usable
            errors.append(f"api-football: {type(error).__name__}")

    fallback = build_demo_snapshot(settings)
    detail = ", ".join(errors) if errors else "fuente no configurada"
    return LeagueSnapshot(
        competition=fallback.competition,
        season=fallback.season,
        source=f"demo (datos reales no disponibles: {detail})",
        updated_at=datetime.now(timezone.utc).isoformat(),
        teams=fallback.teams,
        matches=fallback.matches,
        fair_play=fallback.fair_play,
        data_version=fallback.data_version,
        demo=True,
        data_note=fallback.data_note,
        elo_by_matchday=fallback.elo_by_matchday,
        elo_history=fallback.elo_history,
        elo_verification=fallback.elo_verification,
        elo_timeline=fallback.elo_timeline,
    )
