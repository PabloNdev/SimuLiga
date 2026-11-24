import math

import numpy as np
import pytest

from app.domain.scoreline import (
    ScorelineParams,
    expected_goals,
    fit_scoreline,
    most_likely_score,
    outcome_probabilities,
    sample_scores_batch,
    sample_scores_for_outcome,
    score_matrix,
)


def _scoreline_nll(
    params: ScorelineParams,
    deltas: list[float],
    home_goals: list[int],
    away_goals: list[int],
) -> float:
    total = 0.0
    for delta, home, away in zip(deltas, home_goals, away_goals):
        lh, la = expected_goals(1500 + delta / 2, 1500 - delta / 2, params)
        probability = score_matrix(lh, la, params)[home, away]
        total -= math.log(max(float(probability), 1e-12))
    return total


def test_score_matrix_is_a_probability_distribution():
    matrix = score_matrix(1.6, 1.1, ScorelineParams())
    assert matrix.sum() == pytest.approx(1.0)
    assert (matrix >= 0).all()


def test_equal_teams_without_home_advantage_produce_symmetric_matrix():
    matrix = score_matrix(1.3, 1.3, ScorelineParams())
    assert matrix == pytest.approx(matrix.T)


def test_stronger_attack_increases_home_win_probability():
    params = ScorelineParams()
    weak = outcome_probabilities(1.0, 1.4, params)
    strong = outcome_probabilities(2.2, 0.8, params)
    assert strong.home > weak.home
    assert strong.away < weak.away


def test_most_likely_score_for_typical_lambdas():
    assert most_likely_score(1.6, 0.8, ScorelineParams())[:2] == (1, 0)


def test_dixon_coles_rho_raises_goalless_draw_probability():
    plain = score_matrix(1.2, 1.2, ScorelineParams(rho=0.0))
    corrected = score_matrix(1.2, 1.2, ScorelineParams(rho=-0.1))
    assert corrected[0, 0] > plain[0, 0]


def test_expected_goals_react_to_elo_gap():
    params = ScorelineParams()
    even_home, even_away = expected_goals(1800, 1800, params)
    strong_home, strong_away = expected_goals(2000, 1600, params)
    assert strong_home > even_home
    assert strong_away < even_away


def test_sampling_matches_theoretical_means_and_outcome_rates():
    params = ScorelineParams()
    lh, la = 1.7, 0.9
    rng = np.random.default_rng(42)
    home_goals, away_goals = sample_scores_batch(lh, la, 60_000, rng, params)
    assert home_goals.mean() == pytest.approx(lh, abs=0.06)
    assert away_goals.mean() == pytest.approx(la, abs=0.06)

    matrix = score_matrix(lh, la, params)
    home_rate = np.tril(matrix, -1).sum()
    draw_rate = np.trace(matrix)
    away_rate = np.triu(matrix, 1).sum()
    sampled_home = float((home_goals > away_goals).mean())
    sampled_draw = float((home_goals == away_goals).mean())
    sampled_away = float((home_goals < away_goals).mean())
    assert sampled_home == pytest.approx(home_rate, abs=0.012)
    assert sampled_draw == pytest.approx(draw_rate, abs=0.012)
    assert sampled_away == pytest.approx(away_rate, abs=0.012)

def test_fit_scoreline_learns_home_and_elo_effects():
    deltas = [200.0] * 40 + [-200.0] * 40
    home_goals = [3] * 40 + [1] * 40
    away_goals = [1] * 40 + [3] * 40
    fitted = fit_scoreline(
        deltas,
        home_goals,
        away_goals,
        home_advantage=34.41,
    )

    default = ScorelineParams(home_advantage=34.41)
    assert fitted.home_advantage == pytest.approx(34.41)
    assert fitted.elo_slope > 0
    assert expected_goals(1700, 1500, fitted)[0] > expected_goals(
        1700, 1500, fitted
    )[1]
    assert expected_goals(1500, 1700, fitted)[0] < expected_goals(
        1500, 1700, fitted
    )[1]
    assert _scoreline_nll(
        fitted, deltas, home_goals, away_goals
    ) < _scoreline_nll(default, deltas, home_goals, away_goals)


def test_fit_scoreline_requires_samples():
    with pytest.raises(ValueError):
        fit_scoreline([], [], [])


def test_conditioned_sampling_respects_the_requested_outcome():
    params = ScorelineParams()
    rng = np.random.default_rng(8)
    for outcome, check in (
        ("H", lambda h, a: (h > a).all()),
        ("D", lambda h, a: (h == a).all()),
        ("A", lambda h, a: (h < a).all()),
    ):
        home_goals, away_goals = sample_scores_for_outcome(
            1.5, 1.2, outcome, 4_000, rng, params
        )
        assert check(home_goals, away_goals)
