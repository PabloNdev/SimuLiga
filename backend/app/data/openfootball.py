"""OpenFootball JSON provider: full fixtures and results, no API key."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"
TTL_SECONDS = 21_600


def fetch_season(
    season_label: str,
    cache_dir: str = ".cache",
    ttl_seconds: int = TTL_SECONDS,
) -> dict:
    cache_path = Path(cache_dir) / f"openfootball_{season_label}.json"
    cached: dict | None = None
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
        if cached is not None and time.time() - cache_path.stat().st_mtime < ttl_seconds:
            return cached

    url = f"{BASE_URL}/{season_label}/es.1.json"
    try:
        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        payload = json.loads(response.content.decode("utf-8-sig"))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return payload
    except Exception:
        if cached is not None:
            return cached
        raise


def parse_matches(payload: dict) -> list[dict]:
    matches: list[dict] = []
    for raw in payload.get("matches", []):
        round_label = raw.get("round", "")
        match = re.search(r"(\d+)", round_label or "")
        score = raw.get("score")
        full_time = None
        if isinstance(score, dict):
            ft = score.get("ft")
            if isinstance(ft, list) and len(ft) == 2:
                full_time = (int(ft[0]), int(ft[1]))
        matches.append(
            {
                "round": int(match.group(1)) if match else 0,
                "date": raw.get("date") or "",
                "time": raw.get("time") or "",
                "home": raw.get("team1") or "",
                "away": raw.get("team2") or "",
                "ft": full_time,
            }
        )
    return matches
