from app.champions.domain.standings import build_records, qualification_cuts, rank_teams
from app.champions.models import ChampionsMatch


def match(match_id: str, home: str, away: str, hg: int, ag: int) -> ChampionsMatch:
    return ChampionsMatch(match_id, "league", 1, 0, home, away, hg, ag)


def test_points_then_goal_difference_then_goals():
    teams = ["a", "b", "c"]
    records = build_records(teams, [])
    assert all(record.points == 0 for record in records.values())
    assert rank_teams(teams, [], random_keys={"a": 0.1, "b": 0.2, "c": 0.3}) == [
        "c",
        "b",
        "a",
    ]


def test_away_goals_break_goal_difference_tie():
    matches = [
        match("m1", "c", "a", 0, 1),
        match("m2", "b", "c", 1, 0),
    ]
    assert rank_teams(["a", "b", "c"], matches) == ["a", "b", "c"]


def test_away_wins_break_full_tie():
    matches = [
        match("m1", "c", "0", 0, 1),
        match("m2", "b", "c", 1, 0),
        match("m3", "b", "0", 0, 1),
        match("m4", "0", "a", 0, 1),
        match("m5", "a", "b", 0, 1),
    ]
    records = build_records(["a", "b", "c", "0"], matches)
    assert records["a"].points == 3
    order = rank_teams(["a", "b", "c", "0"], matches)
    assert order.index("a") < order.index("c")


def test_qualification_cuts_for_36_teams():
    assert qualification_cuts(36) == (8, 24)
    assert qualification_cuts(8) == (2, 4)
