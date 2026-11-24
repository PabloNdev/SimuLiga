from app.champions.data.api_football import parse_api_fixtures

PAYLOAD = {
    "response": [
        {
            "fixture": {
                "id": 1,
                "date": "2025-09-16T16:45:00+00:00",
                "status": {"short": "FT"},
            },
            "league": {"round": "League Stage - 1"},
            "teams": {"home": {"name": "Athletic Club"}, "away": {"name": "Arsenal"}},
            "goals": {"home": 0, "away": 2},
            "score": {"fulltime": {"home": 0, "away": 2}},
        },
        {
            "fixture": {
                "id": 2,
                "date": "2026-05-30T16:00:00+00:00",
                "status": {"short": "PEN"},
            },
            "league": {"round": "Final"},
            "teams": {
                "home": {"name": "Paris Saint-Germain"},
                "away": {"name": "Arsenal"},
            },
            "goals": {"home": 4, "away": 3},
            "score": {
                "fulltime": {"home": 1, "away": 1},
                "extratime": {"home": 1, "away": 1},
                "penalty": {"home": 4, "away": 3},
            },
        },
        {
            "fixture": {
                "id": 3,
                "date": "2025-07-08T16:00:00+00:00",
                "status": {"short": "FT"},
            },
            "league": {"round": "Qualification Round 1"},
            "teams": {"home": {"name": "A"}, "away": {"name": "B"}},
            "goals": {"home": 1, "away": 0},
            "score": {"fulltime": {"home": 1, "away": 0}},
        },
    ]
}


def test_api_parser_uses_90_minute_score_and_neutral_final():
    matches = parse_api_fixtures(PAYLOAD, 2025)
    assert len(matches) == 2
    league = [match for match in matches if match["phase"] == "league"][0]
    assert league["matchday"] == 1
    assert (league["home_goals"], league["away_goals"]) == (0, 2)
    final = [match for match in matches if match["phase"] == "final"][0]
    assert final["neutral"] is True
    assert (final["home_goals"], final["away_goals"]) == (1, 1)


def test_api_parser_skips_qualification_rounds():
    matches = parse_api_fixtures(PAYLOAD, 2025)
    assert all(match["home"] != "A" for match in matches)
