"""Due-on-open listing. Nothing here starts a model run by itself."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from local.harness.run_control import default_budget_limits, make_run_token

from .detect import parse_routine
from .store import Routine, RoutineStore, _iso, _now, _zone, advance_due, parse_time

# Personal sleep window in the routine's own timezone. Not a workplace policy.
QUIET_START_HOUR = 22
QUIET_END_HOUR = 7

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


def in_quiet_hours(now: datetime, timezone_name: str = "America/Martinique") -> bool:
    """True from 22:00 inclusive through 07:00 exclusive, local to ``timezone_name``."""
    local = now.astimezone(_zone(timezone_name))
    return local.hour >= QUIET_START_HOUR or local.hour < QUIET_END_HOUR


def _announce_path(workspace: Path | str) -> Path:
    return Path(workspace) / "routines" / "announce_state.json"


def _load_announce(workspace: Path | str) -> dict:
    path = _announce_path(workspace)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_announce(workspace: Path | str, state: dict) -> None:
    path = _announce_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _signature(items: list[Routine]) -> list[list[str]]:
    rows = [[item.id, item.next_due_at or "", item.last_run_at or ""] for item in items]
    rows.sort()
    return rows


def take_due_notices(
    workspace: Path | str,
    *,
    now: datetime | None = None,
    space_id: str | None = None,
) -> dict:
    """Notices for an open. Quiet hours and a repeated due set produce none.

    Listing does not run the routine. Confirm is still required.
    """
    moment = now or _now()
    due = due_routines(workspace, now=moment, space_id=space_id)
    due_ids = {item.id for item in due}
    stale = [
        item
        for item in stale_routines(workspace, now=moment, space_id=space_id)
        if item.id not in due_ids
    ]
    tz_name = "America/Martinique"
    if due:
        tz_name = due[0].timezone or tz_name
    elif stale:
        tz_name = stale[0].timezone or tz_name
    ids = [item.id for item in due]
    if (due or stale) and in_quiet_hours(moment, tz_name):
        return {"notices": [], "reason": "quiet", "due_ids": ids}
    signature = {"due": _signature(due), "stale": _signature(stale)}
    state = _load_announce(workspace)
    key = space_id or ""
    if (due or stale) and state.get(key) == signature:
        return {"notices": [], "reason": "duplicate", "due_ids": ids}
    notices: list[str] = []
    if due:
        titles = "、".join(item.title for item in due[:3])
        notices.append(f"到点的提醒：{titles}。回复「确认提醒」才会执行。")
    if stale:
        notices.append(f"这些提醒很久没用了，可以说「暂停提醒 {stale[0].title}」。")
    if notices:
        state[key] = signature
        _save_announce(workspace, state)
    return {"notices": notices, "reason": "shown" if notices else "none", "due_ids": ids}


def create_explicit(
    workspace: Path | str,
    text: str,
    *,
    owner_space: str,
    now: datetime | None = None,
) -> dict:
    """Create one routine. The same instruction does not create a second row."""
    parsed = parse_routine(text)
    if parsed is None:
        return {"created": False, "reason": "not-routine"}
    store = RoutineStore(workspace)
    existing = store.find_open_duplicate(
        instruction=parsed["instruction"],
        cadence=parsed["cadence"],
        owner_space=owner_space,
    )
    if existing is not None:
        return {"created": False, "reason": "duplicate", "routine": existing}
    routine = store.create(
        title=parsed["title"],
        instruction=parsed["instruction"],
        cadence=parsed["cadence"],
        owner_space=owner_space,
        timezone_name=parsed.get("timezone") or "America/Martinique",
        now=now,
    )
    return {"created": True, "reason": "created", "routine": routine}


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
