"""Rules-first memory flush before compaction.

Failure to write must not stop compaction. Diet, medication, and Never lines
are also pinned with ``metadata.compact = "never"``.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .classify import classify_text, should_pin_text
from .messages import ensure_metadata, in_space
from .prompts import FLUSH_RULES
from .types import ExtractedMemory

# Imported so the rules text ships with the code path, not only the classifier.
_FLUSH_RULES_TEXT = FLUSH_RULES


def daily_note_path(store: Any, day: date) -> Path | None:
    path = getattr(store, "path", None)
    if path is None:
        return None
    return Path(path).resolve().parent / "daily" / f"{day.isoformat()}.md"


def append_daily_note(store: Any, text: str, *, day: date | None = None) -> str | None:
    """APPEND one line. Never overwrites an existing daily note."""
    when = day or datetime.now(timezone.utc).date()
    path = daily_note_path(store, when)
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# {when.isoformat()}\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {text.strip()}\n")
    return str(path)


def _host_scope(host: Any, space_id: str | None) -> tuple[str, str, str | None]:
    user_id = getattr(host, "user_id", None) or "local-user"
    namespace = getattr(host, "namespace", None) or "profile"
    resolved_space = space_id if space_id is not None else getattr(host, "space_id", None)
    return str(user_id), str(namespace), resolved_space


def _plain_user_text(content: str) -> str:
    from LightAgent.core import _strip_ephemeral_memory

    cleaned = _strip_ephemeral_memory([{"role": "user", "content": content}])
    if not cleaned or not isinstance(cleaned[0], dict):
        return ""
    return str(cleaned[0].get("content") or "").strip()


def _write_memory(
    store: Any,
    host: Any,
    item: ExtractedMemory,
    *,
    space_id: str | None,
    seen: set[str],
) -> dict[str, Any] | None:
    text = item.text.strip()
    if not text or text in seen or "<identity" in text or "<persona>" in text or "<memory-context>" in text:
        return None
    seen.add(text)
    user_id, namespace, resolved_space = _host_scope(host, space_id)
    try:
        result = store.learn(
            text,
            user_id=user_id,
            namespace=namespace,
            lane=item.lane,
            facet=item.facet,
            kind=item.kind,
            space_id=resolved_space,
            source="user",
            trust_level="owner",
            evidence="compact-flush",
        )
    except Exception as exc:  # flush must not block compaction
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}", "text": text}
    learning = getattr(result, "learning", None)
    return {
        "status": getattr(result, "status", "unknown"),
        "reason": getattr(result, "reason", None),
        "text": text,
        "id": None if learning is None else learning.id,
        "space_id": resolved_space,
        "facet": item.facet,
        "kind": item.kind,
        "stage": "flush",
    }


def memory_flush(
    messages: list[dict[str, Any]],
    *,
    store: Any = None,
    host: Any = None,
    space_id: str | None = None,
    today: date | None = None,
    seen_texts: set[str] | None = None,
) -> dict[str, Any]:
    """Scan user turns, pin hard boundaries, and admit profile facts.

    Returns a report. Exceptions inside a single write are recorded and skipped.
    """
    seen = seen_texts if seen_texts is not None else set()
    written: list[dict[str, Any]] = []
    notes: list[str] = []
    pinned = 0
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        if not in_space(message, space_id):
            notes.append("skipped other space")
            continue
        metadata = ensure_metadata(message)
        if metadata.get("memory_flushed"):
            continue
        content = message.get("content")
        if not isinstance(content, str):
            metadata["memory_flushed"] = True
            continue
        text = _plain_user_text(content)
        if not text:
            metadata["memory_flushed"] = True
            continue
        try:
            hits, _procedural = classify_text(text, space_id=space_id)
        except Exception as exc:
            notes.append(f"flush classify failed: {type(exc).__name__}")
            metadata["memory_flushed"] = True
            continue
        if should_pin_text(text) and str(metadata.get("compact", "")).lower() != "never":
            metadata["compact"] = "never"
            pinned += 1
        elif any(hit.pin for hit in hits) and str(metadata.get("compact", "")).lower() != "never":
            metadata["compact"] = "never"
            pinned += 1
        if store is not None and hits:
            for hit in hits:
                record = _write_memory(store, host, hit, space_id=space_id, seen=seen)
                if record is not None:
                    written.append(record)
                if hit.kind == "fact" and hit.facet == "life":
                    try:
                        append_daily_note(store, hit.text, day=today)
                    except Exception as exc:
                        notes.append(f"daily note failed: {type(exc).__name__}: {exc}")
        metadata["memory_flushed"] = True
    return {"written": written, "pinned_count": pinned, "notes": notes}
