"""Offline goal tests."""

from __future__ import annotations

import pytest

from local.memory.host import MemoryHost, bind_host, reset_host
from local.memory.store import ProfileStore, set_store


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_FORBID_OPENROUTER", "1")
    monkeypatch.delenv("LIGHTAGENT_WORKSPACE", raising=False)


@pytest.fixture
def env(tmp_path):
    store = ProfileStore(tmp_path / "profile.sqlite")
    set_store(store)
    token = bind_host(MemoryHost(user_id="alice", namespace="profile", session_id="s1"))
    try:
        yield store
    finally:
        reset_host(token)
        set_store(None)
