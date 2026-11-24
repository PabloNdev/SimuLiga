"""Monte Carlo simulation for the Champions League league phase and playoff."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Literal

import numpy as np

from app.champions.domain.playoff import simulate_playoff
from app.champions.domain.standings import build_records, qualification_cuts
from app.champions.models import ChampionsMatch, ChampionsTeam
from app.domain.davidson import (
    DavidsonParams,
    MatchProbabilities,
    probabilities_from_ratings,
)
from app.domain.scoreline import (
    PreparedScoreline,
    ScorelineParams,
    expected_goals,
    prepare_scoreline,
    sample_prepared_scores,
)

Mode = Literal["score", "1x2"]


@dataclass(frozen=True)
class ChampionsMatchPrediction:
    match_id: str
    matchday: int
    home_id: str
    away_id: str
    home_probability: float
    draw_probability: float
    away_probability: float
    most_likely_score: tuple[int, int] | None = None
    most_likely_score_probability: float | None = None


@dataclass
class ChampionsTeamProjection:
    team: ChampionsTeam
    expected_points: float
    points_std: float
    median_points: int
    p10_points: int
    p90_points: int
    expected_position: float
    most_likely_position: int
    top8_probability: float
    playoff_probability: float
    eliminated_probability: float
    playoff_win_probability: float
    round_of_16_probability: float
    position_probabilities: list[float]
    opponent_probabilities: dict[str, float]
    points_histogram: list[float]


@dataclass
class ChampionsPlayoffSummary:
    bracket: list[dict]
    advance_probabilities: dict[str, float]
    opponent_probabilities: dict[str, dict[str, float]]
    matchups: list[dict]


@dataclass
class ChampionsSimulationResult:
    mode: Mode
    n_sims: int
    seed: int | None
    teams: list[ChampionsTeamProjection]
    team_map: dict[str, ChampionsTeamProjection]
    match_predictions: list[ChampionsMatchPrediction]
    playoff: ChampionsPlayoffSummary
    elapsed_seconds: float
    goals_available: bool


@dataclass
class ChampionsSimulationRequest:
    teams: list[ChampionsTeam]
    matches: list[ChampionsMatch]
    mode: Mode = "score"
    n_sims: int = 10_000
    seed: int | None = None
    davidson: DavidsonParams = field(default_factory=DavidsonParams)
    scoreline: ScorelineParams = field(default_factory=ScorelineParams)
    chunk_size: int = 5_000
    progress_callback: Callable[[int, int], None] | None = None


def simulate_champions(request: ChampionsSimulationRequest) -> ChampionsSimulationResult:
    started = time.perf_counter()
    _validate(request)

    teams = request.teams
    team_ids = [team.id for team in teams]
    team_index = {team_id: index for index, team_id in enumerate(team_ids)}
    team_count = len(teams)
    team_map = {team.id: team for team in teams}

    league_matches = [match for match in request.matches if match.phase == "league"]
    played_matches = [match for match in league_matches if match.is_played]
    pending_matches = [match for match in league_matches if not match.is_played]

    records = build_records(team_ids, played_matches)
    base_points = np.array([records[team_id].points for team_id in team_ids], dtype=np.int32)
    base_goals_for = np.array(
        [records[team_id].goals_for for team_id in team_ids], dtype=np.int32
    )
    base_goals_against = np.array(
        [records[team_id].goals_against for team_id in team_ids], dtype=np.int32
    )
    base_away_goals = np.array(
        [records[team_id].away_goals for team_id in team_ids], dtype=np.int32
    )
    base_wins = np.array([records[team_id].won for team_id in team_ids], dtype=np.int32)
    base_away_wins = np.array(
        [records[team_id].away_wins for team_id in team_ids], dtype=np.int32
    )

    max_matches_per_team = max(
        (
            sum(
                1
                for match in league_matches
                if match.home_id == team_id or match.away_id == team_id
            )
            for team_id in team_ids
        ),
        default=0,
    )
    histogram_size = (
        int(base_points.max(initial=0)) + 3 * max_matches_per_team + 1
    )

    predictions, models = _predict_matches(pending_matches, team_map, request)

    direct_cutoff, playoff_cutoff = qualification_cuts(team_count)

    position_histogram = np.zeros((team_count, team_count), dtype=np.int64)
    points_histogram = np.zeros((team_count, histogram_size), dtype=np.int64)
    points_sum = np.zeros(team_count, dtype=np.float64)
    points_squared_sum = np.zeros(team_count, dtype=np.float64)

    advance_counts = {team_id: 0 for team_id in team_ids}
    opponent_counts = {team_id: {other: 0 for other in team_ids} for team_id in team_ids}
    pair_counts: dict[tuple[str, str], int] = {}
    slot_counts: dict[int, dict[str, int]] = {
        position: {team_id: 0 for team_id in team_ids}
        for position in range(direct_cutoff + 1, playoff_cutoff + 1)
    }

    rng = np.random.default_rng(request.seed)
    chunk_size = max(1, min(request.chunk_size, request.n_sims))
    pending_count = len(pending_matches)

    for chunk_start in range(0, request.n_sims, chunk_size):
        size = min(chunk_size, request.n_sims - chunk_start)
        points = np.tile(base_points, (size, 1)).astype(np.int32)
        goals_for = np.tile(base_goals_for, (size, 1)).astype(np.int32)
        goals_against = np.tile(base_goals_against, (size, 1)).astype(np.int32)
        away_goals = np.tile(base_away_goals, (size, 1)).astype(np.int32)
        wins = np.tile(base_wins, (size, 1)).astype(np.int32)
        away_wins = np.tile(base_away_wins, (size, 1)).astype(np.int32)

        for match_index, match in enumerate(pending_matches):
            home_slot = team_index[match.home_id]
            away_slot = team_index[match.away_id]
            if request.mode == "score":
                prepared = models[match_index]
                assert isinstance(prepared, PreparedScoreline)
                home_score, away_score = sample_prepared_scores(
                    prepared, None, size, rng, request.scoreline
                )
                home_wins = home_score > away_score
                draws_mask = home_score == away_score
                away_win_mask = home_score < away_score
                points[:, home_slot] += 3 * home_wins + draws_mask
                points[:, away_slot] += 3 * away_win_mask + draws_mask
                goals_for[:, home_slot] += home_score
                goals_against[:, home_slot] += away_score
                goals_for[:, away_slot] += away_score
                goals_against[:, away_slot] += home_score
                away_goals[:, away_slot] += away_score
                wins[:, home_slot] += home_wins
                wins[:, away_slot] += away_win_mask
                away_wins[:, away_slot] += away_win_mask
            else:
                probabilities = models[match_index]
                assert isinstance(probabilities, MatchProbabilities)
                draws = rng.random(size)
                outcome = np.where(
                    draws < probabilities.home,
                    0,
                    np.where(draws < probabilities.home + probabilities.draw, 1, 2),
                ).astype(np.int8)
                home_wins = outcome == 0
                draws_mask = outcome == 1
                away_win_mask = outcome == 2
                points[:, home_slot] += 3 * home_wins + draws_mask
                points[:, away_slot] += 3 * away_win_mask + draws_mask
                wins[:, home_slot] += home_wins
                wins[:, away_slot] += away_win_mask
                away_wins[:, away_slot] += away_win_mask

        random_keys = rng.random((size, team_count))
        goal_difference = goals_for - goals_against
        order = np.lexsort(
            (
                np.tile(np.arange(team_count), (size, 1)),
                -random_keys,
                -away_wins,
                -wins,
                -away_goals,
                -goals_for,
                -goal_difference,
                -points,
            ),
            axis=1,
        )
        positions = np.empty((size, team_count), dtype=np.int16)
        positions[np.arange(size)[:, None], order] = np.arange(1, team_count + 1)

        points_sum += points.sum(axis=0, dtype=np.float64)
        points_squared_sum += np.square(points, dtype=np.float64).sum(axis=0)
        for slot in range(team_count):
            position_histogram[slot] += np.bincount(
                positions[:, slot] - 1, minlength=team_count
            )[:team_count]
            points_histogram[slot] += np.bincount(
                points[:, slot], minlength=histogram_size
            )[:histogram_size]

        positions_by_sim = [
            {team_ids[slot]: int(positions[simulation, slot]) for slot in range(team_count)}
            for simulation in range(size)
        ]
        playoff = simulate_playoff(
            positions_by_sim, team_map, request.scoreline, rng
        )
        for team_id in team_ids:
            advance_counts[team_id] += playoff["advance_counts"][team_id]
            for opponent_id, count in playoff["opponent_counts"][team_id].items():
                opponent_counts[team_id][opponent_id] += count
        for pair, count in playoff["pair_counts"].items():
            pair_counts[pair] = pair_counts.get(pair, 0) + count
        for position, counts in playoff["slot_counts"].items():
            if position not in slot_counts:
                slot_counts[position] = {team_id: 0 for team_id in team_ids}
            for team_id, count in counts.items():
                slot_counts[position][team_id] += count

        if request.progress_callback is not None:
            request.progress_callback(chunk_start + size, request.n_sims)

    position_probabilities = position_histogram / request.n_sims
    point_distributions = points_histogram / request.n_sims
    expected_points = points_sum / request.n_sims
    variance = np.maximum(
        points_squared_sum / request.n_sims - expected_points ** 2, 0.0
    )
    points_std = np.sqrt(variance)

    projections: list[ChampionsTeamProjection] = []
    for slot, team in enumerate(teams):
        distribution = position_probabilities[slot]
        top8 = float(distribution[:direct_cutoff].sum())
        playoff_probability = float(
            distribution[direct_cutoff:playoff_cutoff].sum()
        )
        eliminated = float(distribution[playoff_cutoff:].sum())
        playoff_appearances = int(
            position_histogram[slot, direct_cutoff:playoff_cutoff].sum()
        )
        opponents: dict[str, float] = {}
        if playoff_appearances:
            opponents = {
                opponent_id: count / playoff_appearances
                for opponent_id, count in opponent_counts[team.id].items()
                if count
            }
        playoff_win = advance_counts[team.id] / request.n_sims
        projections.append(
            ChampionsTeamProjection(
                team=team,
                expected_points=float(expected_points[slot]),
                points_std=float(points_std[slot]),
                median_points=_percentile(
                    points_histogram[slot], 0.50, request.n_sims
                ),
                p10_points=_percentile(points_histogram[slot], 0.10, request.n_sims),
                p90_points=_percentile(points_histogram[slot], 0.90, request.n_sims),
                expected_position=float(
                    sum(
                        (position + 1) * probability
                        for position, probability in enumerate(distribution)
                    )
                ),
                most_likely_position=int(np.argmax(distribution)) + 1,
                top8_probability=top8,
                playoff_probability=playoff_probability,
                eliminated_probability=eliminated,
                playoff_win_probability=playoff_win,
                round_of_16_probability=top8 + playoff_win,
                position_probabilities=[float(value) for value in distribution],
                opponent_probabilities=opponents,
                points_histogram=[
                    float(value) for value in point_distributions[slot]
                ],
            )
        )

    projections.sort(
        key=lambda projection: (projection.expected_position, projection.team.name)
    )
    projection_map = {
        projection.team.id: projection for projection in projections
    }

    bracket = _build_bracket(slot_counts, direct_cutoff, playoff_cutoff)
    matchups = [
        {
            "better_id": better_id,
            "worse_id": worse_id,
            "probability": count / request.n_sims,
        }
        for (better_id, worse_id), count in sorted(
            pair_counts.items(), key=lambda item: item[1], reverse=True
        )[:20]
    ]
    playoff_summary = ChampionsPlayoffSummary(
        bracket=bracket,
        advance_probabilities={
            team_id: count / request.n_sims
            for team_id, count in advance_counts.items()
        },
        opponent_probabilities={
            team_id: {
                opponent_id: count / max(1, sum(values.values()))
                for opponent_id, count in values.items()
                if count
            }
            for team_id, values in opponent_counts.items()
        },
        matchups=matchups,
    )

    return ChampionsSimulationResult(
        mode=request.mode,
        n_sims=request.n_sims,
        seed=request.seed,
        teams=projections,
        team_map=projection_map,
        match_predictions=predictions,
        playoff=playoff_summary,
        elapsed_seconds=time.perf_counter() - started,
        goals_available=request.mode == "score",
    )


def _predict_matches(
    pending_matches: list[ChampionsMatch],
    team_map: dict[str, ChampionsTeam],
    request: ChampionsSimulationRequest,
) -> tuple[list[ChampionsMatchPrediction], list[MatchProbabilities | PreparedScoreline]]:
    predictions: list[ChampionsMatchPrediction] = []
    models: list[MatchProbabilities | PreparedScoreline] = []
    for match in pending_matches:
        home = team_map[match.home_id]
        away = team_map[match.away_id]
        if request.mode == "score":
            home_lambda, away_lambda = expected_goals(
                home.elo, away.elo, request.scoreline
            )
            prepared = prepare_scoreline(home_lambda, away_lambda, request.scoreline)
            probabilities = prepared.probabilities
            score = (prepared.most_likely[0], prepared.most_likely[1])
            score_probability = prepared.most_likely[2]
            models.append(prepared)
        else:
            probabilities = probabilities_from_ratings(
                home.elo, away.elo, request.davidson
            )
            score, score_probability = None, None
            models.append(probabilities)
        predictions.append(
            ChampionsMatchPrediction(
                match_id=match.id,
                matchday=match.matchday,
                home_id=match.home_id,
                away_id=match.away_id,
                home_probability=probabilities.home,
                draw_probability=probabilities.draw,
                away_probability=probabilities.away,
                most_likely_score=score,
                most_likely_score_probability=score_probability,
            )
        )
    predictions.sort(key=lambda prediction: (prediction.matchday, prediction.match_id))
    return predictions, models


def _build_bracket(
    slot_counts: dict[int, dict[str, int]],
    direct_cutoff: int,
    playoff_cutoff: int,
) -> list[dict]:
    slots = list(range(direct_cutoff + 1, playoff_cutoff + 1))
    bracket: list[dict] = []
    for index in range(len(slots) // 2):
        better_slot = slots[index]
        worse_slot = slots[-1 - index]
        better_counts = slot_counts.get(better_slot, {})
        worse_counts = slot_counts.get(worse_slot, {})
        better_team = max(better_counts, key=better_counts.get) if better_counts else None
        worse_team = max(worse_counts, key=worse_counts.get) if worse_counts else None
        better_total = sum(better_counts.values()) or 1
        worse_total = sum(worse_counts.values()) or 1
        bracket.append(
            {
                "better_slot": better_slot,
                "worse_slot": worse_slot,
                "better_team_id": better_team,
                "better_probability": (
                    better_counts.get(better_team, 0) / better_total
                    if better_team
                    else 0.0
                ),
                "worse_team_id": worse_team,
                "worse_probability": (
                    worse_counts.get(worse_team, 0) / worse_total
                    if worse_team
                    else 0.0
                ),
            }
        )
    return bracket


def _validate(request: ChampionsSimulationRequest) -> None:
    if request.n_sims <= 0:
        raise ValueError("n_sims must be positive")
    if request.mode not in ("score", "1x2"):
        raise ValueError(f"unknown mode: {request.mode}")
    if not request.teams:
        raise ValueError("at least one team is required")
    team_ids = {team.id for team in request.teams}
    if len(team_ids) != len(request.teams):
        raise ValueError("team ids must be unique")
    for match in request.matches:
        if match.home_id not in team_ids or match.away_id not in team_ids:
            raise ValueError(f"match {match.id} references an unknown team")
        if match.home_id == match.away_id:
            raise ValueError(f"match {match.id} has the same team on both sides")


def _percentile(histogram: np.ndarray, quantile: float, n_sims: int) -> int:
    cumulative = np.cumsum(histogram)
    target = quantile * n_sims
    index = int(np.searchsorted(cumulative, target, side="left"))
    return min(index, len(histogram) - 1)
