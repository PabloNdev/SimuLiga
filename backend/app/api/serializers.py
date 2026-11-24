"""JSON serializers shared by the API routes."""

from __future__ import annotations

from app.data.league import LeagueSnapshot
from app.domain.davidson import DavidsonParams, probabilities_from_ratings
from app.domain.elo import DEFAULT_HOME_ADVANTAGE, DEFAULT_K
from app.domain.models import Match, Team
from app.domain.scoreline import ScorelineParams, expected_goals, prepare_scoreline
from app.domain.simulation import SimulationResult
from app.domain.standings import build_records, rank_standings

TIEBREAK_RULES = [
    "Mayor número de puntos obtenidos entre los equipos empatados.",
    "Mayor diferencia de goles en los partidos disputados entre sí.",
    "Mayor número de goles marcados en los partidos disputados entre sí.",
    "Mayor diferencia de goles en la clasificación general.",
    "Mayor número de goles marcados en la clasificación general.",
    "Menor puntuación de fair play.",
    "Sorteo si persiste el empate.",
]


def serialize_team(team: Team) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "short_name": team.short_name,
        "color": team.color,
        "elo": round(team.elo, 1),
    }


def serialize_elo(snapshot: LeagueSnapshot) -> dict:
    start_ratings = snapshot.elo_by_matchday.get(1, {})
    played: dict[str, int] = {}
    for match in snapshot.matches:
        if not match.is_played:
            continue
        played[match.home_id] = played.get(match.home_id, 0) + 1
        played[match.away_id] = played.get(match.away_id, 0) + 1

    ordered = sorted(snapshot.teams, key=lambda team: (-team.elo, team.name))
    teams = []
    for position, team in enumerate(ordered, start=1):
        start_elo = start_ratings.get(team.id, team.elo)
        teams.append(
            {
                "position": position,
                "id": team.id,
                "name": team.name,
                "short_name": team.short_name,
                "color": team.color,
                "elo": round(team.elo, 1),
                "start_elo": round(start_elo, 1),
                "delta": round(team.elo - start_elo, 1),
                "played": played.get(team.id, 0),
            }
        )

    matchdays = [match.matchday for match in snapshot.matches]
    return {
        "season": snapshot.season,
        "source": snapshot.source,
        "demo": snapshot.demo,
        "data_note": snapshot.data_note,
        "updated_at": snapshot.updated_at,
        "data_version": snapshot.data_version,
        "current_matchday": current_matchday(snapshot),
        "total_matchdays": max(matchdays, default=0),
        "played_matches": sum(1 for match in snapshot.matches if match.is_played),
        "params": {
            "k": DEFAULT_K,
            "home_advantage": DEFAULT_HOME_ADVANTAGE,
            "elo_scale": 400.0,
            "start_rating": 1500.0,
        },
        "teams": teams,
        "history": snapshot.elo_history
        or {
            "seasons": [],
            "series": [],
            "origin": 1500.0,
        },
        "verification": snapshot.elo_verification or {"available": False},
        "timeline": snapshot.elo_timeline
        or {
            "dates": [],
            "series": [],
        },
    }


def serialize_model(
    davidson: DavidsonParams, scoreline: ScorelineParams
) -> dict:
    return {
        "davidson": {
            "home_advantage": round(davidson.home_advantage, 2),
            "nu": round(davidson.nu, 4),
            "elo_scale": davidson.elo_scale,
        },
        "scoreline": {
            "home_base": scoreline.home_base,
            "away_base": scoreline.away_base,
            "elo_slope": scoreline.elo_slope,
            "home_advantage": scoreline.home_advantage,
            "rho": scoreline.rho,
            "max_goals": scoreline.max_goals,
        },
    }


def serialize_standings(
    snapshot: LeagueSnapshot, matches: list[Match] | None = None
) -> list[dict]:
    team_map = {team.id: team for team in snapshot.teams}
    played = matches if matches is not None else [
        match for match in snapshot.matches if match.is_played
    ]
    team_ids = [team.id for team in snapshot.teams]
    records = build_records(team_ids, played, snapshot.fair_play)
    order = rank_standings(
        team_ids,
        played,
        fair_play=snapshot.fair_play,
        require_complete_head_to_head=True,
    )
    standings = []
    for position, team_id in enumerate(order, start=1):
        record = records[team_id]
        team = team_map[team_id]
        standings.append(
            {
                "position": position,
                "team": serialize_team(team),
                "played": record.played,
                "won": record.won,
                "drawn": record.drawn,
                "lost": record.lost,
                "goals_for": record.goals_for or 0,
                "goals_against": record.goals_against or 0,
                "goal_difference": record.goal_difference or 0,
                "points": record.points,
            }
        )
    return standings


def completed_matchdays(snapshot: LeagueSnapshot) -> list[int]:
    by_matchday: dict[int, list[bool]] = {}
    for match in snapshot.matches:
        by_matchday.setdefault(match.matchday, []).append(match.is_played)
    return [
        matchday
        for matchday, flags in sorted(by_matchday.items())
        if flags and all(flags)
    ]


