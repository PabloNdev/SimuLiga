"""Build a real 2026/27 snapshot from OpenFootball plus football-data.co.uk."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.data.football_data_csv import fair_play_points, fetch_results
from app.data.names import normalize_name, slugify
from app.data.openfootball import fetch_season, parse_matches
from app.data.teams import team_by_name_map
from app.domain.elo import PROMOTED_START_RATING, update_ratings
from app.domain.models import Match, Team

FALLBACK_COLORS = [
    "#1D4ED8",
    "#0F766E",
    "#B45309",
    "#7E22CE",
    "#BE123C",
    "#0369A1",
    "#4D7C0F",
    "#9A3412",
]

# Teams relegated from LaLiga at the end of 2024/25. Their final ratings define
# the entry baseline for clubs promoted to 2025/26.
RELEGATED_2024 = ("valladolid", "las palmas", "leganes")

# Provider names for historical clubs that are not part of the 2026/27 seed list.
HISTORICAL_ALIASES = {
    "girona": "girona",
    "girona fc": "girona",
    "mallorca": "mallorca",
    "rcd mallorca": "mallorca",
    "oviedo": "oviedo",
    "real oviedo": "oviedo",
    "valladolid": "valladolid",
    "real valladolid": "valladolid",
    "las palmas": "las palmas",
    "ud las palmas": "las palmas",
    "leganes": "leganes",
    "cd leganes": "leganes",
    "almeria": "almeria",
    "ud almeria": "almeria",
    "cadiz": "cadiz",
    "cadiz cf": "cadiz",
    "granada": "granada",
    "granada cf": "granada",
    "eibar": "eibar",
    "sd eibar": "eibar",
    "huesca": "huesca",
    "sd huesca": "huesca",
}

SEASON_START_LABELS = [
    "2020/21",
    "2021/22",
    "2022/23",
    "2023/24",
    "2024/25",
    "2025/26",
    "2026/27",
]


def fetch_real_snapshot(settings: Settings):
    season_payload = fetch_season(
        settings.openfootball_season,
        settings.cache_dir,
        settings.cache_ttl_seconds,
    )
    season_matches = parse_matches(season_payload)

    try:
        results = fetch_results(
            settings.football_data_season,
            settings.cache_dir,
            settings.cache_ttl_seconds,
        )
    except Exception:  # noqa: BLE001 - OpenFootball is enough if the CSV fails
        results = []

    previous_matches: list[dict] = []
    if settings.previous_openfootball_season:
        try:
            previous_payload = fetch_season(
                settings.previous_openfootball_season,
                settings.cache_dir,
                settings.cache_ttl_seconds,
            )
            previous_matches = parse_matches(previous_payload)
        except Exception:  # noqa: BLE001 - previous season is an optional seed
            previous_matches = []

    previous_results: list[dict] = []
    if settings.previous_football_data_season:
        try:
            previous_results = fetch_results(
                settings.previous_football_data_season,
                settings.cache_dir,
                settings.cache_ttl_seconds,
            )
        except Exception:  # noqa: BLE001 - OpenFootball still provides most results
            previous_results = []

    return build_snapshot_from_sources(
        season_matches,
        results,
        settings,
        seed_ratings=load_historical_ratings(),
        previous_matches=previous_matches,
        previous_results=previous_results,
        historical_payload=load_historical_payload(),
    )


def load_historical_payload() -> dict:
    path = Path(__file__).resolve().parent / "historical_ratings.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_historical_ratings() -> dict[str, float]:
    final = load_historical_payload().get("final_2024", {})
    return {str(team): float(elo) for team, elo in final.items()}


def build_snapshot_from_sources(
    season_matches: list[dict],
    results: list[dict],
    settings: Settings,
    *,
    seed_ratings: dict[str, float] | None = None,
    previous_matches: list[dict] | None = None,
    previous_results: list[dict] | None = None,
    historical_payload: dict | None = None,
):
    from app.data.league import LeagueSnapshot, _version

    alias_map = team_by_name_map()
    teams: dict[str, Team] = {}

    def resolve_team(name: str) -> str:
        normalized = normalize_name(name)
        seed = alias_map.get(normalized)
        if seed is not None:
            team_id = seed["id"]
            teams.setdefault(
                team_id,
                Team(
                    id=team_id,
                    name=seed["name"],
                    short_name=seed["short_name"],
                    color=seed["color"],
                    elo=seed["elo"],
                ),
            )
            return team_id

        team_id = slugify(name)
        if team_id not in teams:
            words = normalized.split()
            short = "".join(word[0] for word in words[:3]).upper() or normalized[:3].upper()
            color = FALLBACK_COLORS[len(teams) % len(FALLBACK_COLORS)]
            teams[team_id] = Team(
                id=team_id,
                name=name,
                short_name=short[:3],
                color=color,
                elo=1500.0,
            )
        return team_id

    for raw in season_matches:
        resolve_team(raw["home"])
        resolve_team(raw["away"])

    result_map: dict[tuple[str, str], tuple[int, int]] = {}
    card_map: dict[tuple[str, str], tuple[int, int, int, int]] = {}
    for row in results:
        home_id = _existing_team_id(row["home"], alias_map, teams)
        away_id = _existing_team_id(row["away"], alias_map, teams)
        if home_id and away_id:
            result_map[(home_id, away_id)] = (
                int(row["home_goals"]),
                int(row["away_goals"]),
            )
            if all(
                key in row
                for key in ("home_yellow", "away_yellow", "home_red", "away_red")
            ):
                card_map[(home_id, away_id)] = (
                    int(row["home_yellow"]),
                    int(row["away_yellow"]),
                    int(row["home_red"]),
                    int(row["away_red"]),
                )

    fair_play: dict[str, int] = {}
    matches: list[Match] = []
    for raw in season_matches:
        home_id = resolve_team(raw["home"])
        away_id = resolve_team(raw["away"])
        score = result_map.get((home_id, away_id)) or raw.get("ft")
        kickoff = None
        if raw.get("date"):
            kickoff = f"{raw['date']}T{raw.get('time') or '00:00'}:00+00:00"
        matches.append(
            Match(
                id=f"of-{raw.get('round', 0)}-{home_id}-{away_id}",
                matchday=int(raw.get("round") or 0),
                home_id=home_id,
                away_id=away_id,
                home_goals=score[0] if score else None,
                away_goals=score[1] if score else None,
                outcome=None,
                kickoff=kickoff,
            )
        )
        cards = card_map.get((home_id, away_id))
        if score and cards is not None:
            home_yellow, away_yellow, home_red, away_red = cards
            fair_play[home_id] = fair_play.get(home_id, 0) + fair_play_points(
                home_yellow, home_red
            )
            fair_play[away_id] = fair_play.get(away_id, 0) + fair_play_points(
                away_yellow, away_red
            )
    matches.sort(key=lambda match: (match.matchday, match.kickoff or "", match.id))

    seed_ratings = seed_ratings or {}
    previous_matches = previous_matches or []
    previous_results = previous_results or []
    historical_payload = historical_payload or {}
    current_ids = set(teams)

    season_teams_2024 = set(historical_payload.get("season_teams", {}).get("2024", []))
    promoted_baselines = historical_payload.get("promoted_baselines", {})
    promoted_baseline_2025 = float(
        promoted_baselines.get("2025", _promoted_baseline_2025(seed_ratings))
    )

    previous_result_map: dict[tuple[str, str], tuple[int, int, str]] = {}
    for row in previous_results:
        home_id = _previous_team_id(row["home"], alias_map, current_ids, seed_ratings)
        away_id = _previous_team_id(row["away"], alias_map, current_ids, seed_ratings)
        if home_id and away_id:
            previous_result_map[(home_id, away_id)] = (
                int(row["home_goals"]),
                int(row["away_goals"]),
                row.get("date") or "",
            )

    previous_entries: list[tuple[str, str, str, int, int]] = []
    used_previous_results: set[tuple[str, str]] = set()
    openfootball_without_score = sum(1 for raw in previous_matches if not raw.get("ft"))
    filled_from_csv = 0
    missing_score = 0
    unresolved_matches = 0
    unresolved_names: set[str] = set()

    for raw in sorted(previous_matches, key=lambda item: item.get("date") or ""):
        home_id = _previous_team_id(raw["home"], alias_map, current_ids, seed_ratings)
        away_id = _previous_team_id(raw["away"], alias_map, current_ids, seed_ratings)
        if home_id is None or away_id is None:
            unresolved_matches += 1
            unresolved_names.add(raw["home"])
            unresolved_names.add(raw["away"])
            continue

        ft = raw.get("ft")
        if not ft:
            fallback = previous_result_map.get((home_id, away_id))
            if fallback is None:
                missing_score += 1
                continue
            ft = (fallback[0], fallback[1])
            filled_from_csv += 1

        used_previous_results.add((home_id, away_id))
        previous_entries.append(
            (
                raw.get("date") or "",
                home_id,
                away_id,
                int(ft[0]),
                int(ft[1]),
            )
        )

    # Append any CSV result whose fixture was not present in OpenFootball.
    for (home_id, away_id), (home_goals, away_goals, date) in previous_result_map.items():
        if (home_id, away_id) in used_previous_results:
            continue
        previous_entries.append((date, home_id, away_id, home_goals, away_goals))
        used_previous_results.add((home_id, away_id))

    previous_entries.sort(key=lambda entry: (entry[0], entry[1], entry[2]))
    previous_team_ids = {entry[1] for entry in previous_entries} | {
        entry[2] for entry in previous_entries
    }

    def uses_historical_seed(team: Team) -> bool:
        key = _history_key(team.name, seed_ratings, alias_map)
        if season_teams_2024:
            return key is not None and key in season_teams_2024
        return key is not None

    ratings: dict[str, float] = {}
    for team_id, team in teams.items():
        if uses_historical_seed(team):
            ratings[team_id] = _seed_for(team, seed_ratings, alias_map)
        else:
            ratings[team_id] = promoted_baseline_2025

    for team_id in previous_team_ids:
        if team_id not in ratings:
            if season_teams_2024 and team_id not in season_teams_2024:
                ratings[team_id] = promoted_baseline_2025
            else:
                ratings[team_id] = seed_ratings.get(team_id, promoted_baseline_2025)

    previous_label = (
        settings.previous_openfootball_season.replace("-", "/")
        if settings.previous_openfootball_season
        else "temporada anterior"
    )
    previous_timeline: list[dict] = []
    if previous_entries:
        first_date = previous_entries[0][0]
        previous_timeline.append(
            {
                "date": first_date,
                "season": previous_label,
                "month": "start",
                "ratings": {
                    team_id: round(elo, 2) for team_id, elo in sorted(ratings.items())
                },
            }
        )
        current_month = first_date[:7]
        last_date = first_date
    else:
        current_month = ""
        last_date = ""

    for entry_date, home_id, away_id, home_goals, away_goals in previous_entries:
        if entry_date[:7] != current_month:
            previous_timeline.append(
                {
                    "date": last_date,
                    "season": previous_label,
                    "month": current_month,
                    "ratings": {
                        team_id: round(elo, 2)
                        for team_id, elo in sorted(ratings.items())
                    },
                }
            )
            current_month = entry_date[:7]

        home_after, away_after = update_ratings(
            ratings[home_id], ratings[away_id], home_goals, away_goals
        )
        ratings[home_id] = home_after
        ratings[away_id] = away_after
        last_date = entry_date

    if previous_entries:
        previous_timeline.append(
            {
                "date": last_date,
                "season": previous_label,
                "month": current_month,
                "ratings": {
                    team_id: round(elo, 2) for team_id, elo in sorted(ratings.items())
                },
            }
        )

    relegated_previous = sorted(
        team_id for team_id in previous_team_ids if team_id not in current_ids
    )
    if relegated_previous:
        promoted_baseline_2026 = sum(ratings[team_id] for team_id in relegated_previous) / len(
            relegated_previous
        )
    else:
        promoted_baseline_2026 = promoted_baseline_2025

    for team_id, team in teams.items():
        if not uses_historical_seed(team) and team_id not in previous_team_ids:
            ratings[team_id] = promoted_baseline_2026

    start_ratings = {team_id: ratings[team_id] for team_id in teams}
    elo_by_matchday: dict[int, dict[str, float]] = {1: dict(start_ratings)}

    for matchday in sorted({match.matchday for match in matches}):
        played_group = [
            match
            for match in matches
            if match.matchday == matchday and match.is_played and match.has_score
        ]
        if not played_group:
            continue
        for match in played_group:
            assert match.home_goals is not None and match.away_goals is not None
            home_after, away_after = update_ratings(
                ratings[match.home_id],
                ratings[match.away_id],
                match.home_goals,
                match.away_goals,
            )
            ratings[match.home_id] = home_after
            ratings[match.away_id] = away_after
        elo_by_matchday[matchday + 1] = {
            team_id: ratings[team_id] for team_id in teams
        }

    updated_teams = [team.with_elo(round(ratings[team.id], 2)) for team in teams.values()]
    elo_by_matchday = {
        matchday: {team_id: round(value, 2) for team_id, value in values.items()}
        for matchday, values in elo_by_matchday.items()
    }

    current_label = settings.openfootball_season.replace("-", "/")
    current_timeline: list[dict] = []
    played_current = [match for match in matches if match.is_played and match.kickoff]
    if played_current:
        first_date = min((match.kickoff or "")[:10] for match in played_current)
        current_timeline.append(
            {
                "date": first_date,
                "season": current_label,
                "month": "start",
                "ratings": {
                    team_id: round(value, 2)
                    for team_id, value in start_ratings.items()
                },
            }
        )
        for matchday in sorted({match.matchday for match in played_current}):
            matchday_matches = [
                match for match in played_current if match.matchday == matchday
            ]
            last_date = max((match.kickoff or "")[:10] for match in matchday_matches)
            matchday_ratings = elo_by_matchday.get(matchday + 1)
            if matchday_ratings:
                current_timeline.append(
                    {
                        "date": last_date,
                        "season": current_label,
                        "month": last_date[:7],
                        "ratings": matchday_ratings,
                    }
                )

    historical_timeline = historical_payload.get("timeline", [])
    combined_timeline = sorted(
        [*historical_timeline, *previous_timeline, *current_timeline],
        key=lambda point: point.get("date") or "",
    )
    team_history_keys = {
        team_id: _history_key(team.name, seed_ratings, alias_map)
        for team_id, team in teams.items()
    }
    timeline_dates: list[str] = []
    timeline_values: dict[str, list[float | None]] = {
        team_id: [] for team_id in teams
    }
    for point in combined_timeline:
        point_ratings = point.get("ratings", {})
        timeline_dates.append(point.get("date") or "")
        for team_id in teams:
            value = point_ratings.get(team_id)
            if value is None:
                key = team_history_keys[team_id]
                if key is not None:
                    value = point_ratings.get(key)
            timeline_values[team_id].append(
                round(float(value), 2) if value is not None else None
            )

    elo_timeline = {
        "dates": timeline_dates,
        "series": [
            {"team_id": team_id, "values": values}
            for team_id, values in timeline_values.items()
        ],
    }

    pending_matchdays = [match.matchday for match in matches if not match.is_played]
    played_count = sum(1 for match in matches if match.is_played)
    by_matchday: dict[int, list[bool]] = {}
    for match in matches:
        by_matchday.setdefault(match.matchday, []).append(match.is_played)
    completed = [
        matchday
        for matchday, flags in sorted(by_matchday.items())
        if flags and all(flags)
    ]
    last_complete = max(completed) if completed else 0
    season_label = settings.openfootball_season.replace("-", "/")
    if pending_matchdays:
        note = (
            f"Datos reales {season_label} · jornadas 1–{last_complete} completadas"
        )
        if any(matchday <= last_complete for matchday in pending_matchdays):
            note += " (+ aplazados)"
        note += " (OpenFootball + football-data.co.uk)"
    else:
        note = f"Datos reales {season_label} · temporada completa"

    sources = ["OpenFootball", "football-data.co.uk"] if previous_results else ["OpenFootball"]
    matches_stats = {
        "total": len(previous_matches),
        "applied": len(previous_entries),
        "without_score": openfootball_without_score,
        "filled": filled_from_csv,
        "missing": missing_score,
        "unresolved": unresolved_matches,
        "unresolved_names": len(unresolved_names),
        "teams_resolved": len(previous_team_ids),
        "sources": sources,
    }

    elo_history = _build_elo_history(
        historical_payload,
        teams,
        previous_team_ids,
        start_ratings,
        seed_ratings,
        alias_map,
        promoted_baseline_2025,
    )
    elo_verification = _build_verification(
        teams,
        previous_team_ids,
        seed_ratings,
        alias_map,
        historical_payload,
        matches_stats=matches_stats,
        promoted_baseline_2025=promoted_baseline_2025,
        promoted_baseline_2026=promoted_baseline_2026,
        previous_season_label=settings.previous_openfootball_season.replace("-", "/")
        if settings.previous_openfootball_season
        else "",
    )

    return LeagueSnapshot(
        competition="LaLiga",
        season=season_label,
        source="openfootball+football-data",
        updated_at=datetime.now(timezone.utc).isoformat(),
        teams=updated_teams,
        matches=matches,
        fair_play=fair_play,
        data_version=_version(
            updated_teams,
            matches,
            "openfootball+football-data",
            fair_play=fair_play,
        ),
        demo=False,
        data_note=f"{note} · {played_count} partidos jugados",
        elo_by_matchday=elo_by_matchday,
        elo_history=elo_history,
        elo_verification=elo_verification,
        elo_timeline=elo_timeline,
    )


def _existing_team_id(
    name: str, alias_map: dict[str, dict], teams: dict[str, Team]
) -> str | None:
    normalized = normalize_name(name)
    seed = alias_map.get(normalized)
    if seed is not None and seed["id"] in teams:
        return seed["id"]
    slug = slugify(name)
    if slug in teams:
        return slug
    return None


def _previous_team_id(
    name: str,
    alias_map: dict[str, dict],
    current_ids: set[str],
    seed_ratings: dict[str, float],
) -> str | None:
    normalized = normalize_name(name)
    seed = alias_map.get(normalized)
    if seed is not None and seed["id"] in current_ids:
        return seed["id"]
    slug = slugify(name)
    if slug in current_ids:
        return slug
    return _history_key(name, seed_ratings, alias_map)


def _history_key(
    name: str, seed_ratings: dict[str, float], alias_map: dict[str, dict]
) -> str | None:
    normalized = normalize_name(name)
    if normalized in seed_ratings:
        return normalized
    seed = alias_map.get(normalized)
    if seed is not None:
        for alias, candidate in alias_map.items():
            if candidate["id"] == seed["id"] and alias in seed_ratings:
                return alias
    slug = slugify(name)
    if slug in seed_ratings:
        return slug
    return HISTORICAL_ALIASES.get(normalized)


def _seed_for(
    team: Team, seed_ratings: dict[str, float], alias_map: dict[str, dict]
) -> float:
    key = _history_key(team.name, seed_ratings, alias_map)
    if key is not None and key in seed_ratings:
        return seed_ratings[key]
    return team.elo


def _promoted_baseline_2025(seed_ratings: dict[str, float]) -> float:
    values = [seed_ratings[key] for key in RELEGATED_2024 if key in seed_ratings]
    if not values:
        return PROMOTED_START_RATING
    return sum(values) / len(values)


def _build_elo_history(
    historical_payload: dict,
    teams: dict[str, Team],
    previous_team_ids: set[str],
    start_ratings: dict[str, float],
    seed_ratings: dict[str, float],
    alias_map: dict[str, dict],
    promoted_baseline_2025: float,
) -> dict:
    season_starts = historical_payload.get("season_starts", {})
    season_teams = historical_payload.get("season_teams", {})
    final_2024 = historical_payload.get("final_2024", {})
    teams_by_year = {
        year: set(season_teams.get(str(year), [])) for year in range(2020, 2025)
    }

    def start_value(year: int, key: str | None) -> float | None:
        ratings = season_starts.get(str(year), {})
        value = ratings.get(key) if key is not None else None
        if value is not None:
            return float(value)
        if key is not None and key in teams_by_year.get(year, set()):
            return 1500.0
        return None

    series = []
    for team in teams.values():
        key = _history_key(team.name, seed_ratings, alias_map)
        values: list[float | None] = []

        values.append(
            1500.0 if key is not None and key in teams_by_year.get(2020, set()) else None
        )
        for year in (2021, 2022, 2023, 2024):
            values.append(start_value(year, key))

        played_2024 = key is not None and key in teams_by_year.get(2024, set())
        if not teams_by_year.get(2024) and key is not None and key in final_2024:
            # Legacy payload without season_teams: keep the old behaviour.
            played_2024 = True

        if played_2024:
            values.append(float(final_2024[key]) if key in final_2024 else None)
        elif team.id in previous_team_ids:
            values.append(promoted_baseline_2025)
        elif key is not None and key in final_2024:
            values.append(float(final_2024[key]))
        else:
            values.append(None)

        next_start = start_ratings.get(team.id)
        values.append(float(next_start) if next_start is not None else None)

        series.append(
            {
                "team_id": team.id,
                "values": [round(value, 2) if value is not None else None for value in values],
            }
        )

    return {
        "seasons": list(SEASON_START_LABELS),
        "series": series,
        "origin": 1500.0,
        "promoted_baseline_2025": round(promoted_baseline_2025, 2),
    }


def _build_verification(
    teams: dict[str, Team],
    previous_team_ids: set[str],
    seed_ratings: dict[str, float],
    alias_map: dict[str, dict],
    historical_payload: dict,
    *,
    matches_stats: dict,
    promoted_baseline_2025: float,
    promoted_baseline_2026: float,
    previous_season_label: str,
) -> dict:
    final_2024 = historical_payload.get("final_2024", {})
    season_teams = historical_payload.get("season_teams", {})
    season_teams_2024 = set(season_teams.get("2024", []))
    baseline: dict[str, float | None] = {}
    played_previous: dict[str, bool] = {}

    for team in teams.values():
        key = _history_key(team.name, seed_ratings, alias_map)
        played_previous[team.id] = team.id in previous_team_ids
        has_2024_rating = (
            key is not None and key in season_teams_2024
            if season_teams_2024
            else key is not None and key in final_2024
        )
        if has_2024_rating:
            baseline[team.id] = round(float(final_2024[key]), 2)
        elif team.id in previous_team_ids:
            baseline[team.id] = round(promoted_baseline_2025, 2)
        else:
            baseline[team.id] = None

    return {
        "available": matches_stats["total"] > 0,
        "previous_season": previous_season_label,
        "matches_total": matches_stats["total"],
        "matches_applied": matches_stats["applied"],
        "matches_without_score": matches_stats["without_score"],
        "matches_filled_from_football_data": matches_stats["filled"],
        "matches_missing": matches_stats["missing"],
        "matches_unresolved": matches_stats["unresolved"],
        "teams_total": matches_stats["teams_resolved"] + matches_stats["unresolved_names"],
        "teams_resolved": matches_stats["teams_resolved"],
        "sources": matches_stats["sources"],
        "baseline_label": "Final 2024/25",
        "baseline": baseline,
        "played_previous_season": played_previous,
        "promoted_baseline_2025": round(promoted_baseline_2025, 2),
        "promoted_baseline_2026": round(promoted_baseline_2026, 2),
    }
