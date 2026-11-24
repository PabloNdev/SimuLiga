"""Monte Carlo season simulation with LaLiga tiebreak rules.

Two simulation modes are supported:

``score``
    Samples an exact scoreline for every pending match from the Dixon-Coles
    model, so goal difference and head-to-head goals can be used by the
    official LaLiga tiebreak rules.

``1x2``
    Samples only home win / draw / away win from the Davidson model. Goal
    based criteria cannot be evaluated without scorelines, so ties are
    resolved by head-to-head points and then the remaining criteria that are
    available (fair play, drawing lots).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Literal

import numpy as np

from app.domain.davidson import (
    OUTCOME_CODES,
    DavidsonParams,
    MatchProbabilities,
    probabilities_from_ratings,
)
from app.domain.models import Match, Outcome, Team
from app.domain.scoreline import (
    PreparedScoreline,
    ScorelineParams,
    expected_goals,
    prepare_scoreline,
    sample_prepared_scores,
)
from app.domain.standings import build_records

Mode = Literal["score", "1x2"]


@dataclass(frozen=True)
class MatchPrediction:
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
class TeamProjection:
    team: Team
    expected_points: float
    points_std: float
    median_points: int
    p10_points: int
    p90_points: int
    expected_position: float
    most_likely_position: int
    champion_probability: float
    top4_probability: float
    relegation_probability: float
    position_probabilities: list[float]
    points_histogram: list[float]


@dataclass
class SimulationResult:
    mode: Mode
    n_sims: int
    seed: int | None
    teams: list[TeamProjection]
    team_map: dict[str, TeamProjection]
    match_predictions: list[MatchPrediction]
    elapsed_seconds: float
    goals_available: bool
    start_matchday: int | None = None


@dataclass
class SimulationRequest:
    teams: list[Team]
    matches: list[Match]
    mode: Mode = "score"
    n_sims: int = 10_000
    seed: int | None = None
    davidson: DavidsonParams = field(default_factory=DavidsonParams)
    scoreline: ScorelineParams = field(default_factory=ScorelineParams)
    elo_delta: dict[str, float] = field(default_factory=dict)
    forced_results: dict[str, Outcome] = field(default_factory=dict)
    forced_scores: dict[str, tuple[int, int]] = field(default_factory=dict)
    fair_play: dict[str, int] = field(default_factory=dict)
    chunk_size: int = 5_000
    progress_callback: Callable[[int, int], None] | None = None
    start_matchday: int | None = None


def simulate_season(request: SimulationRequest) -> SimulationResult:
    started = time.perf_counter()
    _validate(request)

    teams = [
        team.with_elo(min(2600.0, max(800.0, team.elo + request.elo_delta.get(team.id, 0.0))))
        for team in request.teams
    ]
    team_ids = [team.id for team in teams]
    team_index = {team_id: index for index, team_id in enumerate(team_ids)}
    team_count = len(teams)

    if request.start_matchday is not None:
        effective_matches = [
            match.as_pending() if match.matchday >= request.start_matchday else match
            for match in request.matches
        ]
    else:
        effective_matches = list(request.matches)

    played_matches = [match for match in effective_matches if match.is_played]
    pending_matches = [match for match in effective_matches if not match.is_played]
    base_records = build_records(team_ids, played_matches, request.fair_play)
    goals_available = request.mode == "score" and all(
        match.has_score for match in played_matches
    )

    base_points = np.array([base_records[team_id].points for team_id in team_ids], dtype=np.int32)
    if goals_available:
        base_goals_for = np.array(
            [base_records[team_id].goals_for or 0 for team_id in team_ids], dtype=np.int32
        )
        base_goals_against = np.array(
            [base_records[team_id].goals_against or 0 for team_id in team_ids], dtype=np.int32
        )
    else:
        base_goals_for = np.zeros(team_count, dtype=np.int32)
        base_goals_against = np.zeros(team_count, dtype=np.int32)

    fair_play = np.array(
        [request.fair_play.get(team_id, 0) for team_id in team_ids], dtype=np.int32
    )

    all_matches = list(effective_matches)
    all_home_index = np.array(
        [team_index[match.home_id] for match in all_matches], dtype=np.int32
    )
    all_away_index = np.array(
        [team_index[match.away_id] for match in all_matches], dtype=np.int32
    )
    played_mask = np.array([match.is_played for match in all_matches], dtype=bool)
    base_home_goals = np.array(
        [match.home_goals if match.has_score else -1 for match in all_matches], dtype=np.int32
    )
    base_away_goals = np.array(
        [match.away_goals if match.has_score else -1 for match in all_matches], dtype=np.int32
    )
    base_outcome = np.array(
        [OUTCOME_CODES[match.result] if match.is_played else -1 for match in all_matches],
        dtype=np.int8,
    )

    pending_index = {match.id: index for index, match in enumerate(pending_matches)}
    pending_index_for_all = np.array(
        [
            pending_index.get(match.id, -1) if not match.is_played else -1
            for match in all_matches
        ],
        dtype=np.int32,
    )

    pair_indices: dict[tuple[int, int], list[int]] = {}
    for index in range(len(all_matches)):
        first = int(all_home_index[index])
        second = int(all_away_index[index])
        pair = (min(first, second), max(first, second))
        pair_indices.setdefault(pair, []).append(index)

    match_predictions, match_models = _predict_pending_matches(
        pending_matches, teams, team_index, request
    )

    max_matches_per_team = max(
        (sum(1 for m in all_matches if m.home_id == team_id or m.away_id == team_id)
         for team_id in team_ids),
        default=0,
    )
    histogram_size = max(
        int(base_points.max(initial=0)), 3 * max_matches_per_team
    ) + 1

    position_histogram = np.zeros((team_count, team_count), dtype=np.int64)
    points_histogram = np.zeros((team_count, histogram_size), dtype=np.int64)
    points_sum = np.zeros(team_count, dtype=np.float64)
    points_squared_sum = np.zeros(team_count, dtype=np.float64)

    rng = np.random.default_rng(request.seed)
    chunk_size = max(1, min(request.chunk_size, request.n_sims))
    pending_count = len(pending_matches)

    for chunk_start in range(0, request.n_sims, chunk_size):
        size = min(chunk_size, request.n_sims - chunk_start)
        points = np.tile(base_points, (size, 1)).astype(np.int32)
        if request.mode == "score":
            goals_for = np.tile(base_goals_for, (size, 1)).astype(np.int32)
            goals_against = np.tile(base_goals_against, (size, 1)).astype(np.int32)
            home_goals = np.empty((size, pending_count), dtype=np.int16)
            away_goals = np.empty((size, pending_count), dtype=np.int16)
            outcomes = None
        else:
            goals_for = np.zeros((size, team_count), dtype=np.int32)
            goals_against = np.zeros((size, team_count), dtype=np.int32)
            home_goals = None
            away_goals = None
            outcomes = np.empty((size, pending_count), dtype=np.int8)

        for match_index, match in enumerate(pending_matches):
            home_slot = team_index[match.home_id]
            away_slot = team_index[match.away_id]
            if request.mode == "1x2":
                forced = request.forced_results.get(match.id)
                if forced is not None:
                    outcome = np.full(size, OUTCOME_CODES[forced], dtype=np.int8)
                elif match.id in request.forced_scores:
                    home_score, away_score = request.forced_scores[match.id]
                    outcome = np.full(
                        size,
                        0 if home_score > away_score else 1 if home_score == away_score else 2,
                        dtype=np.int8,
                    )
                else:
                    probabilities = match_models[match_index]
                    draws = rng.random(size)
                    outcome = np.where(
                        draws < probabilities.home,
                        0,
                        np.where(draws < probabilities.home + probabilities.draw, 1, 2),
                    ).astype(np.int8)
                assert outcomes is not None
                outcomes[:, match_index] = outcome
                home_wins = outcome == 0
                draws_mask = outcome == 1
                away_wins = outcome == 2
                points[:, home_slot] += 3 * home_wins + draws_mask
                points[:, away_slot] += 3 * away_wins + draws_mask
            else:
                prepared = match_models[match_index]
                assert isinstance(prepared, PreparedScoreline)
                forced_score = request.forced_scores.get(match.id)
                forced_result = request.forced_results.get(match.id)
                if forced_score is not None:
                    home_score = np.full(size, forced_score[0], dtype=np.int16)
                    away_score = np.full(size, forced_score[1], dtype=np.int16)
                else:
                    home_score, away_score = sample_prepared_scores(
                        prepared, forced_result, size, rng, request.scoreline
                    )
                assert home_goals is not None and away_goals is not None
                home_goals[:, match_index] = home_score
                away_goals[:, match_index] = away_score
                home_wins = home_score > away_score
                draws_mask = home_score == away_score
                away_wins = home_score < away_score
                points[:, home_slot] += 3 * home_wins + draws_mask
                points[:, away_slot] += 3 * away_wins + draws_mask
                goals_for[:, home_slot] += home_score
                goals_against[:, home_slot] += away_score
                goals_for[:, away_slot] += away_score
                goals_against[:, away_slot] += home_score

        random_keys = rng.random((size, team_count))
        positions = _rank_chunk(
            points=points,
            goals_for=goals_for,
            goals_against=goals_against,
            home_goals=home_goals,
            away_goals=away_goals,
            outcomes=outcomes,
            random_keys=random_keys,
            fair_play=fair_play,
            mode=request.mode,
            goals_available=goals_available,
            team_count=team_count,
            all_home_index=all_home_index,
            all_away_index=all_away_index,
            played_mask=played_mask,
            base_home_goals=base_home_goals,
            base_away_goals=base_away_goals,
            base_outcome=base_outcome,
            pending_index_for_all=pending_index_for_all,
            pair_indices=pair_indices,
        )

        points_sum += points.sum(axis=0, dtype=np.float64)
        points_squared_sum += np.square(points, dtype=np.float64).sum(axis=0)
        for slot in range(team_count):
            position_histogram[slot] += np.bincount(
                positions[:, slot] - 1, minlength=team_count
            )[:team_count]
            points_histogram[slot] += np.bincount(
                points[:, slot], minlength=histogram_size
            )[:histogram_size]

        if request.progress_callback is not None:
            request.progress_callback(chunk_start + size, request.n_sims)

    position_probabilities = position_histogram / request.n_sims
    point_distributions = points_histogram / request.n_sims
    expected_points = points_sum / request.n_sims
    variance = np.maximum(points_squared_sum / request.n_sims - expected_points ** 2, 0.0)
    points_std = np.sqrt(variance)

    projections: list[TeamProjection] = []
    for slot, team in enumerate(teams):
        distribution = point_distributions[slot]
        counts = points_histogram[slot]
        positions_for_team = position_probabilities[slot]
        projections.append(
            TeamProjection(
                team=team,
                expected_points=float(expected_points[slot]),
                points_std=float(points_std[slot]),
                median_points=_percentile(counts, 0.50, request.n_sims),
                p10_points=_percentile(counts, 0.10, request.n_sims),
                p90_points=_percentile(counts, 0.90, request.n_sims),
                expected_position=float(
                    sum((position + 1) * probability for position, probability in enumerate(positions_for_team))
                ),
                most_likely_position=int(np.argmax(positions_for_team)) + 1,
                champion_probability=float(positions_for_team[0]),
                top4_probability=float(positions_for_team[: min(4, team_count)].sum()),
                relegation_probability=float(
                    positions_for_team[max(0, team_count - 3) :].sum()
                ),
                position_probabilities=[float(value) for value in positions_for_team],
                points_histogram=[float(value) for value in distribution],
            )
        )

    projections.sort(key=lambda projection: (projection.expected_position, projection.team.name))
    team_map = {projection.team.id: projection for projection in projections}

    return SimulationResult(
        mode=request.mode,
        n_sims=request.n_sims,
        seed=request.seed,
        teams=projections,
        team_map=team_map,
        match_predictions=match_predictions,
        elapsed_seconds=time.perf_counter() - started,
        goals_available=goals_available,
        start_matchday=request.start_matchday,
    )


def _validate(request: SimulationRequest) -> None:
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
    for score in request.forced_scores.values():
        if len(score) != 2 or score[0] < 0 or score[1] < 0:
            raise ValueError("forced scores must be non-negative pairs")
    if request.start_matchday is not None:
        matchdays = [match.matchday for match in request.matches] or [1]
        if request.start_matchday < 1 or request.start_matchday > max(matchdays):
            raise ValueError("start_matchday is outside the season")


def _predict_pending_matches(
    pending_matches: list[Match],
    teams: list[Team],
    team_index: dict[str, int],
    request: SimulationRequest,
) -> tuple[list[MatchPrediction], list[MatchProbabilities | PreparedScoreline]]:
    predictions: list[MatchPrediction] = []
    models: list[MatchProbabilities | PreparedScoreline] = []
    for match in pending_matches:
        home = teams[team_index[match.home_id]]
        away = teams[team_index[match.away_id]]
        if request.mode == "score":
            home_lambda, away_lambda = expected_goals(home.elo, away.elo, request.scoreline)
            prepared = prepare_scoreline(home_lambda, away_lambda, request.scoreline)
            probabilities = prepared.probabilities
            score = (prepared.most_likely[0], prepared.most_likely[1])
            score_probability = prepared.most_likely[2]
            models.append(prepared)
        else:
            probabilities = probabilities_from_ratings(home.elo, away.elo, request.davidson)
            score, score_probability = None, None
            models.append(probabilities)
        predictions.append(
            MatchPrediction(
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


def _rank_chunk(
    *,
    points: np.ndarray,
    goals_for: np.ndarray,
    goals_against: np.ndarray,
    home_goals: np.ndarray | None,
    away_goals: np.ndarray | None,
    outcomes: np.ndarray | None,
    random_keys: np.ndarray,
    fair_play: np.ndarray,
    mode: Mode,
    goals_available: bool,
    team_count: int,
    all_home_index: np.ndarray,
    all_away_index: np.ndarray,
    played_mask: np.ndarray,
    base_home_goals: np.ndarray,
    base_away_goals: np.ndarray,
    base_outcome: np.ndarray,
    pending_index_for_all: np.ndarray,
    pair_indices: dict[tuple[int, int], list[int]],
) -> np.ndarray:
    size = points.shape[0]
    sorted_indices = np.argsort(-points, axis=1, kind="stable")
    sorted_points = np.take_along_axis(points, sorted_indices, axis=1)
    positions = np.empty((size, team_count), dtype=np.int16)

    for simulation in range(size):
        order = sorted_indices[simulation]
        row_points = sorted_points[simulation]
        ranked: list[int] = []
        start = 0
        while start < team_count:
            end = start + 1
            while end < team_count and row_points[end] == row_points[start]:
                end += 1
            group = order[start:end].tolist()
            if len(group) == 1:
                ranked.append(group[0])
            else:
                ranked.extend(
                    _rank_group(
                        group,
                        simulation,
                        points,
                        goals_for,
                        goals_against,
                        home_goals,
                        away_goals,
                        outcomes,
                        random_keys,
                        fair_play,
                        mode,
                        goals_available,
                        all_home_index,
                        all_away_index,
                        played_mask,
                        base_home_goals,
                        base_away_goals,
                        base_outcome,
                        pending_index_for_all,
                        pair_indices,
                    )
                )
            start = end
        positions[simulation, np.asarray(ranked, dtype=np.int32)] = np.arange(
            1, team_count + 1
        )
    return positions


def _rank_group(
    group: list[int],
    simulation: int,
    points: np.ndarray,
    goals_for: np.ndarray,
    goals_against: np.ndarray,
    home_goals: np.ndarray | None,
    away_goals: np.ndarray | None,
    outcomes: np.ndarray | None,
    random_keys: np.ndarray,
    fair_play: np.ndarray,
    mode: Mode,
    goals_available: bool,
    all_home_index: np.ndarray,
    all_away_index: np.ndarray,
    played_mask: np.ndarray,
    base_home_goals: np.ndarray,
    base_away_goals: np.ndarray,
    base_outcome: np.ndarray,
    pending_index_for_all: np.ndarray,
    pair_indices: dict[tuple[int, int], list[int]],
) -> list[int]:
    if len(group) <= 1:
        return list(group)

    h2h_points = {team: 0 for team in group}
    h2h_goals_for = {team: 0 for team in group}
    h2h_goals_against = {team: 0 for team in group}
    h2h_goals_available = True

    for first_index in range(len(group)):
        for second_index in range(first_index + 1, len(group)):
            pair = tuple(sorted((group[first_index], group[second_index])))
            for match_index in pair_indices.get(pair, ()):
                home_slot = int(all_home_index[match_index])
                away_slot = int(all_away_index[match_index])
                if played_mask[match_index]:
                    outcome = int(base_outcome[match_index])
                    if outcome < 0:
                        continue
                    if base_home_goals[match_index] >= 0:
                        home_score = int(base_home_goals[match_index])
                        away_score = int(base_away_goals[match_index])
                    else:
                        home_score = away_score = None
                else:
                    pending = int(pending_index_for_all[match_index])
                    if mode == "1x2":
                        assert outcomes is not None
                        outcome = int(outcomes[simulation, pending])
                        home_score = away_score = None
                    else:
                        assert home_goals is not None and away_goals is not None
                        home_score = int(home_goals[simulation, pending])
                        away_score = int(away_goals[simulation, pending])
                        outcome = 0 if home_score > away_score else 1 if home_score == away_score else 2

                if outcome == 0:
                    h2h_points[home_slot] += 3
                elif outcome == 2:
                    h2h_points[away_slot] += 3
                else:
                    h2h_points[home_slot] += 1
                    h2h_points[away_slot] += 1

                if home_score is None or away_score is None:
                    h2h_goals_available = False
                else:
                    h2h_goals_for[home_slot] += home_score
                    h2h_goals_against[home_slot] += away_score
                    h2h_goals_for[away_slot] += away_score
                    h2h_goals_against[away_slot] += home_score

    if not h2h_goals_available:
        h2h_goals_for = {team: 0 for team in group}
        h2h_goals_against = {team: 0 for team in group}

    keys = {
        team: (
            h2h_points[team],
            h2h_goals_for[team] - h2h_goals_against[team],
            h2h_goals_for[team],
        )
        for team in group
    }
    ordered = sorted(group, key=lambda team: (keys[team], team), reverse=True)
    partitions: list[list[int]] = []
    for team in ordered:
        if partitions and keys[partitions[-1][0]] == keys[team]:
            partitions[-1].append(team)
        else:
            partitions.append([team])

    if len(partitions) > 1:
        ranked: list[int] = []
        for partition in partitions:
            if len(partition) == 1:
                ranked.extend(partition)
            else:
                ranked.extend(
                    _rank_group(
                        partition,
                        simulation,
                        points,
                        goals_for,
                        goals_against,
                        home_goals,
                        away_goals,
                        outcomes,
                        random_keys,
                        fair_play,
                        mode,
                        goals_available,
                        all_home_index,
                        all_away_index,
                        played_mask,
                        base_home_goals,
                        base_away_goals,
                        base_outcome,
                        pending_index_for_all,
                        pair_indices,
                    )
                )
        return ranked

    return sorted(
        group,
        key=lambda team: (lambda goals: (
            -goals[0],
            -goals[1],
            int(fair_play[team]),
            float(random_keys[simulation, team]),
            team,
        ))(
            (
                (int(goals_for[simulation, team]) - int(goals_against[simulation, team]),
                 int(goals_for[simulation, team]))
                if goals_available
                else (0, 0)
            )
        ),
    )


def _percentile(histogram: np.ndarray, quantile: float, n_sims: int) -> int:
    cumulative = np.cumsum(histogram)
    target = quantile * n_sims
    index = int(np.searchsorted(cumulative, target, side="left"))
    return min(index, len(histogram) - 1)
