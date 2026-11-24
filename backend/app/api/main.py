"""FastAPI application for SimuLiga."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.schemas import FullProjectionRequest, ScenarioRequest
from app.champions.api.routes import router as champions_router
from app.api.serializers import (
    TIEBREAK_RULES,
    current_matchday,
    serialize_elo,
    serialize_matches,
    serialize_model,
    serialize_projection,
    serialize_season,
)
from app.data.league import LeagueSnapshot, get_snapshot
from app.domain.davidson import DavidsonParams
from app.domain.models import Outcome
from app.domain.scoreline import ScorelineParams
from app.domain.simulation import SimulationRequest, simulate_season

app = FastAPI(title="SimuLiga API", version="0.1.0")
app.include_router(champions_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CACHE: dict[tuple, dict] = {}
_CACHE_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_SYNC_SIM_LIMIT = 200_000
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _calibration() -> dict | None:
    path = _DATA_DIR / "calibrated_params.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _teams_for_start(snapshot: LeagueSnapshot, start_matchday: int | None):
    if start_matchday is None:
        return snapshot.teams
    available = [
        matchday
        for matchday in snapshot.elo_by_matchday
        if matchday <= start_matchday
    ]
    if not available:
        return snapshot.teams
    ratings = snapshot.elo_by_matchday[max(available)]
    return [
        team.with_elo(ratings.get(team.id, team.elo)) for team in snapshot.teams
    ]


def _default_params() -> tuple[DavidsonParams, ScorelineParams]:
    calibration = _calibration()
    if calibration:
        home_advantage = float(calibration.get("home_advantage", 60.0))
        nu = float(calibration.get("nu", 0.9))
        return (
            DavidsonParams(home_advantage=home_advantage, nu=nu),
            ScorelineParams(home_advantage=home_advantage),
        )
    return DavidsonParams(), ScorelineParams()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "SimuLiga API",
        "version": app.version,
    }


@app.get("/api/ready")
def ready() -> dict:
    snapshot = get_snapshot()
    return {
        "status": "ready",
        "source": snapshot.source,
        "data_version": snapshot.data_version,
        "demo": snapshot.demo,
        "updated_at": snapshot.updated_at,
        "teams": len(snapshot.teams),
        "matches": len(snapshot.matches),
    }


@app.get("/api/season")
def season() -> dict:
    snapshot = get_snapshot()
    davidson, scoreline = _default_params()
    return serialize_season(snapshot, serialize_model(davidson, scoreline))


@app.get("/api/elo")
def elo() -> dict:
    return serialize_elo(get_snapshot())


@app.get("/api/projection")
def projection(
    mode: Literal["score", "1x2"] = "score",
    sims: int = Query(default=10_000, ge=1, le=_SYNC_SIM_LIMIT),
    seed: int = 42,
    start_matchday: int | None = Query(default=None, ge=1, le=38),
) -> dict:
    snapshot = get_snapshot()
    davidson, scoreline = _default_params()
    key = (snapshot.data_version, mode, sims, seed, start_matchday)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if cached is not None:
        return cached

    request = SimulationRequest(
        teams=_teams_for_start(snapshot, start_matchday),
        matches=snapshot.matches,
        mode=mode,
        n_sims=sims,
        seed=seed,
        davidson=davidson,
        scoreline=scoreline,
        fair_play=snapshot.fair_play,
        start_matchday=start_matchday,
    )
    result = simulate_season(request)
    payload = serialize_projection(result, snapshot)
    with _CACHE_LOCK:
        if len(_CACHE) >= 24:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = payload
    return payload


@app.post("/api/projection")
def scenario(payload: ScenarioRequest) -> dict:
    if payload.sims > _SYNC_SIM_LIMIT:
        raise HTTPException(
            status_code=422,
            detail="Para más de 200.000 simulaciones usa /api/projection/full",
        )
    snapshot = get_snapshot()
    return _run_scenario(snapshot, payload)


@app.post("/api/projection/full", status_code=202)
def full_projection(payload: FullProjectionRequest, background_tasks: BackgroundTasks):
    snapshot = get_snapshot()
    _validate_scenario(snapshot, payload)
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "status": "running",
            "created_at": time.time(),
            "result": None,
            "error": None,
            "progress": 0.0,
            "completed_sims": 0,
        }
        _trim_jobs()

    def report(done: int, total: int) -> None:
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if job is not None:
                job.update(
                    progress=(done / total) if total else 0.0,
                    completed_sims=done,
                )

    def run() -> None:
        try:
            result = _run_scenario(snapshot, payload, progress_callback=report)
            with _JOBS_LOCK:
                _JOBS[job_id].update(
                    {"status": "done", "result": result, "progress": 1.0}
                )
        except Exception as error:  # noqa: BLE001 - reported through the job
            with _JOBS_LOCK:
                _JOBS[job_id].update(
                    {
                        "status": "error",
                        "error": f"{type(error).__name__}: {error}",
                    }
                )

    background_tasks.add_task(run)
    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "running"},
    )


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return {
            "job_id": job_id,
            "status": job["status"],
            "result": job["result"],
            "error": job["error"],
            "progress": job.get("progress", 0.0),
            "completed_sims": job.get("completed_sims", 0),
            "elapsed_seconds": round(time.time() - job.get("created_at", time.time()), 1),
        }


@app.get("/api/matches")
def matches(mode: Literal["score", "1x2"] = "score") -> dict:
    snapshot = get_snapshot()
    davidson, scoreline = _default_params()
    pending = [match for match in snapshot.matches if not match.is_played]
    return {
        "source": snapshot.source,
        "data_version": snapshot.data_version,
        "mode": mode,
        "current_matchday": current_matchday(snapshot),
        "matches": serialize_matches(snapshot, mode, davidson, scoreline),
    }


@app.get("/api/validation")
def validation() -> dict:
    snapshot = get_snapshot()
    davidson, scoreline = _default_params()
    calibration = _calibration()
    metrics = calibration.get("validation") if calibration else None
    if not isinstance(metrics, dict):
        metrics = None

    if metrics is not None:
        status = "ok"
        season = metrics.get("season", "histórica")
        message = (
            f"Validación temporal sobre la temporada {season} con resultados reales."
        )
    elif snapshot.demo:
        status = "demo"
        message = (
            "La app está usando datos de demostración y aún no hay métricas de "
            "validación disponibles."
        )
    else:
        status = "pending_historical_validation"
        message = "La validación se calcula al cargar el histórico de resultados."

    return {
        "status": status,
        "message": message,
        "metrics": metrics,
        "calibration": {
            "trained_on": calibration.get("trained_on") if calibration else None,
            "fit_on": calibration.get("fit_on") if calibration else None,
            "generated_at": calibration.get("generated_at") if calibration else None,
        },
        "model": serialize_model(davidson, scoreline),
        "data": {
            "source": snapshot.source,
            "data_version": snapshot.data_version,
            "teams": len(snapshot.teams),
            "matches": len(snapshot.matches),
            "played": sum(1 for match in snapshot.matches if match.is_played),
        },
        "tiebreak_rules": TIEBREAK_RULES,
    }


def _run_scenario(
    snapshot: LeagueSnapshot,
    payload: ScenarioRequest,
    progress_callback=None,
) -> dict:
    _validate_scenario(snapshot, payload)
    davidson, scoreline = _parameters(payload)
    request = SimulationRequest(
        teams=_teams_for_start(snapshot, payload.start_matchday),
        matches=snapshot.matches,
        mode=payload.mode,
        n_sims=payload.sims,
        seed=payload.seed,
        davidson=davidson,
        scoreline=scoreline,
        elo_delta=payload.elo_delta,
        forced_results={
            match_id: outcome for match_id, outcome in payload.forced_results.items()
        },
        forced_scores={
            match_id: (score[0], score[1])
            for match_id, score in payload.forced_scores.items()
        },
        fair_play=snapshot.fair_play,
        progress_callback=progress_callback,
        start_matchday=payload.start_matchday,
    )
    result = simulate_season(request)
    return serialize_projection(result, snapshot)


def _parameters(payload: ScenarioRequest) -> tuple[DavidsonParams, ScorelineParams]:
    default_davidson, default_scoreline = _default_params()
    davidson = DavidsonParams(
        home_advantage=payload.home_advantage
        if payload.home_advantage is not None
        else default_davidson.home_advantage,
        nu=payload.nu if payload.nu is not None else default_davidson.nu,
    )
    scoreline = ScorelineParams(
        home_advantage=payload.home_advantage
        if payload.home_advantage is not None
        else default_scoreline.home_advantage,
        rho=payload.rho if payload.rho is not None else default_scoreline.rho,
    )
    return davidson, scoreline


def _validate_scenario(snapshot: LeagueSnapshot, payload: ScenarioRequest) -> None:
    team_ids = {team.id for team in snapshot.teams}
    unknown_teams = sorted(set(payload.elo_delta) - team_ids)
    if unknown_teams:
        raise HTTPException(
            status_code=422,
            detail=f"Equipos desconocidos: {', '.join(unknown_teams)}",
        )
    match_map = {match.id: match for match in snapshot.matches}
    for match_id in payload.forced_results:
        if match_id not in match_map:
            raise HTTPException(status_code=422, detail=f"Partido desconocido: {match_id}")
        if match_map[match_id].is_played:
            raise HTTPException(
                status_code=422,
                detail=f"El partido {match_id} ya se jugó y no se puede forzar",
            )
    for match_id in payload.forced_scores:
        if match_id not in match_map:
            raise HTTPException(status_code=422, detail=f"Partido desconocido: {match_id}")
        if match_map[match_id].is_played:
            raise HTTPException(
                status_code=422,
                detail=f"El partido {match_id} ya se jugó y no se puede forzar",
            )


def _trim_jobs() -> None:
    if len(_JOBS) <= 20:
        return
    finished = sorted(
        (job_id, job) for job_id, job in _JOBS.items() if job["status"] != "running"
    )
    for job_id, _ in finished[: len(_JOBS) - 20]:
        _JOBS.pop(job_id, None)
