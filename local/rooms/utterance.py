"""One room bubble is one single-level run_delegation. Children cannot delegate."""

from __future__ import annotations

import os
import time

from local.conversations.collaborate import DelegateError, DelegateQuota, resolve_bot, run_delegation
from local.conversations.models import ConversationMeta, new_id

from .digest import strip_ephemeral
from .types import GroupRoom, RoomMessage

_PACK_MARKERS = ("<memory-context>", "<persona>", "<identity>")


def collaboration_enabled() -> bool:
    return os.environ.get("LIGHTAGENT_COLLAB", "1") != "0"


def role_task(room: GroupRoom, meta: ConversationMeta, user_text: str) -> str:
    role = (meta.identity.role_title or meta.title or "成员").strip()
    note = ""
    blob = f"{meta.identity.template_id or ''} {role} {meta.title}"
    if "饮食" in blob or "nutrition" in blob:
        note = "请尊重用户原话里的忌口和否决，不要诊疗。"
    elif "习惯" in blob or "教练" in blob or "habit" in blob:
        note = "请给很小的运动下一步，避开用户明确禁止的动作。"
    original = strip_ephemeral(user_text)
    return f"你在群「{room.title}」中发言；只代表自己（{role}）；2–5 句。{note}用户原话：{original}"


def run_room_utterance(
    room: GroupRoom,
    bot_id: str,
    user_text: str,
    digest: str,
    roster: list[ConversationMeta],
    quota: DelegateQuota,
    mode: str = "mock",
    *,
    turn_id: str,
    profile_block: str = "",
    runner=None,
) -> RoomMessage:
    """Parent depth. The child tool list stays without delegate_to_bot and without ToT."""
    if not collaboration_enabled():
        raise DelegateError("协作未启用，群聊不会请成员发言。")
    meta = resolve_bot(roster, bot_id)
    if meta is None:
        raise DelegateError(f"找不到 Bot「{bot_id}」。请确认它已存在且未删除。")
    task = role_task(room, meta, user_text)
    context = strip_ephemeral(digest)
    for marker in _PACK_MARKERS:
        if marker in task or marker in context:
            raise DelegateError("任务正文里不能夹带记忆包或身份块")
    outcome = run_delegation(
        roster=roster,
        bot_id=meta.id,
        task=task,
        context_summary=context,
        depth=0,
        quota=quota,
        profile_block=profile_block if meta.share_user_profile else "",
        parent_messages=[],
        mode=mode,
        runner=runner,
    )
    content = outcome.result
    for marker in _PACK_MARKERS:
        content = content.replace(marker, "")
    label = meta.identity.role_title.strip() or meta.identity.display_name.strip() or meta.title
    step = dict(outcome.step)
    return RoomMessage(
        id=new_id(),
        role="assistant",
        speaker=f"bot:{outcome.bot_id}",
        speaker_label=label,
        content=content.strip(),
        ts=time.time(),
        turn_id=turn_id,
        kind="chat",
        meta={"bot_id": outcome.bot_id, "via": "run_delegation", "step": step},
    )
