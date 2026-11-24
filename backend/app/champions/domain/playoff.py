"""Champions League knockout-playoff simulation."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from app.champions.domain.standings import qualification_cuts
from app.champions.models import ChampionsTeam
from app.domain.scoreline import (
    ScorelineParams,
    expected_goals,
    prepare_scoreline,
    sample_prepared_scores,
    sample_scores_batch,
)


def pair_slots(
    positions: dict[str, int], team_count: int | None = None
) -> list[tuple[str, str]]:
    """Pair playoff teams: best vs worst, second vs second-worst, etc."""
    if team_count is None:
        team_count = len(positions)
    direct, playoff_cutoff = qualification_cuts(team_count)
    slots = list(range(direct + 1, playoff_cutoff + 1))
    by_position = {position: team_id for team_id, position in positions.items()}
    pairs: list[tuple[str, str]] = []
    for index in range(len(slots) // 2):
        better = by_position.get(slots[index])
        worse = by_position.get(slots[-1 - index])
        if better is not None and worse is not None:
            pairs.append((better, worse))
    return pairs


def _sample_goals(
    home_id: str,
    away_id: str,
    teams: dict[str, ChampionsTeam],
    params: ScorelineParams,
    rng: np.random.Generator,
    *,
    cache: dict | None = None,
    scale: float = 1.0,
) -> tuple[int, int]:
    key = (home_id, away_id, scale)
    prepared = cache.get(key) if cache is not None else None
    if prepared is None:
        home_lambda, away_lambda = expected_goals(
            teams[home_id].elo, teams[away_id].elo, params
        )
        prepared = prepare_scoreline(
            home_lambda * scale, away_lambda * scale, params
        )
        if cache is not None:
            cache[key] = prepared
    home_goals, away_goals = sample_prepared_scores(prepared, None, 1, rng, params)
    return int(home_goals[0]), int(away_goals[0])


def simulate_tie(
    better_id: str,
    worse_id: str,
    teams: dict[str, ChampionsTeam],
    params: ScorelineParams,
    rng: np.random.Generator,
    *,
    cache: dict | None = None,
) -> str:
    """Simulate a two-legged tie. The better seed hosts the second leg."""
    worse_home, better_away = _sample_goals(
        worse_id, better_id, teams, params, rng, cache=cache
    )
    better_home, worse_away = _sample_goals(
        better_id, worse_id, teams, params, rng, cache=cache
    )

    aggregate_better = better_away + better_home
    aggregate_worse = worse_home + worse_away
    if aggregate_better != aggregate_worse:
        return better_id if aggregate_better > aggregate_worse else worse_id

    extra_home, extra_away = _sample_goals(
        better_id, worse_id, teams, params, rng, cache=cache, scale=1.0 / 3.0
    )
    if extra_home != extra_away:
        return better_id if extra_home > extra_away else worse_id
    return better_id if rng.random() < 0.5 else worse_id


def simulate_playoff(
    positions_by_sim: Sequence[dict[str, int]],
    teams: dict[str, ChampionsTeam],
    params: ScorelineParams,
    rng: np.random.Generator,
) -> dict:
    """Accumulate playoff advancement, opponents and slot winners."""
    team_ids = list(teams)
    direct_cutoff, playoff_cutoff = qualification_cuts(len(team_ids))
    advance_counts = {team_id: 0 for team_id in team_ids}
    opponent_counts = {team_id: {other: 0 for other in team_ids} for team_id in team_ids}
    slot_counts: dict[int, dict[str, int]] = {
        position: {team_id: 0 for team_id in team_ids}
        for position in range(direct_cutoff + 1, playoff_cutoff + 1)
    }
    pair_counts: dict[tuple[str, str], int] = {}
    cache: dict = {}

    for positions in positions_by_sim:
        for better_id, worse_id in pair_slots(positions):
            winner = simulate_tie(
                better_id, worse_id, teams, params, rng, cache=cache
            )
            loser = worse_id if winner == better_id else better_id
            advance_counts[winner] += 1
            opponent_counts[winner][loser] += 1
            opponent_counts[loser][winner] += 1
            pair_counts[(better_id, worse_id)] = (
                pair_counts.get((better_id, worse_id), 0) + 1
            )
            for team_id in (better_id, worse_id):
                position = positions[team_id]
                if position in slot_counts:
                    slot_counts[position][team_id] += 1

    return {
        "advance_counts": advance_counts,
        "opponent_counts": opponent_counts,
        "slot_counts": slot_counts,
        "pair_counts": pair_counts,
    }
