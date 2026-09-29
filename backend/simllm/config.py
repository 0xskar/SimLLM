from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from simllm.models.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "default_settings.json"
SAVES_DIR = REPO_ROOT / "saves"
LOGS_DIR = REPO_ROOT / "logs"
FRONTEND_DIST_DIR = REPO_ROOT / "frontend" / "dist"


@lru_cache(maxsize=1)
def load_default_settings_dict() -> dict:
    with open(DEFAULT_SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def default_settings() -> Settings:
    return Settings.model_validate(load_default_settings_dict())
