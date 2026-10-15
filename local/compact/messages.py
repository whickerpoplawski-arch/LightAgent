"""Small message helpers shared by flush, extract, and the pipeline."""

from __future__ import annotations

from typing import Any


def ensure_metadata(message: dict[str, Any]) -> dict[str, Any]:
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        message["metadata"] = metadata
    return metadata


def message_space(message: dict[str, Any]) -> str | None:
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        return None
    space = metadata.get("space_id")
    if space in (None, ""):
        return None
    return str(space)


def in_space(message: dict[str, Any], space_id: str | None) -> bool:
    """Unscoped messages belong to the compact that is running.

    A message explicitly tagged with another space_id is left out of flush,
    extraction, and the summarizer input.
    """
    if not space_id:
        return True
    tagged = message_space(message)
    return tagged is None or tagged == space_id
