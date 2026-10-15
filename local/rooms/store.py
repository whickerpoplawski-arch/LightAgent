"""Room index lives on workspace.json; transcripts live under rooms/."""

from __future__ import annotations

import json
from pathlib import Path

from local.conversations.store import workspace_file

from .types import GroupRoom, RoomMessage


def _read_raw(root: Path) -> dict:
    path = workspace_file(root)
    if not path.is_file():
        return {"version": 1, "projects": [], "conversations": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "projects": [], "conversations": []}
    if not isinstance(data, dict):
        return {"version": 1, "projects": [], "conversations": []}
    return data


def _write_raw(root: Path, data: dict) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    workspace_file(root).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_rooms(root: Path) -> list[GroupRoom]:
    raw = _read_raw(root)
    return [GroupRoom.from_dict(item) for item in (raw.get("rooms") or []) if isinstance(item, dict)]


def save_rooms(root: Path, rooms: list[GroupRoom]) -> None:
    raw = _read_raw(root)
    raw["version"] = raw.get("version") or 1
    raw["rooms"] = [room.to_dict() for room in rooms]
    _write_raw(root, raw)


def transcript_path(root: Path, room_id: str) -> Path:
    return Path(root) / "rooms" / f"{room_id}.json"


def load_transcript(root: Path, room_id: str) -> tuple[list[RoomMessage], dict]:
    path = transcript_path(root, room_id)
    if not path.is_file():
        return [], {}
    data = json.loads(path.read_text(encoding="utf-8"))
    messages = [RoomMessage.from_dict(item) for item in (data.get("messages") or []) if isinstance(item, dict)]
    return messages, dict(data.get("trace") or {})


def save_transcript(root: Path, room_id: str, messages: list[RoomMessage], trace: dict | None = None) -> None:
    path = transcript_path(root, room_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "messages": [item.to_dict() for item in messages],
        "trace": dict(trace or {}),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_transcript(root: Path, room_id: str) -> None:
    path = transcript_path(root, room_id)
    if path.is_file():
        path.unlink()
