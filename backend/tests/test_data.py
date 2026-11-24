from collections import Counter

from app.data.league import build_demo_snapshot, get_snapshot
from app.data.schedule import generate_double_round_robin
from app.domain.standings import build_records


def test_schedule_is_a_complete_double_round_robin():
    team_ids = [f"T{i}" for i in range(20)]
    matches = generate_double_round_robin(team_ids)
    assert len(matches) == 380
    assert len({match.id for match in matches}) == 380

    per_team = Counter()
    pairs = Counter()
    home_pairs = Counter()
    for match in matches:
        per_team[match.home_id] += 1
        per_team[match.away_id] += 1
        pairs[tuple(sorted((match.home_id, match.away_id)))] += 1
        home_pairs[(match.home_id, match.away_id)] += 1
    assert all(count == 38 for count in per_team.values())
    assert all(count == 2 for count in pairs.values())
    assert all(count == 1 for count in home_pairs.values())

    matchdays = Counter(match.matchday for match in matches)
    assert set(matchdays) == set(range(1, 39))
    assert all(count == 10 for count in matchdays.values())


def test_demo_snapshot_has_twenty_teams_and_eight_played_matchdays():
    snapshot = build_demo_snapshot()
    assert len(snapshot.teams) == 20
    assert len(snapshot.matches) == 380
    assert snapshot.source == "demo"
    assert snapshot.season == "2026/27"

    played = [match for match in snapshot.matches if match.is_played]
    pending = [match for match in snapshot.matches if not match.is_played]
    assert len(played) == 80
    assert len(pending) == 300
    assert all(match.has_score for match in played)

    records = build_records([team.id for team in snapshot.teams], played)
    assert sum(record.played for record in records.values()) == 160
    assert sum(record.points for record in records.values()) > 0


def test_demo_snapshot_is_deterministic():
    first = build_demo_snapshot()
    second = build_demo_snapshot()
    assert first.data_version == second.data_version
    assert [(m.id, m.home_goals, m.away_goals) for m in first.matches] == [
        (m.id, m.home_goals, m.away_goals) for m in second.matches
    ]


def test_snapshot_uses_demo_when_no_api_key_is_configured():
    snapshot = get_snapshot(force=True)
    assert snapshot.source == "demo"
    assert snapshot.teams
    assert snapshot.matches
