"""Parser for OpenFootball's ``cl.txt`` Champions League format."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.champions.names import clean_provider_name, country_from_name

MATCH_RE = re.compile(
    r"^\s*(?:(?P<time>\d{1,2}:\d{2})\s+)?"
    r"(?P<home>.+?)\s+v\s+(?P<away>.+?)\s+"
    r"(?P<score>\d+-\d+)(?P<extra>.*)$"
)
DATE_RE = re.compile(
    r"^\s+(?P<weekday>[A-Za-z]{3})\s+(?P<month>[A-Za-z]{3})\s+"
    r"(?P<day>\d{1,2})(?:\s+(?P<year>\d{4}))?\s*$"
)
SEASON_RE = re.compile(r"(\d{4})\s*/\s*(\d{2,4})")
SECTION_RE = re.compile(r"^\s*[?▪•]\s*(?P<section>.+?)\s*$")
PAREN_SCORE_RE = re.compile(r"\((\d+)-(\d+)")

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _season_start_year(text: str) -> int:
    match = SEASON_RE.search(text)
    if match:
        return int(match.group(1))
    return 2025


def _make_date(month_name: str, day: int, year: int | None, start_year: int) -> date | None:
    month = MONTHS.get(month_name.lower()[:3])
    if month is None:
        return None
    if year is None:
        year = start_year if month >= 7 else start_year + 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _phase_from_section(section: str) -> dict[str, Any]:
    lowered = section.lower()
    if lowered.startswith("league"):
        match = re.search(r"(\d+)", section)
        return {"phase": "league", "matchday": int(match.group(1)) if match else 0, "leg": 0, "neutral": False}
    if lowered.startswith("playoffs"):
        match = re.search(r"(\d+)", section)
        leg = int(match.group(1)) if match else 1
        return {"phase": "playoff", "matchday": leg, "leg": leg, "neutral": False}
    if "round of 16" in lowered:
        return {"phase": "r16", "matchday": 0, "leg": 1, "neutral": False}
    if "quarterfinal" in lowered or "quarter-final" in lowered:
        return {"phase": "qf", "matchday": 0, "leg": 1, "neutral": False}
    if "semifinal" in lowered or "semi-final" in lowered:
        return {"phase": "sf", "matchday": 0, "leg": 1, "neutral": False}
    if lowered.endswith("final") or "final" in lowered:
        return {"phase": "final", "matchday": 0, "leg": 0, "neutral": True}
    return {"phase": "league", "matchday": 0, "leg": 0, "neutral": False}


def _ninety_minute_score(
    main_home: int, main_away: int, extra: str
) -> tuple[int, int]:
    """Return the 90-minute score.

    OpenFootball uses ``1-1 (0-0)`` for a normal match where the parenthetical
    is half-time, but ``1-1 a.e.t. (1-1, 0-1)`` for a match that needed extra
    time. In the latter case the first parenthetical score is the 90-minute
    result.
    """
    lowered = extra.lower()
    if "a.e.t." in lowered or "pen." in lowered:
        match = PAREN_SCORE_RE.search(extra)
        if match:
            return int(match.group(1)), int(match.group(2))
    return main_home, main_away


def parse_openfootball_cl(text: str) -> list[dict]:
    """Parse a Champions League ``cl.txt`` document into match dictionaries."""
    start_year = _season_start_year(text)
    current_section: dict[str, Any] = {
        "phase": "league",
        "matchday": 0,
        "leg": 0,
        "neutral": False,
    }
    current_date: date | None = None
    current_time = ""
    matches: list[dict] = []

    for line in text.splitlines():
        section_match = SECTION_RE.match(line)
        if section_match:
            current_section = _phase_from_section(section_match.group("section"))
            continue

        if not line.strip() or line.lstrip().startswith("#"):
            continue

        if " v " not in line:
            date_match = DATE_RE.match(line)
            if date_match:
                current_date = _make_date(
                    date_match.group("month"),
                    int(date_match.group("day")),
                    int(date_match.group("year")) if date_match.group("year") else None,
                    start_year,
                )
                current_time = ""
            continue

        match = MATCH_RE.match(line)
        if not match:
            continue

        time = match.group("time") or current_time
        current_time = time
        home_raw = match.group("home").strip()
        away_raw = match.group("away").strip()
        home_goals_raw, away_goals_raw = match.group("score").split("-")
        home_goals, away_goals = _ninety_minute_score(
            int(home_goals_raw), int(away_goals_raw), match.group("extra") or ""
        )

        kickoff = None
        if current_date is not None:
            kickoff = current_date.isoformat()
            if time:
                kickoff = f"{kickoff}T{time}:00+00:00"

        matches.append(
            {
                "phase": current_section["phase"],
                "matchday": current_section["matchday"],
                "leg": current_section["leg"],
                "home": clean_provider_name(home_raw),
                "away": clean_provider_name(away_raw),
                "home_country": country_from_name(home_raw),
                "away_country": country_from_name(away_raw),
                "home_goals": home_goals,
                "away_goals": away_goals,
                "kickoff": kickoff,
                "neutral": current_section["neutral"],
            }
        )

    _assign_knockout_legs(matches)
    return matches


def _assign_knockout_legs(matches: list[dict]) -> None:
    """Assign first/second legs to r16, qf and sf from their appearance order."""
    for phase in ("r16", "qf", "sf"):
        group = [match for match in matches if match["phase"] == phase]
        if not group:
            continue
        half = len(group) // 2
        for index, match in enumerate(group):
            match["leg"] = 1 if index < half else 2
            match["matchday"] = match["leg"]
