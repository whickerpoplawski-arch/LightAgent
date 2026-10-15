"""Room tests stay offline. OpenRouter is forbidden unless a test opts in."""

from __future__ import annotations

import os

import pytest

os.environ["LIGHTAGENT_FORBID_OPENROUTER"] = "1"
os.environ.pop("LIGHTAGENT_ALLOW_OPENROUTER", None)
os.environ.pop("LIGHTAGENT_ROOM_HOST_LLM", None)


@pytest.fixture(autouse=True)
def _forbid_network(monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_FORBID_OPENROUTER", "1")
    monkeypatch.delenv("LIGHTAGENT_WORKSPACE", raising=False)
    monkeypatch.delenv("LIGHTAGENT_ALLOW_OPENROUTER", raising=False)
    monkeypatch.delenv("LIGHTAGENT_ROOM_HOST_LLM", raising=False)
    import local.openrouter_config as orc

    def _blocked(*_args, **_kwargs):
        raise AssertionError("run_free")

    monkeypatch.setattr(orc, "run_free", _blocked)
    yield
