"""Runtime configuration loaded from environment variables or .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    api_football_key: str = ""
    api_football_base_url: str = "https://v3.football.api-sports.io"
    league_id: int = 140
    season: int = 2026
    cache_dir: str = str(BASE_DIR / ".cache")
    cache_ttl_seconds: int = 21_600
    demo_played_matchdays: int = 8
    rewind_matchday: int = 0
    clubelo_enabled: bool = True
    clubelo_date: str = ""
    data_source: str = "auto"
    openfootball_season: str = "2026-27"
    previous_openfootball_season: str = "2025-26"
    football_data_season: str = "2627"
    previous_football_data_season: str = "2526"
    snapshot_ttl_seconds: int = 3_600


@lru_cache
def get_settings() -> Settings:
    return Settings()
