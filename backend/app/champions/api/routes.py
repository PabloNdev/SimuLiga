"""FastAPI routes for SimuChampions."""

from __future__ import annotations

import threading
from typing import Literal

from fastapi import APIRouter, Query

from app.champions.api.serializers import (
    current_matchday,
    serialize_elo,
    serialize_matches,
    serialize_projection,
    serialize_season,
    serialize_validation,
)
from app.champions.data.snapshot import get_champions_snapshot
from app.champions.domain.simulation import (
    ChampionsSimulationRequest,
    simulate_champions,
)
from app.domain.davidson import DavidsonParams
from app.domain.scoreline import ScorelineParams

router = APIRouter(prefix="/api/champions", tags=["champions"])

_CACHE: dict[tuple, dict] = {}
_CACHE_LOCK = threading.Lock()
_SYNC_SIM_LIMIT = 100_000


def _params(snapshot) -> tuple[DavidsonParams, ScorelineParams]:
    model = snapshot.model or {}
    davidson = model.get("davidson", {})
    scoreline = model.get("scoreline", {})
    return (
        DavidsonParams(
            home_advantage=float(davidson.get("home_advantage", 60.0)),
            nu=float(davidson.get("nu", 0.9)),
        ),
        ScorelineParams(
            home_advantage=float(scoreline.get("home_advantage", 60.0)),
            home_base=float(scoreline.get("home_base", 1.45)),
            away_base=float(scoreline.get("away_base", 1.15)),
            elo_slope=float(scoreline.get("elo_slope", 0.0018)),
            rho=float(scoreline.get("rho", -0.05)),
            max_goals=int(scoreline.get("max_goals", 10)),
        ),
    )


@router.get("/season")
def season() -> dict:
    return serialize_season(get_champions_snapshot())


@router.get("/projection")
def projection(
    mode: Literal["score", "1x2"] = "score",
    sims: int = Query(default=10_000, ge=1, le=_SYNC_SIM_LIMIT),
    seed: int = 42,
) -> dict:
    snapshot = get_champions_snapshot()
    davidson, scoreline = _params(snapshot)
    key = (snapshot.data_version, mode, sims, seed)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if cached is not None:
        return cached

    result = simulate_champions(
        ChampionsSimulationRequest(
            teams=snapshot.teams,
            matches=snapshot.matches,
            mode=mode,
            n_sims=sims,
            seed=seed,
            davidson=davidson,
            scoreline=scoreline,
        )
    )
    payload = serialize_projection(result, snapshot)
    with _CACHE_LOCK:
        if len(_CACHE) >= 24:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = payload
    return payload


@router.get("/matches")
def matches(mode: Literal["score", "1x2"] = "score") -> dict:
    snapshot = get_champions_snapshot()
    davidson, scoreline = _params(snapshot)
    return {
        "source": snapshot.source,
        "demo": snapshot.demo,
        "fallback": snapshot.fallback,
        "data_note": snapshot.data_note,
        "data_version": snapshot.data_version,
        "mode": mode,
        "current_matchday": current_matchday(snapshot),
        "matches": serialize_matches(snapshot, mode, davidson, scoreline),
    }


@router.get("/elo")
def elo() -> dict:
    return serialize_elo(get_champions_snapshot())


@router.get("/validation")
def validation() -> dict:
    return serialize_validation(get_champions_snapshot())
