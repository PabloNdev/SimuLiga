"""Backtest helpers for the five-season Champions Elo."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable

from scipy.stats import spearmanr

from app.champions.data.snapshot import (
    HistoryReplayResult,
    _side_country,
    make_team,
    replay_history,
    resolve_teams,
)
from app.data.history import evaluate_predictions
from app.domain.davidson import (
    DavidsonParams,
    outcome_probabilities,
    probabilities_from_ratings,
)
from app.domain.elo import DEFAULT_HOME_ADVANTAGE


@dataclass(frozen=True)
class RatingEvaluation:
    matches: int
    accuracy: float
    log_loss: float
    brier: float


def season_groups(
    matches: Iterable[dict], labels: list[str]
) -> list[tuple[str, list[dict]]]:
    by_season: dict[str, list[dict]] = {}
    for raw in matches:
        by_season.setdefault(str(raw.get("season") or ""), []).append(raw)
    return [(label, by_season.get(label, [])) for label in labels]


def replay_for_window(
    matches: list[dict],
    labels: list[str],
    *,
    regression: float,
    k: float,
) -> HistoryReplayResult:
    teams = resolve_teams(matches)
    seeded = {
        team_id: team.with_elo(1500.0)
        for team_id, team in teams.items()
    }
    return replay_history(
        season_groups(matches, labels),
        seeded.values(),
        {"k": k, "home_advantage": DEFAULT_HOME_ADVANTAGE},
        regression=regression,
    )


def ratings_for_window(
    matches: list[dict],
    labels: list[str],
    *,
    regression: float,
    k: float,
) -> dict[str, float]:
    return replay_for_window(
        matches, labels, regression=regression, k=k
    ).ratings


def evaluate_ratings(
    matches: Iterable[dict],
    ratings: dict[str, float],
    params: DavidsonParams,
) -> RatingEvaluation:
    probabilities: list[tuple[float, float, float]] = []
    outcomes: list[str] = []
    for raw in sorted(
        matches,
        key=lambda item: (
            item.get("kickoff") or "",
            item.get("sequence") or 0,
        ),
    ):
        if raw.get("home_goals") is None or raw.get("away_goals") is None:
            continue
        home_id = make_team(
            raw["home"], country=_side_country(raw, "home")
        ).id
        away_id = make_team(
            raw["away"], country=_side_country(raw, "away")
        ).id
        home_elo = ratings.get(home_id, 1500.0)
        away_elo = ratings.get(away_id, 1500.0)
        if raw.get("neutral"):
            probability = outcome_probabilities(
                home_elo - away_elo,
                replace(params, home_advantage=0.0),
            )
        else:
            probability = probabilities_from_ratings(
                home_elo, away_elo, params
            )
        probabilities.append(probability.as_tuple())
        home_goals = int(raw["home_goals"])
        away_goals = int(raw["away_goals"])
        outcomes.append(
            "H"
            if home_goals > away_goals
            else "A"
            if home_goals < away_goals
            else "D"
        )
    metrics = evaluate_predictions(probabilities, outcomes)
    return RatingEvaluation(**metrics)


def points_by_team(matches: Iterable[dict]) -> dict[str, float]:
    points: dict[str, float] = {}
    for raw in matches:
        if raw.get("phase") != "league":
            continue
        if raw.get("home_goals") is None or raw.get("away_goals") is None:
            continue
        home_id = make_team(
            raw["home"], country=_side_country(raw, "home")
        ).id
        away_id = make_team(
            raw["away"], country=_side_country(raw, "away")
        ).id
        points.setdefault(home_id, 0.0)
        points.setdefault(away_id, 0.0)
        home_goals = int(raw["home_goals"])
        away_goals = int(raw["away_goals"])
        if home_goals > away_goals:
            points[home_id] += 3
        elif home_goals < away_goals:
            points[away_id] += 3
        else:
            points[home_id] += 1
            points[away_id] += 1
    return points


def spearman_correlation(
    ratings: dict[str, float], points: dict[str, float]
) -> float:
    common = sorted(set(ratings) & set(points))
    if len(common) < 2:
        return 0.0
    result = spearmanr(
        [ratings[team_id] for team_id in common],
        [points[team_id] for team_id in common],
    )
    value = float(result.statistic)
    return 0.0 if math.isnan(value) else value


def top_overlap(
    ratings: dict[str, float], points: dict[str, float], size: int = 8
) -> int:
    common = set(ratings) & set(points)
    top_ratings = set(
        sorted(
            common,
            key=lambda team_id: (ratings[team_id], team_id),
            reverse=True,
        )[:size]
    )
    top_points = set(
        sorted(
            common,
            key=lambda team_id: (points[team_id], team_id),
            reverse=True,
        )[:size]
    )
    return len(top_ratings & top_points)
