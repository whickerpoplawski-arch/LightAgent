"""Short room digest. Ephemeral packs never travel into a child task."""

from __future__ import annotations

import re

from .types import RoomMessage

_BLOCK = re.compile(
    r"<(memory-context|persona|identity)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_TAG = re.compile(r"</?(?:memory-context|persona|identity)\b[^>]*>", re.IGNORECASE)
MAX_DIGEST_CHARS = 480


def strip_ephemeral(text: str) -> str:
    cleaned = _BLOCK.sub("", text or "")
    return _TAG.sub("", cleaned).strip()


def build_room_digest(
    messages: list[RoomMessage],
    *,
    limit: int = 6,
    max_chars: int = MAX_DIGEST_CHARS,
) -> str:
    lines: list[str] = []
    for message in (messages or [])[-limit:]:
        if message.kind == "error":
            continue
        body = strip_ephemeral(message.content).replace("\n", " ")
        if not body:
            continue
        label = message.speaker_label or message.speaker
        lines.append(f"{label}：{body[:160]}")
    return "\n".join(lines)[:max_chars]


# Extra rows kept outside the tail: recent user lines, plus a few constraint hits.
MAX_CONSTRAINT_EXTRAS = 8
_CONSTRAINT_CUES = ("忌口", "过敏", "不能吃", "不要吃", "不吃", "别吃", "硬限制", "禁忌")


def _hits_constraint(content: str, constraint_texts: list[str]) -> bool:
    blob = content or ""
    if not blob.strip():
        return False
    from local.constraints.card import topic_key

    for needle in constraint_texts:
        text = (needle or "").strip()
        if not text:
            continue
        if text in blob or (len(blob) <= len(text) and blob in text):
            return True
        topic = topic_key(text)
        if topic and topic_key(blob) == topic and any(cue in blob for cue in _CONSTRAINT_CUES):
            return True
    return False


def compact_room_messages(
    messages: list[RoomMessage],
    *,
    keep: int = 40,
    constraint_texts: list[str] | None = None,
    keep_user: int = 10,
) -> list[RoomMessage]:
    """Zero-LLM tail window plus recent user lines and constraint hits.

    Without ``constraint_texts``, a history longer than ``keep`` is still the
    last ``keep`` messages (recent user lines already sit in that tail).

    Upper bound when fidelity rows sit outside the tail:
    ``keep + keep_user + MAX_CONSTRAINT_EXTRAS``.
    """
    items = list(messages or [])
    if keep < 1:
        keep = 1
    if len(items) <= keep:
        return items
    tail = items[-keep:]
    chosen = {message.id for message in tail}
    extras: list[RoomMessage] = []

    if keep_user > 0:
        users = [message for message in items if message.role == "user" or message.speaker == "user"]
        for message in users[-keep_user:]:
            if message.id not in chosen:
                extras.append(message)
                chosen.add(message.id)

    hits = 0
    for message in items:
        if hits >= MAX_CONSTRAINT_EXTRAS:
            break
        if message.id in chosen:
            continue
        if _hits_constraint(message.content or "", list(constraint_texts or [])):
            extras.append(message)
            chosen.add(message.id)
            hits += 1

    if not extras:
        return tail
    return [message for message in items if message.id in chosen]


def prepare_room_transcript(
    messages: list[RoomMessage],
    *,
    workspace,
    room_id: str | None = None,
    keep: int = 40,
    store=None,
    host=None,
) -> list[RoomMessage]:
    """Flush, absorb constraints, then compact. Compact failure keeps the bubbles and the card."""
    from pathlib import Path

    from local.harness.ephemeral import scrub_room_messages

    items = scrub_room_messages(list(messages or []))
    try:
        from local.compact.flush import memory_flush

        rows = []
        for message in items:
            if message.role == "user" or message.speaker == "user":
                rows.append({
                    "role": "user",
                    "content": message.content,
                    "metadata": dict(message.meta or {}),
                })
        if rows:
            memory_flush(rows, store=store, host=host)
            pinned = {row["content"]: row.get("metadata") or {} for row in rows}
            for message in items:
                meta = pinned.get(message.content) or {}
                if meta.get("compact") == "never":
                    message.meta = dict(message.meta or {})
                    message.meta["compact"] = "never"
    except Exception:
        pass
    try:
        from local.constraints.extract import absorb_messages

        absorb_messages(workspace, items)
    except Exception:
        pass
    try:
        from local.constraints.card import ConstraintStore

        texts = ConstraintStore(workspace).active_texts()
        compacted = compact_room_messages(items, keep=keep, constraint_texts=texts, keep_user=10)
    except Exception:
        return items
    if room_id and len(compacted) < len(items):
        flag = Path(workspace) / "rooms" / f"{room_id}.resumed_after_compact"
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("1", encoding="utf-8")
    return compacted
