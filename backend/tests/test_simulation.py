import itertools

import numpy as np
import pytest

from app.domain.models import Match, Team
from app.domain.simulation import SimulationRequest, simulate_season


def make_teams():
    return [
        Team("A", "Equipo A", "A", "#111111", 1800),
        Team("B", "Equipo B", "B", "#222222", 1720),
        Team("C", "Equipo C", "C", "#333333", 1640),
        Team("D", "Equipo D", "D", "#444444", 1560),
    ]


def double_round_robin(teams, *, with_scores=False):
    matches = []
    matchday = 1
    for home, away in itertools.permutations([team.id for team in teams], 2):
        score = (2, 0) if with_scores else (None, None)
        matches.append(
            Match(
                id=f"{home}-{away}",
                matchday=matchday,
                home_id=home,
                away_id=away,
                home_goals=score[0],
                away_goals=score[1],
                outcome=None if with_scores else None,
            )
        )
        matchday += 1
    return matches


def forced_table(teams):
    """A wins everything, B beats C and D, C beats D."""
    results = {}
    for home in [team.id for team in teams]:
        for away in [team.id for team in teams]:
            if home == away:
                continue
            if home == "A":
                results[f"{home}-{away}"] = "H"
            elif away == "A":
                results[f"{home}-{away}"] = "A"
            elif home == "B":
                results[f"{home}-{away}"] = "H"
            elif away == "B":
                results[f"{home}-{away}"] = "A"
            elif home == "C":
                results[f"{home}-{away}"] = "H"
            else:
                results[f"{home}-{away}"] = "A"
    return results


def forced_scores(teams):
    scores = {}
    strength = {"A": 3, "B": 2, "C": 1, "D": 0}
    for home in [team.id for team in teams]:
        for away in [team.id for team in teams]:
            if home == away:
                continue
            if strength[home] >= strength[away]:
                scores[f"{home}-{away}"] = (3, 0)
            else:
                scores[f"{home}-{away}"] = (0, 2)
    return scores


def test_forced_results_produce_a_deterministic_table_in_1x2_mode():
    teams = make_teams()
    matches = double_round_robin(teams)
    result = simulate_season(
        SimulationRequest(
            teams=teams,
            matches=matches,
            mode="1x2",
            n_sims=1_000,
            seed=1,
            forced_results=forced_table(teams),
        )
    )
    assert result.team_map["A"].champion_probability == pytest.approx(1.0)
    assert result.team_map["D"].relegation_probability == pytest.approx(1.0)
    assert result.team_map["A"].expected_points == pytest.approx(18.0)
    assert result.team_map["B"].expected_points == pytest.approx(12.0)


def test_forced_scores_produce_a_deterministic_table_in_exact_mode():
    teams = make_teams()
    matches = double_round_robin(teams)
    result = simulate_season(
        SimulationRequest(
            teams=teams,
            matches=matches,
            mode="score",
            n_sims=500,
            seed=7,
            forced_scores=forced_scores(teams),
        )
    )
    assert result.team_map["A"].champion_probability == pytest.approx(1.0)
    assert result.team_map["B"].most_likely_position == 2
    assert result.team_map["D"].most_likely_position == 4
    assert result.team_map["A"].points_histogram[18] == pytest.approx(1.0)


def test_champion_probabilities_sum_to_one():
    teams = make_teams()
    result = simulate_season(
        SimulationRequest(
            teams=teams,
            matches=double_round_robin(teams),
            mode="score",
            n_sims=2_000,
            seed=11,
        )
    )
    assert sum(team.champion_probability for team in result.teams) == pytest.approx(1.0)
    for team in result.teams:
        assert sum(team.position_probabilities) == pytest.approx(1.0)
        assert sum(team.points_histogram) == pytest.approx(1.0)


def test_same_seed_is_reproducible():
    teams = make_teams()
    request = SimulationRequest(
        teams=teams,
        matches=double_round_robin(teams),
        mode="score",
        n_sims=1_000,
        seed=123,
    )
    first = simulate_season(request)
    second = simulate_season(request)
    for team in teams:
        assert first.team_map[team.id].champion_probability == pytest.approx(
            second.team_map[team.id].champion_probability
        )
        assert first.team_map[team.id].expected_points == pytest.approx(
            second.team_map[team.id].expected_points
        )


def test_elo_override_changes_the_projection():
    teams = make_teams()
    matches = double_round_robin(teams)
    weak = simulate_season(
        SimulationRequest(
            teams=teams,
            matches=matches,
            mode="score",
            n_sims=3_000,
            seed=4,
            elo_delta={"A": -250, "D": 250},
        )
    )
    strong = simulate_season(
        SimulationRequest(
            teams=teams,
            matches=matches,
            mode="score",
            n_sims=3_000,
            seed=4,
            elo_delta={"A": 250, "D": -250},
        )
    )
    assert strong.team_map["A"].champion_probability > weak.team_map["A"].champion_probability


