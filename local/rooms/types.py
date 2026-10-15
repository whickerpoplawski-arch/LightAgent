"""Hosted-room models. Members point at existing ConversationMeta ids."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from local.conversations.models import new_id


def _dedupe(ids: list[str]) -> list[str]:
    seen: list[str] = []
    for item in ids or []:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.append(text)
    return seen


@dataclass
class GroupRoom:
    id: str
    title: str
    member_bot_ids: list[str]
    host_bot_id: str | None = None
    max_speakers: int = 3
    max_bubbles_per_turn: int = 4
    scenario_hints: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    pinned: bool = False
    hidden: bool = False
    unread: bool = False
    space_id: str | None = None

    def __post_init__(self) -> None:
        self.member_bot_ids = _dedupe(list(self.member_bot_ids))
        self.max_speakers = max(1, int(self.max_speakers))
        self.max_bubbles_per_turn = max(1, int(self.max_bubbles_per_turn))
        self.scenario_hints = [str(item) for item in (self.scenario_hints or []) if item]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "member_bot_ids": list(self.member_bot_ids),
            "host_bot_id": self.host_bot_id,
            "max_speakers": self.max_speakers,
            "max_bubbles_per_turn": self.max_bubbles_per_turn,
            "scenario_hints": list(self.scenario_hints),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pinned": self.pinned,
            "hidden": self.hidden,
            "unread": self.unread,
            "space_id": self.space_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GroupRoom:
        return cls(
            id=str(data["id"]),
            title=str(data.get("title") or "群聊"),
            member_bot_ids=[str(item) for item in (data.get("member_bot_ids") or [])],
            host_bot_id=data.get("host_bot_id") or None,
            max_speakers=int(data.get("max_speakers") or 3),
            max_bubbles_per_turn=int(data.get("max_bubbles_per_turn") or 4),
            scenario_hints=[str(item) for item in (data.get("scenario_hints") or [])],
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            pinned=bool(data.get("pinned")),
            hidden=bool(data.get("hidden")),
            unread=bool(data.get("unread")),
            space_id=data.get("space_id") or None,
        )


@dataclass
class RoomMessage:
    id: str
    role: str
    speaker: str
    speaker_label: str
    content: str
    ts: float
    turn_id: str | None = None
    kind: str = "chat"
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "speaker": self.speaker,
            "speaker_label": self.speaker_label,
            "content": self.content,
            "ts": self.ts,
            "turn_id": self.turn_id,
            "kind": self.kind,
            "meta": dict(self.meta or {}),
        }

    @classmethod
    def from_dict(cls, data: dict) -> RoomMessage:
        return cls(
            id=str(data.get("id") or new_id()),
            role=str(data.get("role") or "assistant"),
            speaker=str(data.get("speaker") or "system"),
            speaker_label=str(data.get("speaker_label") or ""),
            content=str(data.get("content") or ""),
            ts=float(data.get("ts") or time.time()),
            turn_id=data.get("turn_id") or None,
            kind=str(data.get("kind") or "chat"),
            meta=dict(data.get("meta") or {}),
        )


@dataclass
class TurnPlan:
    turn_id: str
    speakers: list[str]
    reason: str
    include_host_summary: bool = True
    silent_member_ids: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)


@dataclass
class TurnResult:
    turn_id: str
    plan: TurnPlan
    bubbles: list[RoomMessage]
    errors: list[str] = field(default_factory=list)