def current_matchday(snapshot: LeagueSnapshot) -> int:
    matchdays = sorted({match.matchday for match in snapshot.matches})
    pending = [match.matchday for match in snapshot.matches if not match.is_played]
    if not pending:
        return max(matchdays, default=0)
    completed = completed_matchdays(snapshot)
    if completed:
        return min(max(completed) + 1, max(matchdays, default=1))
    return min(pending)


def serialize_season(snapshot: LeagueSnapshot, model: dict) -> dict:
    matchdays = [match.matchday for match in snapshot.matches]
    pending = [match for match in snapshot.matches if not match.is_played]
    next_matchday = current_matchday(snapshot)
    return {
        "competition": snapshot.competition,
        "season": snapshot.season,
        "source": snapshot.source,
        "demo": snapshot.demo,
        "data_note": snapshot.data_note,
        "updated_at": snapshot.updated_at,
        "data_version": snapshot.data_version,
        "current_matchday": next_matchday,
        "total_matchdays": max(matchdays, default=0),
        "played_matches": sum(1 for match in snapshot.matches if match.is_played),
        "pending_matches": len(pending),
        "teams": [serialize_team(team) for team in snapshot.teams],
        "standings": serialize_standings(snapshot),
        "model": model,
        "tiebreak_rules": TIEBREAK_RULES,
    }


def serialize_projection(result: SimulationResult, snapshot: LeagueSnapshot) -> dict:
    start_matchday = result.start_matchday
    base_matches = [
        match
        for match in snapshot.matches
        if match.is_played
        and (start_matchday is None or match.matchday < start_matchday)
    ]
    return {
        "mode": result.mode,
        "n_sims": result.n_sims,
        "seed": result.seed,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "goals_available": result.goals_available,
        "start_matchday": start_matchday,
        "base_played_matches": len(base_matches),
        "base_standings": serialize_standings(snapshot, base_matches),
        "data_version": snapshot.data_version,
        "source": snapshot.source,
        "teams": [
            {
                "team": serialize_team(projection.team),
                "expected_points": round(projection.expected_points, 2),
                "points_std": round(projection.points_std, 2),
                "median_points": projection.median_points,
                "p10_points": projection.p10_points,
                "p90_points": projection.p90_points,
                "expected_position": round(projection.expected_position, 2),
                "most_likely_position": projection.most_likely_position,
                "champion_probability": projection.champion_probability,
                "top4_probability": projection.top4_probability,
                "relegation_probability": projection.relegation_probability,
                "position_probabilities": projection.position_probabilities,
                "points_histogram": projection.points_histogram,
            }
            for projection in result.teams
        ],
        "match_predictions": [
            {
                "match_id": prediction.match_id,
                "matchday": prediction.matchday,
                "home_id": prediction.home_id,
                "away_id": prediction.away_id,
                "home_probability": prediction.home_probability,
                "draw_probability": prediction.draw_probability,
                "away_probability": prediction.away_probability,
                "most_likely_score": list(prediction.most_likely_score)
                if prediction.most_likely_score is not None
                else None,
                "most_likely_score_probability": prediction.most_likely_score_probability,
            }
            for prediction in result.match_predictions
        ],
    }


def serialize_matches(
    snapshot: LeagueSnapshot, mode: str, davidson: DavidsonParams, scoreline: ScorelineParams
) -> list[dict]:
    team_map = {team.id: team for team in snapshot.teams}
    payload = []
    for match in sorted(
        snapshot.matches, key=lambda item: (item.matchday, item.kickoff or "", item.id)
    ):
        base = {
            "id": match.id,
            "matchday": match.matchday,
            "kickoff": match.kickoff,
            "home": serialize_team(team_map[match.home_id]),
            "away": serialize_team(team_map[match.away_id]),
            "status": "played" if match.is_played else "pending",
            "score": [match.home_goals, match.away_goals] if match.has_score else None,
            "outcome": match.result,
        }
        if match.is_played:
            base.update(
                {
                    "home_probability": None,
                    "draw_probability": None,
                    "away_probability": None,
                    "most_likely_score": None,
                }
            )
        else:
            home = team_map[match.home_id]
            away = team_map[match.away_id]
            if mode == "score":
                home_lambda, away_lambda = expected_goals(home.elo, away.elo, scoreline)
                prepared = prepare_scoreline(home_lambda, away_lambda, scoreline)
                probabilities = prepared.probabilities
                base["most_likely_score"] = [
                    prepared.most_likely[0],
                    prepared.most_likely[1],
                ]
            else:
                probabilities = probabilities_from_ratings(
                    home.elo, away.elo, davidson
                )
                base["most_likely_score"] = None
            base.update(
                {
                    "home_probability": probabilities.home,
                    "draw_probability": probabilities.draw,
                    "away_probability": probabilities.away,
                }
            )
        payload.append(base)
    return payload
