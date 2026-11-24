"""Round-robin schedule generation for the demo competition."""

from __future__ import annotations

from app.domain.models import Match


def generate_double_round_robin(
    team_ids: list[str], *, start_matchday: int = 1
) -> list[Match]:
    """Build a balanced double round-robin schedule using the circle method."""
    if len(team_ids) % 2 != 0:
        raise ValueError("an even number of teams is required")
    rotation = list(team_ids)
    team_count = len(rotation)
    first_leg: list[tuple[int, str, str]] = []

    for round_index in range(team_count - 1):
        for pair_index in range(team_count // 2):
            first = rotation[pair_index]
            second = rotation[team_count - 1 - pair_index]
            if (round_index + pair_index) % 2 == 0:
                home, away = first, second
            else:
                home, away = second, first
            first_leg.append((start_matchday + round_index, home, away))
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]

    matches: list[Match] = []
    for matchday, home, away in first_leg:
        matches.append(
            Match(
                id=f"md{matchday}-{home}-{away}",
                matchday=matchday,
                home_id=home,
                away_id=away,
            )
        )
    for matchday, home, away in first_leg:
        reversed_matchday = matchday + team_count - 1
        matches.append(
            Match(
                id=f"md{reversed_matchday}-{away}-{home}",
                matchday=reversed_matchday,
                home_id=away,
                away_id=home,
            )
        )

    matches.sort(key=lambda match: (match.matchday, match.home_id, match.away_id))
    return matches
