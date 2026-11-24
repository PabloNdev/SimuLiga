import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_champions_season_endpoint():
    response = client.get("/api/champions/season")
    assert response.status_code == 200
    payload = response.json()
    assert payload["competition"] == "Champions League"
    assert len(payload["teams"]) == 36
    assert len(payload["standings"]) == 36
    assert payload["total_matchdays"] == 8
    assert payload["demo"] is True
    assert payload["qualification_zones"]["direct"] == [1, 8]


def test_champions_projection_endpoint():
    response = client.get(
        "/api/champions/projection", params={"sims": 100, "seed": 1}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["n_sims"] == 100
    assert len(payload["teams"]) == 36
    assert all("top8_probability" in team for team in payload["teams"])
    assert "bracket" in payload["playoff"]
    assert sum(
        team["top8_probability"]
        + team["playoff_probability"]
        + team["eliminated_probability"]
        for team in payload["teams"]
    ) == pytest.approx(36.0, abs=1e-6)


def test_champions_matches_endpoint():
    response = client.get("/api/champions/matches", params={"mode": "score"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["matches"]) == 144
    pending = [match for match in payload["matches"] if match["status"] == "pending"]
    assert pending
    assert (
        pending[0]["home_probability"]
        + pending[0]["draw_probability"]
        + pending[0]["away_probability"]
    ) == pytest.approx(1.0)


def test_champions_pending_matches_have_expected_score_in_1x2_mode():
    response = client.get("/api/champions/matches", params={"mode": "1x2"})
    assert response.status_code == 200
    pending = [
        match for match in response.json()["matches"] if match["status"] == "pending"
    ]
    assert pending
    assert all(match["most_likely_score"] is not None for match in pending)


def test_champions_elo_endpoint():
    response = client.get("/api/champions/elo")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["teams"]) == 36
    assert payload["params"]["k"] == 20
    assert payload["verification"]["available"] is False


def test_champions_validation_endpoint():
    response = client.get("/api/champions/validation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["teams"] == 36
    assert "model" in payload
