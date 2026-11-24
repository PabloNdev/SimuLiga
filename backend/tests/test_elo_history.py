import pytest

from app.config import Settings
from app.data.real_league import build_snapshot_from_sources
from app.domain.elo import update_ratings


def _settings() -> Settings:
    return Settings(
        openfootball_season="2026-27",
        previous_openfootball_season="2025-26",
        previous_football_data_season="2526",
    )


def _fixture(matchday: int, home: str, away: str, ft=None, date: str = "2026-08-15"):
    return {
        "round": matchday,
        "date": date,
        "time": "20:00",
        "home": home,
        "away": away,
        "ft": ft,
    }


def test_previous_season_replay_includes_non_current_teams_and_promoted_baselines():
    seed_ratings = {
        "real madrid": 1800.0,
        "barcelona": 1700.0,
        "girona": 1600.0,
        "mallorca": 1550.0,
        "valladolid": 1300.0,
        "las palmas": 1400.0,
        "leganes": 1500.0,
    }
    historical_payload = {
        "season_starts": {
            "2023": {"real madrid": 1500.0, "barcelona": 1500.0},
            "2024": {"real madrid": 1800.0, "barcelona": 1700.0},
        },
        "final_2024": {"real madrid": 1800.0, "barcelona": 1700.0},
    }
    previous_matches = [
        _fixture(1, "Real Madrid", "Girona", (2, 0), "2025-08-15"),
        _fixture(2, "Girona", "Barcelona", (1, 1), "2025-08-16"),
        _fixture(3, "Levante", "Mallorca", (1, 0), "2025-08-17"),
    ]
    current_matches = [
        _fixture(1, "Real Madrid", "Barcelona", None, "2026-08-15"),
        _fixture(1, "Málaga", "Levante", None, "2026-08-16"),
    ]

    snapshot = build_snapshot_from_sources(
        current_matches,
        [],
        _settings(),
        seed_ratings=seed_ratings,
        previous_matches=previous_matches,
        previous_results=[],
        historical_payload=historical_payload,
    )

    teams = {team.id: team for team in snapshot.teams}
    verification = snapshot.elo_verification

    expected_real, girona_after_real = update_ratings(1800.0, 1600.0, 2, 0)
    girona_after_barcelona, expected_barcelona = update_ratings(
        girona_after_real, 1700.0, 1, 1
    )

    assert teams["real-madrid"].elo == pytest.approx(expected_real, abs=0.01)
    assert teams["barcelona"].elo == pytest.approx(expected_barcelona, abs=0.01)
    assert verification["available"] is True
    assert verification["matches_total"] == 3
    assert verification["matches_applied"] == 3
    assert verification["matches_unresolved"] == 0
    assert verification["teams_total"] == 5
    assert verification["teams_resolved"] == 5
    assert verification["promoted_baseline_2025"] == pytest.approx(1400.0)
    assert verification["played_previous_season"]["levante"] is True
    assert verification["played_previous_season"]["malaga"] is False
    assert verification["baseline"]["levante"] == pytest.approx(1400.0)
    assert verification["baseline"]["malaga"] is None

    _, expected_mallorca = update_ratings(1400.0, 1550.0, 1, 0)
    expected_2026_baseline = (girona_after_barcelona + expected_mallorca) / 2
    assert verification["promoted_baseline_2026"] == pytest.approx(
        expected_2026_baseline, abs=0.01
    )
    assert teams["malaga"].elo == pytest.approx(expected_2026_baseline, abs=0.01)

    history = {
        entry["team_id"]: entry["values"] for entry in snapshot.elo_history["series"]
    }
    assert snapshot.elo_history["seasons"] == [
        "2020/21",
        "2021/22",
        "2022/23",
        "2023/24",
        "2024/25",
        "2025/26",
        "2026/27",
    ]
    assert history["real-madrid"][3:6] == [1500.0, 1800.0, 1800.0]
    assert history["real-madrid"][6] == pytest.approx(expected_real, abs=0.01)
    assert history["levante"][:5] == [None, None, None, None, None]
    assert history["levante"][5] == 1400.0
    assert history["malaga"][:6] == [None, None, None, None, None, None]
    assert history["malaga"][6] == pytest.approx(expected_2026_baseline, abs=0.01)

    timeline = snapshot.elo_timeline
    assert len(timeline["dates"]) >= 2
    assert timeline["dates"] == sorted(timeline["dates"])
    assert len(timeline["series"]) == len(teams)
    assert all(
        len(entry["values"]) == len(timeline["dates"])
        for entry in timeline["series"]
    )


def test_previous_season_missing_score_is_filled_from_football_data():
    previous_matches = [
        _fixture(1, "Girona", "Real Madrid", None, "2025-08-15"),
    ]
    previous_results = [
        {
            "date": "2025-08-15",
            "home": "Girona",
            "away": "Real Madrid",
            "home_goals": 0,
            "away_goals": 3,
        }
    ]
    seed_ratings = {"real madrid": 1800.0, "girona": 1600.0}

    snapshot = build_snapshot_from_sources(
        [_fixture(1, "Real Madrid", "Barcelona", None, "2026-08-15")],
        [],
        _settings(),
        seed_ratings=seed_ratings,
        previous_matches=previous_matches,
        previous_results=previous_results,
        historical_payload={"season_starts": {}, "final_2024": seed_ratings},
    )

    verification = snapshot.elo_verification
    teams = {team.id: team for team in snapshot.teams}
    assert verification["matches_without_score"] == 1
    assert verification["matches_filled_from_football_data"] == 1
    assert verification["matches_applied"] == 1
    assert verification["matches_missing"] == 0
    assert teams["real-madrid"].elo > 1800.0
