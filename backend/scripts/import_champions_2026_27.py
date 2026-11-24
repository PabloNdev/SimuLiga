"""Import the real 2026/27 Champions League league-phase fixtures.

Source: UEFA Champions League fixture list (matchdays 1-8). Matchdays 1-4
(3-4 November 2026) are already played; matchdays 5-8 are pending.

Run from ``backend/``:

    python scripts/import_champions_2026_27.py
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"

# (date, home, away, home_goals, away_goals)
MATCHDAYS: dict[int, list[tuple[str, str, str, int | None, int | None]]] = {
    1: [
        ("2026-09-08", "AEK Athens", "LASK", 1, 0),
        ("2026-09-08", "Club Brugge", "Aston Villa", 2, 3),
        ("2026-09-08", "Borussia Dortmund", "Villarreal", 3, 2),
        ("2026-09-08", "Porto", "Manchester City", 0, 2),
        ("2026-09-08", "Lille", "Real Betis", 2, 3),
        ("2026-09-08", "Real Madrid", "Inter", 2, 1),
        ("2026-09-09", "Barcelona", "Feyenoord", 5, 1),
        ("2026-09-09", "Stuttgart", "Viking", 3, 1),
        ("2026-09-09", "Liverpool", "Atlético de Madrid", 2, 1),
        ("2026-09-09", "Paris Saint-Germain", "Slovan Bratislava", 6, 1),
        ("2026-09-09", "Sporting CP", "Galatasaray", 3, 1),
        ("2026-09-09", "Napoli", "Arsenal", 0, 1),
        ("2026-09-10", "Fenerbahçe", "Roma", 1, 1),
        ("2026-09-10", "PSV Eindhoven", "Shakhtar Donetsk", 1, 1),
        ("2026-09-10", "Como", "Leipzig", 4, 1),
        ("2026-09-10", "Bayern München", "Bodø/Glimt", 5, 0),
        ("2026-09-10", "Manchester United", "Sabah", 4, 0),
        ("2026-09-10", "Slavia Praha", "Lens", 2, 3),
    ],
    2: [
        ("2026-10-13", "Lens", "Sporting CP", 0, 2),
        ("2026-10-13", "Sabah", "Slavia Praha", 2, 0),
        ("2026-10-13", "Arsenal", "Lille", 3, 0),
        ("2026-10-13", "Atlético de Madrid", "Manchester United", 2, 0),
        ("2026-10-13", "Inter", "Club Brugge", 3, 4),
        ("2026-10-13", "Galatasaray", "Barcelona", 1, 4),
        ("2026-10-13", "Leipzig", "PSV Eindhoven", 1, 0),
        ("2026-10-13", "Viking", "Bayern München", 3, 3),
        ("2026-10-13", "Villarreal", "Napoli", 3, 1),
        ("2026-10-14", "Feyenoord", "Como", 3, 2),
        ("2026-10-14", "LASK", "Liverpool", 3, 6),
        ("2026-10-14", "Roma", "Real Madrid", 3, 4),
        ("2026-10-14", "Aston Villa", "Fenerbahçe", 6, 0),
        ("2026-10-14", "Shakhtar Donetsk", "AEK Athens", 3, 1),
        ("2026-10-14", "Bodø/Glimt", "Borussia Dortmund", 1, 0),
        ("2026-10-14", "Manchester City", "Paris Saint-Germain", 2, 4),
        ("2026-10-14", "Real Betis", "Porto", 3, 2),
        ("2026-10-14", "Slovan Bratislava", "Stuttgart", 0, 3),
    ],
    3: [
        ("2026-10-20", "Fenerbahçe", "Slavia Praha", 2, 2),
        ("2026-10-20", "Sabah", "Borussia Dortmund", 1, 2),
        ("2026-10-20", "Roma", "Slovan Bratislava", 4, 0),
        ("2026-10-20", "Porto", "PSV Eindhoven", 0, 1),
        ("2026-10-20", "Liverpool", "Villarreal", 4, 3),
        ("2026-10-20", "Manchester City", "AEK Athens", 5, 1),
        ("2026-10-20", "Paris Saint-Germain", "Barcelona", 4, 2),
        ("2026-10-20", "Napoli", "Bodø/Glimt", 4, 3),
        ("2026-10-20", "Stuttgart", "Atlético de Madrid", 1, 1),
        ("2026-10-21", "Como", "Manchester United", 4, 1),
        ("2026-10-21", "Lille", "Galatasaray", 2, 4),
        ("2026-10-21", "Aston Villa", "Viking", 3, 1),
        ("2026-10-21", "Club Brugge", "Lens", 3, 0),
        ("2026-10-21", "Bayern München", "Arsenal", 2, 2),
        ("2026-10-21", "Inter", "Shakhtar Donetsk", 1, 0),
        ("2026-10-21", "Real Madrid", "Leipzig", 4, 1),
        ("2026-10-21", "Real Betis", "Feyenoord", 1, 0),
        ("2026-10-21", "Sporting CP", "LASK", 2, 3),
    ],
    4: [
        ("2026-11-03", "Shakhtar Donetsk", "Sporting CP", 0, 1),
        ("2026-11-03", "Galatasaray", "Stuttgart", 2, 0),
        ("2026-11-03", "Atlético de Madrid", "Bayern München", 0, 2),
        ("2026-11-03", "Barcelona", "Aston Villa", 3, 0),
        ("2026-11-03", "Feyenoord", "Inter", 0, 3),
        ("2026-11-03", "Bodø/Glimt", "Lille", 0, 0),
        ("2026-11-03", "LASK", "Slovan Bratislava", 4, 0),
        ("2026-11-03", "Manchester United", "Roma", 3, 2),
        ("2026-11-03", "Villarreal", "Paris Saint-Germain", 0, 6),
        ("2026-11-04", "AEK Athens", "Real Madrid", 2, 3),
        ("2026-11-04", "Fenerbahçe", "Liverpool", 3, 2),
        ("2026-11-04", "Borussia Dortmund", "Real Betis", 2, 1),
        ("2026-11-04", "Porto", "Napoli", 4, 1),
        ("2026-11-04", "PSV Eindhoven", "Club Brugge", 1, 2),
        ("2026-11-04", "Leipzig", "Manchester City", 2, 3),
        ("2026-11-04", "Lens", "Como", 1, 9),
        ("2026-11-04", "Slavia Praha", "Arsenal", 1, 2),
        ("2026-11-04", "Viking", "Sabah", 4, 1),
    ],
    5: [
        ("2026-11-24", "Bodø/Glimt", "LASK", None, None),
        ("2026-11-24", "Galatasaray", "Aston Villa", None, None),
        ("2026-11-24", "Arsenal", "Borussia Dortmund", None, None),
        ("2026-11-24", "Como", "AEK Athens", None, None),
        ("2026-11-24", "Feyenoord", "Porto", None, None),
        ("2026-11-24", "Manchester City", "Napoli", None, None),
        ("2026-11-24", "Leipzig", "Lens", None, None),
        ("2026-11-24", "Real Madrid", "PSV Eindhoven", None, None),
        ("2026-11-24", "Slovan Bratislava", "Real Betis", None, None),
        ("2026-11-25", "Sabah", "Barcelona", None, None),
        ("2026-11-25", "Slavia Praha", "Villarreal", None, None),
        ("2026-11-25", "Atlético de Madrid", "Viking", None, None),
        ("2026-11-25", "Club Brugge", "Liverpool", None, None),
        ("2026-11-25", "Inter", "Stuttgart", None, None),
        ("2026-11-25", "Shakhtar Donetsk", "Fenerbahçe", None, None),
        ("2026-11-25", "Lille", "Bayern München", None, None),
        ("2026-11-25", "Paris Saint-Germain", "Roma", None, None),
        ("2026-11-25", "Sporting CP", "Manchester United", None, None),
    ],
    6: [
        ("2026-12-08", "Viking", "Feyenoord", None, None),
        ("2026-12-08", "Villarreal", "Sabah", None, None),
        ("2026-12-08", "AEK Athens", "Galatasaray", None, None),
        ("2026-12-08", "Roma", "Sporting CP", None, None),
        ("2026-12-08", "Aston Villa", "Paris Saint-Germain", None, None),
        ("2026-12-08", "Barcelona", "Manchester City", None, None),
        ("2026-12-08", "Bayern München", "Slavia Praha", None, None),
        ("2026-12-08", "Manchester United", "Leipzig", None, None),
        ("2026-12-08", "Napoli", "Club Brugge", None, None),
        ("2026-12-09", "Real Betis", "Como", None, None),
        ("2026-12-09", "Slovan Bratislava", "Shakhtar Donetsk", None, None),
        ("2026-12-09", "Arsenal", "Real Madrid", None, None),
        ("2026-12-09", "Borussia Dortmund", "Inter", None, None),
        ("2026-12-09", "LASK", "Fenerbahçe", None, None),
        ("2026-12-09", "Liverpool", "Porto", None, None),
        ("2026-12-09", "Lens", "Bodø/Glimt", None, None),
        ("2026-12-09", "PSV Eindhoven", "Atlético de Madrid", None, None),
        ("2026-12-09", "Stuttgart", "Lille", None, None),
    ],
    7: [
        ("2027-01-19", "Bodø/Glimt", "Atlético de Madrid", None, None),
        ("2027-01-19", "Galatasaray", "Feyenoord", None, None),
        ("2027-01-19", "AEK Athens", "Roma", None, None),
        ("2027-01-19", "Aston Villa", "Borussia Dortmund", None, None),
        ("2027-01-19", "Inter", "Liverpool", None, None),
        ("2027-01-19", "Porto", "Slavia Praha", None, None),
        ("2027-01-19", "Lille", "Slovan Bratislava", None, None),
        ("2027-01-19", "Real Madrid", "LASK", None, None),
        ("2027-01-19", "Stuttgart", "Club Brugge", None, None),
        ("2027-01-20", "Fenerbahçe", "Villarreal", None, None),
        ("2027-01-20", "Sabah", "Napoli", None, None),
        ("2027-01-20", "Como", "Paris Saint-Germain", None, None),
        ("2027-01-20", "Manchester United", "Bayern München", None, None),
        ("2027-01-20", "Leipzig", "Shakhtar Donetsk", None, None),
        ("2027-01-20", "Lens", "Manchester City", None, None),
        ("2027-01-20", "Real Betis", "Arsenal", None, None),
        ("2027-01-20", "Sporting CP", "Barcelona", None, None),
        ("2027-01-20", "Viking", "PSV Eindhoven", None, None),
    ],
    8: [
        ("2027-01-27", "Arsenal", "Sabah", None, None),
        ("2027-01-27", "Roma", "Lille", None, None),
        ("2027-01-27", "Atlético de Madrid", "Fenerbahçe", None, None),
        ("2027-01-27", "Borussia Dortmund", "AEK Athens", None, None),
        ("2027-01-27", "Club Brugge", "Bodø/Glimt", None, None),
        ("2027-01-27", "Bayern München", "Real Betis", None, None),
        ("2027-01-27", "Barcelona", "Como", None, None),
        ("2027-01-27", "Shakhtar Donetsk", "Real Madrid", None, None),
        ("2027-01-27", "Feyenoord", "Leipzig", None, None),
        ("2027-01-27", "LASK", "Porto", None, None),
        ("2027-01-27", "Liverpool", "Lens", None, None),
        ("2027-01-27", "Manchester City", "Sporting CP", None, None),
        ("2027-01-27", "Paris Saint-Germain", "Galatasaray", None, None),
        ("2027-01-27", "PSV Eindhoven", "Stuttgart", None, None),
        ("2027-01-27", "Slavia Praha", "Aston Villa", None, None),
        ("2027-01-27", "Napoli", "Viking", None, None),
        ("2027-01-27", "Villarreal", "Manchester United", None, None),
        ("2027-01-27", "Slovan Bratislava", "Inter", None, None),
    ],
}


def main() -> None:
    matches = []
    for matchday, rows in MATCHDAYS.items():
        for date, home, away, home_goals, away_goals in rows:
            matches.append(
                {
                    "phase": "league",
                    "matchday": matchday,
                    "leg": 0,
                    "home": home,
                    "away": away,
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "kickoff": f"{date}T21:00:00+00:00",
                    "neutral": False,
                }
            )

    assert len(matches) == 144, len(matches)
    assert sum(1 for match in matches if match["home_goals"] is not None) == 72
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "champions_2026_27.json"
    path.write_text(json.dumps(matches, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(matches)} matches ({sum(1 for m in matches if m['home_goals'] is not None)} played) to {path}")


if __name__ == "__main__":
    main()
