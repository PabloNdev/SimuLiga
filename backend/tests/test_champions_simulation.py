import pytest

from app.champions.domain.simulation import (
    ChampionsSimulationRequest,
    simulate_champions,
)
from app.champions.models import ChampionsMatch, ChampionsTeam


def make_teams(count: int = 8) -> list[ChampionsTeam]:
    return [
        ChampionsTeam(
            f"t{i}", f"Team {i}", f"T{i}", "#000000", "ESP", 1500.0 + i * 10
        )
        for i in range(count)
    ]


def make_matches(teams: list[ChampionsTeam]) -> list[ChampionsMatch]:
    matches: list[ChampionsMatch] = []
    for first in range(len(teams)):
        for second in range(first + 1, len(teams)):
            matches.append(
                ChampionsMatch(
                    f"m{first}-{second}",
                    "league",
                    1,
                    0,
                    teams[first].id,
                    teams[second].id,
                )
            )
    return matches


def test_probabilities_sum_to_one():
    teams = make_teams()
    result = simulate_champions(
        ChampionsSimulationRequest(
            teams=teams, matches=make_matches(teams), n_sims=200, seed=1
        )
    )
    total = sum(
        team.top8_probability + team.playoff_probability + team.eliminated_probability
        for team in result.teams
    )
    assert total == pytest.approx(len(teams), abs=1e-9)
    assert len(result.teams) == len(teams)


def test_round_of_16_is_top_plus_playoff_winners():
    teams = make_teams()
    result = simulate_champions(
        ChampionsSimulationRequest(
            teams=teams, matches=make_matches(teams), n_sims=100, seed=2
        )
    )
    total = sum(team.round_of_16_probability for team in result.teams)
    assert total == pytest.approx(3.0, abs=1e-9)


def test_same_seed_is_deterministic():
    teams = make_teams()
    matches = make_matches(teams)
    first = simulate_champions(
        ChampionsSimulationRequest(teams=teams, matches=matches, n_sims=100, seed=7)
    )
    second = simulate_champions(
        ChampionsSimulationRequest(teams=teams, matches=matches, n_sims=100, seed=7)
    )
    assert [team.expected_points for team in first.teams] == [
        team.expected_points for team in second.teams
    ]


def test_played_matches_are_respected():
    teams = make_teams()
    matches = make_matches(teams)
    matches[0] = matches[0].with_score(4, 0)
    result = simulate_champions(
        ChampionsSimulationRequest(teams=teams, matches=matches, n_sims=50, seed=3)
    )
    assert result.teams
    assert result.goals_available is True
