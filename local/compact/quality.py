"""Quality gate for summarizer output. Failure means drop the summary."""

from __future__ import annotations

import re
from typing import Any

_EPHEMERAL_TAGS = ("<identity", "<persona>", "<memory-context>")
_SPACE_RE = re.compile(r"space_id\s*[:：]\s*([A-Za-z0-9_\-]+)")


def _section_body(summary: str, keyword: str) -> str | None:
    lines = summary.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("##") and keyword in line:
            start = index
            break
    if start is None:
        return None
    body: list[str] = []
    for line in lines[start + 1:]:
        if line.startswith("##"):
            break
        body.append(line)
    return "\n".join(body).strip()


def _untrusted(message: dict[str, Any]) -> bool:
    if message.get("role") == "tool":
        return True
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        return False
    trust = str(metadata.get("trust") or metadata.get("source") or "").lower()
    return bool(metadata.get("untrusted") or trust in {"untrusted", "web", "tool"})


def audit_summary(
    summary: str | None,
    *,
    original_messages: list[dict[str, Any]],
    removed: list[dict[str, Any]],
    space_id: str | None = None,
    ephemeral_bodies: list[str] | None = None,
) -> tuple[bool, str]:
    """Return (ok, reason). Empty, tag leaks, and missing safety sections fail."""
    text = (summary or "").strip()
    if not text:
        return False, "empty"
    for tag in _EPHEMERAL_TAGS:
        if tag in text:
            return False, "ephemeral tag"
    for body in ephemeral_bodies or []:
        probe = body.strip()
        if len(probe) >= 12 and probe in text:
            return False, "ephemeral body"
        if len(probe) >= 24 and probe[:24] in text:
            return False, "ephemeral body"
    if _section_body(text, "禁止事项") is None:
        return False, "missing 禁止事项"
    if _section_body(text, "未决") is None:
        return False, "missing 未决"
    for keyword in ("禁止事项", "未决"):
        body = _section_body(text, keyword)
        if body is not None and body == "":
            return False, f"empty {keyword}"
    if space_id:
        for match in _SPACE_RE.finditer(text):
            if match.group(1) != space_id:
                return False, "cross space"
    for message in removed:
        if not _untrusted(message):
            continue
        content = str(message.get("content") or "")
        if content.startswith("[Tool result stored"):
            continue
        if len(content) >= 48:
            snippet = content[10:58]
            if snippet and snippet in text:
                return False, "untrusted promotion"
    del original_messages
    return True, ""
