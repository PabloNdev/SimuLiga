"""Core domain entities shared by the models and the simulation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Outcome = Literal["H", "D", "A"]


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    short_name: str
    color: str
    elo: float

    def with_elo(self, elo: float) -> "Team":
        return Team(
            id=self.id,
            name=self.name,
            short_name=self.short_name,
            color=self.color,
            elo=elo,
        )


@dataclass(frozen=True)
class Match:
    id: str
    matchday: int
    home_id: str
    away_id: str
    home_goals: int | None = None
    away_goals: int | None = None
    outcome: Outcome | None = None
    kickoff: str | None = None

    @property
    def has_score(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    @property
    def is_played(self) -> bool:
        return self.result is not None

    @property
    def result(self) -> Outcome | None:
        if self.outcome is not None:
            return self.outcome
        if not self.has_score:
            return None
        if self.home_goals > self.away_goals:
            return "H"
        if self.home_goals < self.away_goals:
            return "A"
        return "D"

    def with_outcome(self, outcome: Outcome) -> "Match":
        return Match(
            id=self.id,
            matchday=self.matchday,
            home_id=self.home_id,
            away_id=self.away_id,
            home_goals=self.home_goals,
            away_goals=self.away_goals,
            outcome=outcome,
            kickoff=self.kickoff,
        )

    def as_pending(self) -> "Match":
        return Match(
            id=self.id,
            matchday=self.matchday,
            home_id=self.home_id,
            away_id=self.away_id,
            home_goals=None,
            away_goals=None,
            outcome=None,
            kickoff=self.kickoff,
        )

    def with_score(self, home_goals: int, away_goals: int) -> "Match":
        return Match(
            id=self.id,
            matchday=self.matchday,
            home_id=self.home_id,
            away_id=self.away_id,
            home_goals=home_goals,
            away_goals=away_goals,
            outcome=None,
            kickoff=self.kickoff,
        )
