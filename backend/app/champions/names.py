"""Champions League team registry and provider name normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.data.names import normalize_name, slugify

FALLBACK_COLORS = [
    "#1D4ED8",
    "#0F766E",
    "#B45309",
    "#7E22CE",
    "#BE123C",
    "#0369A1",
    "#4D7C0F",
    "#9A3412",
    "#0F172A",
    "#B91C1C",
]

COUNTRY_SUFFIX_RE = re.compile(r"\s*\(([A-Z]{2,3})\)\s*$")


@dataclass(frozen=True)
class TeamSeed:
    id: str
    name: str
    short_name: str
    color: str
    country: str
    aliases: tuple[str, ...] = ()


TEAM_SEEDS: list[TeamSeed] = [
    TeamSeed("real-madrid", "Real Madrid", "RMA", "#FEBE10", "ESP", ("Real Madrid CF", "Real Madrid")),
    TeamSeed("barcelona", "Barcelona", "BAR", "#A50044", "ESP", ("FC Barcelona", "Barcelona")),
    TeamSeed("bayern-munich", "Bayern Múnich", "BAY", "#DC052D", "GER", ("FC Bayern München", "Bayern Munich", "Bayern")),
    TeamSeed("liverpool", "Liverpool", "LIV", "#C8102E", "ENG", ("Liverpool FC", "Liverpool")),
    TeamSeed("manchester-city", "Manchester City", "MCI", "#6CABDD", "ENG", ("Manchester City FC", "Manchester City")),
    TeamSeed("psg", "Paris Saint-Germain", "PSG", "#004170", "FRA", ("Paris Saint-Germain FC", "Paris SG", "PSG")),
    TeamSeed("inter", "Inter de Milán", "INT", "#0068A8", "ITA", ("FC Internazionale Milano", "Internazionale", "Inter")),
    TeamSeed("arsenal", "Arsenal", "ARS", "#EF0107", "ENG", ("Arsenal FC", "Arsenal")),
    TeamSeed("atletico", "Atlético de Madrid", "ATM", "#CB3524", "ESP", ("Club Atlético de Madrid", "Atletico Madrid", "Atlético")),
    TeamSeed("chelsea", "Chelsea", "CHE", "#034694", "ENG", ("Chelsea FC", "Chelsea")),
    TeamSeed("dortmund", "Borussia Dortmund", "BVB", "#FDE100", "GER", ("Borussia Dortmund", "Dortmund")),
    TeamSeed("juventus", "Juventus", "JUV", "#000000", "ITA", ("Juventus FC", "Juventus")),
    TeamSeed("benfica", "Benfica", "BEN", "#E30613", "POR", ("Sport Lisboa e Benfica", "Benfica")),
    TeamSeed("sporting", "Sporting CP", "SCP", "#008057", "POR", ("Sporting Clube de Portugal", "Sporting CP", "Sporting")),
    TeamSeed("napoli", "Napoli", "NAP", "#12A0D7", "ITA", ("SSC Napoli", "Napoli")),
    TeamSeed("atalanta", "Atalanta", "ATA", "#1E71B8", "ITA", ("Atalanta BC", "Atalanta")),
    TeamSeed("leverkusen", "Bayer Leverkusen", "B04", "#E32221", "GER", ("Bayer 04 Leverkusen", "Leverkusen")),
    TeamSeed("eintracht", "Eintracht Frankfurt", "SGE", "#E1000F", "GER", ("Eintracht Frankfurt", "Eintracht")),
    TeamSeed("club-brugge", "Club Brujas", "CLB", "#005CA9", "BEL", ("Club Brugge KV", "Club Brugge", "Brujas")),
    TeamSeed("psv", "PSV Eindhoven", "PSV", "#ED1C24", "NED", ("PSV", "PSV Eindhoven")),
    TeamSeed("ajax", "Ajax", "AJA", "#D2122E", "NED", ("AFC Ajax", "Ajax")),
    TeamSeed("galatasaray", "Galatasaray", "GAL", "#A90432", "TUR", ("Galatasaray SK", "Galatasaray")),
    TeamSeed("olympiacos", "Olympiacos", "OLY", "#D40000", "GRE", ("PAE Olympiakos SFP", "Olympiacos", "Olympiakos")),
    TeamSeed("slavia-prague", "Slavia Praga", "SLA", "#D71920", "CZE", ("SK Slavia Praha", "Slavia Prague")),
    TeamSeed("copenhagen", "Copenhague", "FCK", "#0F3A5F", "DEN", ("FC København", "FC Copenhagen", "Copenhagen")),
    TeamSeed("monaco", "Mónaco", "ASM", "#E51B22", "MCO", ("AS Monaco FC", "Monaco")),
    TeamSeed("marseille", "Marsella", "OM", "#2FAEE0", "FRA", ("Olympique de Marseille", "Marseille")),
    TeamSeed("tottenham", "Tottenham", "TOT", "#132257", "ENG", ("Tottenham Hotspur FC", "Tottenham Hotspur", "Tottenham")),
    TeamSeed("newcastle", "Newcastle", "NEW", "#241F20", "ENG", ("Newcastle United FC", "Newcastle United")),
    TeamSeed("villarreal", "Villarreal", "VIL", "#FFE667", "ESP", ("Villarreal CF", "Villarreal")),
    TeamSeed("athletic", "Athletic Club", "ATH", "#EE2523", "ESP", ("Athletic Club", "Athletic Bilbao")),
    TeamSeed("union-saint-gilloise", "Union Saint-Gilloise", "USG", "#F5D000", "BEL", ("Royale Union Saint-Gilloise", "Union SG")),
    TeamSeed("qarabag", "Qarabag", "QAR", "#000000", "AZE", ("Qarabag Agdam FK", "Qarabag")),
    TeamSeed("kairat", "Kairat Almaty", "KAI", "#FDD10C", "KAZ", ("FK Kairat", "Kairat")),
    TeamSeed("paphos", "Pafos", "PAF", "#0B4EA2", "CYP", ("Paphos FC", "Pafos")),
    TeamSeed("bodo-glimt", "Bodø/Glimt", "BOD", "#FFD200", "NOR", ("FK Bodø/Glimt", "Bodo/Glimt", "Bodø/Glimt")),
]

EXTRA_TEAM_SEEDS: list[TeamSeed] = [
    TeamSeed("aek-athens", "AEK Atenas", "AEK", "#F7D117", "GRE", ("AEK Athens", "AEK")),
    TeamSeed("aston-villa", "Aston Villa", "AVL", "#670E36", "ENG", ("Aston Villa",)),
    TeamSeed("como", "Como", "COM", "#003DA5", "ITA", ("Como",)),
    TeamSeed("fenerbahce", "Fenerbahçe", "FEN", "#FFED00", "TUR", ("Fenerbahçe", "Fenerbahce")),
    TeamSeed("feyenoord", "Feyenoord", "FEY", "#E21E2B", "NED", ("Feyenoord",)),
    TeamSeed("lask", "LASK", "LAS", "#1A1A1A", "AUT", ("LASK", "LASK Linz")),
    TeamSeed("leipzig", "RB Leipzig", "RBL", "#DD0741", "GER", ("RB Leipzig", "Leipzig")),
    TeamSeed("lens", "Lens", "RCL", "#E30613", "FRA", ("Lens", "RC Lens")),
    TeamSeed("lille", "Lille", "LOS", "#E01E13", "FRA", ("Lille", "LOSC Lille")),
    TeamSeed("manchester-united", "Manchester United", "MUN", "#DA291C", "ENG", ("Manchester United", "Man United")),
    TeamSeed("porto", "Porto", "POR", "#003DA5", "POR", ("FC Porto", "Porto")),
    TeamSeed("real-betis", "Real Betis", "BET", "#0B8A4B", "ESP", ("Real Betis", "Betis")),
    TeamSeed("roma", "Roma", "ROM", "#8E1F2F", "ITA", ("AS Roma", "Roma")),
    TeamSeed("sabah", "Sabah", "SAB", "#009B3A", "AZE", ("Sabah", "Sabah FK")),
    TeamSeed("shakhtar", "Shakhtar Donetsk", "SHK", "#FF6600", "UKR", ("Shakhtar Donetsk", "Shakhtar")),
    TeamSeed("slovan-bratislava", "Slovan Bratislava", "SLO", "#0B4EA2", "SVK", ("Slovan Bratislava", "Slovan")),
    TeamSeed("stuttgart", "Stuttgart", "VFB", "#E32219", "GER", ("VfB Stuttgart", "Stuttgart")),
    TeamSeed("viking", "Viking", "VIK", "#00205B", "NOR", ("Viking", "Viking Stavanger")),
]

_ALL_SEEDS = [*TEAM_SEEDS, *EXTRA_TEAM_SEEDS]
_BY_ID = {seed.id: seed for seed in _ALL_SEEDS}

# 2026/27 pots reconstructed from the league-phase draw: every team plays
# exactly two opponents from each pot, one home and one away. The Elo ranking
# only breaks ties between valid partitions.
TEAM_POTS: dict[str, int] = {
    "aek-athens": 4,
    "arsenal": 1,
    "aston-villa": 2,
    "atletico": 1,
    "barcelona": 1,
    "bayern-munich": 1,
    "bodo-glimt": 3,
    "club-brugge": 2,
    "como": 4,
    "dortmund": 2,
    "fenerbahce": 3,
    "feyenoord": 3,
    "galatasaray": 3,
    "inter": 1,
    "lask": 4,
    "leipzig": 3,
    "lens": 4,
    "lille": 3,
    "liverpool": 1,
    "manchester-city": 1,
    "manchester-united": 2,
    "napoli": 3,
    "porto": 2,
    "psg": 1,
    "psv": 2,
    "real-betis": 2,
    "real-madrid": 1,
    "roma": 2,
    "sabah": 4,
    "shakhtar": 3,
    "slavia-prague": 4,
    "slovan-bratislava": 4,
    "sporting": 2,
    "stuttgart": 4,
    "viking": 4,
    "villarreal": 3,
}

TEAM_ALIASES: dict[str, str] = {}
for _seed in _ALL_SEEDS:
    TEAM_ALIASES[normalize_name(_seed.id)] = _seed.id
    TEAM_ALIASES[normalize_name(_seed.name)] = _seed.id
    TEAM_ALIASES[normalize_name(_seed.short_name)] = _seed.id
    for _alias in _seed.aliases:
        TEAM_ALIASES[normalize_name(_alias)] = _seed.id

# Extra short names used by ClubElo and other providers.
TEAM_ALIASES.update(
    {
        normalize_name("Bayern"): "bayern-munich",
        normalize_name("Dortmund"): "dortmund",
        normalize_name("Paris SG"): "psg",
        normalize_name("Inter"): "inter",
        normalize_name("Atletico"): "atletico",
        normalize_name("Man City"): "manchester-city",
        normalize_name("Sporting"): "sporting",
        normalize_name("Brugge"): "club-brugge",
        normalize_name("Olympiakos"): "olympiacos",
        normalize_name("Slavia"): "slavia-prague",
        normalize_name("Copenhagen"): "copenhagen",
        normalize_name("Bodo"): "bodo-glimt",
    }
)

HISTORICAL_ALIASES: dict[str, str] = {
    "Bayern München": "bayern-munich",
    "Bayern Munchen": "bayern-munich",
    "Aston Villa FC": "aston-villa",
    "SL Benfica": "benfica",
    "Feyenoord Rotterdam": "feyenoord",
    "Racing Club de Lens": "lens",
    "Lille OSC": "lille",
    "Manchester United FC": "manchester-united",
    "Olympique Marseille": "marseille",
    "Real Sociedad de Fútbol": "real-sociedad",
    "Real Sociedad de Futbol": "real-sociedad",
    "Sevilla FC": "sevilla",
    "FK Shakhtar Donetsk": "shakhtar",
    "ŠK Slovan Bratislava": "slovan-bratislava",
    "SK Slovan Bratislava": "slovan-bratislava",
    "Slavia Praha": "slavia-prague",
    "AC Milan": "ac-milan",
    "Milan": "ac-milan",
    "AC Sparta Praha": "sparta-prague",
    "Sparta Praha": "sparta-prague",
    "GNK Dinamo Zagreb": "dinamo-zagreb",
    "Dinamo Zagreb": "dinamo-zagreb",
    "RB Salzburg": "rb-salzburg",
    "FC Red Bull Salzburg": "rb-salzburg",
    "Dinamo Kiev": "dynamo-kyiv",
    "Dynamo Kyiv": "dynamo-kyiv",
    "FC Sheriff": "sheriff",
    "Sheriff Tiraspol": "sheriff",
    "BSC Young Boys": "young-boys",
    "Young Boys": "young-boys",
    "Beşiktaş": "besiktas",
    "Besiktas": "besiktas",
    "Bologna FC 1909": "bologna",
    "Bologna": "bologna",
    "Celtic FC": "celtic",
    "Celtic": "celtic",
    "Girona FC": "girona",
    "Girona": "girona",
    "Maccabi Haifa": "maccabi-haifa",
    "Malmö FF": "malmo",
    "Malmo FF": "malmo",
    "Rangers FC": "rangers",
    "Rangers": "rangers",
    "Royal Antwerp FC": "antwerp",
    "Antwerp": "antwerp",
    "SK Sturm Graz": "sturm-graz",
    "Sturm Graz": "sturm-graz",
    "SS Lazio": "lazio",
    "Lazio": "lazio",
    "Sporting Clube de Braga": "braga",
    "Braga": "braga",
    "Stade Brestois 29": "brest",
    "Brest": "brest",
    "VfL Wolfsburg": "wolfsburg",
    "Wolfsburg": "wolfsburg",
    "Viktoria Plzeň": "plzen",
    "Viktoria Plzen": "plzen",
    "Zenit St. Petersburg": "zenit",
    "Zenit": "zenit",
    "1. FC Union Berlin": "union-berlin",
    "Union Berlin": "union-berlin",
}

TEAM_ALIASES.update(
    {normalize_name(alias): team_id for alias, team_id in HISTORICAL_ALIASES.items()}
)


def clean_provider_name(name: str) -> str:
    """Remove country suffixes such as ``(ENG)`` from provider names."""
    return COUNTRY_SUFFIX_RE.sub("", name).strip()


def country_from_name(name: str) -> str | None:
    match = COUNTRY_SUFFIX_RE.search(name)
    return match.group(1) if match else None


def normalize_team_key(name: str) -> str | None:
    """Return the canonical id for a provider name, or ``None``."""
    cleaned = clean_provider_name(name)
    return TEAM_ALIASES.get(normalize_name(cleaned))


def team_seed(team_id: str) -> TeamSeed | None:
    return _BY_ID.get(team_id)


def team_key_map() -> dict[str, str]:
    return dict(TEAM_ALIASES)


def fallback_identity(name: str) -> tuple[str, str, str]:
    cleaned = clean_provider_name(name)
    team_id = slugify(cleaned)
    words = normalize_name(cleaned).split()
    short = "".join(word[0] for word in words[:3]).upper() or cleaned[:3].upper()
    color = FALLBACK_COLORS[sum(ord(char) for char in team_id) % len(FALLBACK_COLORS)]
    return team_id, short[:3], color
