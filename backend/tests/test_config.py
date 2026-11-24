from pathlib import Path

from app.champions.config import ChampionsSettings
from app.config import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_settings_resolve_env_and_cache_paths_from_the_project_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    settings = Settings()
    env_file = Path(str(Settings.model_config["env_file"]))

    assert env_file == BACKEND_ROOT / ".env"
    assert env_file.is_absolute()
    assert Path(settings.cache_dir) == BACKEND_ROOT / ".cache"


def test_champions_settings_resolve_env_and_cache_paths_from_the_project_root(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    settings = ChampionsSettings()
    env_file = Path(str(ChampionsSettings.model_config["env_file"]))

    assert env_file == BACKEND_ROOT / ".env"
    assert env_file.is_absolute()
    assert Path(settings.cache_dir) == BACKEND_ROOT / ".cache"
