import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_season_payload_contains_teams_standings_and_metadata():
    response = client.get("/api/season")
    assert response.status_code == 200
    payload = response.json()
    assert payload["competition"] == "LaLiga"
    assert payload["season"] == "2026/27"
    assert payload["source"] == "demo"
    assert len(payload["teams"]) == 20
    assert len(payload["standings"]) == 20
    assert payload["current_matchday"] == 9
    assert payload["played_matches"] == 80
    assert payload["pending_matches"] == 300
    assert payload["standings"][0]["position"] == 1
    assert payload["model"]["davidson"]["nu"] > 0
    assert len(payload["tiebreak_rules"]) >= 5


def test_elo_endpoint_lists_ratings_with_start_and_delta():
    response = client.get("/api/elo")
    assert response.status_code == 200
    payload = response.json()
    assert payload["season"] == "2026/27"
    assert payload["source"] == "demo"
    assert payload["params"]["k"] == 20
    assert payload["params"]["home_advantage"] == 60
    assert payload["params"]["start_rating"] == 1500
    assert len(payload["teams"]) == 20

    ratings = [team["elo"] for team in payload["teams"]]
    assert ratings == sorted(ratings, reverse=True)
    assert [team["position"] for team in payload["teams"]] == list(range(1, 21))
    assert sum(team["played"] for team in payload["teams"]) == 2 * payload["played_matches"]
    assert any(team["delta"] != 0 for team in payload["teams"])
    for team in payload["teams"]:
        assert team["elo"] == pytest.approx(team["start_elo"] + team["delta"], abs=0.2)
    assert payload["history"]["seasons"] == []
    assert payload["history"]["series"] == []
    assert payload["verification"]["available"] is False
    assert payload["timeline"]["dates"] == []
    assert payload["timeline"]["series"] == []


def test_projection_returns_probabilities_and_predictions():
    response = client.get("/api/projection", params={"mode": "score", "sims": 1000})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "score"
    assert payload["n_sims"] == 1000
    assert len(payload["teams"]) == 20
    assert len(payload["match_predictions"]) == 300
    assert sum(team["champion_probability"] for team in payload["teams"]) == pytest.approx(
        1.0, abs=1e-6
    )
    assert payload["goals_available"] is True


def test_1x2_projection_has_no_scoreline_fields():
    response = client.get("/api/projection", params={"mode": "1x2", "sims": 500})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "1x2"
    assert payload["goals_available"] is False
    assert all(
        prediction["most_likely_score"] is None
        for prediction in payload["match_predictions"]
    )


def test_scenario_endpoint_applies_elo_overrides():
    baseline = client.get("/api/projection", params={"mode": "score", "sims": 1200, "seed": 5})
    scenario = client.post(
        "/api/projection",
        json={
            "mode": "score",
            "sims": 1200,
            "seed": 5,
            "elo_delta": {"real-madrid": 220, "malaga": -120},
        },
    )
    assert scenario.status_code == 200
    scenario_payload = scenario.json()
    baseline_payload = baseline.json()
    baseline_team = next(
        team for team in baseline_payload["teams"] if team["team"]["id"] == "real-madrid"
    )
    scenario_team = next(
        team for team in scenario_payload["teams"] if team["team"]["id"] == "real-madrid"
    )
    assert scenario_team["champion_probability"] > baseline_team["champion_probability"]


def test_scenario_endpoint_rejects_unknown_team():
    response = client.post(
        "/api/projection",
        json={"mode": "score", "sims": 100, "elo_delta": {"nope": 50}},
    )
    assert response.status_code == 422


def test_matches_endpoint_lists_pending_and_played_games():
    response = client.get("/api/matches", params={"mode": "score"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["matches"]) == 380
    pending = [match for match in payload["matches"] if match["status"] == "pending"]
    assert len(pending) == 300
    assert pending[0]["home_probability"] + pending[0]["draw_probability"] + pending[0][
        "away_probability"
    ] == pytest.approx(1.0)


def test_full_projection_job_completes():
    created = client.post(
        "/api/projection/full",
        json={"mode": "score", "sims": 600, "seed": 3},
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]

    status = client.get(f"/api/jobs/{job_id}")
    assert status.status_code == 200
    payload = status.json()
    assert payload["status"] == "done"
    assert len(payload["result"]["teams"]) == 20
    assert payload["progress"] == pytest.approx(1.0)
    assert payload["completed_sims"] == 600
    assert payload["elapsed_seconds"] >= 0

def test_projection_start_matchday_one_has_no_base_points():
    response = client.get(
        "/api/projection",
        params={"mode": "score", "sims": 400, "start_matchday": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["start_matchday"] == 1
    assert len(payload["base_standings"]) == 20
    assert all(row["points"] == 0 for row in payload["base_standings"])
    assert payload["base_played_matches"] == 0


def test_projection_start_matchday_keeps_previous_results():
    response = client.get(
        "/api/projection",
        params={"mode": "score", "sims": 400, "start_matchday": 9},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["start_matchday"] == 9
    assert payload["base_played_matches"] == 80
    assert sum(row["points"] for row in payload["base_standings"]) > 0


def test_scenario_accepts_start_matchday():
    response = client.post(
        "/api/projection",
        json={"mode": "score", "sims": 300, "start_matchday": 1, "seed": 9},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["start_matchday"] == 1
    assert all(row["points"] == 0 for row in payload["base_standings"])


def test_scenario_without_model_overrides_matches_baseline_projection():
    params = {
        "mode": "score",
        "sims": 700,
        "seed": 11,
        "start_matchday": 9,
    }
    baseline = client.get("/api/projection", params=params)
    scenario = client.post("/api/projection", json=params)

    assert baseline.status_code == 200
    assert scenario.status_code == 200

    baseline_teams = {team["team"]["id"]: team for team in baseline.json()["teams"]}
    scenario_teams = {team["team"]["id"]: team for team in scenario.json()["teams"]}

    for team_id, expected in baseline_teams.items():
        actual = scenario_teams[team_id]
        assert actual["champion_probability"] == pytest.approx(
            expected["champion_probability"], abs=1e-9
        )
        assert actual["top4_probability"] == pytest.approx(
            expected["top4_probability"], abs=1e-9
        )
        assert actual["relegation_probability"] == pytest.approx(
            expected["relegation_probability"], abs=1e-9
        )
        assert actual["expected_points"] == pytest.approx(
            expected["expected_points"], abs=1e-9
        )


def test_validation_returns_calibration_and_historical_metrics():
    response = client.get("/api/validation")
    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    metrics = payload["metrics"]
    assert metrics is not None
    assert metrics["season"] == 2024
    assert metrics["matches"] == 380
    assert 0 < metrics["accuracy"] < 1
    assert metrics["log_loss"] > 0
    assert metrics["brier"] > 0

    calibration = payload["calibration"]
    assert calibration["trained_on"]
    assert calibration["generated_at"]


def test_health_does_not_load_the_league_snapshot(monkeypatch):
    import app.api.main as main

    def explode(*args, **kwargs):
        raise AssertionError("health must not load the snapshot")

    monkeypatch.setattr(main, "get_snapshot", explode)
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "SimuLiga API"


def test_ready_reports_snapshot_metadata():
    response = client.get("/api/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["source"] == "demo"
    assert payload["teams"] == 20
    assert payload["matches"] == 380
    assert payload["data_version"]
