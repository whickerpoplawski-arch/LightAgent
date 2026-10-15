"""Create, rename, and edit a room. The TUI only displays the result."""

from __future__ import annotations

import time

from local.conversations.collaborate import resolve_bot
from local.conversations.models import ConversationMeta, new_id

from .types import GroupRoom, RoomMessage


class RoomError(Exception):
    """A room action the user can read. Nothing was half-applied."""


def _members(member_bot_ids: list[str]) -> list[str]:
    seen: list[str] = []
    for item in member_bot_ids or []:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.append(text)
    if not 2 <= len(seen) <= 6:
        raise RoomError("群成员需要 2 到 6 个已有 Bot")
    return seen


def create_room(
    title: str,
    member_bot_ids: list[str],
    *,
    host_bot_id: str | None = None,
    scenario_hints: list[str] | None = None,
    space_id: str | None = None,
    max_speakers: int = 3,
) -> GroupRoom:
    now = time.time()
    return GroupRoom(
        id=new_id(),
        title=(title or "").strip() or "健康日常",
        member_bot_ids=_members(member_bot_ids),
        host_bot_id=host_bot_id or None,
        max_speakers=max_speakers,
        scenario_hints=list(scenario_hints or []),
        created_at=now,
        updated_at=now,
        space_id=space_id,
    )


def rename_room(room: GroupRoom, title: str) -> None:
    cleaned = (title or "").strip()
    if not cleaned:
        raise RoomError("名称不能为空")
    room.title = cleaned
    room.updated_at = time.time()


def set_members(room: GroupRoom, member_bot_ids: list[str]) -> None:
    room.member_bot_ids = _members(member_bot_ids)
    room.updated_at = time.time()


def delete_room(rooms: list[GroupRoom], room_id: str) -> list[GroupRoom]:
    return [room for room in rooms if room.id != room_id]


def welcome_message(room: GroupRoom, roster: list[ConversationMeta]) -> RoomMessage:
    labels = []
    for bot_id in room.member_bot_ids:
        meta = resolve_bot(roster, bot_id)
        if meta is None:
            labels.append(bot_id)
        else:
            labels.append(meta.identity.role_title.strip() or meta.title)
    return RoomMessage(
        id=new_id(),
        role="system",
        speaker="system",
        speaker_label="系统",
        content=f"已创建群聊「{room.title}」。成员：{'、'.join(labels)}。可以说「今日健身和饮食」，或 @某人。",
        ts=time.time(),
        kind="system_notice",
    )
