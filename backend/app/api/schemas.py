"""Request payloads for the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ScenarioRequest(BaseModel):
    mode: Literal["score", "1x2"] = "score"
    sims: int = Field(default=10_000, ge=1, le=1_000_000)
    start_matchday: int | None = Field(default=None, ge=1, le=38)
    seed: int | None = 42
    elo_delta: dict[str, float] = Field(default_factory=dict)
    forced_results: dict[str, Literal["H", "D", "A"]] = Field(default_factory=dict)
    forced_scores: dict[str, list[int]] = Field(default_factory=dict)
    home_advantage: float | None = Field(default=None, ge=0, le=200)
    nu: float | None = Field(default=None, gt=0, le=5)
    rho: float | None = Field(default=None, ge=-0.2, le=0.2)

    @field_validator("elo_delta")
    @classmethod
    def elo_delta_must_be_reasonable(cls, value: dict[str, float]) -> dict[str, float]:
        for team_id, delta in value.items():
            if abs(delta) > 500:
                raise ValueError(f"elo delta for {team_id} is too large")
        return value

    @field_validator("forced_scores")
    @classmethod
    def scores_must_be_non_negative(cls, value: dict[str, list[int]]) -> dict[str, list[int]]:
        for match_id, score in value.items():
            if len(score) != 2 or any(goal < 0 or goal > 15 for goal in score):
                raise ValueError(f"invalid forced score for {match_id}")
        return value


class FullProjectionRequest(ScenarioRequest):
    sims: int = Field(default=1_000_000, ge=1, le=1_000_000)
