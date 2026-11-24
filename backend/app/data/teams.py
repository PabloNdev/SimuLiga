"""LaLiga 2026/27 clubs, colors, Elo seeds and provider aliases.

Promoted clubs without a historical rating use the fallback promoted baseline
(1370), below the 1500 reconstruction origin. The real-data pipeline replaces
it with the average rating of the three teams relegated from the previous
season; see ``real_league.build_snapshot_from_sources``.
"""

from __future__ import annotations

from app.data.names import normalize_name
from app.domain.models import Team

TEAM_SEEDS: list[dict] = [
    {"id": "real-madrid", "name": "Real Madrid", "short_name": "RMA", "color": "#E7B93C", "elo": 1955},
    {"id": "barcelona", "name": "Barcelona", "short_name": "BAR", "color": "#A50044", "elo": 1940},
    {"id": "atletico", "name": "Atlético de Madrid", "short_name": "ATM", "color": "#CB3524", "elo": 1875},
    {"id": "athletic", "name": "Athletic Club", "short_name": "ATH", "color": "#EE2523", "elo": 1840},
    {"id": "villarreal", "name": "Villarreal", "short_name": "VIL", "color": "#D8B500", "elo": 1815},
    {"id": "betis", "name": "Real Betis", "short_name": "BET", "color": "#0B8A4B", "elo": 1790},
    {"id": "real-sociedad", "name": "Real Sociedad", "short_name": "RSO", "color": "#0067B1", "elo": 1765},
    {"id": "sevilla", "name": "Sevilla", "short_name": "SEV", "color": "#D40000", "elo": 1740},
    {"id": "valencia", "name": "Valencia", "short_name": "VAL", "color": "#F58220", "elo": 1720},
    {"id": "celta", "name": "Celta de Vigo", "short_name": "CEL", "color": "#6DB7E8", "elo": 1690},
    {"id": "osasuna", "name": "Osasuna", "short_name": "OSA", "color": "#D91A21", "elo": 1675},
    {"id": "rayo", "name": "Rayo Vallecano", "short_name": "RAY", "color": "#E53027", "elo": 1650},
    {"id": "getafe", "name": "Getafe", "short_name": "GET", "color": "#005999", "elo": 1640},
    {"id": "espanyol", "name": "Espanyol", "short_name": "ESP", "color": "#007FC8", "elo": 1625},
    {"id": "alaves", "name": "Alavés", "short_name": "ALA", "color": "#0761AF", "elo": 1610},
    {"id": "elche", "name": "Elche", "short_name": "ELC", "color": "#0A6E3A", "elo": 1590},
    {"id": "levante", "name": "Levante", "short_name": "LEV", "color": "#B4053F", "elo": 1370},
    {"id": "malaga", "name": "Málaga", "short_name": "MAL", "color": "#004B9B", "elo": 1370},
    {"id": "deportivo", "name": "Deportivo de A Coruña", "short_name": "DEP", "color": "#1B4F9C", "elo": 1370},
    {"id": "racing", "name": "Racing de Santander", "short_name": "RAC", "color": "#00843D", "elo": 1370},
]

ALIASES: dict[str, str] = {
    # OpenFootball
    "athletic club": "athletic",
    "ca osasuna": "osasuna",
    "club atletico de madrid": "atletico",
    "deportivo alaves": "alaves",
    "elche cf": "elche",
    "fc barcelona": "barcelona",
    "getafe cf": "getafe",
    "levante ud": "levante",
    "malaga cf": "malaga",
    "rc celta de vigo": "celta",
    "rc deportivo la coruna": "deportivo",
    "rcd espanyol de barcelona": "espanyol",
    "rayo vallecano de madrid": "rayo",
    "real betis balompie": "betis",
    "real madrid cf": "real-madrid",
    "real racing club de santander": "racing",
    "real sociedad de futbol": "real-sociedad",
    "sevilla fc": "sevilla",
    "valencia cf": "valencia",
    "villarreal cf": "villarreal",
    # football-data.co.uk
    "alaves": "alaves",
    "ath bilbao": "athletic",
    "ath madrid": "atletico",
    "barcelona": "barcelona",
    "betis": "betis",
    "celta": "celta",
    "elche": "elche",
    "espanol": "espanyol",
    "getafe": "getafe",
    "la coruna": "deportivo",
    "levante": "levante",
    "malaga": "malaga",
    "osasuna": "osasuna",
    "real madrid": "real-madrid",
    "santander": "racing",
    "sevilla": "sevilla",
    "sociedad": "real-sociedad",
    "valencia": "valencia",
    "vallecano": "rayo",
    "villarreal": "villarreal",
    # API-Football / older seasons
    "atletico de madrid": "atletico",
    "atletico madrid": "atletico",
    "real betis": "betis",
    "real sociedad": "real-sociedad",
    "celta vigo": "celta",
    "espanyol": "espanyol",
    "real oviedo": "oviedo",
    "oviedo": "oviedo",
}


def seed_teams() -> list[Team]:
    return [Team(**seed) for seed in TEAM_SEEDS]


def team_by_name_map() -> dict[str, dict]:
    """Map normalized provider names (and canonical ids) to seeded clubs."""
    by_id = {seed["id"]: seed for seed in TEAM_SEEDS}
    mapping: dict[str, dict] = {}
    for seed in TEAM_SEEDS:
        mapping[normalize_name(seed["id"])] = seed
        mapping[normalize_name(seed["name"])] = seed
    for alias, team_id in ALIASES.items():
        seed = by_id.get(team_id)
        if seed is not None:
            mapping[normalize_name(alias)] = seed
    return mapping
