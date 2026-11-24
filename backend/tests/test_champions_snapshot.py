import pytest

from app.champions.api.serializers import serialize_validation
from app.champions.config import ChampionsSettings
from app.champions.data.snapshot import (
    build_demo_snapshot,
    build_snapshot_from_matches,
    calibration_score_samples,
    replay_history,
    resolve_teams,
)
from app.domain.elo import update_ratings


def raw_match(season, kickoff, home, away, home_goals, away_goals, matchday=1):
    return {
        "season": season,
        "season_start": int(season.split("/")[0]),
        "sequence": 0,
        "phase": "league",
        "matchday": matchday,
        "leg": 0,
        "home": home,
        "away": away,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "kickoff": kickoff,
        "neutral": False,
    }


def test_demo_snapshot_has_36_teams_and_8_matchdays():
    snapshot = build_demo_snapshot()
    assert snapshot.demo is True
    assert len(snapshot.teams) == 36
    league_matchdays = {
        match.matchday for match in snapshot.matches if match.phase == "league"
    }
    assert league_matchdays == set(range(1, 9))
    assert sum(1 for match in snapshot.matches if match.is_played) > 0


def test_demo_snapshot_is_deterministic():
    first = build_demo_snapshot()
    second = build_demo_snapshot()
    assert first.data_version == second.data_version
    assert [(match.id, match.home_goals, match.away_goals) for match in first.matches] == [
        (match.id, match.home_goals, match.away_goals) for match in second.matches
    ]


def test_snapshot_uses_history_seasons_and_verification():
    settings = ChampionsSettings(
        data_source="demo",
        clubelo_enabled=False,
        history_seasons=2,
        season_regression=0.2,
        previous_season=2025,
        season=2026,
    )
    history = [
        raw_match("2024/25", "2024-09-01", "Real Madrid", "Barcelona", 2, 1),
        raw_match("2024/25", "2024-09-02", "Barcelona", "Real Madrid", 1, 1),
        raw_match("2025/26", "2025-09-01", "Real Madrid", "Barcelona", 1, 0),
        raw_match("2025/26", "2025-09-02", "Barcelona", "Real Madrid", 2, 2),
    ]
    current = [
        raw_match("2026/27", "2026-09-01", "Real Madrid", "Barcelona", 1, 1),
        raw_match(
            "2026/27", "2026-09-02", "Barcelona", "Real Madrid", None, None
        ),
    ]
    snapshot = build_snapshot_from_matches(
        history,
        current,
        settings,
        source="test",
        history_labels=["2024/25", "2025/26"],
        current_label="2026/27",
        history_sources=["test"],
    )
    assert snapshot.elo_history["seasons"] == [
        "2024/25",
        "2025/26",
        "2026/27",
    ]
    assert len(snapshot.elo_history["series"]) == 2
    assert all(
        len(series["values"]) == 3 for series in snapshot.elo_history["series"]
    )
    assert snapshot.elo_verification["history_seasons"] == 2
    assert snapshot.elo_verification["history_complete"] is True
    assert snapshot.elo_verification["season_regression"] == 0.2
    assert snapshot.elo_verification["history_matches_applied"] == 4


def test_calibration_score_samples_include_goals_and_pre_match_delta():
    matches = [
        raw_match("2025/26", "2025-09-01", "Real Madrid", "Barcelona", 2, 1),
        raw_match("2025/26", "2025-09-02", "Barcelona", "Real Madrid", 1, 1),
    ]
    teams = resolve_teams(matches)
    ratings = {
        team_id: team.with_elo(1600.0 if team_id == "real-madrid" else 1500.0)
        for team_id, team in teams.items()
    }
    samples = calibration_score_samples(
        matches,
        ratings.values(),
        {"k": 20, "home_advantage": 60},
    )
    assert samples[0] == (100.0, 2, 1, "league", 1)
    assert samples[1][1:] == (1, 1, "league", 1)


def test_snapshot_fits_scoreline_from_historical_matches():
    settings = ChampionsSettings(
        data_source="demo",
        clubelo_enabled=False,
        history_seasons=2,
        season_regression=0.2,
        previous_season=2025,
        season=2026,
    )
    history = [
        raw_match("2024/25", "2024-09-01", "Real Madrid", "Barcelona", 2, 1),
        *[
            raw_match(
                "2025/26",
                f"2025-09-{(index % 28) + 1:02d}",
                "Real Madrid" if index % 2 == 0 else "Barcelona",
                "Barcelona" if index % 2 == 0 else "Real Madrid",
                3,
                1,
                matchday=(index % 6) + 1,
            )
            for index in range(48)
        ],
    ]
    snapshot = build_snapshot_from_matches(
        history,
        [],
        settings,
        source="test",
        history_labels=["2024/25", "2025/26"],
        current_label="2026/27",
        history_sources=["test"],
    )
    scoreline = snapshot.model["scoreline"]
    assert scoreline["home_base"] > 1.5
    assert scoreline["home_base"] > scoreline["away_base"]
    assert scoreline["home_advantage"] == pytest.approx(
        snapshot.model["davidson"]["home_advantage"]
    )


