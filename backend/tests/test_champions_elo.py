import pytest

from app.champions.data.snapshot import (
    calibration_samples,
    replay_history,
    replay_matches,
)
from app.champions.models import ChampionsTeam


def team(team_id: str, elo: float) -> ChampionsTeam:
    return ChampionsTeam(team_id, team_id, team_id[:3].upper(), "#000000", "ESP", elo)


def test_replay_updates_both_sides_and_preserves_total():
    teams = [team("a", 1600.0), team("b", 1500.0)]
    matches = [
        {
            "phase": "league",
            "matchday": 1,
            "home": "a",
            "away": "b",
            "home_goals": 2,
            "away_goals": 0,
            "neutral": False,
        }
    ]
    result = replay_matches(matches, teams, {"k": 20, "home_advantage": 60})
    assert result.ratings["a"] > 1600
    assert result.ratings["b"] < 1500
    assert result.ratings["a"] + result.ratings["b"] == pytest.approx(3100.0)


def test_calibration_uses_pre_match_deltas():
    teams = [team("a", 1600.0), team("b", 1500.0)]
    matches = [
        {
            "phase": "league",
            "matchday": 1,
            "home": "a",
            "away": "b",
            "home_goals": 1,
            "away_goals": 0,
            "neutral": False,
        }
    ]
    samples = calibration_samples(matches, teams, {"k": 20, "home_advantage": 60})
    assert samples[0][0] == pytest.approx(160.0)
    assert samples[0][1] == "H"


def test_neutral_match_has_no_home_advantage():
    teams = [team("a", 1600.0), team("b", 1500.0)]
    matches = [
        {
            "phase": "final",
            "matchday": 0,
            "home": "a",
            "away": "b",
            "home_goals": 1,
            "away_goals": 0,
            "neutral": True,
        }
    ]
    samples = calibration_samples(matches, teams, {"k": 20, "home_advantage": 60})
    assert samples[0][0] == pytest.approx(100.0)


def test_replay_history_applies_regression_at_season_boundary():
    teams = [team("a", 1500.0), team("b", 1500.0)]
    seasons = [
        (
            "2021/22",
            [
                {
                    "home": "a",
                    "away": "b",
                    "home_goals": 2,
                    "away_goals": 0,
                    "neutral": False,
                    "kickoff": "2021-09-01",
                    "sequence": 0,
                }
            ],
        ),
        ("2022/23", []),
    ]
    result = replay_history(
        seasons, teams, {"k": 20, "home_advantage": 60}, regression=0.2
    )
    end_a = result.season_ends["2021/22"]["a"]
    start_a = result.season_starts["2022/23"]["a"]
    assert start_a == pytest.approx(1500.0 + 0.8 * (end_a - 1500.0))


def test_replay_history_regresses_later_team_seed_at_boundary():
    teams = [team("a", 1500.0), team("b", 1500.0), team("c", 1900.0)]
    seasons = [
        (
            "2021/22",
            [
                {
                    "home": "a",
                    "away": "b",
                    "home_goals": 1,
                    "away_goals": 0,
                    "neutral": False,
                    "kickoff": "2021-09-01",
                    "sequence": 0,
                }
            ],
        ),
        (
            "2022/23",
            [
                {
                    "home": "c",
                    "away": "a",
                    "home_goals": 1,
                    "away_goals": 0,
                    "neutral": False,
                    "kickoff": "2022-09-01",
                    "sequence": 0,
                }
            ],
        ),
    ]
    result = replay_history(
        seasons, teams, {"k": 20, "home_advantage": 60}, regression=0.2
    )
    assert result.season_ends["2021/22"]["c"] == pytest.approx(1900.0)
    assert result.season_starts["2022/23"]["c"] == pytest.approx(
        1500.0 + 0.8 * (1900.0 - 1500.0)
    )
    assert result.season_starts["2022/23"]["c"] != pytest.approx(1500.0)


def test_replay_history_applies_season_prior():
    teams = [team("a", 1500.0)]
    seasons = [("2021/22", []), ("2022/23", [])]
    result = replay_history(
        seasons,
        teams,
        {"k": 20, "home_advantage": 60},
        regression=0.0,
        season_priors={"2022/23": {"a": 1800.0}},
        prior_weight=0.5,
    )
    assert result.season_starts["2022/23"]["a"] == pytest.approx(1650.0)


def test_replay_history_preserves_total_without_regression():
    teams = [team("a", 1600.0), team("b", 1500.0)]
    seasons = [
        (
            "2021/22",
            [
                {
                    "home": "a",
                    "away": "b",
                    "home_goals": 2,
                    "away_goals": 0,
                    "neutral": False,
                    "kickoff": "2021-09-01",
                    "sequence": 0,
                }
            ],
        )
    ]
    result = replay_history(
        seasons, teams, {"k": 20, "home_advantage": 60}, regression=0.0
    )
    assert result.ratings["a"] + result.ratings["b"] == pytest.approx(3100.0)
