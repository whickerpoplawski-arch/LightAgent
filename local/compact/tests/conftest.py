"""Offline compact tests. No OpenRouter."""

from __future__ import annotations

import os

import pytest

from local.compact.recall_spill import reset_spill_store


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_FORBID_OPENROUTER", "1")
    monkeypatch.delenv("LIGHTAGENT_COMPACT_LLM", raising=False)
    monkeypatch.setenv("LIGHTAGENT_PROFILE_DB", os.devnull)
    reset_spill_store()
    yield
    reset_spill_store()
