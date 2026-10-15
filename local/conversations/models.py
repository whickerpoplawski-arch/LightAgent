"""Conversation metadata. Identity is per bot; it is not a user-profile learning."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


def new_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class BotIdentity:
    """User-written role for one bot.

    ``template_id`` only records which starter was last applied. Injection
    always uses ``role_title`` and ``job_description`` as the user left them.
    """

    display_name: str = ""
    role_title: str = ""
    job_description: str = ""
    template_id: str | None = None
    persona_mode: str = "inherit"  # inherit | override
    persona_text: str = ""

    def __post_init__(self) -> None:
        if self.persona_mode not in ("inherit", "override"):
            raise ValueError("persona_mode must be inherit or override")
        if self.template_id == "":
            self.template_id = None

    @property
    def defined(self) -> bool:
        return bool(self.role_title.strip() or self.job_description.strip())

    def to_dict(self) -> dict:
        return {
            "display_name": self.display_name,
            "role_title": self.role_title,
            "job_description": self.job_description,
            "template_id": self.template_id,
            "persona_mode": self.persona_mode,
            "persona_text": self.persona_text,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> BotIdentity:
        data = dict(data or {})
        return cls(
            display_name=str(data.get("display_name") or ""),
            role_title=str(data.get("role_title") or ""),
            job_description=str(data.get("job_description") or ""),
            template_id=data.get("template_id") or None,
            persona_mode=str(data.get("persona_mode") or "inherit"),
            persona_text=str(data.get("persona_text") or ""),
        )


@dataclass
class ConversationMeta:
    id: str
    title: str
    avatar: str = "🤖"
    accent: str = "#60a5fa"
    project_id: str | None = None
    space_id: str | None = None
    pinned: bool = False
    hidden: bool = False
    unread: bool = False
    updated_at: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    identity: BotIdentity = field(default_factory=BotIdentity)
    share_user_profile: bool = True
    agent_id: str | None = None

    def __post_init__(self) -> None:
        if not self.agent_id:
            self.agent_id = f"bot-{self.id}"
        if not isinstance(self.identity, BotIdentity):
            self.identity = BotIdentity.from_dict(self.identity)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "avatar": self.avatar,
            "accent": self.accent,
            "project_id": self.project_id,
            "space_id": self.space_id,
            "pinned": self.pinned,
            "hidden": self.hidden,
            "unread": self.unread,
            "updated_at": self.updated_at,
            "created_at": self.created_at,
            "identity": self.identity.to_dict(),
            "share_user_profile": self.share_user_profile,
            "agent_id": self.agent_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConversationMeta:
        return cls(
            id=str(data["id"]),
            title=str(data.get("title") or "新会话"),
            avatar=str(data.get("avatar") or "🤖"),
            accent=str(data.get("accent") or "#60a5fa"),
            project_id=data.get("project_id") or None,
            space_id=data.get("space_id") or None,
            pinned=bool(data.get("pinned")),
            hidden=bool(data.get("hidden")),
            unread=bool(data.get("unread")),
            updated_at=float(data.get("updated_at") or time.time()),
            created_at=float(data.get("created_at") or time.time()),
            identity=BotIdentity.from_dict(data.get("identity")),
            share_user_profile=bool(data.get("share_user_profile", True)),
            agent_id=data.get("agent_id") or None,
        )


@dataclass
class ProjectGroup:
    name: str
    id: str = field(default_factory=new_id)
    expanded: bool = True
    session_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "expanded": self.expanded,
            "session_ids": list(self.session_ids),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectGroup:
        return cls(
            name=str(data.get("name") or "分组"),
            id=str(data.get("id") or new_id()),
            expanded=bool(data.get("expanded", True)),
            session_ids=[str(item) for item in (data.get("session_ids") or [])],
        )
