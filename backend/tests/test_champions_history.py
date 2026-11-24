from app.champions.config import ChampionsSettings
from app.champions.data import api_football


def test_history_seasons_uses_previous_season_and_count():
    settings = ChampionsSettings(previous_season=2025, history_seasons=5)
    assert api_football.history_seasons(settings) == [2021, 2022, 2023, 2024, 2025]


def test_load_history_matches_annotates_and_skips_missing(monkeypatch):
    settings = ChampionsSettings(previous_season=2025, history_seasons=2)

    def fake_fetch(settings, season):
        if season == 2024:
            raise RuntimeError("missing")
        return [
            {
                "phase": "league",
                "matchday": 1,
                "home": "Real Madrid",
                "away": "Barcelona",
                "home_goals": 2,
                "away_goals": 1,
                "kickoff": "2025-09-01",
                "neutral": False,
            }
        ]

    monkeypatch.setattr(api_football, "fetch_openfootball_matches", fake_fetch)
    monkeypatch.setattr(
        api_football,
        "load_source_matches",
        lambda settings, season: (_ for _ in ()).throw(RuntimeError("missing")),
    )

    matches, labels, sources = api_football.load_history_matches(settings)
    assert labels == ["2025/26"]
    assert sources == ["openfootball"]
    assert len(matches) == 1
    assert matches[0]["season"] == "2025/26"
    assert matches[0]["season_start"] == 2025
    assert matches[0]["sequence"] == 0
