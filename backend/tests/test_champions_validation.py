import pytest

from app.champions.data.validation import (
    evaluate_ratings,
    points_by_team,
    ratings_for_window,
    season_groups,
    spearman_correlation,
    top_overlap,
)
from app.domain.davidson import DavidsonParams


def raw_match(home, away, home_goals, away_goals):
    return {
        "home": home,
        "away": away,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "phase": "league",
        "kickoff": "2025-09-01",
        "sequence": 0,
        "neutral": False,
    }


def test_points_by_team_counts_results():
    points = points_by_team(
        [
            raw_match("Real Madrid", "Barcelona", 2, 1),
            raw_match("Barcelona", "Real Madrid", 1, 1),
        ]
    )
    assert points["real-madrid"] == 4
    assert points["barcelona"] == 1


def test_evaluate_ratings_returns_metrics():
    metrics = evaluate_ratings(
        [raw_match("Real Madrid", "Barcelona", 2, 1)],
        {"real-madrid": 1700.0, "barcelona": 1500.0},
        DavidsonParams(home_advantage=17.3, nu=0.45),
    )
    assert metrics.matches == 1
    assert 0.0 <= metrics.accuracy <= 1.0
    assert metrics.log_loss > 0.0


def test_evaluate_ratings_known_values():
    metrics = evaluate_ratings(
        [raw_match("Real Madrid", "Barcelona", 2, 1)],
        {"real-madrid": 1700.0, "barcelona": 1500.0},
        DavidsonParams(home_advantage=17.3, nu=0.45),
    )
    assert metrics.matches == 1
    assert metrics.accuracy == 1.0
    assert metrics.log_loss == pytest.approx(0.4233146735, rel=1e-9)
    assert metrics.brier == pytest.approx(0.1791132063, rel=1e-9)


def test_evaluate_ratings_neutral_ignores_home_advantage():
    metrics = evaluate_ratings(
        [{**raw_match("Real Madrid", "Barcelona", 2, 1), "neutral": True}],
        {"real-madrid": 1500.0, "barcelona": 1500.0},
        DavidsonParams(home_advantage=100.0, nu=0.45),
    )
    assert metrics.matches == 1
    assert metrics.accuracy == 1.0
    assert metrics.log_loss == pytest.approx(0.8960880246, rel=1e-9)
    assert metrics.brier == pytest.approx(0.5506039150, rel=1e-9)


def test_top_overlap_and_spearman():
    ratings = {"a": 1700.0, "b": 1600.0, "c": 1500.0}
    points = {"a": 9.0, "b": 6.0, "c": 3.0}
    assert top_overlap(ratings, points, size=2) == 2
    assert spearman_correlation(ratings, points) == pytest.approx(1.0)


def test_top_overlap_uses_common_keys_only():
    ratings = {"a": 1800.0, "b": 1600.0, "x": 2500.0, "y": 2400.0}
    points = {"a": 9.0, "b": 6.0, "c": 3.0, "d": 1.0}
    assert top_overlap(ratings, points, size=2) == 2

    partial_ratings = {"a": 1800.0, "b": 1600.0, "c": 1500.0}
    partial_points = {"a": 9.0, "c": 6.0, "b": 3.0}
    assert top_overlap(partial_ratings, partial_points, size=2) == 1


def test_season_groups_keeps_label_order_and_empty_seasons():
    matches = [
        {**raw_match("Real Madrid", "Barcelona", 2, 1), "season": "2024/25"},
        {**raw_match("Barcelona", "Real Madrid", 1, 1), "season": "2025/26"},
    ]
    groups = season_groups(matches, ["2025/26", "2024/25", "2023/24"])
    assert [label for label, _ in groups] == [
        "2025/26",
        "2024/25",
        "2023/24",
    ]
    assert len(groups[0][1]) == 1
    assert len(groups[1][1]) == 1
    assert groups[2][1] == []


def test_ratings_for_window_applies_season_regression():
    first = {
        **raw_match("Real Madrid", "Barcelona", 2, 1),
        "season": "2024/25",
    }
    second = {
        **raw_match("Real Madrid", "Barcelona", 2, 1),
        "season": "2025/26",
    }
    labels = ["2024/25", "2025/26"]
    without_regression = ratings_for_window(
        [first, second], labels, regression=0.0, k=20
    )
    full_regression = ratings_for_window(
        [first, second], labels, regression=1.0, k=20
    )
    assert without_regression["real-madrid"] > full_regression["real-madrid"]
    assert full_regression["real-madrid"] > 1500.0
    assert full_regression["barcelona"] < 1500.0

