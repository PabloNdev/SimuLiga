from app.config import Settings
from app.data.api_football import _fetch_fixtures, build_snapshot_from_fixtures
from app.data.clubelo import parse_clubelo_csv


def fixture(fixture_id, matchday, home, away, home_goals, away_goals, status="FT"):
    return {
        "fixture": {
            "id": fixture_id,
            "date": f"2024-08-{10 + matchday:02d}T18:00:00+00:00",
            "status": {"short": status},
        },
        "league": {"round": f"Regular Season - {matchday}"},
        "teams": {
            "home": {"name": home},
            "away": {"name": away},
        },
        "goals": {"home": home_goals, "away": away_goals},
    }


def settings(tmp_path, rewind=1):
    return Settings(
        api_football_key="test-key",
        season=2024,
        rewind_matchday=rewind,
        cache_dir=str(tmp_path),
    )


def test_parse_clubelo_csv_reads_normalized_ratings():
    csv = (
        "Rank,Club,Country,Level,Elo,From,To\n"
        "1,Real Madrid,ESP,1,1950,2024-08-14,2024-08-15\n"
        "2,Atletico Madrid,ESP,1,1880,2024-08-14,2024-08-15\n"
    )
    ratings = parse_clubelo_csv(csv)
    assert ratings["real madrid"] == 1950
    assert ratings["atletico madrid"] == 1880


def test_build_snapshot_rewinds_completed_season_to_requested_matchday(tmp_path):
    fixtures = [
        fixture(1, 1, "Real Madrid", "Barcelona", 2, 1),
        fixture(2, 1, "Sevilla", "Valencia", 1, 0),
        fixture(3, 2, "Barcelona", "Sevilla", 1, 1),
        fixture(4, 2, "Valencia", "Real Madrid", 0, 2),
    ]
    ratings = {"real madrid": 1950, "barcelona": 1940, "sevilla": 1740, "valencia": 1720}
    snapshot = build_snapshot_from_fixtures(fixtures, settings(tmp_path), ratings)

    assert snapshot.season == "2024/25"
    assert snapshot.source == "api-football"
    assert snapshot.demo is False
    assert "jornadas 1–1" in (snapshot.data_note or "")
    played = [match for match in snapshot.matches if match.is_played]
    pending = [match for match in snapshot.matches if not match.is_played]
    assert len(played) == 2
    assert len(pending) == 2
    assert all(match.matchday == 1 for match in played)
    assert all(match.matchday == 2 for match in pending)

    team_map = {team.id: team for team in snapshot.teams}
    assert team_map["real-madrid"].elo > 1950
    assert team_map["barcelona"].elo < 1940


def test_fetch_fixtures_follows_pagination(monkeypatch, tmp_path):
    calls = []
    pages = {
        1: [fixture(1, 1, "Real Madrid", "Barcelona", 2, 1)],
        2: [fixture(2, 1, "Sevilla", "Valencia", 1, 0)],
    }

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, headers, params, timeout):
        page = params.get("page", 1)
        calls.append(page)
        return FakeResponse(
            {
                "errors": [],
                "paging": {"current": page, "total": 2},
                "response": pages[page],
            }
        )

    monkeypatch.setattr("app.data.api_football.httpx.get", fake_get)
    fixtures = _fetch_fixtures(settings(tmp_path, rewind=0))
    assert calls == [1, 2]
    assert len(fixtures) == 2