def test_validation_serializer_uses_previous_season_totals():
    settings = ChampionsSettings(
        data_source="demo",
        clubelo_enabled=False,
        history_seasons=2,
        season_regression=0.2,
        previous_season=2025,
        season=2026,
    )
    history = [
        raw_match("2024/25", "2024-09-01", "Real Madrid", "Barcelona", 2, 1),
        raw_match("2024/25", "2024-09-02", "Barcelona", "Real Madrid", 1, 1),
        raw_match("2025/26", "2025-09-01", "Real Madrid", "Barcelona", 1, 0),
        raw_match("2025/26", "2025-09-02", "Barcelona", "Real Madrid", 2, 2),
    ]
    snapshot = build_snapshot_from_matches(
        history,
        [],
        settings,
        source="test",
        history_labels=["2024/25", "2025/26"],
        current_label="2026/27",
        history_sources=["test"],
    )
    data = serialize_validation(snapshot)["data"]
    assert data["previous_matches"] == 2
    assert data["previous_applied"] == 2
    assert snapshot.elo_verification["history_matches_total"] == 4


def test_current_start_rating_is_one_regression_from_history_end():
    settings = ChampionsSettings(
        data_source="demo",
        clubelo_enabled=False,
        history_seasons=2,
        season_regression=0.2,
        previous_season=2025,
        season=2026,
    )
    history = [
        raw_match("2024/25", "2024-09-01", "Real Madrid", "Barcelona", 2, 1),
        raw_match("2025/26", "2025-09-01", "Real Madrid", "Barcelona", 3, 0),
    ]
    current = [
        raw_match("2026/27", "2026-09-01", "Real Madrid", "Barcelona", 2, 0),
    ]
    snapshot = build_snapshot_from_matches(
        history,
        current,
        settings,
        source="test",
        history_labels=["2024/25", "2025/26"],
        current_label="2026/27",
        history_sources=["test"],
    )
    teams = [
        team.with_elo(1500.0) for team in resolve_teams(history).values()
    ]
    replay = replay_history(
        [("2024/25", history[:1]), ("2025/26", history[1:])],
        teams,
        {"k": 20, "home_advantage": 60},
        regression=0.2,
    )
    boundary: dict[str, float] = {}
    for team_id in ("real-madrid", "barcelona"):
        end = replay.season_ends["2025/26"][team_id]
        boundary[team_id] = end + 0.2 * (1500.0 - end)
        assert snapshot.elo_by_matchday[1][team_id] == pytest.approx(
            boundary[team_id], abs=0.01
        )

    home_after, away_after = update_ratings(
        boundary["real-madrid"],
        boundary["barcelona"],
        2,
        0,
        k=20,
        home_advantage=float(
            snapshot.elo_verification["params"]["home_advantage"]
        ),
    )
    assert snapshot.elo_by_matchday[2]["real-madrid"] == pytest.approx(
        home_after, abs=0.01
    )
    assert snapshot.elo_by_matchday[2]["barcelona"] == pytest.approx(
        away_after, abs=0.01
    )


def test_fallback_rewinds_previous_season_after_four_matchdays():
    settings = ChampionsSettings(
        data_source="demo",
        clubelo_enabled=False,
        history_seasons=2,
        season_regression=0.2,
        previous_season=2025,
        season=2026,
    )
    history = [
        raw_match("2024/25", "2024-09-01", "Real Madrid", "Barcelona", 2, 1),
        *[
            raw_match(
                "2025/26",
                f"2025-09-0{matchday}",
                "Real Madrid" if matchday % 2 else "Barcelona",
                "Barcelona" if matchday % 2 else "Real Madrid",
                1,
                0,
                matchday=matchday,
            )
            for matchday in range(1, 6)
        ],
    ]
    snapshot = build_snapshot_from_matches(
        history,
        [],
        settings,
        source="test",
        history_labels=["2024/25", "2025/26"],
        current_label="2026/27",
        history_sources=["test"],
    )
    assert snapshot.fallback is True
    played = sorted(
        {
            match.matchday
            for match in snapshot.matches
            if match.is_played
        }
    )
    pending = sorted(
        {
            match.matchday
            for match in snapshot.matches
            if not match.is_played
        }
    )
    assert played == [1, 2, 3, 4]
    assert pending == [5]
    assert snapshot.elo_history["seasons"] == ["2024/25", "2025/26"]


