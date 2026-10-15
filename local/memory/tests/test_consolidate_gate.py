"""L-P0-2: consolidate waits for 6h and 2 new memories, and does not double-write."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Barrier, Thread

from local.constraints.card import ConstraintCard, ConstraintItem, ConstraintStore
from local.memory.consolidate_config import MIN_INTERVAL_HOURS, MIN_NEW_MEMORIES
from local.memory.jobs import enqueue, run_due
from local.memory.tests.test_consolidate import _learn

T0 = datetime(2026, 1, 3, tzinfo=timezone.utc)


def _statuses(store, user_id="alice"):
    return sorted(
        (row.text, row.status, row.updated_at)
        for row in store.list_learnings(user_id=user_id, namespace="profile")
    )


def test_gate_defaults_are_the_life_values():
    assert MIN_INTERVAL_HOURS >= 6
    assert MIN_NEW_MEMORIES >= 2


def test_one_memory_skips_until_a_second_arrives(env, tmp_path):
    _learn(env, "忌口：海鲜", "2026-01-01T00:00:00+00:00")
    enqueue(env, user_id="alice")
    due = run_due(env, workspace=tmp_path, now=T0)
    assert due[0]["status"] == "skipped"
    assert due[0]["reason"] == "min_new_memories"
    assert due[0]["diff"]["gate"]["new_memories"] == 1
    assert all(row.status == "active" for row in env.list_learnings(user_id="alice", namespace="profile"))

    _learn(env, "别再给我虾", "2026-01-02T00:00:00+00:00")
    enqueue(env, user_id="alice")
    due = run_due(env, workspace=tmp_path, now=T0)
    assert due[0]["status"] == "done"
    assert due[0]["reason"] == "folded"
    active = [row for row in env.list_learnings(user_id="alice", namespace="profile") if row.status == "active"]
    assert len(active) == 1


def test_second_run_due_is_a_noop(env, tmp_path):
    _learn(env, "忌口：海鲜", "2026-01-01T00:00:00+00:00")
    _learn(env, "别再给我虾", "2026-01-02T00:00:00+00:00")
    enqueue(env, user_id="alice")
    first = run_due(env, workspace=tmp_path, now=T0)
    assert first[0]["status"] == "done"
    snap = _statuses(env)

    enqueue(env, user_id="alice")
    second = run_due(env, workspace=tmp_path, now=T0 + timedelta(hours=1))
    assert second[0]["status"] == "skipped"
    assert second[0]["reason"] == "min_interval"
    assert _statuses(env) == snap

    assert run_due(env, workspace=tmp_path, now=T0 + timedelta(hours=1)) == []
    assert _statuses(env) == snap


def test_interval_opens_again_after_six_hours(env, tmp_path):
    _learn(env, "忌口：海鲜", "2026-01-01T00:00:00+00:00")
    _learn(env, "别再给我虾", "2026-01-02T00:00:00+00:00")
    enqueue(env, user_id="alice")
    assert run_due(env, workspace=tmp_path, now=T0)[0]["status"] == "done"

    _learn(env, "忌口：花生", "2026-01-03T02:00:00+00:00")
    _learn(env, "别再给我花生", "2026-01-03T03:00:00+00:00")
    enqueue(env, user_id="alice")
    early = run_due(env, workspace=tmp_path, now=T0 + timedelta(hours=1))
    assert early[0]["reason"] == "min_interval"
    assert sum(row.status == "active" and "花生" in row.text for row in env.list_learnings(user_id="alice", namespace="profile")) == 2

    enqueue(env, user_id="alice")
    later = run_due(env, workspace=tmp_path, now=T0 + timedelta(hours=8))
    assert later[0]["status"] == "done"
    peanuts = [
        row for row in env.list_learnings(user_id="alice", namespace="profile")
        if "花生" in row.text and row.status == "active"
    ]
    assert len(peanuts) == 1


def test_concurrent_run_due_does_not_double_write(env, tmp_path, monkeypatch):
    _learn(env, "忌口：海鲜", "2026-01-01T00:00:00+00:00")
    _learn(env, "别再给我虾", "2026-01-02T00:00:00+00:00")
    ConstraintStore(tmp_path).save(ConstraintCard(items=[
        ConstraintItem(id="old", text="忌口：海鲜", status="active", updated_at="2026-01-01T00:00:00+00:00", topic="seafood"),
        ConstraintItem(id="new", text="别再给我虾", status="active", updated_at="2026-01-02T00:00:00+00:00", topic="seafood"),
    ]))
    enqueue(env, user_id="alice")
    calls = {"save": 0, "mark": 0}
    original_save = ConstraintStore.save
    original_mark = env.mark_learnings_superseded

    def counting_save(self, card):
        calls["save"] += 1
        return original_save(self, card)

    def counting_mark(*args, **kwargs):
        calls["mark"] += 1
        return original_mark(*args, **kwargs)

    monkeypatch.setattr(ConstraintStore, "save", counting_save)
    monkeypatch.setattr(env, "mark_learnings_superseded", counting_mark)
    barrier = Barrier(2)
    results: list = []
    errors: list = []

    def worker():
        try:
            barrier.wait()
            results.append(run_due(env, workspace=tmp_path, now=T0))
        except Exception as exc:
            errors.append(exc)

    threads = [Thread(target=worker), Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    flat = [item for batch in results for item in batch]
    assert [item["status"] for item in flat].count("done") == 1
    assert calls["save"] == 1
    assert calls["mark"] == 1
    rows = env.list_learnings(user_id="alice", namespace="profile")
    assert sum(row.status == "superseded" for row in rows) == 1
    assert sum(row.status == "active" for row in rows) == 1
    card = ConstraintStore(tmp_path).load()
    assert sum(item.status == "active" for item in card.items) == 1
    assert sum(item.status == "superseded" for item in card.items) == 1
