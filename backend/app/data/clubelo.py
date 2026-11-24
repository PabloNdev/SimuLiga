"""ClubElo CSV client used to seed the internal Elo ratings."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from app.data.names import normalize_name

CLUBELO_TTL_SECONDS = 86_400


def parse_clubelo_csv(text: str) -> dict[str, float]:
    """Parse ClubElo's CSV into a map of normalized club name -> Elo."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].lower().startswith("rank"):
        return {}
    ratings: dict[str, float] = {}
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 5:
            continue
        club = parts[1].strip()
        try:
            elo = float(parts[4])
        except ValueError:
            continue
        if club:
            ratings[normalize_name(club)] = elo
    return ratings


def fetch_clubelo_ratings(
    date: str,
    cache_dir: str = ".cache",
    ttl_seconds: int = CLUBELO_TTL_SECONDS,
) -> dict[str, float]:
    """Fetch a daily snapshot of every club's Elo. Returns {} on failure."""
    cache_path = Path(cache_dir) / f"clubelo_{date}.csv"
    if cache_path.exists() and time.time() - cache_path.stat().st_mtime < ttl_seconds:
        return parse_clubelo_csv(cache_path.read_text(encoding="utf-8"))

    headers = {"User-Agent": "SimuLiga/0.1 (project data seed)"}
    for scheme in ("https", "http"):
        try:
            response = httpx.get(
                f"{scheme}://api.clubelo.com/{date}",
                headers=headers,
                timeout=20.0,
                follow_redirects=True,
            )
            if response.status_code != 200:
                continue
            ratings = parse_clubelo_csv(response.text)
            if not ratings:
                continue
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(response.text, encoding="utf-8")
            return ratings
        except Exception:  # noqa: BLE001 - ClubElo is an optional seed
            continue
    return {}
