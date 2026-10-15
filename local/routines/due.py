"""Due-on-open listing. Nothing here starts a model run by itself."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from local.harness.run_control import default_budget_limits, make_run_token

from .store import Routine, RoutineStore, _iso, _now, advance_due, parse_time

_STALE_DAYS = 21


def due_routines(
    workspace: Path | str,
    *,
    now: datetime | None = None,
    space_id: str | None = None,
) -> list[Routine]:
    """Routines whose next_due_at has arrived. Paused rows are omitted. No model call."""
    moment = now or _now()
    found: list[Routine] = []
    for routine in RoutineStore(workspace).list_routines():
        if routine.paused:
            continue
        if space_id and routine.owner_space and routine.owner_space != space_id:
            continue
        due = parse_time(routine.next_due_at)
        if due is not None and due <= moment:
            found.append(routine)
    return found


def needs_keep_prompt(routine: Routine, *, now: datetime | None = None, days: int = _STALE_DAYS) -> bool:
    if routine.paused:
        return False
    anchor = parse_time(routine.last_run_at) or parse_time(routine.created_at)
    if anchor is None:
        return False
    moment = now or _now()
    return moment - anchor >= timedelta(days=days)


def stale_routines(workspace: Path | str, *, now: datetime | None = None, space_id: str | None = None) -> list[Routine]:
    rows = []
    for routine in RoutineStore(workspace).list_routines():
        if space_id and routine.owner_space and routine.owner_space != space_id:
            continue
        if needs_keep_prompt(routine, now=now):
            rows.append(routine)
    return rows


def confirm_routine(
    workspace: Path | str,
    routine_id: str,
    *,
    runner: Callable[..., Any] | None = None,
    now: datetime | None = None,
) -> dict:
    """User confirmed one routine. The runner, when given, receives the M4 budget and token."""
    store = RoutineStore(workspace)
    routine = store.load(routine_id)
    if routine is None or routine.paused:
        return {"ok": False, "reason": "not-runnable"}
    moment = now or _now()
    limits = default_budget_limits()
    token = make_run_token()
    content = None
    if runner is not None:
        content = runner(routine.instruction, budget_limits=limits, cancellation_token=token)
    routine.last_run_at = _iso(moment)
    nxt = advance_due(routine.cadence, timezone_name=routine.timezone, now=moment)
    if routine.cadence == "once" or nxt is None:
        routine.paused = True
        routine.next_due_at = None
    else:
        routine.next_due_at = _iso(nxt.astimezone(timezone.utc))
    store.save(routine)
    return {
        "ok": True,
        "content": content,
        "budget": limits,
        "token": token,
        "routine": routine,
    }


def confirm_first_due(
    workspace: Path | str,
    *,
    space_id: str | None = None,
    runner: Callable[..., Any] | None = None,
    now: datetime | None = None,
) -> dict:
    """Confirm the single oldest due item. Extra missed periods are not replayed."""
    moment = now or _now()
    due = due_routines(workspace, now=moment, space_id=space_id)
    if not due:
        return {"ok": False, "reason": "none-due"}
    due.sort(key=lambda item: item.next_due_at or "")
    return confirm_routine(workspace, due[0].id, runner=runner, now=moment)
