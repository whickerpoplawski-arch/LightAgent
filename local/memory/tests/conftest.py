"""Offline tests for the profile memory foundation. No network."""

from __future__ import annotations

import pytest

from local.memory.host import bind_host, reset_host
from local.memory.store import ProfileStore, set_store


@pytest.fixture
def env(tmp_path):
    store = ProfileStore(tmp_path / "profile.sqlite")
    set_store(store)
    from local.memory.host import MemoryHost

    token = bind_host(MemoryHost(user_id="alice", namespace="profile", session_id="s1", agent_id="assistant"))
    try:
        yield store
    finally:
        reset_host(token)
        set_store(None)