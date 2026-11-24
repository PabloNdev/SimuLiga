"""JSON serializers for the Champions League API."""

from __future__ import annotations

from app.champions.domain.standings import build_records, rank_teams
from app.champions.models import ChampionsMatch, ChampionsSnapshot, ChampionsTeam
from app.champions.domain.simulation import ChampionsSimulationResult
from app.domain.davidson import DavidsonParams, probabilities_from_ratings
from app.domain.scoreline import ScorelineParams, expected_goals, prepare_scoreline

TIEBREAK_RULES = [
    "Mayor número de puntos.",
    "Mayor diferencia de goles.",
    "Mayor número de goles marcados.",
    "Mayor número de goles marcados como visitante.",
    "Mayor número de victorias.",
    "Mayor número de victorias como visitante.",
    "Sorteo si persiste el empate.",
]

QUALIFICATION_ZONES = {
    "direct": [1, 8],
    "playoff": [9, 24],
    "eliminated": [25, 36],
}


def serialize_team(team: ChampionsTeam) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "short_name": team.short_name,
        "color": team.color,
        "country": team.country,
        "elo": round(team.elo, 1),
        "pot": team.pot,
    }


def _league_matches(snapshot: ChampionsSnapshot) -> list[ChampionsMatch]:
    return [match for match in snapshot.matches if match.phase == "league"]


def serialize_standings(snapshot: ChampionsSnapshot) -> list[dict]:
    team_map = {team.id: team for team in snapshot.teams}
    team_ids = [team.id for team in snapshot.teams]
    played = [match for match in _league_matches(snapshot) if match.is_played]
    records = build_records(team_ids, played)
    order = rank_teams(team_ids, played)
    standings = []
    for position, team_id in enumerate(order, start=1):
        record = records[team_id]
        standings.append(
            {
                "position": position,
                "team": serialize_team(team_map[team_id]),
                "played": record.played,
                "won": record.won,
                "drawn": record.drawn,
                "lost": record.lost,
                "goals_for": record.goals_for,
                "goals_against": record.goals_against,
                "goal_difference": record.goal_difference,
                "away_goals": record.away_goals,
                "wins": record.won,
                "away_wins": record.away_wins,
                "points": record.points,
            }
        )
    return standings


def current_matchday(snapshot: ChampionsSnapshot) -> int:
    league = _league_matches(snapshot)
    matchdays = sorted({match.matchday for match in league})
    if not matchdays:
        return 1
    completed = [
        matchday
        for matchday in matchdays
        if all(
            match.is_played
            for match in league
            if match.matchday == matchday
        )
    ]
    if not completed:
        return min(matchdays)
    return min(max(completed) + 1, max(matchdays))


def serialize_season(snapshot: ChampionsSnapshot) -> dict:
    league = _league_matches(snapshot)
    played = sum(1 for match in league if match.is_played)
    return {
        "competition": snapshot.competition,
        "season": snapshot.season,
        "target_season": snapshot.target_season,
        "phase": "league",
        "source": snapshot.source,
        "demo": snapshot.demo,
        "fallback": snapshot.fallback,
        "data_note": snapshot.data_note,
        "updated_at": snapshot.updated_at,
        "data_version": snapshot.data_version,
        "current_matchday": current_matchday(snapshot),
        "total_matchdays": max((match.matchday for match in league), default=0),
        "played_matches": played,
        "pending_matches": sum(1 for match in league if not match.is_played),
        "teams": [serialize_team(team) for team in snapshot.teams],
        "standings": serialize_standings(snapshot),
        "model": snapshot.model,
        "tiebreak_rules": TIEBREAK_RULES,
        "qualification_zones": QUALIFICATION_ZONES,
    }


def serialize_projection(
    result: ChampionsSimulationResult, snapshot: ChampionsSnapshot
) -> dict:
    team_map = {team.id: team for team in snapshot.teams}
    return {
        "mode": result.mode,
        "n_sims": result.n_sims,
        "seed": result.seed,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "goals_available": result.goals_available,
        "data_version": snapshot.data_version,
        "source": snapshot.source,
        "demo": snapshot.demo,
        "fallback": snapshot.fallback,
        "data_note": snapshot.data_note,
        "base_standings": serialize_standings(snapshot),
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
                "top8_probability": projection.top8_probability,
                "playoff_probability": projection.playoff_probability,
                "eliminated_probability": projection.eliminated_probability,
                "playoff_win_probability": projection.playoff_win_probability,
                "round_of_16_probability": projection.round_of_16_probability,
                "position_probabilities": projection.position_probabilities,
                "opponent_probabilities": projection.opponent_probabilities,
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
        "playoff": {
            "bracket": [
                {
                    "better_slot": entry["better_slot"],
                    "worse_slot": entry["worse_slot"],
                    "better_team": (
                        serialize_team(team_map[entry["better_team_id"]])
                        if entry.get("better_team_id") in team_map
                        else None
                    ),
                    "better_probability": entry["better_probability"],
                    "worse_team": (
                        serialize_team(team_map[entry["worse_team_id"]])
                        if entry.get("worse_team_id") in team_map
                        else None
                    ),
                    "worse_probability": entry["worse_probability"],
                }
                for entry in result.playoff.bracket
            ],
            "advance_probabilities": result.playoff.advance_probabilities,
            "opponent_probabilities": result.playoff.opponent_probabilities,
            "matchups": [
                {
                    **matchup,
                    "better_team": (
                        serialize_team(team_map[matchup["better_id"]])
                        if matchup["better_id"] in team_map
                        else None
                    ),
                    "worse_team": (
                        serialize_team(team_map[matchup["worse_id"]])
                        if matchup["worse_id"] in team_map
                        else None
                    ),
                }
                for matchup in result.playoff.matchups
            ],
        },
    }


