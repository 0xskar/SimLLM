from __future__ import annotations

import pytest

from simllm.state import AppState


def test_require_conn_raises_when_no_save_loaded():
    state = AppState()
    with pytest.raises(RuntimeError):
        state.require_conn()


def test_require_settings_raises_when_no_save_loaded():
    state = AppState()
    with pytest.raises(RuntimeError):
        state.require_settings()
