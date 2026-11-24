from pathlib import Path

from app.champions.data.openfootball import parse_openfootball_cl

FIXTURE = Path(__file__).parent / "fixtures" / "champions_cl_2025_26.txt"


def test_openfootball_parses_all_2025_26_matches():
    matches = parse_openfootball_cl(FIXTURE.read_text(encoding="utf-8"))
    assert len(matches) == 189
    league = [match for match in matches if match["phase"] == "league"]
    assert len(league) == 144
    assert {match["matchday"] for match in league} == set(range(1, 9))
    assert len({match["home"] for match in matches}) == 36
    assert all(match["home_goals"] is not None for match in matches)
    final = [match for match in matches if match["phase"] == "final"][0]
    assert final["neutral"] is True
    assert final["home"] == "Paris Saint-Germain FC"
    assert final["away"] == "Arsenal FC"
    assert (final["home_goals"], final["away_goals"]) == (1, 1)


def test_openfootball_parses_extra_time_and_penalties_as_90_minutes():
    text = """
= UEFA Champions League 2025/26

▪ Finals, Final
  Sat May 30
    18:00  Paris Saint-Germain FC (FRA) v Arsenal FC (ENG)  4-3 pen. 1-1 a.e.t. (1-1, 0-1)
"""
    matches = parse_openfootball_cl(text)
    assert len(matches) == 1
    assert (matches[0]["home_goals"], matches[0]["away_goals"]) == (1, 1)
    assert matches[0]["neutral"] is True
