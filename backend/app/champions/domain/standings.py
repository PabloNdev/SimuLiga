"""Champions League league-phase standings and tiebreakers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from app.champions.models import ChampionsMatch


@dataclass
class TeamRecord:
    team_id: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    points: int = 0
    goals_for: int = 0
    goals_against: int = 0
    away_goals: int = 0
    away_wins: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against


def build_records(
    team_ids: Sequence[str], matches: Iterable[ChampionsMatch]
) -> dict[str, TeamRecord]:
    records = {team_id: TeamRecord(team_id) for team_id in team_ids}
    for match in matches:
        result = match.result
        if result is None:
            continue
        home = records.get(match.home_id)
        away = records.get(match.away_id)
        if home is None or away is None:
            continue
        assert match.home_goals is not None and match.away_goals is not None
        home.played += 1
        away.played += 1
        home.goals_for += match.home_goals
        home.goals_against += match.away_goals
        away.goals_for += match.away_goals
        away.goals_against += match.home_goals
        away.away_goals += match.away_goals

        if result == "H":
            home.won += 1
            home.points += 3
            away.lost += 1
        elif result == "A":
            away.won += 1
            away.away_wins += 1
            away.points += 3
            home.lost += 1
        else:
            home.drawn += 1
            away.drawn += 1
            home.points += 1
            away.points += 1
    return records


def rank_teams(
    team_ids: Sequence[str],
    matches: Iterable[ChampionsMatch],
    *,
    random_keys: dict[str, float] | None = None,
) -> list[str]:
    """Rank teams with the UCL league-phase criteria.

    Order: points, goal difference, goals scored, away goals, wins, away wins,
    then a deterministic random key (a proxy for the final draw).
    """
    records = build_records(team_ids, matches)
    random_keys = random_keys or {}

    def key(team_id: str) -> tuple:
        record = records[team_id]
        return (
            -record.points,
            -record.goal_difference,
            -record.goals_for,
            -record.away_goals,
            -record.won,
            -record.away_wins,
            -float(random_keys.get(team_id, 0.0)),
            team_id,
        )

    return sorted(team_ids, key=key)


def qualification_cuts(team_count: int) -> tuple[int, int]:
    """Return ``(direct_cutoff, playoff_cutoff)`` position boundaries.

    The real competition uses positions 1-8 direct and 9-24 playoff for 36
    teams. Smaller sizes are used by tests and scale down proportionally.
    """
    if team_count >= 36:
        return 8, 24
    direct = max(1, team_count // 4)
    playoff_cutoff = max(direct + 1, team_count // 2)
    return direct, min(team_count, playoff_cutoff)
