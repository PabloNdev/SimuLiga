"""Verify the SimuChampions snapshot and Elo replay.

Run from ``backend/``:

    python scripts/verify_champions.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.champions.data.snapshot import get_champions_snapshot  # noqa: E402


def main() -> None:
    snapshot = get_champions_snapshot(force=True)
    league = [match for match in snapshot.matches if match.phase == "league"]
    matchdays = sorted({match.matchday for match in league})
    played = sum(1 for match in league if match.is_played)
    verification = snapshot.elo_verification or {}

    print("competition:", snapshot.competition)
    print("season:", snapshot.season, "target:", snapshot.target_season)
    print("source:", snapshot.source, "demo:", snapshot.demo, "fallback:", snapshot.fallback)
    print("teams:", len(snapshot.teams))
    print("league matches:", len(league), "matchdays:", matchdays)
    print("played:", played, "pending:", len(league) - played)
    print("previous season:", verification.get("previous_season"))
    print("seed source:", verification.get("seed_source"))
    print(
        "history:",
        verification.get("history_start"),
        "-",
        verification.get("history_end"),
        "seasons:",
        verification.get("history_seasons_loaded"),
    )
    print(
        "history applied:",
        verification.get("history_matches_applied"),
        "/",
        verification.get("history_matches_total"),
        "regression:",
        verification.get("season_regression"),
    )
    print("note:", snapshot.data_note)
    params = verification.get("params", {})
    if params:
        print(
            "params:",
            f"H={params.get('home_advantage')}",
            f"nu={params.get('nu')}",
        )
        print("validation:", params.get("validation"))

    if len(snapshot.teams) != 36:
        raise SystemExit(f"expected 36 teams, got {len(snapshot.teams)}")
    if len(league) != 144:
        raise SystemExit(f"expected 144 league matches, got {len(league)}")
    if matchdays != list(range(1, 9)):
        raise SystemExit(f"expected matchdays 1-8, got {matchdays}")


if __name__ == "__main__":
    main()
