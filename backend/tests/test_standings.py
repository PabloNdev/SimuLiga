import pytest

from app.domain.models import Match
from app.domain.standings import build_records, rank_standings


def match(home, away, home_goals=None, away_goals=None, outcome=None, matchday=1, suffix=""):
    return Match(
        id=f"{home}-{away}-{matchday}{suffix}",
        matchday=matchday,
        home_id=home,
        away_id=away,
        home_goals=home_goals,
        away_goals=away_goals,
        outcome=outcome,
    )


def test_teams_are_ordered_by_points():
    teams = ["A", "B", "C"]
    matches = [
        match("A", "B", 1, 0),
        match("B", "C", 1, 0),
        match("A", "C", 1, 0),
    ]
    order = rank_standings(teams, matches)
    assert order == ["A", "B", "C"]


def test_head_to_head_points_beat_overall_goal_difference():
    teams = ["A", "B", "C", "D"]
    matches = [
        match("A", "B", 1, 0, matchday=1),
        match("B", "A", 1, 2, matchday=2),
        match("A", "C", 0, 5, matchday=3),
        match("C", "A", 0, 0, matchday=4),
        match("A", "D", 0, 5, matchday=5),
        match("D", "A", 0, 0, matchday=6),
        match("B", "C", 5, 0, matchday=3),
        match("C", "B", 0, 0, matchday=4),
        match("B", "D", 5, 0, matchday=5),
        match("D", "B", 0, 0, matchday=6),
    ]
    records = build_records(teams, matches)
    assert records["A"].points == 8
    assert records["B"].points == 8
    assert records["B"].goal_difference > records["A"].goal_difference

    order = rank_standings(teams, matches)
    assert order.index("A") < order.index("B")


def test_head_to_head_goal_difference_breaks_points_tie():
    teams = ["A", "B", "C", "D", "E"]
    matches = [
        match("A", "B", 3, 0, matchday=1),
        match("B", "A", 1, 0, matchday=2),
        match("A", "C", 1, 0, matchday=3),
        match("B", "C", 1, 0, matchday=3),
        match("A", "D", 0, 6, matchday=4),
        match("B", "D", 0, 1, matchday=4),
        match("C", "E", 1, 0, matchday=5),
        match("D", "E", 1, 1, matchday=5),
    ]
    records = build_records(teams, matches)
    assert records["A"].points == records["B"].points == 6
    assert records["B"].goal_difference > records["A"].goal_difference
    assert records["D"].points == 7

    order = rank_standings(teams, matches)
    assert order.index("D") < order.index("A") < order.index("B")


def test_head_to_head_goals_scored_breaks_points_and_goal_difference_tie():
    teams = ["A", "B", "C"]
    matches = [
        match("A", "B", 1, 1, matchday=1),
        match("B", "C", 2, 2, matchday=1),
        match("C", "A", 3, 3, matchday=1),
    ]
    records = build_records(teams, matches)
    assert all(records[t].points == 2 for t in teams)
    assert all(records[t].goal_difference == 0 for t in teams)

    order = rank_standings(teams, matches, expected_meetings=1)
    assert order == ["C", "A", "B"]


def test_incomplete_head_to_head_falls_back_to_overall_goal_difference():
    teams = ["A", "B", "C", "D"]
    matches = [
        match("A", "B", 1, 0, matchday=1),
        match("A", "C", 0, 4, matchday=2),
        match("B", "C", 4, 0, matchday=3),
        match("C", "D", 1, 1, matchday=4),
    ]
    records = build_records(teams, matches)
    assert records["A"].points == records["B"].points == 3
    assert records["B"].goal_difference > records["A"].goal_difference

    order = rank_standings(teams, matches, expected_meetings=2)
    assert order.index("B") < order.index("A")


def test_incomplete_head_to_head_can_be_used_when_requested():
    teams = ["A", "B", "C", "D"]
    matches = [
        match("A", "B", 1, 0, matchday=1),
        match("A", "C", 0, 4, matchday=2),
        match("B", "C", 4, 0, matchday=3),
        match("C", "D", 1, 1, matchday=4),
    ]
    order = rank_standings(
        teams, matches, expected_meetings=2, require_complete_head_to_head=False
    )
    assert order.index("A") < order.index("B")


def test_overall_goal_difference_then_goals_scored():
    teams = ["A", "B", "C"]
    matches = [
        match("A", "C", 3, 1, matchday=1),
        match("B", "C", 2, 0, matchday=2),
    ]
    records = build_records(teams, matches)
    assert records["A"].points == records["B"].points == 3
    assert records["A"].goal_difference == records["B"].goal_difference == 2
    assert records["A"].goals_for > records["B"].goals_for

    order = rank_standings(teams, matches)
    assert order.index("A") < order.index("B")


def test_fair_play_breaks_a_fully_equal_tie():
    teams = ["A", "B", "C"]
    matches = [
        match("A", "C", 2, 0, matchday=1),
        match("B", "C", 2, 0, matchday=2),
    ]
    order = rank_standings(teams, matches, fair_play={"A": 4, "B": 1, "C": 6})
    assert order.index("B") < order.index("A")


def test_final_deterministic_tiebreak_key_orders_equal_teams():
    teams = ["A", "B", "C"]
    matches = [
        match("A", "C", 1, 0, matchday=1),
        match("B", "C", 1, 0, matchday=2),
    ]
    order = rank_standings(teams, matches, tiebreak_key={"A": 0.8, "B": 0.2, "C": 0.5})
    assert order.index("B") < order.index("A")


def test_result_only_matches_rank_by_points_and_head_to_head():
    teams = ["A", "B", "C"]
    matches = [
        match("A", "B", outcome="H", matchday=1),
        match("B", "A", outcome="H", matchday=2),
        match("A", "C", outcome="H", matchday=3),
        match("B", "C", outcome="A", matchday=4),
    ]
    records = build_records(teams, matches)
    assert records["A"].points == 6
    assert records["B"].points == 3
    assert records["A"].goals_for is None

    order = rank_standings(teams, matches)
    assert order[0] == "A"


def test_build_records_computes_points_and_goal_difference():
    teams = ["A", "B"]
    matches = [match("A", "B", 3, 1), match("B", "A", 1, 1)]
    records = build_records(teams, matches)
    assert records["A"].played == 2
    assert records["A"].won == 1
    assert records["A"].drawn == 1
    assert records["A"].points == 4
    assert records["A"].goal_difference == 2
    assert records["B"].points == 1
