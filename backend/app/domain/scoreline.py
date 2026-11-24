"""Poisson / Dixon-Coles model for exact scorelines."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from app.domain.davidson import MatchProbabilities


@dataclass(frozen=True)
class ScorelineParams:
    home_base: float = 1.45
    away_base: float = 1.15
    elo_slope: float = 0.0018
    home_advantage: float = 60.0
    rho: float = -0.05
    max_goals: int = 10


def expected_goals_from_delta(
    delta_elo: float, params: ScorelineParams
) -> tuple[float, float]:
    """Expected goals for each side from the Elo difference and home advantage."""
    gap = delta_elo + params.home_advantage
    home_lambda = params.home_base * math.exp(params.elo_slope * gap)
    away_lambda = params.away_base * math.exp(-params.elo_slope * gap)
    clamp = lambda value: min(6.0, max(0.05, value))
    return clamp(home_lambda), clamp(away_lambda)


def expected_goals(
    home_elo: float, away_elo: float, params: ScorelineParams
) -> tuple[float, float]:
    """Expected goals for each side from the Elo gap and home advantage."""
    return expected_goals_from_delta(home_elo - away_elo, params)


def _tau(home_goals: int, away_goals: int, lh: float, la: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1.0 - lh * la * rho
    if home_goals == 1 and away_goals == 0:
        return 1.0 + la * rho
    if home_goals == 0 and away_goals == 1:
        return 1.0 + lh * rho
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(lh: float, la: float, params: ScorelineParams) -> np.ndarray:
    """Normalized probability matrix indexed by [home_goals, away_goals]."""
    size = params.max_goals + 1
    home_pmf = poisson.pmf(np.arange(size), max(lh, 1e-6))
    away_pmf = poisson.pmf(np.arange(size), max(la, 1e-6))
    matrix = np.outer(home_pmf, away_pmf)
    for home_goals in range(min(2, size)):
        for away_goals in range(min(2, size)):
            matrix[home_goals, away_goals] *= _tau(
                home_goals, away_goals, lh, la, params.rho
            )
    matrix = np.clip(matrix, 0.0, None)
    total = matrix.sum()
    if total <= 0:
        raise ValueError("score matrix has no probability mass")
    return matrix / total


def outcome_probabilities(
    lh: float, la: float, params: ScorelineParams, *, matrix: np.ndarray | None = None
) -> MatchProbabilities:
    if matrix is None:
        matrix = score_matrix(lh, la, params)
    home = float(np.tril(matrix, -1).sum())
    draw = float(np.trace(matrix))
    away = float(np.triu(matrix, 1).sum())
    return MatchProbabilities(home=home, draw=draw, away=away)


def most_likely_score(
    lh: float,
    la: float,
    params: ScorelineParams,
    *,
    matrix: np.ndarray | None = None,
) -> tuple[int, int, float]:
    if matrix is None:
        matrix = score_matrix(lh, la, params)
    flat_index = int(np.argmax(matrix))
    size = params.max_goals + 1
    home_goals, away_goals = divmod(flat_index, size)
    return home_goals, away_goals, float(matrix[home_goals, away_goals])


@dataclass(frozen=True)
class PreparedScoreline:
    home_lambda: float
    away_lambda: float
    matrix: np.ndarray
    cdf: np.ndarray
    probabilities: MatchProbabilities
    most_likely: tuple[int, int, float]


def prepare_scoreline(
    lh: float, la: float, params: ScorelineParams
) -> PreparedScoreline:
    matrix = score_matrix(lh, la, params)
    cdf = np.cumsum(matrix.ravel())
    cdf[-1] = 1.0
    return PreparedScoreline(
        home_lambda=lh,
        away_lambda=la,
        matrix=matrix,
        cdf=cdf,
        probabilities=outcome_probabilities(lh, la, params, matrix=matrix),
        most_likely=most_likely_score(lh, la, params, matrix=matrix),
    )


def _scoreline_nll(
    theta: np.ndarray,
    deltas: list[float],
    home_goals: list[int],
    away_goals: list[int],
    home_advantage: float,
    max_goals: int,
) -> float:
    params = ScorelineParams(
        home_base=float(theta[0]),
        away_base=float(theta[1]),
        elo_slope=float(theta[2]),
        home_advantage=home_advantage,
        rho=float(theta[3]),
        max_goals=max_goals,
    )
    total = 0.0
    for delta, home, away in zip(deltas, home_goals, away_goals):
        home_lambda, away_lambda = expected_goals_from_delta(delta, params)
        matrix = score_matrix(home_lambda, away_lambda, params)
        probability = matrix[min(home, max_goals), min(away, max_goals)]
        total -= math.log(max(float(probability), 1e-12))
    return total


def fit_scoreline(
    deltas: Sequence[float],
    home_goals: Sequence[int],
    away_goals: Sequence[int],
    *,
    home_advantage: float = 60.0,
    max_goals: int = 10,
) -> ScorelineParams:
    """Fit home/away scoring rates, Elo slope and Dixon-Coles rho by MLE."""
    deltas_list = [float(delta) for delta in deltas]
    home_list = [int(goals) for goals in home_goals]
    away_list = [int(goals) for goals in away_goals]
    if not deltas_list:
        raise ValueError("at least one match is required to fit the scoreline")
    if not (len(deltas_list) == len(home_list) == len(away_list)):
        raise ValueError("deltas and goals must have the same length")

    bounds = [
        (0.3, 3.5),
        (0.3, 3.5),
        (0.0001, 0.008),
        (-0.15, 0.15),
    ]
    starts = (
        (1.45, 1.15, 0.0018, -0.05),
        (1.8, 1.4, 0.0015, 0.0),
    )
    best = None
    for start in starts:
        result = minimize(
            _scoreline_nll,
            np.array(start, dtype=float),
            args=(
                deltas_list,
                home_list,
                away_list,
                float(home_advantage),
                int(max_goals),
            ),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 500, "ftol": 1e-9, "gtol": 1e-7},
        )
        if best is None or result.fun < best.fun:
            best = result
    assert best is not None
    if not np.isfinite(best.fun):
        raise ValueError("scoreline calibration did not converge")
    return ScorelineParams(
        home_base=float(best.x[0]),
        away_base=float(best.x[1]),
        elo_slope=float(best.x[2]),
        home_advantage=float(home_advantage),
        rho=float(best.x[3]),
        max_goals=int(max_goals),
    )


def _sample_from_cdf(
    cdf: np.ndarray,
    size: int,
    rng: np.random.Generator,
    params: ScorelineParams,
) -> tuple[np.ndarray, np.ndarray]:
    draws = rng.random(size)
    flat_indices = np.searchsorted(cdf, draws, side="right")
    flat_indices = np.clip(flat_indices, 0, cdf.size - 1)
    width = params.max_goals + 1
    home_goals = (flat_indices // width).astype(np.int16)
    away_goals = (flat_indices % width).astype(np.int16)
    return home_goals, away_goals


def sample_scores_batch(
    lh: float,
    la: float,
    size: int,
    rng: np.random.Generator,
    params: ScorelineParams,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw scorelines from the Dixon-Coles adjusted distribution."""
    return _sample_from_cdf(
        prepare_scoreline(lh, la, params).cdf, size, rng, params
    )


