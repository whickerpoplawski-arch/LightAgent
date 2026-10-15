"""User-profile memory types.

Persona (who the assistant is) is not modeled here. These records are the
user profile: durable learnings with a preference lane and a life facet.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class LearningKind(str, Enum):
    PREFERENCE = "preference"
    FACT = "fact"
    PROCEDURE = "procedure"
    CORRECTION = "correction"
    OTHER = "other"


class PreferenceLane(str, Enum):
    """Two product lanes. OpenHuman has no module with these names."""

    GENERAL = "general"  # session-stable, always eligible for the pack
    SITUATIONAL = "situational"  # recalled only when the turn's topic overlaps


class Facet(str, Enum):
    """Life-assistant profile faces. Not OpenHuman's explore-metadata Facet."""

    IDENTITY = "identity"
    STYLE = "style"
    GOAL = "goal"
    TOOLING = "tooling"
    VETO = "veto"
    CHANNEL = "channel"
    LIFE = "life"


LANES = {item.value for item in PreferenceLane}
KINDS = {item.value for item in LearningKind}
FACETS = {item.value for item in Facet}

# Rough character estimate for budget trimming. Chosen locally, not copied.
CHARS_PER_TOKEN = 4
DEFAULT_PACK_BUDGET_TOKENS = 1200

UNAVAILABLE_NOTICE = (
    "memory unavailable: 用户画像这一轮没有取到。"
    "不要对用户说「我什么都不记得」；说明记忆暂时不可用，需要时可以再用回忆工具。"
)


@dataclass(frozen=True)
class ScrubResult:
    allowed: bool
    text: str
    reason: str | None = None
    redactions: tuple[str, ...] = ()
    needs_confirm: bool = False


@dataclass(frozen=True)
class Learning:
    id: str
    user_id: str
    namespace: str
    text: str
    kind: str = LearningKind.PREFERENCE.value
    lane: str = PreferenceLane.GENERAL.value
    facet: str = Facet.IDENTITY.value
    confidence: float = 0.8
    pinned: bool = False
    needs_confirm: bool = False
    confirmed: bool = True
    topics: tuple[str, ...] = ()
    space_id: str | None = None
    source: str = "user"
    status: str = "active"  # active | candidate
    injectable: bool = True
    created_at: str = ""
    updated_at: str = ""
    evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["topics"] = list(self.topics)
        return data


@dataclass(frozen=True)
class LearnResult:
    learning: Learning | None
    status: str  # saved | needs_confirm | rejected | duplicate
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "learning": None if self.learning is None else self.learning.to_dict(),
        }


@dataclass(frozen=True)
class MemoryPack:
    markdown: str
    tokens: int
    refs: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    unavailable: bool = False
    notice: str | None = None
    cached: bool = False

    def injection(self) -> str:
        body = self.notice if self.unavailable else self.markdown
        body = (body or "").strip()
        if not body:
            return ""
        return f"<memory-context>\n{body}\n</memory-context>"


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def normalize_lane(value: str | None) -> str:
    lane = (value or PreferenceLane.GENERAL.value).strip().lower()
    if lane not in LANES:
        raise ValueError(f"lane must be one of {sorted(LANES)}")
    return lane


def normalize_kind(value: str | None) -> str:
    kind = (value or LearningKind.PREFERENCE.value).strip().lower()
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {sorted(KINDS)}")
    return kind


def normalize_facet(value: str | None) -> str:
    facet = (value or Facet.IDENTITY.value).strip().lower()
    if facet not in FACETS:
        raise ValueError(f"facet must be one of {sorted(FACETS)}")
    return facet