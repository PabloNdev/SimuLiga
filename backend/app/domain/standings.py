"""LaLiga standings and the official head-to-head tiebreak rules.

Order of criteria between clubs level on points:
  1. Head-to-head points.
  2. Head-to-head goal difference.
  3. Head-to-head goals scored.
  4. Overall goal difference.
  5. Overall goals scored.
  6. Fair play points (lower is better).
  7. Drawing lots (a deterministic/random tiebreak key here).

The head-to-head block only applies once every match between the tied clubs
has been played; otherwise the overall criteria are used. This matters
mid-season and is exposed through ``require_complete_head_to_head``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from app.domain.models import Match


@dataclass
class TeamRecord:
    team_id: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    points: int = 0
    goals_for: int | None = None
    goals_against: int | None = None
    goals_matches: int = 0
    fair_play: int = 0

    @property
    def goal_difference(self) -> int | None:
        if self.goals_for is None or self.goals_against is None:
            return None
        return self.goals_for - self.goals_against


def build_records(
    team_ids: Sequence[str],
    matches: Iterable[Match],
    fair_play: dict[str, int] | None = None,
) -> dict[str, TeamRecord]:
    records = {
        team_id: TeamRecord(
            team_id=team_id,
            fair_play=(fair_play or {}).get(team_id, 0),
        )
        for team_id in team_ids
    }
    for match in matches:
        result = match.result
        if result is None:
            continue
        home = records[match.home_id]
        away = records[match.away_id]
        home.played += 1
        away.played += 1

        if result == "H":
            home.won += 1
            away.lost += 1
            home.points += 3
        elif result == "A":
            away.won += 1
            home.lost += 1
            away.points += 3
        else:
            home.drawn += 1
            away.drawn += 1
            home.points += 1
            away.points += 1

        if match.has_score:
            assert match.home_goals is not None and match.away_goals is not None
            if home.goals_for is None:
                home.goals_for = 0
                home.goals_against = 0
            if away.goals_for is None:
                away.goals_for = 0
                away.goals_against = 0
            home.goals_for += match.home_goals
            home.goals_against += match.away_goals
            away.goals_for += match.away_goals
            away.goals_against += match.home_goals
            home.goals_matches += 1
            away.goals_matches += 1

    return records


def rank_standings(
    team_ids: Sequence[str],
    matches: Iterable[Match],
    *,
    fair_play: dict[str, int] | None = None,
    tiebreak_key: dict[str, float] | None = None,
    expected_meetings: int = 2,
    require_complete_head_to_head: bool = True,
) -> list[str]:
    match_list = list(matches)
    records = build_records(team_ids, match_list, fair_play)

    ordered = sorted(team_ids, key=lambda team: -records[team].points)
    groups: list[list[str]] = []
    for team in ordered:
        if groups and records[groups[-1][0]].points == records[team].points:
            groups[-1].append(team)
        else:
            groups.append([team])

    result: list[str] = []
    for group in groups:
        result.extend(
            _rank_group(
                group,
                records,
                match_list,
                tiebreak_key or {},
                expected_meetings,
                require_complete_head_to_head,
            )
        )
    return result


def _rank_group(
    group: list[str],
    records: dict[str, TeamRecord],
    matches: list[Match],
    tiebreak_key: dict[str, float],
    expected_meetings: int,
    require_complete: bool,
) -> list[str]:
    if len(group) <= 1:
        return list(group)

    h2h_complete = _head_to_head_complete(group, matches, expected_meetings)
    if h2h_complete or not require_complete:
        stats = _head_to_head_stats(group, matches)
        if stats["played"]:
            keys = {
                team: (
                    stats["points"][team],
                    stats["goal_difference"][team],
                    stats["goals_for"][team],
                )
                for team in group
            }
            ordered = sorted(group, key=lambda team: (keys[team], team), reverse=True)
            partitions: list[list[str]] = []
            for team in ordered:
                if partitions and keys[partitions[-1][0]] == keys[team]:
                    partitions[-1].append(team)
                else:
                    partitions.append([team])
            if len(partitions) > 1:
                ranked: list[str] = []
                for partition in partitions:
                    if len(partition) == 1:
                        ranked.extend(partition)
                    else:
                        ranked.extend(
                            _rank_group(
                                partition,
                                records,
                                matches,
                                tiebreak_key,
                                expected_meetings,
                                require_complete,
                            )
                        )
                return ranked

    return _rank_by_overall(group, records, tiebreak_key)


def _rank_by_overall(
    group: list[str],
    records: dict[str, TeamRecord],
    tiebreak_key: dict[str, float],
) -> list[str]:
    goals_available = all(
        records[team].goals_for is not None
        and records[team].goals_matches == records[team].played
        for team in group
    )

    def key(team: str) -> tuple:
        record = records[team]
        goals = (
            -(record.goal_difference or 0),
            -(record.goals_for or 0),
        ) if goals_available else (0, 0)
        return (
            goals[0],
            goals[1],
            record.fair_play,
            tiebreak_key.get(team, 0.0),
            team,
        )

    return sorted(group, key=key)


def _head_to_head_complete(
    group: list[str], matches: list[Match], expected_meetings: int
) -> bool:
    members = set(group)
    counts: dict[tuple[str, str], int] = {}
    for match in matches:
        if match.result is None:
            continue
        if match.home_id in members and match.away_id in members:
            pair = tuple(sorted((match.home_id, match.away_id)))
            counts[pair] = counts.get(pair, 0) + 1
    for i, first in enumerate(group):
        for second in group[i + 1 :]:
            if counts.get(tuple(sorted((first, second))), 0) < expected_meetings:
                return False
    return True


def _head_to_head_stats(group: list[str], matches: list[Match]) -> dict:
    members = set(group)
    points = {team: 0 for team in group}
    goals_for = {team: 0 for team in group}
    goals_against = {team: 0 for team in group}
    played = 0
    goals_available = True

    for match in matches:
        if match.result is None:
            continue
        if match.home_id not in members or match.away_id not in members:
            continue
        played += 1
        if match.result == "H":
            points[match.home_id] += 3
        elif match.result == "A":
            points[match.away_id] += 3
        else:
            points[match.home_id] += 1
            points[match.away_id] += 1

        if match.has_score:
            assert match.home_goals is not None and match.away_goals is not None
            goals_for[match.home_id] += match.home_goals
            goals_against[match.home_id] += match.away_goals
            goals_for[match.away_id] += match.away_goals
            goals_against[match.away_id] += match.home_goals
        else:
            goals_available = False

    if not goals_available:
        goals_for = {team: 0 for team in group}
        goals_against = {team: 0 for team in group}

    return {
        "played": played,
        "points": points,
        "goals_for": goals_for,
        "goal_difference": {
            team: goals_for[team] - goals_against[team] for team in group
        },
    }