def test_current_new_team_starts_at_mean_of_known_current_ratings():
    settings = ChampionsSettings(
        data_source="demo",
        clubelo_enabled=False,
        history_seasons=2,
        season_regression=0.2,
        previous_season=2025,
        season=2026,
    )
    history = [
        raw_match("2024/25", "2024-09-01", "Real Madrid", "Barcelona", 2, 1),
        raw_match("2025/26", "2025-09-01", "Real Madrid", "Barcelona", 3, 0),
    ]
    current = [
        raw_match(
            "2026/27", "2026-09-01", "Real Madrid", "Barcelona", None, None
        ),
        raw_match(
            "2026/27",
            "2026-09-02",
            "Sevilla",
            "Real Madrid",
            None,
            None,
            matchday=2,
        ),
    ]
    snapshot = build_snapshot_from_matches(
        history,
        current,
        settings,
        source="test",
        history_labels=["2024/25", "2025/26"],
        current_label="2026/27",
        history_sources=["test"],
    )
    start = snapshot.elo_by_matchday[1]
    known = [start["real-madrid"], start["barcelona"]]
    assert start["sevilla"] == pytest.approx(
        sum(known) / len(known), abs=0.01
    )


def test_current_new_teams_start_at_1500_without_known_ratings():
    settings = ChampionsSettings(
        data_source="demo",
        clubelo_enabled=False,
        history_seasons=2,
        season_regression=0.2,
        previous_season=2025,
        season=2026,
    )
    history = [
        raw_match("2024/25", "2024-09-01", "Real Madrid", "Barcelona", 2, 1),
        raw_match("2025/26", "2025-09-01", "Real Madrid", "Barcelona", 3, 0),
    ]
    current = [
        raw_match(
            "2026/27", "2026-09-01", "Sevilla", "Napoli", None, None
        ),
    ]
    snapshot = build_snapshot_from_matches(
        history,
        current,
        settings,
        source="test",
        history_labels=["2024/25", "2025/26"],
        current_label="2026/27",
        history_sources=["test"],
    )
    start = snapshot.elo_by_matchday[1]
    assert start["sevilla"] == pytest.approx(1500.0)
    assert start["napoli"] == pytest.approx(1500.0)


def test_clubelo_prior_blends_history_and_current_season(monkeypatch):
    monkeypatch.setattr(
        "app.champions.data.snapshot._clubelo_snapshot",
        lambda settings, date: {"Liverpool": 1800.0},
    )
    settings = ChampionsSettings(
        data_source="auto",
        clubelo_enabled=True,
        history_seasons=2,
        season_regression=0.2,
        clubelo_prior_weight=0.75,
        previous_season=2025,
        season=2026,
    )
    history = [
        raw_match("2024/25", "2024-09-01", "Real Madrid", "Barcelona", 2, 1),
        raw_match("2025/26", "2025-09-01", "Liverpool", "Real Madrid", 1, 0),
    ]
    current = [
        raw_match("2026/27", "2026-09-01", "Liverpool", "Real Madrid", 1, 1),
    ]
    snapshot = build_snapshot_from_matches(
        history,
        current,
        settings,
        source="test",
        history_labels=["2024/25", "2025/26"],
        current_label="2026/27",
        history_sources=["test"],
    )
    series = {
        item["team_id"]: item["values"]
        for item in snapshot.elo_history["series"]
    }
    assert series["liverpool"][0] == pytest.approx(1800.0)
    assert series["liverpool"][1] == pytest.approx(1785.0)
    assert snapshot.elo_verification["clubelo_prior"] is True
    assert snapshot.elo_verification["clubelo_prior_weight"] == 0.75


def test_current_new_team_uses_clubelo_prior(monkeypatch):
    monkeypatch.setattr(
        "app.champions.data.snapshot._clubelo_snapshot",
        lambda settings, date: {"Sevilla": 1800.0},
    )
    settings = ChampionsSettings(
        data_source="auto",
        clubelo_enabled=True,
        history_seasons=2,
        season_regression=0.2,
        clubelo_prior_weight=0.75,
        previous_season=2025,
        season=2026,
    )
    history = [
        raw_match("2024/25", "2024-09-01", "Real Madrid", "Barcelona", 2, 1),
        raw_match("2025/26", "2025-09-01", "Real Madrid", "Barcelona", 3, 0),
    ]
    current = [
        raw_match(
            "2026/27", "2026-09-01", "Sevilla", "Real Madrid", None, None
        ),
    ]
    snapshot = build_snapshot_from_matches(
        history,
        current,
        settings,
        source="test",
        history_labels=["2024/25", "2025/26"],
        current_label="2026/27",
        history_sources=["test"],
    )
    start = snapshot.elo_by_matchday[1]
    assert start["sevilla"] == pytest.approx(1725.0)


def test_clubelo_by_known_teams_maps_names():
    from app.champions.data.snapshot import (
        _clubelo_by_known_teams,
        make_team,
    )

    teams = {
        "manchester-city": make_team("Manchester City"),
        "bayern-munich": make_team("Bayern München"),
    }
    mapped = _clubelo_by_known_teams(
        {"Man City": 1900.0, "Bayern": 1850.0, "Other FC": 1500.0},
        teams,
    )
    assert mapped == {
        "manchester-city": 1900.0,
        "bayern-munich": 1850.0,
    }
