"""Sidebar preview text: plain latest message, capped by grapheme clusters."""

from __future__ import annotations

import re
import unicodedata

PREVIEW_GRAPHEMES = 15
EMPTY_PREVIEW = "新会话"

_MARKDOWN = re.compile(r"[*_`#>|]")
_MARKS = frozenset({"Mn", "Me", "Mc"})
_ZWJ = "\u200d"
_VARIATION = frozenset({"\ufe0e", "\ufe0f"})
_KEYCAP = "\u20e3"


def _regional(ch: str) -> bool:
    code = ord(ch)
    return 0x1F1E6 <= code <= 0x1F1FF


def _skin(ch: str) -> bool:
    code = ord(ch)
    return 0x1F3FB <= code <= 0x1F3FF


def _tag(ch: str) -> bool:
    code = ord(ch)
    return 0xE0020 <= code <= 0xE007F


def _extends(ch: str) -> bool:
    return (
        ch in _VARIATION
        or ch == _KEYCAP
        or _skin(ch)
        or _tag(ch)
        or unicodedata.category(ch) in _MARKS
    )


def grapheme_clusters(text: str) -> list[str]:
    """Extended grapheme clusters for sidebar truncation.

    Covers combining marks, variation selectors, ZWJ sequences, skin tones,
    regional-indicator pairs, keycaps, and tags. CRLF counts as one cluster.
    """
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    clusters: list[str] = []
    index = 0
    size = len(normalized)
    while index < size:
        char = normalized[index]
        buf = char
        index += 1
        if _regional(char) and index < size and _regional(normalized[index]):
            buf += normalized[index]
            index += 1
        while index < size:
            nxt = normalized[index]
            if nxt == _ZWJ and index + 1 < size:
                buf += nxt + normalized[index + 1]
                index += 2
                continue
            if _extends(nxt):
                buf += nxt
                index += 1
                continue
            break
        clusters.append(buf)
    return clusters


def grapheme_len(text: str) -> int:
    return len(grapheme_clusters(text))


def truncate_graphemes(text: str, limit: int = PREVIEW_GRAPHEMES) -> str:
    """Keep the first ``limit`` graphemes. No ellipsis."""
    if limit <= 0:
        return ""
    clusters = grapheme_clusters(text)
    if len(clusters) <= limit:
        return "".join(clusters)
    return "".join(clusters[:limit])


def plain_message(text: str) -> str:
    """Drop a few markdown markers and collapse whitespace."""
    return " ".join(_MARKDOWN.sub("", str(text)).split())


def latest_message_text(events) -> str:
    """Latest visible user/agent message, untruncated. Empty string if none."""
    for kind, text in reversed(list(events or [])):
        if kind not in ("user", "agent"):
            continue
        plain = plain_message(text)
        if plain:
            return plain
    return ""


def message_preview(text: str, *, empty: str = EMPTY_PREVIEW) -> str:
    plain = plain_message(text)
    if not plain:
        return empty
    return truncate_graphemes(plain, PREVIEW_GRAPHEMES)
