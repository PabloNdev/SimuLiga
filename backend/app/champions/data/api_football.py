"""API-Football and OpenFootball source adapters for the Champions League."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from app.champions.config import ChampionsSettings
from app.champions.data.openfootball import parse_openfootball_cl

API_BASE_URL = "https://v3.football.api-sports.io"
OPENFOOTBALL_BASE = (
    "https://raw.githubusercontent.com/openfootball/champions-league/master"
)
FINISHED_STATUSES = {"FT", "AET", "PEN"}
TTL_SECONDS = 21_600


class DataSourceError(RuntimeError):
    """Raised when no Champions League source can provide data."""


def season_label(season: int) -> str:
    return f"{season}-{(season + 1) % 100:02d}"


def _cache_path(settings: ChampionsSettings, name: str) -> Path:
    return Path(settings.cache_dir) / name


def _fresh(path: Path, ttl_seconds: int) -> bool:
    return path.exists() and time.time() - path.stat().st_mtime < ttl_seconds


def _round_info(round_label: str, kickoff: str | None) -> dict[str, Any] | None:
    label = (round_label or "").strip()
    lowered = label.lower()
    if "qualification" in lowered or "qualifying" in lowered:
        return None

    if lowered.startswith("league stage"):
        digits = "".join(char for char in label if char.isdigit())
        matchday = int(digits) if digits else 0
        return {"phase": "league", "matchday": matchday, "leg": 0, "neutral": False}
    if "knockout round" in lowered or "play-off" in lowered or "playoff" in lowered:
        return {"phase": "playoff", "matchday": 0, "leg": 1, "neutral": False}
    if "round of 16" in lowered or "1/8" in lowered:
        return {"phase": "r16", "matchday": 0, "leg": 1, "neutral": False}
    if "quarter" in lowered:
        return {"phase": "qf", "matchday": 0, "leg": 1, "neutral": False}
    if "semi" in lowered:
        return {"phase": "sf", "matchday": 0, "leg": 1, "neutral": False}
    if lowered.endswith("final") or lowered == "final":
        return {"phase": "final", "matchday": 0, "leg": 0, "neutral": True}
    return None


def _score_from_fixture(item: dict) -> tuple[int | None, int | None]:
    score = item.get("score") or {}
    fulltime = score.get("fulltime") or {}
    if fulltime.get("home") is not None and fulltime.get("away") is not None:
        return int(fulltime["home"]), int(fulltime["away"])
    goals = item.get("goals") or {}
    if goals.get("home") is not None and goals.get("away") is not None:
        return int(goals["home"]), int(goals["away"])
    return None, None


def parse_api_fixtures(payload: dict, season: int) -> list[dict]:
    """Normalize API-Football fixtures into the Champions match dictionaries."""
    matches: list[dict] = []
    for item in payload.get("response", []):
        fixture = item.get("fixture") or {}
        league = item.get("league") or {}
        teams = item.get("teams") or {}
        status = (fixture.get("status") or {}).get("short", "")
        kickoff = fixture.get("date")
        info = _round_info(league.get("round", ""), kickoff)
        if info is None:
            continue

        home = (teams.get("home") or {}).get("name") or ""
        away = (teams.get("away") or {}).get("name") or ""
        if not home or not away:
            continue

        home_goals, away_goals = _score_from_fixture(item)
        played = status in FINISHED_STATUSES and home_goals is not None
        matches.append(
            {
                "phase": info["phase"],
                "matchday": info["matchday"],
                "leg": info["leg"],
                "home": home,
                "away": away,
                "home_country": ((teams.get("home") or {}).get("country") or None),
                "away_country": ((teams.get("away") or {}).get("country") or None),
                "home_goals": home_goals if played else None,
                "away_goals": away_goals if played else None,
                "kickoff": kickoff,
                "neutral": info["neutral"],
                "fixture_id": fixture.get("id"),
                "_season": season,
            }
        )

    _assign_legs(matches)
    matches.sort(key=lambda match: (match.get("kickoff") or "", str(match.get("fixture_id") or "")))
    return matches


def _assign_legs(matches: list[dict]) -> None:
    for phase in ("playoff", "r16", "qf", "sf"):
        group = [match for match in matches if match["phase"] == phase]
        if not group:
            continue
        half = max(1, len(group) // 2)
        for index, match in enumerate(group):
            match["leg"] = 1 if index < half else 2
            match["matchday"] = match["leg"]


def fetch_api_matches(settings: ChampionsSettings, season: int) -> list[dict]:
    cache = _cache_path(settings, f"champions_api_{season}.json")
    if _fresh(cache, settings.cache_ttl_seconds):
        return parse_api_fixtures(json.loads(cache.read_text(encoding="utf-8")), season)

    api_key = settings.resolved_api_key
    if not api_key:
        raise DataSourceError("API-Football key is not configured")

    fixtures: list[dict] = []
    page = 1
    while page <= 20:
        params: dict[str, Any] = {"league": settings.league_id, "season": season}
        if page > 1:
            params["page"] = page
        response = httpx.get(
            f"{API_BASE_URL.rstrip('/')}/fixtures",
            headers={"x-apisports-key": api_key},
            params=params,
            timeout=45.0,
        )
        response.raise_for_status()
        payload = response.json()
        errors = payload.get("errors")
        if errors:
            raise DataSourceError(f"API-Football error: {errors}")
        fixtures.extend(payload.get("response", []))
        paging = payload.get("paging") or {}
        total_pages = int(paging.get("total", 1) or 1)
        if page >= total_pages:
            break
        page += 1

    if not fixtures:
        raise DataSourceError("API-Football returned no Champions League fixtures")

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(fixtures, ensure_ascii=False), encoding="utf-8")
    return parse_api_fixtures({"response": fixtures}, season)


def fetch_openfootball_matches(
    settings: ChampionsSettings, season: int
) -> list[dict]:
    label = season_label(season)
    cache = _cache_path(settings, f"champions_openfootball_{label}.txt")
    text: str | None = None
    if _fresh(cache, settings.cache_ttl_seconds):
        text = cache.read_text(encoding="utf-8")
    else:
        try:
            response = httpx.get(
                f"{OPENFOOTBALL_BASE}/{label}/cl.txt",
                timeout=45.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            text = response.content.decode("utf-8", errors="replace")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(text, encoding="utf-8")
        except Exception:
            if cache.exists():
                text = cache.read_text(encoding="utf-8")
            else:
                raise
    return parse_openfootball_cl(text)


def local_matches_path(season: int) -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / f"champions_{season}_{(season + 1) % 100:02d}.json"
    )


def fetch_local_matches(season: int) -> list[dict]:
    path = local_matches_path(season)
    if not path.exists():
        raise DataSourceError(f"local snapshot not found: {path.name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def load_source_matches(
    settings: ChampionsSettings, season: int
) -> tuple[list[dict], str]:
    """Load a season from the configured source, with graceful fallback."""
    source = settings.data_source.lower()
    if source == "demo":
        return [], "demo"

    errors: list[str] = []
    if source in ("auto", "api-football"):
        try:
            matches = fetch_api_matches(settings, season)
            if matches:
                return matches, "api-football"
        except Exception as error:  # noqa: BLE001 - fallback is intentional
            errors.append(f"api-football: {type(error).__name__}: {error}")

    if source in ("auto", "openfootball"):
        try:
            matches = fetch_openfootball_matches(settings, season)
            if matches:
                return matches, "openfootball"
        except Exception as error:  # noqa: BLE001 - reported below
            errors.append(f"openfootball: {type(error).__name__}: {error}")

    if source in ("auto", "local"):
        try:
            matches = fetch_local_matches(season)
            if matches:
                return matches, "local"
        except Exception as error:  # noqa: BLE001 - reported below
            errors.append(f"local: {type(error).__name__}: {error}")

    detail = "; ".join(errors) if errors else "fuente no configurada"
    raise DataSourceError(detail)


def history_seasons(
    settings: ChampionsSettings, count: int | None = None
) -> list[int]:
    total = max(1, count if count is not None else settings.history_seasons)
    return list(
        range(settings.previous_season - total + 1, settings.previous_season + 1)
    )


def load_history_matches(
    settings: ChampionsSettings,
    seasons: list[int] | None = None,
) -> tuple[list[dict], list[str], list[str]]:
    season_years = seasons if seasons is not None else history_seasons(settings)
    matches: list[dict] = []
    labels: list[str] = []
    sources: list[str] = []

    for season in season_years:
        label = season_label(season).replace("-", "/")
        try:
            season_matches = fetch_openfootball_matches(settings, season)
            source = "openfootball"
        except Exception:
            try:
                season_matches, source = load_source_matches(settings, season)
            except Exception:
                continue

        if not season_matches:
            continue

        for index, raw in enumerate(season_matches):
            raw["season"] = label
            raw["season_start"] = season
            raw["sequence"] = index

        matches.extend(season_matches)
        labels.append(label)
        sources.append(source)

    return matches, labels, sources