def test_exact_mode_reports_most_likely_scores_and_1x2_mode_does_not():
    teams = make_teams()
    matches = double_round_robin(teams)
    exact = simulate_season(
        SimulationRequest(teams=teams, matches=matches, mode="score", n_sims=200, seed=9)
    )
    assert exact.match_predictions
    assert exact.match_predictions[0].most_likely_score is not None
    assert sum(
        [
            exact.match_predictions[0].home_probability,
            exact.match_predictions[0].draw_probability,
            exact.match_predictions[0].away_probability,
        ]
    ) == pytest.approx(1.0)

    simple = simulate_season(
        SimulationRequest(teams=teams, matches=matches, mode="1x2", n_sims=200, seed=9)
    )
    assert simple.match_predictions[0].most_likely_score is None


def test_head_to_head_goals_scored_orders_a_three_way_tie():
    teams = [
        Team("A", "A", "A", "#111111", 1800),
        Team("B", "B", "B", "#222222", 1800),
        Team("C", "C", "C", "#333333", 1800),
    ]
    matches = [
        Match("A-B", 1, "A", "B"),
        Match("B-C", 2, "B", "C"),
        Match("C-A", 3, "C", "A"),
    ]
    result = simulate_season(
        SimulationRequest(
            teams=teams,
            matches=matches,
            mode="score",
            n_sims=100,
            seed=1,
            forced_scores={"A-B": (3, 0), "B-C": (4, 0), "C-A": (5, 0)},
        )
    )
    assert result.team_map["C"].champion_probability == pytest.approx(1.0)
    assert result.team_map["B"].most_likely_position == 2
    assert result.team_map["A"].most_likely_position == 3


def test_percentiles_are_ordered_and_expected_points_is_consistent():
    teams = make_teams()
    result = simulate_season(
        SimulationRequest(
            teams=teams,
            matches=double_round_robin(teams),
            mode="score",
            n_sims=2_000,
            seed=2,
        )
    )
    for team in result.teams:
        assert team.p10_points <= team.median_points <= team.p90_points
        assert team.p10_points <= team.expected_points <= team.p90_points
        assert team.points_std >= 0


def test_invalid_simulation_size_is_rejected():
    teams = make_teams()
    with pytest.raises(ValueError):
        simulate_season(
            SimulationRequest(
                teams=teams,
                matches=double_round_robin(teams),
                mode="score",
                n_sims=0,
            )
        )

def test_progress_callback_reports_each_chunk():
    teams = make_teams()
    calls = []
    result = simulate_season(
        SimulationRequest(
            teams=teams,
            matches=double_round_robin(teams),
            mode="score",
            n_sims=2500,
            seed=15,
            chunk_size=1000,
            progress_callback=lambda done, total: calls.append((done, total)),
        )
    )
    assert result.n_sims == 2500
    assert calls
    assert all(total == 2500 for _, total in calls)
    assert calls[-1] == (2500, 2500)

def test_start_matchday_keeps_earlier_results_and_resimulates_later_ones():
    teams = [
        Team("A", "A", "A", "#111111", 1800),
        Team("B", "B", "B", "#222222", 1700),
        Team("C", "C", "C", "#333333", 1600),
        Team("D", "D", "D", "#444444", 1500),
    ]
    matches = [
        Match("A-B", 1, "A", "B", home_goals=5, away_goals=0),
        Match("C-D", 1, "C", "D", home_goals=5, away_goals=0),
        Match("A-C", 2, "A", "C", home_goals=0, away_goals=5),
        Match("B-D", 2, "B", "D", home_goals=0, away_goals=5),
    ]
    result = simulate_season(
        SimulationRequest(
            teams=teams,
            matches=matches,
            mode="score",
            n_sims=200,
            seed=3,
            start_matchday=2,
            forced_scores={"A-C": (1, 0), "B-D": (1, 0)},
        )
    )
    assert result.start_matchday == 2
    assert result.team_map["A"].expected_points == pytest.approx(6.0)
    assert result.team_map["B"].expected_points == pytest.approx(3.0)
    assert result.team_map["C"].expected_points == pytest.approx(3.0)
    assert result.team_map["D"].expected_points == pytest.approx(0.0)


def test_start_matchday_one_ignores_every_real_result():
    teams = make_teams()
    matches = double_round_robin(teams, with_scores=True)
    forced = {match.id: (1, 0) for match in matches}
    result = simulate_season(
        SimulationRequest(
            teams=teams,
            matches=matches,
            mode="score",
            n_sims=100,
            seed=4,
            start_matchday=1,
            forced_scores=forced,
        )
    )
    assert result.start_matchday == 1
    assert all(team.expected_points > 0 for team in result.teams)


def test_invalid_start_matchday_is_rejected():
    teams = make_teams()
    with pytest.raises(ValueError):
        simulate_season(
            SimulationRequest(
                teams=teams,
                matches=double_round_robin(teams),
                mode="score",
                n_sims=10,
                start_matchday=99,
            )
        )
