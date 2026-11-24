"""Domain entities for the Champions League module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.domain.models import Outcome

Phase = Literal["league", "playoff", "r16", "qf", "sf", "final"]


@dataclass(frozen=True)
class ChampionsTeam:
    id: str
    name: str
    short_name: str
    color: str
    country: str
    elo: float
    pot: int | None = None
    coefficient: float | None = None

    def with_elo(self, elo: float) -> "ChampionsTeam":
        return ChampionsTeam(
            id=self.id,
            name=self.name,
            short_name=self.short_name,
            color=self.color,
            country=self.country,
            elo=elo,
            pot=self.pot,
            coefficient=self.coefficient,
        )


@dataclass(frozen=True)
class ChampionsMatch:
    id: str
    phase: Phase
    matchday: int
    leg: int
    home_id: str
    away_id: str
    home_goals: int | None = None
    away_goals: int | None = None
    kickoff: str | None = None
    neutral: bool = False

    @property
    def has_score(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    @property
    def is_played(self) -> bool:
        return self.result is not None

    @property
    def result(self) -> Outcome | None:
        if not self.has_score:
            return None
        assert self.home_goals is not None and self.away_goals is not None
        if self.home_goals > self.away_goals:
            return "H"
        if self.home_goals < self.away_goals:
            return "A"
        return "D"

    def with_score(self, home_goals: int, away_goals: int) -> "ChampionsMatch":
        return ChampionsMatch(
            id=self.id,
            phase=self.phase,
            matchday=self.matchday,
            leg=self.leg,
            home_id=self.home_id,
            away_id=self.away_id,
            home_goals=home_goals,
            away_goals=away_goals,
            kickoff=self.kickoff,
            neutral=self.neutral,
        )

    def as_pending(self) -> "ChampionsMatch":
        return ChampionsMatch(
            id=self.id,
            phase=self.phase,
            matchday=self.matchday,
            leg=self.leg,
            home_id=self.home_id,
            away_id=self.away_id,
            kickoff=self.kickoff,
            neutral=self.neutral,
        )


@dataclass(frozen=True)
class ChampionsSnapshot:
    competition: str
    season: str
    source: str
    updated_at: str
    teams: list[ChampionsTeam]
    matches: list[ChampionsMatch]
    data_version: str
    demo: bool
    data_note: str | None
    elo_by_matchday: dict[int, dict[str, float]] = field(default_factory=dict)
    elo_history: dict = field(default_factory=dict)
    elo_verification: dict = field(default_factory=dict)
    elo_timeline: dict = field(default_factory=dict)
    model: dict = field(default_factory=dict)
    target_season: str | None = None
    fallback: bool = False
