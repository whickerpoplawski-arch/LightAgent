"""Keep packs on the ephemeral lane. Persisted transcripts stay clean.

``<memory-context>`` (and persona / identity blocks) may be injected into the
system lane for one model request. They must not be written into user or
assistant history, room files, or a child task.
"""

from __future__ import annotations

_MARKERS = ("<memory-context>", "</memory-context>", "<persona>", "</persona>", "<identity")


def _has_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _MARKERS)


def assert_transcript_clean(messages: list[dict] | None) -> None:
    """Raise if ``<memory-context>`` appears in any persisted message."""
    for index, message in enumerate(messages or []):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        blob = content if isinstance(content, str) else ""
        lowered = blob.lower()
        if "<memory-context>" in lowered or "</memory-context>" in lowered:
            role = message.get("role", "")
            raise AssertionError(
                f"<memory-context> in persisted {role} message at index {index}"
            )


def clean_persisted_text(text: str | None) -> str:
    """Drop ephemeral blocks from one persisted string. Untagged text is unchanged."""
    raw = "" if text is None else str(text)
    if not _has_marker(raw):
        return raw
    from local.memory.inject import strip_ephemeral as strip_messages
    from local.rooms.digest import strip_ephemeral as strip_text

    stripped = strip_messages([{"role": "user", "content": raw}])
    content = stripped[0].get("content") if stripped else ""
    return strip_text(str(content or ""))


def sanitize_transcript(messages: list[dict] | None) -> list[dict]:
    """Copy of ``messages`` safe to store. Packs are removed, then asserted gone."""
    cleaned: list[dict] = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        item = dict(message)
        content = item.get("content")
        if isinstance(content, str):
            item["content"] = clean_persisted_text(content)
        cleaned.append(item)
    assert_transcript_clean(cleaned)
    return cleaned


def prepare_model_inputs(history: list[dict] | None, prompt: str) -> tuple[list[dict], str]:
    """History and user sentence passed to ``agent.run`` after the pack is stripped."""
    cleaned_history = sanitize_transcript(history)
    cleaned_prompt = clean_persisted_text(prompt)
    assert_transcript_clean(cleaned_history + [{"role": "user", "content": cleaned_prompt}])
    return cleaned_history, cleaned_prompt


def scrub_room_messages(messages: list) -> list:
    """Strip ephemeral blocks from room bubbles in place. Does not drop bubbles."""
    for message in messages or []:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            message.content = clean_persisted_text(content)
    return list(messages or [])
