"""Runtime configuration for the Champions League module."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import BASE_DIR


class ChampionsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHAMPIONS_", env_file=str(BASE_DIR / ".env"), extra="ignore"
    )

    league_id: int = 2
    season: int = 2026
    previous_season: int = 2025
    data_source: str = "auto"
    clubelo_date_2025: str = "2025-08-01"
    clubelo_date_2026: str = "2026-08-01"
    cache_dir: str = str(BASE_DIR / ".cache")
    cache_ttl_seconds: int = 21_600
    snapshot_ttl_seconds: int = 3_600
    api_football_key: str = ""
    fallback_rewind_matchday: int = 4
    clubelo_enabled: bool = True
    history_seasons: int = 5
    season_regression: float = 0.20
    clubelo_prior_weight: float = 0.75

    @property
    def resolved_api_key(self) -> str:
        if self.api_football_key:
            return self.api_football_key
        from app.config import get_settings

        return get_settings().api_football_key


@lru_cache
def get_champions_settings() -> ChampionsSettings:
    return ChampionsSettings()
