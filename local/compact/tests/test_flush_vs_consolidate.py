"""Flush writes profile or a pin. It does not run consolidate or keep the pack."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from local.compact.flush import memory_flush
from local.compact.pipeline import run_compact
from local.memory.host import MemoryHost
from local.memory.store import ProfileStore


@pytest.fixture
def profile(tmp_path):
    store = ProfileStore(tmp_path / "profile.sqlite")
    host = MemoryHost(user_id="alice", namespace="profile", space_id="home", session_id="s1")
    return SimpleNamespace(store=store, host=host)


def _summary() -> str:
    return "\n".join([
        "## 当前目标",
        "无",
        "## 未决问题（必须逐条保留用户原问意图）",
        "无",
        "## 近期拍板（尽量 verbatim 引用用户原句中的时间/数字/专名）",
        "无",
        "## 禁止事项（否决、Never、忌口——宁缺勿写错）",
        "素食",
        "## 工具指针（仅 ref/sha，禁止粘贴网页正文）",
        "无",
    ])


def test_flush_writes_profile_and_pin_without_calling_run_due(profile, monkeypatch):
    calls = {"n": 0}

    def _forbid_run_due(*_args, **_kwargs):
        calls["n"] += 1
        raise AssertionError("flush must not call run_due")

    monkeypatch.setattr("local.memory.jobs.run_due", _forbid_run_due)
    messages = [
        {"role": "system", "content": "policy\n<memory-context>SECRET_PACK</memory-context>"},
        {"role": "user", "content": "我素食\n<memory-context>SECRET_PACK</memory-context>"},
    ]
    outcome = run_compact(
        messages,
        trigger="manual",
        summarizer=lambda _prompt, _removed: _summary(),
        store=profile.store,
        host=profile.host,
        space_id="home",
    )
    rows = profile.store.list_learnings(user_id="alice", namespace="profile", include_candidates=True)
    saved = [row for row in rows if "素食" in row.text]
    assert saved
    assert all("SECRET_PACK" not in row.text and "<memory-context>" not in row.text for row in rows)
    blob = json.dumps(outcome.messages, ensure_ascii=False)
    assert "SECRET_PACK" not in blob
    assert "<memory-context>" not in blob
    assert outcome.pinned_count >= 1
    assert calls["n"] == 0
    assert profile.store.list_jobs() == []


def test_flush_appends_a_daily_note_and_leaves_consolidate_queued(profile):
    messages = [{"role": "user", "content": "明天9点体检"}]
    report = memory_flush(
        messages,
        store=profile.store,
        host=profile.host,
        space_id="home",
        today=date(2026, 10, 15),
    )
    assert any("体检" in str(item.get("text") or "") for item in report["written"])
    note = profile.store.path.parent / "daily" / "2026-10-15.md"
    body = note.read_text(encoding="utf-8")
    assert "体检" in body
    assert "<memory-context>" not in body
    assert profile.store.list_jobs() == []
