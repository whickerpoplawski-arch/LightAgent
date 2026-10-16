"""Quiet hours, duplicate creates, and one notice per due set. Confirm still runs once."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from local.openrouter_config import NETWORK_CALLS
from local.routines.due import (
    confirm_first_due,
    create_explicit,
    due_routines,
    in_quiet_hours,
    take_due_notices,
)
from local.routines.store import RoutineStore

_ZONE = ZoneInfo("America/Martinique")


def _due_routine(tmp_path, now: datetime):
    created = create_explicit(
        tmp_path,
        "每周一提醒我称重",
        owner_space="life",
        now=now - timedelta(days=2),
    )
    routine = created["routine"]
    RoutineStore(tmp_path).set_next_due(routine.id, now - timedelta(hours=1))
    return routine


def test_quiet_hours_suppress_the_notice_but_keep_the_row(tmp_path):
    night = datetime(2026, 10, 14, 23, 30, tzinfo=_ZONE)
    assert in_quiet_hours(night, "America/Martinique") is True
    assert in_quiet_hours(datetime(2026, 10, 14, 10, 0, tzinfo=_ZONE), "America/Martinique") is False
    routine = _due_routine(tmp_path, night)
    before = NETWORK_CALLS
    payload = take_due_notices(tmp_path, now=night, space_id="life")
    assert payload["notices"] == []
    assert payload["reason"] == "quiet"
    assert [item.id for item in due_routines(tmp_path, now=night, space_id="life")] == [routine.id]
    assert NETWORK_CALLS == before
    morning = datetime(2026, 10, 15, 10, 0, tzinfo=_ZONE)
    shown = take_due_notices(tmp_path, now=morning, space_id="life")
    assert shown["reason"] == "shown"
    assert len(shown["notices"]) == 1
    assert "确认提醒" in shown["notices"][0]


def test_repeat_open_does_not_double_notify_and_confirm_runs_once(tmp_path):
    day = datetime(2026, 10, 14, 10, 0, tzinfo=_ZONE)
    routine = _due_routine(tmp_path, day)
    first = take_due_notices(tmp_path, now=day, space_id="life")
    second = take_due_notices(tmp_path, now=day, space_id="life")
    assert len(first["notices"]) == 1
    assert second["notices"] == []
    assert second["reason"] == "duplicate"
    runs = {"n": 0}

    def runner(instruction, *, budget_limits, cancellation_token):
        runs["n"] += 1
        assert budget_limits.model_calls == 8
        assert cancellation_token is not None
        return instruction

    assert runs["n"] == 0
    result = confirm_first_due(tmp_path, space_id="life", runner=runner, now=day)
    assert result["ok"] is True
    assert runs["n"] == 1
    again = confirm_first_due(tmp_path, space_id="life", runner=runner, now=day)
    assert again["ok"] is False
    assert runs["n"] == 1
    assert due_routines(tmp_path, now=day, space_id="life") == []
    reloaded = RoutineStore(tmp_path).load(routine.id)
    assert reloaded.last_run_at is not None
    later = take_due_notices(tmp_path, now=day, space_id="life")
    assert later["notices"] == []


def test_same_sentence_does_not_create_a_second_routine(tmp_path):
    now = datetime(2026, 10, 14, 10, 0, tzinfo=_ZONE)
    first = create_explicit(tmp_path, "每周一提醒我称重", owner_space="life", now=now)
    second = create_explicit(tmp_path, "每周一提醒我称重", owner_space="life", now=now)
    assert first["created"] is True
    assert second["created"] is False
    assert second["reason"] == "duplicate"
    assert second["routine"].id == first["routine"].id
    assert len(RoutineStore(tmp_path).list_routines()) == 1
