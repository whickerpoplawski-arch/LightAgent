"""JSON workspace: metas in workspace.json, transcripts beside them.

``space_id`` defaults to ``project_id`` when a conversation is created or moved
and the previous space was unset or still equal to the old group.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import ConversationMeta, ProjectGroup


@dataclass
class Transcript:
    messages: list[dict] = field(default_factory=list)
    events: list[list] = field(default_factory=list)
    trace: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "messages": self.messages,
            "events": self.events,
            "trace": self.trace,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> Transcript:
        data = dict(data or {})
        events = []
        for item in data.get("events") or []:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                events.append([str(item[0]), str(item[1])])
        return cls(
            messages=list(data.get("messages") or []),
            events=events,
            trace=dict(data.get("trace") or {}),
        )


@dataclass
class StoredWorkspace:
    projects: list[ProjectGroup] = field(default_factory=list)
    conversations: list[ConversationMeta] = field(default_factory=list)
    transcripts: dict[str, Transcript] = field(default_factory=dict)


def workspace_file(root: Path) -> Path:
    return Path(root) / "workspace.json"


def conversation_file(root: Path, conversation_id: str) -> Path:
    return Path(root) / "conversations" / f"{conversation_id}.json"


def save_workspace(root: Path, stored: StoredWorkspace) -> None:
    root = Path(root)
    conv_dir = root / "conversations"
    conv_dir.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    path = workspace_file(root)
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, json.JSONDecodeError):
            existing = {}
    payload = {
        "version": 1,
        "projects": [project.to_dict() for project in stored.projects],
        "conversations": [meta.to_dict() for meta in stored.conversations],
    }
    if "rooms" in existing:
        payload["rooms"] = existing["rooms"]
    workspace_file(root).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    keep = set()
    for meta in stored.conversations:
        keep.add(meta.id)
        blob = stored.transcripts.get(meta.id, Transcript()).to_dict()
        conversation_file(root, meta.id).write_text(
            json.dumps(blob, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    for path in conv_dir.glob("*.json"):
        if path.stem not in keep:
            path.unlink()


def load_workspace(root: Path) -> StoredWorkspace | None:
    path = workspace_file(root)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    conversations = [ConversationMeta.from_dict(item) for item in raw.get("conversations") or []]
    projects = [ProjectGroup.from_dict(item) for item in raw.get("projects") or []]
    transcripts: dict[str, Transcript] = {}
    for meta in conversations:
        file = conversation_file(root, meta.id)
        if file.is_file():
            transcripts[meta.id] = Transcript.from_dict(json.loads(file.read_text(encoding="utf-8")))
        else:
            transcripts[meta.id] = Transcript()
    return StoredWorkspace(projects=projects, conversations=conversations, transcripts=transcripts)
