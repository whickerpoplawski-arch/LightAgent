"""L-P0-1: run_due folds near-duplicates and same-topic diet rows. No model calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from local.constraints.card import ConstraintCard, ConstraintItem, ConstraintStore, active_texts, topic_key
from local.memory.consolidate import normalize_text
from local.memory.editor import MemoryEditor
from local.memory.host import MemoryHost
from local.memory.jobs import enqueue, run_due
from local.memory.pack import build_for_turn
from local.memory.store import ProfileStore

_ROOT = Path(__file__).resolve().parents[3]


def _stamp(store: ProfileStore, learning_id: str, when: str) -> None:
    with store._lock, store._connect() as conn:
        conn.execute(
            "UPDATE learnings SET updated_at = ?, created_at = ? WHERE id = ?",
            (when, when, learning_id),
        )
        conn.commit()


def _learn(store: ProfileStore, text: str, when: str, *, user_id: str = "alice", facet: str = "veto"):
    saved = store.learn(text, user_id=user_id, namespace="profile", lane="general", facet=facet)
    assert saved.learning is not None, saved.reason
    _stamp(store, saved.learning.id, when)
    return saved.learning


def _active(store: ProfileStore, user_id: str = "alice"):
    return [
        row for row in store.list_learnings(user_id=user_id, namespace="profile")
        if row.status == "active"
    ]


def test_enqueue_requires_a_life_user_id(env):
    with pytest.raises(ValueError):
        enqueue(env, "consolidate", {"reason": "x"}, user_id=" ")


def test_same_topic_learnings_supersede_and_keep_both_rows(env, tmp_path):
    older = _learn(env, "忌口：海鲜", "2026-01-01T00:00:00+00:00")
    newer = _learn(env, "别再给我虾", "2026-02-01T00:00:00+00:00")
    job_id = enqueue(env, "consolidate", {"reason": "topic"}, user_id="alice")
    due = run_due(env, workspace=tmp_path)
    assert due[0]["job_id"] == job_id
    assert due[0]["status"] == "done"
    assert due[0]["reason"] == "folded"
    rows = env.list_learnings(user_id="alice", namespace="profile")
    assert len(rows) == 2
    by_id = {row.id: row for row in rows}
    assert by_id[older.id].status == "superseded"
    assert by_id[older.id].injectable is False
    assert "superseded_by:" in (by_id[older.id].evidence or "")
    assert by_id[newer.id].status == "active"
    assert by_id[newer.id].text == "别再给我虾"
    active = _active(env)
    assert len(active) == 1
    assert topic_key(active[0].text) == "seafood"

    payload = json.loads(env.list_jobs()[0]["payload"])
    assert payload["before"]["learnings"]
    assert payload["after"]["learnings"]
    assert payload["diff"]["learnings"]["superseded"][0]["id"] == older.id
    pack = build_for_turn(env, MemoryHost(user_id="alice"), query="晚饭")
    assert "别再给我虾" in pack.markdown
    assert "忌口：海鲜" not in pack.markdown
    shown = [row["text"] for row in MemoryEditor(env).list_rows()]
    assert shown == ["别再给我虾"]


def test_near_duplicate_text_merges_to_one_active_learning(env, tmp_path):
    _learn(env, "忌口：海鲜", "2026-01-01T00:00:00+00:00")
    keeper = _learn(env, "忌口:  海鲜", "2026-03-01T00:00:00+00:00")
    assert normalize_text("忌口：海鲜") == normalize_text("忌口:  海鲜")
    due = run_due(env, workspace=tmp_path)
    assert due == []
    enqueue(env, user_id="alice")
    due = run_due(env, workspace=tmp_path)
    assert due[0]["status"] == "done"
    active = _active(env)
    assert len(active) == 1
    assert active[0].id == keeper.id
    assert len(env.list_learnings(user_id="alice", namespace="profile")) == 2


def test_distinct_preferences_stay(env, tmp_path):
    _learn(env, "忌口：海鲜", "2026-01-01T00:00:00+00:00")
    _learn(env, "忌口：乳糖", "2026-01-02T00:00:00+00:00")
    _learn(env, "喜欢靠窗", "2026-01-03T00:00:00+00:00", facet="life")
    enqueue(env, user_id="alice")
    due = run_due(env, workspace=tmp_path)
    assert due[0]["status"] == "skipped"
    assert due[0]["reason"] == "nothing_to_fold"
    texts = sorted(row.text for row in _active(env))
    assert texts == ["喜欢靠窗", "忌口：乳糖", "忌口：海鲜"]
    reasons = {item["reason"] for item in due[0]["diff"]["learnings"]["skipped"]}
    assert "distinct" in reasons


def test_pin_and_pinned_mark_are_not_rewritten(env, tmp_path):
    nick = _learn(env, "叫我小Q", "2026-01-01T00:00:00+00:00", facet="identity")
    env.pin(nick.id, user_id="alice", namespace="profile", pinned=True)
    _stamp(env, nick.id, "2026-01-01T00:00:00+00:00")
    marked = _learn(env, "座位 [PINNED] 靠窗", "2026-01-02T00:00:00+00:00", facet="life")
    _learn(env, "忌口：海鲜", "2026-01-03T00:00:00+00:00")
    _learn(env, "别再给我虾", "2026-01-04T00:00:00+00:00")
    before_pin = env.get(nick.id, user_id="alice", namespace="profile")
    before_mark = env.get(marked.id, user_id="alice", namespace="profile")
    enqueue(env, user_id="alice")
    due = run_due(env, workspace=tmp_path)
    assert due[0]["status"] == "done"
    pin = env.get(nick.id, user_id="alice", namespace="profile")
    mark = env.get(marked.id, user_id="alice", namespace="profile")
    assert pin.text == "叫我小Q"
    assert pin.pinned is True
    assert pin.status == "active"
    assert pin.updated_at == before_pin.updated_at
    assert mark.text == before_mark.text
    assert mark.status == "active"
    assert mark.updated_at == before_mark.updated_at
    seafood = [row for row in _active(env) if topic_key(row.text) == "seafood"]
    assert len(seafood) == 1
    assert seafood[0].text == "别再给我虾"


def test_other_user_rows_stay_untouched(env, tmp_path):
    _learn(env, "忌口：海鲜", "2026-01-01T00:00:00+00:00")
    _learn(env, "别再给我虾", "2026-02-01T00:00:00+00:00")
    bob = _learn(env, "忌口：花生", "2026-02-01T00:00:00+00:00", user_id="bob")
    enqueue(env, user_id="alice")
    run_due(env, workspace=tmp_path)
    bob_row = env.get(bob.id, user_id="bob", namespace="profile")
    assert bob_row.status == "active"
    assert bob_row.text == "忌口：花生"
    assert len(env.list_learnings(user_id="bob", namespace="profile")) == 1


def test_duplicate_diet_card_folds_to_one_active_row(env, tmp_path):
    ConstraintStore(tmp_path).save(ConstraintCard(items=[
        ConstraintItem(id="old", text="忌口：海鲜", status="active", updated_at="2026-01-01T00:00:00+00:00", topic="seafood"),
        ConstraintItem(id="new", text="别再给我虾", status="active", updated_at="2026-02-01T00:00:00+00:00", topic="seafood"),
        ConstraintItem(id="milk", text="忌口：乳糖", status="active", updated_at="2026-02-01T00:00:00+00:00", topic="dairy"),
    ]))
    enqueue(env, user_id="alice")
    due = run_due(env, workspace=tmp_path)
    assert due[0]["status"] == "done"
    card = ConstraintStore(tmp_path).load()
    assert len(card.items) == 3
    assert active_texts(card) == ["别再给我虾", "忌口：乳糖"]
    old = next(item for item in card.items if item.id == "old")
    assert old.status == "superseded"
    payload = json.loads(env.list_jobs()[0]["payload"])
    assert payload["diff"]["constraints"]["superseded"]
    assert payload["before"]["constraints"]
    assert any(item["status"] == "superseded" for item in payload["after"]["constraints"])


def test_near_duplicate_card_rows_collapse(env, tmp_path):
    ConstraintStore(tmp_path).save(ConstraintCard(items=[
        ConstraintItem(id="a", text="忌口：海鲜", status="active", updated_at="2026-01-01T00:00:00+00:00", topic="seafood"),
        ConstraintItem(id="b", text="忌口:  海鲜", status="active", updated_at="2026-03-01T00:00:00+00:00", topic="seafood"),
    ]))
    enqueue(env, user_id="alice")
    due = run_due(env, workspace=tmp_path)
    assert due[0]["status"] == "done"
    card = ConstraintStore(tmp_path).load()
    assert [item.text for item in card.items if item.status == "active"] == ["忌口:  海鲜"]
    assert any(item.id == "a" and item.status == "superseded" for item in card.items)


def test_missing_user_id_does_not_fold(env, tmp_path):
    saved = env.learn("忌口：海鲜", user_id="alice", namespace="profile", facet="veto")
    with env._lock, env._connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, kind, payload, status, created_at, user_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("jobmissing01", "consolidate", "{}", "queued", "2026-01-01T00:00:00+00:00", "", ""),
        )
        conn.commit()
    due = run_due(env, workspace=tmp_path)
    assert due[0]["job_id"] == "jobmissing01"
    assert due[0]["status"] == "skipped"
    assert due[0]["reason"] == "missing_user_id"
    row = env.get(saved.learning.id, user_id="alice", namespace="profile")
    assert row is not None and row.status == "active"


def test_failed_save_restores_learnings_and_leaves_the_card(env, tmp_path, monkeypatch):
    _learn(env, "忌口：海鲜", "2026-01-01T00:00:00+00:00")
    _learn(env, "别再给我虾", "2026-02-01T00:00:00+00:00")
    ConstraintStore(tmp_path).save(ConstraintCard(items=[
        ConstraintItem(id="old", text="忌口：海鲜", status="active", updated_at="2026-01-01T00:00:00+00:00", topic="seafood"),
        ConstraintItem(id="new", text="别再给我虾", status="active", updated_at="2026-02-01T00:00:00+00:00", topic="seafood"),
    ]))

    def boom(self, card):
        raise OSError("disk")

    monkeypatch.setattr(ConstraintStore, "save", boom)
    enqueue(env, user_id="alice")
    due = run_due(env, workspace=tmp_path)
    assert due[0]["status"] == "failed"
    assert due[0]["reason"] == "failed: OSError"
    rows = env.list_learnings(user_id="alice", namespace="profile")
    assert len(rows) == 2
    assert all(row.status == "active" for row in rows)
    card = ConstraintStore(tmp_path).load()
    assert sorted(active_texts(card)) == ["别再给我虾", "忌口：海鲜"]


def test_run_due_does_not_call_get_store(env, tmp_path, monkeypatch):
    def boom():
        raise AssertionError("get_store")

    monkeypatch.setattr("local.memory.store.get_store", boom)
    other = ProfileStore(tmp_path / "other.sqlite")
    from local.memory.store import set_store

    set_store(other)
    _learn(env, "忌口：海鲜", "2026-01-01T00:00:00+00:00")
    _learn(env, "别再给我虾", "2026-02-01T00:00:00+00:00")
    enqueue(env, user_id="alice")
    due = run_due(env, workspace=tmp_path)
    assert due[0]["status"] == "done"
    assert other.list_jobs() == []
    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            _ROOT / "local/memory/jobs.py",
            _ROOT / "local/memory/consolidate.py",
        )
    )
    assert "get_store" not in blob
    for token in ("openai", "httpx", "requests", "make_agent", "chat/completions"):
        assert token not in blob
