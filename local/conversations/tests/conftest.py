"""Offline checks for multi-conversation identity. No OpenRouter."""

from __future__ import annotations

import os

import pytest

from local.memory.host import MemoryHost, bind_host, reset_host
from local.memory.store import ProfileStore, set_store

os.environ["LIGHTAGENT_FORBID_OPENROUTER"] = "1"
os.environ.pop("LIGHTAGENT_ALLOW_OPENROUTER", None)


@pytest.fixture(autouse=True)
def _forbid_network(monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_FORBID_OPENROUTER", "1")
    monkeypatch.delenv("LIGHTAGENT_ALLOW_OPENROUTER", raising=False)
    import local.openrouter_config as orc

    def _blocked(*_args, **_kwargs):
        raise AssertionError("run_free")

    monkeypatch.setattr(orc, "run_free", _blocked)
    yield


@pytest.fixture
def env(tmp_path):
    store = ProfileStore(tmp_path / "profile.sqlite")
    set_store(store)
    token = bind_host(MemoryHost(user_id="alice", namespace="profile", session_id="s1", agent_id="assistant"))
    try:
        yield store
    finally:
        reset_host(token)
        set_store(None)
