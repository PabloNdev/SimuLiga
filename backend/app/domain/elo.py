"""Elo ratings with a World Football Elo style goal-margin multiplier."""

from __future__ import annotations

DEFAULT_K = 20.0
DEFAULT_HOME_ADVANTAGE = 60.0
PROMOTED_START_RATING = 1370.0


def expected_score(rating_a: float, rating_b: float, home_advantage: float = 0.0) -> float:
    """Probability that side A beats side B, given the rating gap."""
    return 1.0 / (1.0 + 10.0 ** (-((rating_a + home_advantage) - rating_b) / 400.0))


def goal_margin_multiplier(home_goals: int, away_goals: int) -> float:
    """World Football Elo index: larger wins move ratings further."""
    margin = abs(home_goals - away_goals)
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return (11.0 + margin) / 8.0


def update_ratings(
    home_rating: float,
    away_rating: float,
    home_goals: int,
    away_goals: int,
    *,
    k: float = DEFAULT_K,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
) -> tuple[float, float]:
    """Return the updated (home, away) ratings after a finished match."""
    expected_home = expected_score(home_rating, away_rating, home_advantage)
    if home_goals > away_goals:
        actual_home = 1.0
    elif home_goals < away_goals:
        actual_home = 0.0
    else:
        actual_home = 0.5

    change = k * goal_margin_multiplier(home_goals, away_goals) * (actual_home - expected_home)
    return home_rating + change, away_rating - change
