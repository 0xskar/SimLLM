from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

import simllm.config as config_module


@pytest.fixture()
def isolated_saves_dir(tmp_path, monkeypatch):
    """Redirect SAVES_DIR to a temp dir so tests never touch real saves/."""
    saves_dir = tmp_path / "saves"
    monkeypatch.setattr(config_module, "SAVES_DIR", saves_dir)

    import simllm.db.save_repo as save_repo_module

    monkeypatch.setattr(save_repo_module, "SAVES_DIR", saves_dir)
    return saves_dir
