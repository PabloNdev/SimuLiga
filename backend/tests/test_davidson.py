import numpy as np
import pytest

from app.domain.davidson import (
    DavidsonParams,
    fit_davidson,
    outcome_probabilities,
    probabilities_from_ratings,
)


def test_probabilities_sum_to_one():
    for delta in (-400, -120, 0, 35, 250, 600):
        probs = outcome_probabilities(delta, DavidsonParams(home_advantage=60, nu=0.9))
        assert probs.home + probs.draw + probs.away == pytest.approx(1.0)


def test_stronger_home_team_wins_more_often():
    strong = outcome_probabilities(300, DavidsonParams(60, 0.9))
    even = outcome_probabilities(0, DavidsonParams(60, 0.9))
    weak = outcome_probabilities(-300, DavidsonParams(60, 0.9))
    assert strong.home > even.home > weak.home
    assert strong.away < even.away < weak.away


def test_home_advantage_increases_home_probability():
    without = outcome_probabilities(0, DavidsonParams(0, 0.9))
    with_advantage = outcome_probabilities(0, DavidsonParams(80, 0.9))
    assert with_advantage.home > without.home


def test_nu_controls_draw_frequency():
    low = outcome_probabilities(0, DavidsonParams(0, 0.3))
    high = outcome_probabilities(0, DavidsonParams(0, 1.4))
    assert high.draw > low.draw


def test_swapping_sides_swaps_home_and_away_probabilities_without_home_advantage():
    params = DavidsonParams(0, 0.8)
    home = outcome_probabilities(180, params)
    away = outcome_probabilities(-180, params)
    assert home.home == pytest.approx(away.away)
    assert home.away == pytest.approx(away.home)
    assert home.draw == pytest.approx(away.draw)


def test_probabilities_from_ratings_implements_the_elo_transform():
    params = DavidsonParams(60, 0.9)
    from_delta = outcome_probabilities(140, params)
    from_ratings = probabilities_from_ratings(1740, 1600, params)
    assert from_ratings == pytest.approx(from_delta)


def test_fit_recovers_known_parameters():
    true_params = DavidsonParams(home_advantage=70, nu=0.85)
    rng = np.random.default_rng(20261020)
    deltas = rng.normal(0, 160, size=20_000)
    outcomes = []
    for delta in deltas:
        probs = outcome_probabilities(float(delta), true_params)
        outcomes.append(rng.choice(["H", "D", "A"], p=[probs.home, probs.draw, probs.away]))

    fitted = fit_davidson(deltas, outcomes)
    assert fitted.home_advantage == pytest.approx(70, abs=30)
    assert fitted.nu == pytest.approx(0.85, abs=0.12)
