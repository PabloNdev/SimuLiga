"""Historical Elo reconstruction and model validation metrics."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from app.domain.elo import update_ratings


@dataclass(frozen=True)
class HistoryMatch:
    season: int
    date: str
    home: str
    away: str
    home_goals: int
    away_goals: int

    @property
    def outcome(self) -> str:
        if self.home_goals > self.away_goals:
            return "H"
        if self.home_goals < self.away_goals:
            return "A"
        return "D"


@dataclass
class EloHistory:
    samples: list[tuple[float, str, int]]
    season_starts: dict[int, dict[str, float]]
    season_ends: dict[int, dict[str, float]]
    timeline: list[dict] = field(default_factory=list)


def compute_elo_history(
    matches: list[HistoryMatch],
    *,
    start_rating: float = 1500.0,
    home_advantage: float = 60.0,
    k: float = 20.0,
    collect_timeline: bool = False,
) -> EloHistory:
    by_season: dict[int, list[HistoryMatch]] = defaultdict(list)
    for match in matches:
        by_season[match.season].append(match)

    ratings: dict[str, float] = {}
    samples: list[tuple[float, str, int]] = []
    season_starts: dict[int, dict[str, float]] = {}
    season_ends: dict[int, dict[str, float]] = {}
    timeline: list[dict] = []

    for season in sorted(by_season):
        season_starts[season] = dict(ratings)
        ordered = sorted(
            by_season[season],
            key=lambda match: (match.date, match.home, match.away),
        )
        if collect_timeline and ordered:
            start_snapshot = dict(ratings)
            for team in {match.home for match in ordered} | {
                match.away for match in ordered
            }:
                start_snapshot.setdefault(team, start_rating)
            timeline.append(
                {
                    "date": ordered[0].date,
                    "season": season,
                    "month": "start",
                    "ratings": {
                        team: round(elo, 2)
                        for team, elo in sorted(start_snapshot.items())
                    },
                }
            )

        current_month = ordered[0].date[:7] if ordered else ""
        last_date = ordered[0].date if ordered else ""

        for match in ordered:
            if collect_timeline and match.date[:7] != current_month:
                timeline.append(
                    {
                        "date": last_date,
                        "season": season,
                        "month": current_month,
                        "ratings": {
                            team: round(elo, 2)
                            for team, elo in sorted(ratings.items())
                        },
                    }
                )
                current_month = match.date[:7]

            home_rating = ratings.get(match.home, start_rating)
            away_rating = ratings.get(match.away, start_rating)
            samples.append((home_rating - away_rating, match.outcome, season))
            home_after, away_after = update_ratings(
                home_rating,
                away_rating,
                match.home_goals,
                match.away_goals,
                k=k,
                home_advantage=home_advantage,
            )
            ratings[match.home] = home_after
            ratings[match.away] = away_after
            last_date = match.date

        if collect_timeline and ordered:
            timeline.append(
                {
                    "date": last_date,
                    "season": season,
                    "month": current_month,
                    "ratings": {
                        team: round(elo, 2) for team, elo in sorted(ratings.items())
                    },
                }
            )
        season_ends[season] = dict(ratings)

    return EloHistory(
        samples=samples,
        season_starts=season_starts,
        season_ends=season_ends,
        timeline=timeline,
    )


def evaluate_predictions(
    probabilities: list[tuple[float, float, float]],
    outcomes: list[str],
) -> dict[str, float]:
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have the same length")
    if not probabilities:
        return {"matches": 0, "accuracy": 0.0, "log_loss": 0.0, "brier": 0.0}

    index = {"H": 0, "D": 1, "A": 2}
    correct = 0
    log_loss = 0.0
    brier = 0.0
    for probability, outcome in zip(probabilities, outcomes):
        target = index[outcome]
        predicted = max(range(3), key=lambda position: probability[position])
        correct += int(predicted == target)
        chosen = max(probability[target], 1e-12)
        log_loss -= math.log(chosen)
        brier += sum(
            (probability[position] - (1.0 if position == target else 0.0)) ** 2
            for position in range(3)
        )

    count = len(probabilities)
    return {
        "matches": count,
        "accuracy": correct / count,
        "log_loss": log_loss / count,
        "brier": brier / count,
    }
