from collections import Counter

from app.champions.data.snapshot import make_team
from app.champions.names import TEAM_POTS, normalize_team_key


def test_historical_current_aliases_resolve_to_seed_ids():
    assert normalize_team_key("Bayern München") == "bayern-munich"
    assert normalize_team_key("Aston Villa FC") == "aston-villa"
    assert normalize_team_key("Lille OSC") == "lille"
    assert normalize_team_key("Real Sociedad de Fútbol") == "real-sociedad"
    assert normalize_team_key("Sevilla FC") == "sevilla"
    assert normalize_team_key("SL Benfica") == "benfica"
    assert normalize_team_key("Racing Club de Lens") == "lens"
    assert normalize_team_key("ŠK Slovan Bratislava") == "slovan-bratislava"
    assert normalize_team_key("Slavia Praha") == "slavia-prague"


def test_historical_non_seed_aliases_are_stable():
    assert normalize_team_key("AC Milan") == "ac-milan"
    assert normalize_team_key("Milan") == "ac-milan"
    assert normalize_team_key("GNK Dinamo Zagreb") == "dinamo-zagreb"
    assert normalize_team_key("Dinamo Zagreb") == "dinamo-zagreb"
    assert normalize_team_key("RB Salzburg") == "rb-salzburg"
    assert normalize_team_key("FC Red Bull Salzburg") == "rb-salzburg"


def test_make_team_uses_canonical_key_for_non_seed_alias():
    assert make_team("Milan").id == "ac-milan"
    assert make_team("AC Milan").id == "ac-milan"


def test_current_champions_teams_have_pot_categories():
    assert make_team("Real Madrid").pot == 1
    assert make_team("Aston Villa").pot == 2
    assert make_team("Napoli").pot == 3
    assert make_team("Slovan Bratislava").pot == 4
    assert make_team("Unknown FC").pot is None


def test_current_pot_categories_are_balanced():
    assert len(TEAM_POTS) == 36
    assert Counter(TEAM_POTS.values()) == {1: 9, 2: 9, 3: 9, 4: 9}
