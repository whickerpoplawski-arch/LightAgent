"""M7: explicit routines, pause, and due-on-open without a hidden model run."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from local.harness.run_control import USER_CANCEL_NOTICE
from local.openrouter_config import NETWORK_CALLS
from local.routines.detect import parse_routine, routine_action
from local.routines.due import confirm_first_due, confirm_routine, due_routines, stale_routines
from local.routines.store import RoutineStore


def test_e12_create_pause_and_due_do_not_call_the_model(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "local.openrouter_config.make_agent",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("make_agent")),
    )
    parsed = parse_routine("每周一提醒我称重")
    assert parsed is not None
    assert parsed["cadence"] == "weekly"
    assert parsed["timezone"] == "America/Martinique"
    assert parse_routine("今天吃什么") is None
    before = NETWORK_CALLS
    store = RoutineStore(tmp_path)
    routine = store.create(
        title=parsed["title"],
        instruction=parsed["instruction"],
        cadence=parsed["cadence"],
        owner_space="life",
        timezone_name=parsed["timezone"],
        now=datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc),
    )
    assert routine.paused is False
    assert due_routines(tmp_path, now=datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)) == []
    store.set_next_due(routine.id, datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc))
    due = due_routines(tmp_path, now=datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc))
    assert [item.id for item in due] == [routine.id]
    assert NETWORK_CALLS == before

    store.pause(routine.id)
    assert due_routines(tmp_path, now=datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)) == []
    store.delete(routine.id)
    assert due_routines(tmp_path, now=datetime(2026, 10, 20, tzinfo=timezone.utc)) == []


def test_confirm_uses_the_run_budget_and_does_not_backfill(tmp_path):
    before = NETWORK_CALLS
    store = RoutineStore(tmp_path)
    now = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)
    routine = store.create(
        title="称重",
        instruction="提醒我称重并记录",
        cadence="weekly",
        owner_space="life",
        now=now - timedelta(days=21),
    )
    store.set_next_due(routine.id, now - timedelta(days=21))
    seen = {}

    def runner(instruction, *, budget_limits, cancellation_token):
        seen["instruction"] = instruction
        seen["budget"] = budget_limits
        seen["token"] = cancellation_token
        cancellation_token.cancel(reason="user_cancel")
        return USER_CANCEL_NOTICE

    result = confirm_first_due(tmp_path, space_id="life", runner=runner, now=now)
    assert result["ok"] is True
    assert seen["budget"].model_calls == 8
    assert seen["budget"].seconds == 120
    assert seen["token"] is result["token"]
    assert seen["instruction"] == "提醒我称重并记录"
    assert NETWORK_CALLS == before
    assert due_routines(tmp_path, now=now, space_id="life") == []
    reloaded = RoutineStore(tmp_path).load(routine.id)
    assert reloaded.last_run_at is not None
    nxt = datetime.fromisoformat(reloaded.next_due_at)
    assert nxt > now
    assert nxt - now < timedelta(days=8)


def test_once_routine_pauses_after_confirm(tmp_path):
    parsed = parse_routine("提醒我一次称体重")
    assert parsed["cadence"] == "once"
    routine = RoutineStore(tmp_path).create(
        title=parsed["title"],
        instruction=parsed["instruction"],
        cadence="once",
        owner_space="life",
    )
    now = datetime.now(timezone.utc)
    result = confirm_routine(tmp_path, routine.id, runner=None, now=now)
    assert result["ok"] is True
    assert result["budget"].model_calls == 8
    assert RoutineStore(tmp_path).load(routine.id).paused is True
    assert due_routines(tmp_path, now=now + timedelta(days=1)) == []


def test_stale_flag_asks_without_running(tmp_path):
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    routine = RoutineStore(tmp_path).create(
        title="称重",
        instruction="每周提醒我称重",
        cadence="weekly",
        owner_space="life",
        now=old,
    )
    assert stale_routines(tmp_path, now=datetime(2026, 10, 14, tzinfo=timezone.utc))[0].id == routine.id
    RoutineStore(tmp_path).pause(routine.id)
    assert stale_routines(tmp_path, now=datetime(2026, 10, 14, tzinfo=timezone.utc)) == []


def test_confirm_and_pause_phrases():
    assert routine_action("确认提醒") == ("confirm", "")
    assert routine_action("跑一下提醒") == ("confirm", "")
    assert routine_action("暂停提醒 称重") == ("pause", "称重")
    assert routine_action("删除提醒称重") == ("delete", "称重")
    assert routine_action("今天吃什么") is None


def test_tui_confirm_does_not_call_the_model(tmp_path, monkeypatch):
    pytest.importorskip("textual")
    monkeypatch.delenv("LIGHTAGENT_WORKSPACE", raising=False)
    monkeypatch.setenv("LIGHTAGENT_FORBID_OPENROUTER", "1")
    monkeypatch.setattr(
        "local.openrouter_config.make_agent",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("make_agent")),
    )
    asyncio.run(_tui_confirm(tmp_path))


async def _tui_confirm(tmp_path):
    from local.tui.app import LightAgentTUI, Session
    from local.tui.backend import MockBackend

    before = NETWORK_CALLS
    backend = MockBackend(delay=0)
    app = LightAgentTUI(
        backend,
        [Session("主对话", id="life")],
        [],
        workspace_dir=tmp_path,
        persist=False,
    )
    async with app.run_test(size=(100, 32)) as pilot:
        prompt = app.query_one("#prompt")
        prompt.focus()
        prompt.value = "每周一提醒我称重"
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert backend._mock_used == 0
        routines = RoutineStore(tmp_path).list_routines()
        assert len(routines) == 1
        assert routines[0].owner_space == "life"
        notes = " ".join(text for _kind, text in app.current.events)
        assert "已记下提醒：称重" in notes
        assert "确认后才跑" in notes

        RoutineStore(tmp_path).set_next_due(
            routines[0].id,
            datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
        prompt.value = "确认提醒"
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert backend._mock_used == 0
        assert NETWORK_CALLS == before
        notes = " ".join(text for _kind, text in app.current.events)
        assert "这次不调用模型" in notes
        assert due_routines(tmp_path, space_id="life") == []

        prompt.value = "暂停提醒 称重"
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert RoutineStore(tmp_path).load(routines[0].id).paused is True
        assert backend._mock_used == 0

        prompt.value = "今天吃什么"
        await pilot.press("enter")
        for _ in range(40):
            if backend._mock_used and not app.busy:
                break
            await pilot.pause(0.1)
        assert backend._mock_used == 1
        assert NETWORK_CALLS == before