def serialize_matches(
    snapshot: ChampionsSnapshot,
    mode: str,
    davidson: DavidsonParams,
    scoreline: ScorelineParams,
) -> list[dict]:
    team_map = {team.id: team for team in snapshot.teams}
    payload: list[dict] = []
    for match in sorted(
        _league_matches(snapshot),
        key=lambda item: (item.matchday, item.kickoff or "", item.id),
    ):
        base = {
            "id": match.id,
            "matchday": match.matchday,
            "kickoff": match.kickoff,
            "home": serialize_team(team_map[match.home_id]),
            "away": serialize_team(team_map[match.away_id]),
            "status": "played" if match.is_played else "pending",
            "score": [match.home_goals, match.away_goals]
            if match.has_score
            else None,
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
            home_lambda, away_lambda = expected_goals(
                home.elo, away.elo, scoreline
            )
            prepared = prepare_scoreline(home_lambda, away_lambda, scoreline)
            base["most_likely_score"] = [
                prepared.most_likely[0],
                prepared.most_likely[1],
            ]
            if mode == "score":
                probabilities = prepared.probabilities
            else:
                probabilities = probabilities_from_ratings(
                    home.elo, away.elo, davidson
                )
            base.update(
                {
                    "home_probability": probabilities.home,
                    "draw_probability": probabilities.draw,
                    "away_probability": probabilities.away,
                }
            )
        payload.append(base)
    return payload


def serialize_elo(snapshot: ChampionsSnapshot) -> dict:
    start_ratings = snapshot.elo_by_matchday.get(1, {})
    played: dict[str, int] = {}
    for match in _league_matches(snapshot):
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
                "country": team.country,
                "elo": round(team.elo, 1),
                "start_elo": round(start_elo, 1),
                "delta": round(team.elo - start_elo, 1),
                "played": played.get(team.id, 0),
            }
        )
    league = _league_matches(snapshot)
    return {
        "season": snapshot.season,
        "source": snapshot.source,
        "demo": snapshot.demo,
        "fallback": snapshot.fallback,
        "data_note": snapshot.data_note,
        "updated_at": snapshot.updated_at,
        "data_version": snapshot.data_version,
        "current_matchday": current_matchday(snapshot),
        "total_matchdays": max((match.matchday for match in league), default=0),
        "played_matches": sum(1 for match in league if match.is_played),
        "params": {
            "k": 20,
            "home_advantage": snapshot.model.get("davidson", {}).get(
                "home_advantage", 60.0
            ),
            "elo_scale": 400.0,
            "start_rating": 1500.0,
        },
        "teams": teams,
        "history": snapshot.elo_history
        or {"seasons": [], "series": [], "origin": 1500.0},
        "verification": snapshot.elo_verification or {"available": False},
        "timeline": snapshot.elo_timeline or {"dates": [], "series": []},
    }


def serialize_validation(snapshot: ChampionsSnapshot) -> dict:
    verification = snapshot.elo_verification or {}
    params = verification.get("params", {})
    metrics = params.get("validation") if isinstance(params, dict) else None
    league = _league_matches(snapshot)
    return {
        "status": "ok" if metrics else "pending_historical_validation",
        "message": (
            "Calibración temporal sobre la Champions 2025/26."
            if metrics
            else "La calibración se calcula al cargar la temporada anterior."
        ),
        "metrics": metrics,
        "model": snapshot.model,
        "data": {
            "source": snapshot.source,
            "data_version": snapshot.data_version,
            "demo": snapshot.demo,
            "fallback": snapshot.fallback,
            "teams": len(snapshot.teams),
            "matches": len(league),
            "played": sum(1 for match in league if match.is_played),
            "seed_source": verification.get("seed_source"),
            "previous_season": verification.get("previous_season"),
            "previous_matches": verification.get(
                "previous_matches_total",
                verification.get("matches_total"),
            ),
            "previous_applied": verification.get(
                "previous_matches_applied",
                verification.get("matches_applied"),
            ),
        },
    }
