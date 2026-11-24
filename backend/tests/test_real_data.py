from app.config import Settings
from app.data.football_data_csv import fair_play_points, parse_results
from app.data.openfootball import parse_matches
from app.data.real_league import build_snapshot_from_sources


def openfootball_payload():
    return {
        "matches": [
            {
                "round": "Matchday 1",
                "date": "2026-08-15",
                "time": "19:30",
                "team1": "Real Madrid CF",
                "team2": "FC Barcelona",
                "score": {"ht": [1, 0], "ft": [2, 1]},
            },
            {
                "round": "Matchday 1",
                "date": "2026-08-16",
                "time": "21:00",
                "team1": "Sevilla FC",
                "team2": "Valencia CF",
                "score": {"ht": [0, 0], "ft": [1, 0]},
            },
            {
                "round": "Matchday 2",
                "date": "2026-08-22",
                "time": "19:30",
                "team1": "FC Barcelona",
                "team2": "Sevilla FC",
                "score": [0, 0],
            },
            {
                "round": "Matchday 2",
                "date": "2026-08-23",
                "time": "21:00",
                "team1": "Valencia CF",
                "team2": "Real Madrid CF",
                "score": [0, 0],
            },
        ]
    }


CSV = """Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR
SP1,15/08/2026,Real Madrid,Barcelona,2,1,H
SP1,16/08/2026,Sevilla,Valencia,1,0,H
SP1,23/08/2026,Valencia,Real Madrid,0,2,A
"""


def test_parse_openfootball_treats_list_scores_as_pending():
    matches = parse_matches(openfootball_payload())
    assert [match["round"] for match in matches] == [1, 1, 2, 2]
    assert matches[0]["ft"] == (2, 1)
    assert matches[2]["ft"] is None


def test_parse_football_data_csv_normalizes_dates_and_scores():
    results = parse_results(CSV)
    assert len(results) == 3
    assert results[0] == {
        "date": "2026-08-15",
        "home": "Real Madrid",
        "away": "Barcelona",
        "home_goals": 2,
        "away_goals": 1,
    }


def test_build_snapshot_merges_both_sources_and_updates_elo(tmp_path):
    settings = Settings(
        data_source="openfootball",
        openfootball_season="2026-27",
        cache_dir=str(tmp_path),
    )
    snapshot = build_snapshot_from_sources(
        parse_matches(openfootball_payload()),
        parse_results(CSV),
        settings,
        seed_ratings={
            "real madrid": 1900,
            "barcelona": 1880,
            "sevilla": 1750,
            "valencia": 1730,
        },
        previous_matches=[],
    )

    assert snapshot.season == "2026/27"
    assert snapshot.source == "openfootball+football-data"
    assert snapshot.demo is False
    assert "jornadas 1–1" in (snapshot.data_note or "")
    assert "3 partidos jugados" in (snapshot.data_note or "")

    played = [match for match in snapshot.matches if match.is_played]
    pending = [match for match in snapshot.matches if not match.is_played]
    assert len(played) == 3
    assert len(pending) == 1
    assert pending[0].home_id == "barcelona"
    assert pending[0].away_id == "sevilla"

    team_map = {team.id: team for team in snapshot.teams}
    assert team_map["real-madrid"].elo > 1900
    assert team_map["barcelona"].elo < 1880
    assert team_map["valencia"].elo < 1730

    overlay = next(
        match
        for match in snapshot.matches
        if match.home_id == "valencia" and match.away_id == "real-madrid"
    )
    assert overlay.is_played
    assert (overlay.home_goals, overlay.away_goals) == (0, 2)


CSV_CARDS = """Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HY,AY,HR,AR
SP1,15/08/2026,Real Madrid,Barcelona,2,1,H,2,1,0,0
SP1,16/08/2026,Sevilla,Valencia,1,0,H,3,0,0,1
SP1,23/08/2026,Valencia,Real Madrid,0,2,A,0,2,0,0
"""


def test_parse_football_data_csv_extracts_card_counts():
    results = parse_results(CSV_CARDS)
    assert results[0]["home_yellow"] == 2
    assert results[0]["away_yellow"] == 1
    assert results[0]["home_red"] == 0
    assert results[1]["away_red"] == 1


def test_fair_play_points_combine_yellow_and_red_cards():
    assert fair_play_points(0, 0) == 0
    assert fair_play_points(2, 0) == 2
    assert fair_play_points(1, 1) == 4


def test_build_snapshot_populates_fair_play_from_card_data(tmp_path):
    settings = Settings(
        data_source="openfootball",
        openfootball_season="2026-27",
        cache_dir=str(tmp_path),
    )
    snapshot = build_snapshot_from_sources(
        parse_matches(openfootball_payload()),
        parse_results(CSV_CARDS),
        settings,
        seed_ratings={
            "real madrid": 1900,
            "barcelona": 1880,
            "sevilla": 1750,
            "valencia": 1730,
        },
        previous_matches=[],
    )

    assert snapshot.fair_play["real-madrid"] == 2 + 2
    assert snapshot.fair_play["barcelona"] == 1
    assert snapshot.fair_play["sevilla"] == 3
    assert snapshot.fair_play["valencia"] == 3


def test_snapshot_version_changes_when_fair_play_changes(tmp_path):
    settings = Settings(
        data_source="openfootball",
        openfootball_season="2026-27",
        cache_dir=str(tmp_path),
    )
    base_results = parse_results(CSV_CARDS)
    more_cards = parse_results(CSV_CARDS.replace(",2,1,0,0", ",4,1,0,0"))
    seed_ratings = {
        "real madrid": 1900,
        "barcelona": 1880,
        "sevilla": 1750,
        "valencia": 1730,
    }

    first = build_snapshot_from_sources(
        parse_matches(openfootball_payload()),
        base_results,
        settings,
        seed_ratings=seed_ratings,
        previous_matches=[],
    )
    second = build_snapshot_from_sources(
        parse_matches(openfootball_payload()),
        more_cards,
        settings,
        seed_ratings=seed_ratings,
        previous_matches=[],
    )

    assert first.fair_play != second.fair_play
    assert first.data_version != second.data_version
