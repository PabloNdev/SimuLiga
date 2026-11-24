"""Davidson model for home win / draw / away win probabilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.optimize import minimize

OUTCOME_CODES = {"H": 0, "D": 1, "A": 2}


@dataclass(frozen=True)
class DavidsonParams:
    home_advantage: float = 60.0
    nu: float = 0.9
    elo_scale: float = 400.0


@dataclass(frozen=True)
class MatchProbabilities:
    home: float
    draw: float
    away: float

    def as_tuple(self) -> tuple[float, float, float]:
        return self.home, self.draw, self.away

    def as_list(self) -> list[float]:
        return [self.home, self.draw, self.away]


def outcome_probabilities(delta_elo: float, params: DavidsonParams) -> MatchProbabilities:
    """Davidson probabilities for a match with the given Elo difference."""
    strength = 10.0 ** ((delta_elo + params.home_advantage) / params.elo_scale)
    root = math.sqrt(strength)
    denominator = strength + 1.0 + params.nu * root
    return MatchProbabilities(
        home=strength / denominator,
        draw=params.nu * root / denominator,
        away=1.0 / denominator,
    )


def probabilities_from_ratings(
    home_elo: float, away_elo: float, params: DavidsonParams
) -> MatchProbabilities:
    return outcome_probabilities(home_elo - away_elo, params)


def _negative_log_likelihood(
    theta: np.ndarray, deltas: np.ndarray, outcomes: np.ndarray
) -> float:
    home_advantage, nu = float(theta[0]), float(theta[1])
    if nu <= 0:
        return 1e12
    strength = 10.0 ** ((deltas + home_advantage) / 400.0)
    root = np.sqrt(strength)
    denominator = strength + 1.0 + nu * root
    probs = np.column_stack(
        (strength / denominator, nu * root / denominator, 1.0 / denominator)
    )
    chosen = probs[np.arange(len(outcomes)), outcomes]
    return float(-np.log(np.clip(chosen, 1e-12, 1.0)).sum())


def fit_davidson(
    deltas: Sequence[float] | np.ndarray,
    outcomes: Sequence[str] | np.ndarray,
    *,
    elo_scale: float = 400.0,
) -> DavidsonParams:
    """Fit home advantage and the draw parameter by maximum likelihood."""
    deltas_array = np.asarray(deltas, dtype=float)
    if isinstance(outcomes, np.ndarray) and outcomes.dtype.kind in "iu":
        codes = outcomes.astype(int)
    else:
        codes = np.array([OUTCOME_CODES[str(o).upper()] for o in outcomes], dtype=int)

    if len(deltas_array) != len(codes):
        raise ValueError("deltas and outcomes must have the same length")
    if len(deltas_array) == 0:
        raise ValueError("at least one match is required to fit the model")

    def objective(theta: np.ndarray) -> float:
        return _negative_log_likelihood(theta, deltas_array, codes)

    bounds = [(-300.0, 400.0), (1e-4, 5.0)]
    best = None
    for start in ((60.0, 0.9), (0.0, 0.5), (120.0, 1.4)):
        result = minimize(
            objective,
            x0=np.array(start),
            method="L-BFGS-B",
            bounds=bounds,
        )
        if best is None or result.fun < best.fun:
            best = result
    assert best is not None
    return DavidsonParams(
        home_advantage=float(best.x[0]),
        nu=float(best.x[1]),
        elo_scale=elo_scale,
    )
