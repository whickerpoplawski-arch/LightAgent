"""Compact data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CompactTrigger(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


@dataclass(frozen=True)
class ExtractedMemory:
    """A profile / preference / veto fact admitted straight into Memory."""

    text: str
    kind: str
    facet: str
    lane: str = "general"
    pin: bool = False


@dataclass(frozen=True)
class ProceduralCandidate:
    """A reusable how-to waiting for the user to confirm a skill write."""

    id: str
    title: str
    description: str
    steps: tuple[str, ...]
    source_text: str
    space_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "steps": list(self.steps),
            "source_text": self.source_text,
            "space_id": self.space_id,
        }


@dataclass
class CompactOutcome:
    messages: list[dict[str, Any]]
    removed_count: int
    summary: str | None
    spilled: list[dict[str, Any]] = field(default_factory=list)
    trigger: CompactTrigger = CompactTrigger.MANUAL
    fallback: bool = False
    notice: str = ""
    memories_written: list[dict[str, Any]] = field(default_factory=list)
    procedural_pending: list[ProceduralCandidate] = field(default_factory=list)
    pinned_count: int = 0
    notes: list[str] = field(default_factory=list)
    space_id: str | None = None
    prompt: str = ""
    summarizer_input: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        spills = []
        for item in self.spilled:
            spills.append({key: value for key, value in item.items() if key != "content"})
        return {
            "messages": self.messages,
            "removed_count": self.removed_count,
            "summary": self.summary,
            "spilled": spills,
            "trigger": self.trigger.value,
            "fallback": self.fallback,
            "notice": self.notice,
            "pinned_count": self.pinned_count,
            "space_id": self.space_id,
            "procedural_pending": [item.to_dict() for item in self.procedural_pending],
            "memories_written": list(self.memories_written),
        }
