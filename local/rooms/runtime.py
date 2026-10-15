"""One user turn: plan, speak in order, then a short host summary."""

from __future__ import annotations

import time

from local.conversations.collaborate import DelegateError, DelegateQuota, resolve_bot
from local.conversations.models import ConversationMeta, new_id

from .digest import build_room_digest
from .host_summary import render_host_summary
from .plan import build_turn_plan
from .sensitive import SENSITIVE_NOTICE, sensitive_reason
from .types import GroupRoom, RoomMessage, TurnPlan, TurnResult
from .utterance import run_room_utterance


def _room_progress(room: GroupRoom) -> tuple[list[str], str | None]:
    """Active constraints and the open goal step. Empty when no workspace is set."""
    import os

    root = os.environ.get("LIGHTAGENT_WORKSPACE")
    if not root:
        return [], None
    constraints: list[str] = []
    next_step = None
    try:
        from local.constraints.card import ConstraintStore

        constraints = ConstraintStore(root).active_texts()
    except Exception:
        constraints = []
    try:
        from local.goals.inject import current_step_title
        from local.goals.store import get_active_goal

        goal = get_active_goal(root, str(room.space_id or room.id))
        if goal is not None:
            next_step = current_step_title(goal)
    except Exception:
        next_step = None
    return constraints, next_step


def _maybe_checkpoint_room(room: GroupRoom) -> None:
    import os

    root = os.environ.get("LIGHTAGENT_WORKSPACE")
    if not root:
        return
    try:
        from local.checkpoints.store import write_checkpoint_for_space

        write_checkpoint_for_space(
            root,
            str(room.space_id or room.id),
            reason="room_turn_end",
            room_id=room.id,
        )
    except Exception:
        return


def _maybe_open_room_goal(room: GroupRoom, text: str) -> None:
    import os

    root = os.environ.get("LIGHTAGENT_WORKSPACE")
    if not root:
        return
    try:
        from local.goals.store import ensure_goal_for_room

        ensure_goal_for_room(root, room, text)
    except Exception:
        return


def _bubble(**kwargs) -> RoomMessage:
    return RoomMessage(id=new_id(), ts=time.time(), meta={}, **kwargs)


def _spent(bubbles: list[RoomMessage]) -> int:
    return sum(1 for item in bubbles if item.speaker != "user" and item.kind in ("chat", "host_summary", "error"))


def _host_label(room: GroupRoom, roster: list[ConversationMeta]) -> str:
    if room.host_bot_id:
        meta = resolve_bot(roster, room.host_bot_id)
        if meta is not None:
            return meta.identity.role_title.strip() or meta.title
    return "生活助手"


def run_user_turn(
    room: GroupRoom,
    text: str,
    roster: list[ConversationMeta],
    messages: list[RoomMessage],
    *,
    quota: DelegateQuota | None = None,
    mode: str = "mock",
    profile_block: str = "",
    runner=None,
    status=None,
    trace: dict | None = None,
) -> TurnResult:
    """Append this turn onto ``messages``. Failures become bubbles; they do not raise."""
    quota = quota or DelegateQuota()
    _maybe_open_room_goal(room, text)
    plan = build_turn_plan(text, room, roster)
    bubbles: list[RoomMessage] = []
    errors: list[str] = []

    def push(message: RoomMessage) -> None:
        messages.append(message)
        bubbles.append(message)

    push(
        _bubble(
            role="user",
            speaker="user",
            speaker_label="用户",
            content=text,
            turn_id=plan.turn_id,
            kind="chat",
        )
    )
    try:
        if sensitive_reason(text):
            plan = TurnPlan(
                turn_id=plan.turn_id,
                speakers=[],
                reason="sensitive",
                include_host_summary=False,
                silent_member_ids=list(room.member_bot_ids),
            )
            push(
                _bubble(
                    role="system",
                    speaker="system",
                    speaker_label="系统",
                    content=SENSITIVE_NOTICE,
                    turn_id=plan.turn_id,
                    kind="system_notice",
                )
            )
            return TurnResult(turn_id=plan.turn_id, plan=plan, bubbles=bubbles, errors=errors)

        for notice in plan.notices:
            push(
                _bubble(
                    role="system",
                    speaker="system",
                    speaker_label="系统",
                    content=notice,
                    turn_id=plan.turn_id,
                    kind="system_notice",
                )
            )

        digest = build_room_digest(messages)
        for bot_id in plan.speakers:
            if _spent(bubbles) >= room.max_bubbles_per_turn:
                break
            meta = resolve_bot(roster, bot_id)
            if meta is None:
                push(
                    _bubble(
                        role="system",
                        speaker="system",
                        speaker_label="系统",
                        content=f"成员「{bot_id}」已经不在，这一轮已跳过。",
                        turn_id=plan.turn_id,
                        kind="system_notice",
                    )
                )
                continue
            label = meta.identity.role_title.strip() or meta.title
            if status:
                status(f"正在请{label}…")
            try:
                message = run_room_utterance(
                    room,
                    meta.id,
                    text,
                    digest,
                    roster,
                    quota,
                    mode,
                    turn_id=plan.turn_id,
                    profile_block=profile_block,
                    runner=runner,
                )
            except DelegateError as exc:
                errors.append(str(exc))
                push(
                    _bubble(
                        role="system",
                        speaker="system",
                        speaker_label="系统",
                        content=str(exc),
                        turn_id=plan.turn_id,
                        kind="error",
                    )
                )
                if "额度" in str(exc):
                    break
                continue
            step = message.meta.pop("step", None)
            if trace is not None and step:
                trace.setdefault("steps", []).append(step)
            push(message)

        if plan.include_host_summary and _spent(bubbles) < room.max_bubbles_per_turn:
            constraints, next_step = _room_progress(room)
            push(
                _bubble(
                    role="assistant",
                    speaker="host",
                    speaker_label=_host_label(room, roster),
                    content=render_host_summary(
                        bubbles,
                        user_text=text,
                        constraints=constraints,
                        next_step=next_step,
                    ),
                    turn_id=plan.turn_id,
                    kind="host_summary",
                )
            )
    finally:
        if status:
            status("")
        room.updated_at = time.time()
        room.unread = True
        _maybe_checkpoint_room(room)
    return TurnResult(turn_id=plan.turn_id, plan=plan, bubbles=bubbles, errors=errors)
