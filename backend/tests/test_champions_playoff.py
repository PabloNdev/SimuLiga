import numpy as np

from app.champions.domain.playoff import pair_slots, simulate_tie
from app.champions.models import ChampionsTeam
from app.domain.scoreline import ScorelineParams


def test_pairings_are_deterministic():
    positions = {f"t{i}": i for i in range(1, 37)}
    pairs = pair_slots(positions)
    assert pairs[0] == ("t9", "t24")
    assert pairs[1] == ("t10", "t23")
    assert pairs[-1] == ("t16", "t17")


def test_two_leg_tie_returns_one_winner():
    teams = {
        "better": ChampionsTeam("better", "Better", "BET", "#000000", "ESP", 1700.0),
        "worse": ChampionsTeam("worse", "Worse", "WOR", "#FFFFFF", "ESP", 1500.0),
    }
    rng = np.random.default_rng(1)
    winner = simulate_tie("better", "worse", teams, ScorelineParams(), rng)
    assert winner in {"better", "worse"}
