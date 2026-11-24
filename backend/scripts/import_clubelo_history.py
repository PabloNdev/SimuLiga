"""Regenerate the compact ClubElo snapshot used by SimuChampions.

Run from ``backend/``:

    python scripts/import_clubelo_history.py

The source is the open xgabora/Club-Football-Match-Data EloRatings.csv, which
contains ClubElo snapshots from 2000 to 2026. Only the season-start dates used
by the Champions Elo prior are kept.
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = (
    "https://raw.githubusercontent.com/xgabora/"
    "Club-Football-Match-Data/main/data/EloRatings.csv"
)
DATES = {
    "2020-08-01",
    "2021-08-01",
    "2022-08-01",
    "2023-08-01",
    "2024-08-01",
    "2025-08-01",
    "2026-08-01",
}
OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "app"
    / "data"
    / "clubelo_snapshots.json"
)


def main() -> None:
    request = urllib.request.Request(
        URL, headers={"User-Agent": "SimuLiga/0.1"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        text = response.read().decode("utf-8-sig", errors="replace")

    ratings = {date: {} for date in sorted(DATES)}
    for row in csv.DictReader(io.StringIO(text)):
        date = (row.get("date") or "").strip()
        if date not in DATES:
            continue
        club = (row.get("club") or "").strip()
        elo_raw = (row.get("elo") or "").strip()
        if not club or not elo_raw:
            continue
        try:
            ratings[date][club] = round(float(elo_raw), 2)
        except ValueError:
            continue

    import json

    payload = {
        "source": "xgabora/Club-Football-Match-Data (ClubElo snapshots)",
        "generated_at": datetime.now(timezone.utc).date().isoformat(),
        "dates": sorted(DATES),
        "ratings": ratings,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print("written", OUTPUT)
    for date in sorted(DATES):
        print(date, len(ratings[date]))


if __name__ == "__main__":
    main()
