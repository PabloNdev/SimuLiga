"""API-Football adapter with pagination, optional rewind and ClubElo seeds."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import Settings
from app.data.clubelo import fetch_clubelo_ratings
from app.data.names import normalize_name, slugify
from app.data.teams import team_by_name_map
from app.domain.elo import update_ratings
from app.domain.models import Match, Team

FINISHED_STATUSES = {"FT", "AET", "PEN"}
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


def fetch_api_snapshot(settings: Settings):
    fixtures = _fetch_fixtures(settings)
    if not fixtures:
        raise RuntimeError("API-Football returned no fixtures")
    ratings = _seed_ratings(settings)
    return build_snapshot_from_fixtures(fixtures, settings, ratings)


def _seed_ratings(settings: Settings) -> dict[str, float]:
    historical = Path(__file__).resolve().parent / "historical_ratings.json"
    if settings.season == 2024 and historical.exists():
        import json

        try:
            data = json.loads(historical.read_text(encoding="utf-8"))
            start = data.get("start_2024", {})
            if start:
                return {str(team): float(elo) for team, elo in start.items()}
        except (OSError, ValueError):
            pass
    if settings.clubelo_enabled:
        date = settings.clubelo_date or f"{settings.season}-08-14"
        return fetch_clubelo_ratings(date, settings.cache_dir)
    return {}


def build_snapshot_from_fixtures(
    fixtures: list[dict], settings: Settings, ratings: dict[str, float]
):
    from app.data.league import LeagueSnapshot, _version

    alias_map = team_by_name_map()
    teams: dict[str, Team] = {}
    matches: list[Match] = []

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
                elo=1600.0,
            )
        return team_id

    def rating_for(name: str, fallback: float) -> float:
        normalized = normalize_name(name)
        if normalized in ratings:
            return ratings[normalized]
        seed = alias_map.get(normalized)
        if seed is not None:
            for alias, candidate in alias_map.items():
                if candidate["id"] == seed["id"] and alias in ratings:
                    return ratings[alias]
            seed_name = normalize_name(seed["name"])
            if seed_name in ratings:
                return ratings[seed_name]
        return fallback

    rewind = settings.rewind_matchday
    for index, item in enumerate(fixtures):
        fixture = item["fixture"]
        league = item.get("league", {})
        home_name = item["teams"]["home"]["name"]
        away_name = item["teams"]["away"]["name"]
        home_id = resolve_team(home_name)
        away_id = resolve_team(away_name)
        status = fixture["status"]["short"]
        goals = item.get("goals", {})
        matchday = _matchday(league.get("round", ""), index)
        within_rewind = rewind <= 0 or matchday <= rewind
        played = (
            status in FINISHED_STATUSES
            and goals.get("home") is not None
            and within_rewind
        )
        matches.append(
            Match(
                id=str(fixture["id"]),
                matchday=matchday,
                home_id=home_id,
                away_id=away_id,
                home_goals=int(goals["home"]) if played else None,
                away_goals=int(goals["away"]) if played else None,
                outcome=None,
                kickoff=fixture.get("date"),
            )
        )

    matches.sort(key=lambda match: (match.matchday, match.kickoff or "", match.id))
    seeded_teams = [
        team.with_elo(round(rating_for(team.name, team.elo), 2))
        for team in teams.values()
    ]
    team_map = {team.id: team for team in seeded_teams}
    current_elo = {team.id: team.elo for team in seeded_teams}
    elo_by_matchday: dict[int, dict[str, float]] = {1: dict(current_elo)}
    for matchday in sorted({match.matchday for match in matches}):
        group = [
            match
            for match in matches
            if match.matchday == matchday and match.is_played and match.has_score
        ]
        if not group:
            continue
        for match in group:
            assert match.home_goals is not None and match.away_goals is not None
            home_after, away_after = update_ratings(
                current_elo[match.home_id],
                current_elo[match.away_id],
                match.home_goals,
                match.away_goals,
            )
            current_elo[match.home_id] = home_after
            current_elo[match.away_id] = away_after
        elo_by_matchday[matchday + 1] = dict(current_elo)

    updated_teams = [
        team.with_elo(round(current_elo[team.id], 2)) for team in seeded_teams
    ]
    elo_by_matchday = {
        matchday: {team_id: round(value, 2) for team_id, value in values.items()}
        for matchday, values in elo_by_matchday.items()
    }
    season_label = f"{settings.season}/{(settings.season + 1) % 100:02d}"
    if rewind > 0:
        data_note = f"Datos reales {season_label} · jornadas 1–{rewind}"
    else:
        data_note = f"Datos reales {season_label}"
    return LeagueSnapshot(
        competition="LaLiga",
        season=season_label,
        source="api-football",
        updated_at=datetime.now(timezone.utc).isoformat(),
        teams=updated_teams,
        matches=matches,
        fair_play={},
        data_version=_version(updated_teams, matches, "api-football"),
        demo=False,
        data_note=data_note,
        elo_by_matchday=elo_by_matchday,
    )



def _fetch_fixtures(settings: Settings) -> list[dict]:
    cached = _read_cache(settings)
    if cached is not None:
        return cached

    url = f"{settings.api_football_base_url.rstrip('/')}/fixtures"
    headers = {"x-apisports-key": settings.api_football_key}
    fixtures: list[dict] = []
    page = 1
    while page <= 20:
        params = {
            "league": settings.league_id,
            "season": settings.season,
        }
        if page > 1:
            params["page"] = page
        response = httpx.get(url, headers=headers, params=params, timeout=30.0)
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"API-Football error: {payload['errors']}")
        fixtures.extend(payload.get("response", []))
        paging = payload.get("paging", {})
        total_pages = int(paging.get("total", 1) or 1)
        if page >= total_pages:
            break
        page += 1
    _write_cache(settings, fixtures)
    return fixtures


def _cache_path(settings: Settings) -> Path:
    return Path(settings.cache_dir) / f"fixtures_{settings.league_id}_{settings.season}.json"


def _read_cache(settings: Settings) -> list[dict] | None:
    path = _cache_path(settings)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > settings.cache_ttl_seconds:
        return None
    import json

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_cache(settings: Settings, fixtures: list[dict]) -> None:
    import json

    path = _cache_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixtures), encoding="utf-8")


def _matchday(round_label: str, fallback_index: int) -> int:
    match = re.search(r"(\d+)", round_label or "")
    if match:
        return int(match.group(1))
    return fallback_index // 10 + 1