def sample_scores_for_outcome(
    lh: float,
    la: float,
    outcome: str,
    size: int,
    rng: np.random.Generator,
    params: ScorelineParams,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw scorelines conditioned on a fixed home/draw/away result."""
    return sample_prepared_scores(
        prepare_scoreline(lh, la, params), outcome, size, rng, params
    )


def sample_prepared_scores(
    prepared: PreparedScoreline,
    outcome: str | None,
    size: int,
    rng: np.random.Generator,
    params: ScorelineParams,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw scorelines from an already prepared match distribution."""
    if outcome is None:
        return _sample_from_cdf(prepared.cdf, size, rng, params)

    matrix = prepared.matrix
    rows = np.arange(matrix.shape[0])[:, None]
    cols = np.arange(matrix.shape[1])[None, :]
    if outcome == "H":
        mask = rows > cols
    elif outcome == "D":
        mask = rows == cols
    elif outcome == "A":
        mask = rows < cols
    else:
        raise ValueError(f"unknown outcome: {outcome}")

    conditioned = matrix * mask
    total = conditioned.sum()
    if total <= 0:
        raise ValueError("the requested outcome has no probability mass")
    cdf = np.cumsum((conditioned / total).ravel())
    cdf[-1] = 1.0
    return _sample_from_cdf(cdf, size, rng, params)
