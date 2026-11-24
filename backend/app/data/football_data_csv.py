"""football-data.co.uk CSV results provider, no API key required."""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime
from pathlib import Path

import httpx

BASE_URL = "https://www.football-data.co.uk/mmz4281"
TTL_SECONDS = 21_600
CARD_COLUMNS = ("HY", "AY", "HR", "AR")
CARD_KEYS = ("home_yellow", "away_yellow", "home_red", "away_red")


def fetch_results(
    season_code: str,
    cache_dir: str = ".cache",
    ttl_seconds: int = TTL_SECONDS,
) -> list[dict]:
    cache_path = Path(cache_dir) / f"football_data_SP1_{season_code}.csv"
    cached_text: str | None = None
    if cache_path.exists():
        try:
            cached_text = cache_path.read_text(encoding="utf-8-sig")
        except OSError:
            cached_text = None
        if cached_text is not None and time.time() - cache_path.stat().st_mtime < ttl_seconds:
            return parse_results(cached_text)

    url = f"{BASE_URL}/{season_code}/SP1.csv"
    try:
        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        text = response.content.decode("utf-8-sig", errors="replace")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
        return parse_results(text)
    except Exception:
        if cached_text is not None:
            return parse_results(cached_text)
        raise


def fair_play_points(yellow_cards: int, red_cards: int) -> int:
    """LaLiga fair play points: a yellow is worth 1 and a red is worth 3."""
    return max(0, int(yellow_cards)) + 3 * max(0, int(red_cards))


def _card_count(row: dict, column: str) -> int:
    raw = (row.get(column) or "").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def parse_results(text: str) -> list[dict]:
    rows: list[dict] = []
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    for row in reader:
        home_goals = (row.get("FTHG") or "").strip()
        away_goals = (row.get("FTAG") or "").strip()
        if not home_goals or not away_goals:
            continue
        raw_date = (row.get("Date") or "").strip()
        if not raw_date:
            continue
        try:
            date = datetime.strptime(raw_date, "%d/%m/%Y").date().isoformat()
            entry = {
                "date": date,
                "home": (row.get("HomeTeam") or "").strip(),
                "away": (row.get("AwayTeam") or "").strip(),
                "home_goals": int(home_goals),
                "away_goals": int(away_goals),
            }
            if any(column in row for column in CARD_COLUMNS):
                entry.update(
                    {
                        key: _card_count(row, column)
                        for key, column in zip(CARD_KEYS, CARD_COLUMNS)
                    }
                )
            rows.append(entry)
        except ValueError:
            continue
    return rows
