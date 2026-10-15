"""Parse ``/compact`` so the TUI can intercept it before a normal chat turn."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .policy import FOCUS_MAX_CHARS, clamp_focus

_COMMAND = re.compile(r"^/compact\b", re.IGNORECASE)
_FOCUS_LABEL = re.compile(r"^(焦点|focus)\s*[:：]\s*", re.IGNORECASE)


@dataclass(frozen=True)
class CompactCommand:
    focus: str | None
    raw: str


def parse_compact_command(text: str) -> CompactCommand | None:
    """Return a command when ``text`` starts with ``/compact``. Otherwise None."""
    raw = (text or "").strip()
    if not raw or _COMMAND.match(raw) is None:
        return None
    rest = _COMMAND.sub("", raw, count=1).strip()
    if not rest:
        return CompactCommand(focus=None, raw=raw)
    rest = _FOCUS_LABEL.sub("", rest, count=1).strip()
    if len(rest) > FOCUS_MAX_CHARS:
        rest = rest[:FOCUS_MAX_CHARS]
    return CompactCommand(focus=clamp_focus(rest), raw=raw)
