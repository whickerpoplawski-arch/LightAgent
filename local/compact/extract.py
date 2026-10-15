"""Post-compact split: profile facts go to Memory; procedures wait for confirmation."""

from __future__ import annotations

from typing import Any

from .classify import classify_text
from .messages import ensure_metadata, in_space
from .types import ExtractedMemory, ProceduralCandidate


def _write(store: Any, host: Any, item: ExtractedMemory, *, space_id: str | None, seen: set[str]) -> dict[str, Any] | None:
    text = item.text.strip()
    if not text or text in seen:
        return None
    seen.add(text)
    user_id = getattr(host, "user_id", None) or "local-user"
    namespace = getattr(host, "namespace", None) or "profile"
    resolved_space = space_id if space_id is not None else getattr(host, "space_id", None)
    try:
        result = store.learn(
            text,
            user_id=str(user_id),
            namespace=str(namespace),
            lane=item.lane,
            facet=item.facet,
            kind=item.kind,
            space_id=resolved_space,
            source="user",
            trust_level="owner",
            evidence="compact-extract",
        )
    except Exception as exc:
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}", "text": text, "stage": "extract"}
    learning = getattr(result, "learning", None)
    return {
        "status": getattr(result, "status", "unknown"),
        "reason": getattr(result, "reason", None),
        "text": text,
        "id": None if learning is None else learning.id,
        "space_id": resolved_space,
        "facet": item.facet,
        "kind": item.kind,
        "stage": "extract",
    }


def extract_after_compact(
    messages: list[dict[str, Any]],
    *,
    store: Any = None,
    host: Any = None,
    space_id: str | None = None,
    seen_texts: set[str] | None = None,
) -> dict[str, Any]:
    """Scan user turns already stripped of ephemeral packs.

    Profile hits are admitted immediately. Procedural hits are returned and
    are not written to Memory. ``compact_extracted`` stops a later compact
    from asking about the same sentence again.
    """
    seen = seen_texts if seen_texts is not None else set()
    written: list[dict[str, Any]] = []
    pending: list[ProceduralCandidate] = []
    notes: list[str] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        if not in_space(message, space_id):
            continue
        metadata = ensure_metadata(message)
        if metadata.get("compact_extracted"):
            continue
        content = message.get("content")
        text = content.strip() if isinstance(content, str) else ""
        if not text:
            metadata["compact_extracted"] = True
            continue
        try:
            hits, procedural = classify_text(text, space_id=space_id)
        except Exception as exc:
            notes.append(f"extract failed: {type(exc).__name__}")
            metadata["compact_extracted"] = True
            continue
        if store is not None:
            for hit in hits:
                record = _write(store, host, hit, space_id=space_id, seen=seen)
                if record is not None:
                    written.append(record)
        pending.extend(procedural)
        metadata["compact_extracted"] = True
    return {"written": written, "procedural": pending, "notes": notes}
