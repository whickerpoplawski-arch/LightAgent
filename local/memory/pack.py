"""Token-budgeted memory pack.

Priority (kept first, trimmed from the tail): pinned and veto, other general
preferences, then situational hits. Situational rows are included only when
the current query shares a topic with them.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from .host import MemoryHost
from .store import ProfileStore
from .types import (
    CHARS_PER_TOKEN,
    DEFAULT_PACK_BUDGET_TOKENS,
    UNAVAILABLE_NOTICE,
    Learning,
    MemoryPack,
    PreferenceLane,
    estimate_tokens,
)

_LATIN = re.compile(r"[a-z0-9_]{2,}")
_CJK = re.compile(r"[\u4e00-\u9fff]+")
_STOP = {
    "的", "了", "我", "是", "在", "和", "也", "就", "不", "有", "这", "那",
    "一个", "什么", "怎么", "今天", "一下", "please", "the", "and", "you",
}
# Short nicknames stay in the pack even if the chat already mentioned them.
_MIN_WINDOW_EXCLUDE = 8


def tokens(text: str) -> set[str]:
    found: set[str] = set()
    lowered = (text or "").lower()
    found.update(match.group(0) for match in _LATIN.finditer(lowered))
    for block in _CJK.findall(text or ""):
        if len(block) == 1:
            found.add(block)
            continue
        found.add(block)
        for index in range(len(block) - 1):
            found.add(block[index:index + 2])
    return {item for item in found if item not in _STOP}


def topic_overlap(query: str, learning: Learning) -> bool:
    query_tokens = tokens(query)
    if not query_tokens:
        return False
    bag = tokens(learning.text)
    bag.update(tokens(" ".join(learning.topics)))
    return bool(query_tokens & bag)


def already_in_prompt(text: str, window_texts: list[str] | tuple[str, ...]) -> bool:
    needle = (text or "").strip()
    if len(needle) < _MIN_WINDOW_EXCLUDE:
        return False
    return any(needle in (blob or "") for blob in window_texts)


def _sort_key(item: Learning) -> tuple[int, int, float]:
    pin_rank = 0 if item.pinned or item.facet == "veto" else 1
    lane_rank = 0 if item.lane == PreferenceLane.GENERAL.value else 1
    return (lane_rank, pin_rank, -item.confidence)


def _line(item: Learning) -> str:
    mark = "pin " if item.pinned else ""
    return f"- [{mark}{item.lane}/{item.facet}] {item.text}"


def build_pack(
    learnings: list[Learning],
    *,
    query: str,
    budget_tokens: int = DEFAULT_PACK_BUDGET_TOKENS,
    window_texts: list[str] | tuple[str, ...] | None = None,
    space_id: str | None = None,
) -> MemoryPack:
    """Assemble a pack. ``learnings`` must already be the caller's scope."""
    window = list(window_texts or [])
    budget = max(32, int(budget_tokens))
    general: list[Learning] = []
    situational: list[Learning] = []
    skipped: list[str] = []

    for item in learnings:
        if not item.injectable or item.status != "active" or not item.confirmed:
            skipped.append(item.id)
            continue
        if item.space_id and space_id and item.space_id != space_id:
            skipped.append(item.id)
            continue
        if already_in_prompt(item.text, window):
            skipped.append(item.id)
            continue
        if item.lane == PreferenceLane.SITUATIONAL.value:
            if topic_overlap(query, item):
                situational.append(item)
            else:
                skipped.append(item.id)
            continue
        general.append(item)

    general.sort(key=_sort_key)
    situational.sort(key=_sort_key)

    def render(rows: list[Learning], title: str) -> list[str]:
        if not rows:
            return []
        return [title, *[_line(item) for item in rows]]

    # Tail sections are dropped first: situational, then unpinned general.
    general_lines = render(general, "## 常驻偏好")
    situational_lines = render(situational, "## 情景偏好")
    while _over_budget(general_lines, situational_lines, budget) and (situational_lines or general_lines):
        if len(situational_lines) > 1:
            dropped = situational_lines.pop()
            skipped.append(dropped)
            if len(situational_lines) == 1:
                situational_lines.clear()
            continue
        if situational_lines:
            skipped.extend(situational_lines)
            situational_lines = []
            continue
        if len(general_lines) > 1:
            dropped = general_lines.pop()
            skipped.append(dropped)
            if len(general_lines) == 1:
                general_lines.clear()
            continue
        skipped.extend(general_lines)
        general_lines = []

    parts = ["# 用户画像"]
    if general_lines:
        parts.extend(general_lines)
    if situational_lines:
        parts.extend(situational_lines)
    if len(parts) == 1:
        markdown = ""
        sections: tuple[str, ...] = ()
    else:
        markdown = "\n".join(parts).strip()
        sections = tuple(
            name for name, lines in (("general", general_lines), ("situational", situational_lines)) if lines
        )
    refs = tuple(item.id for item in general + situational if _line(item) in markdown)
    return MemoryPack(
        markdown=markdown,
        tokens=estimate_tokens(markdown),
        refs=refs,
        sections=sections,
        skipped=tuple(skipped),
    )


def _over_budget(general_lines: list[str], situational_lines: list[str], budget: int) -> bool:
    body = "\n".join(["# 用户画像", *general_lines, *situational_lines]).strip()
    return estimate_tokens(body) > budget


def unavailable_pack(notice: str = UNAVAILABLE_NOTICE) -> MemoryPack:
    return MemoryPack(
        markdown="",
        tokens=estimate_tokens(notice),
        unavailable=True,
        notice=notice,
        sections=("unavailable",),
    )


@dataclass
class PackCache:
    """Short-lived pack cache so a live turn can reuse a finished pack."""

    ttl_seconds: float = 60.0
    _entries: dict[tuple, tuple[float, MemoryPack]] | None = None

    def __post_init__(self) -> None:
        self._entries = {}

    def get(self, key: tuple) -> MemoryPack | None:
        assert self._entries is not None
        found = self._entries.get(key)
        if found is None:
            return None
        saved_at, pack = found
        if time.monotonic() - saved_at > self.ttl_seconds:
            self._entries.pop(key, None)
            return None
        return MemoryPack(
            markdown=pack.markdown,
            tokens=pack.tokens,
            refs=pack.refs,
            sections=pack.sections,
            skipped=pack.skipped,
            unavailable=pack.unavailable,
            notice=pack.notice,
            cached=True,
        )

    def put(self, key: tuple, pack: MemoryPack) -> None:
        assert self._entries is not None
        self._entries[key] = (time.monotonic(), pack)


def build_for_turn(
    store: ProfileStore,
    host: MemoryHost,
    *,
    query: str,
    window_texts: list[str] | None = None,
    budget_tokens: int = DEFAULT_PACK_BUDGET_TOKENS,
    cache: PackCache | None = None,
) -> MemoryPack:
    """Build a pack from local storage. Failures become an unavailable notice."""
    try:
        revision = store.revision()
        key = (host.user_id, host.namespace, host.space_id or "", query.strip(), revision, int(budget_tokens))
        if cache is not None:
            cached = cache.get(key)
            if cached is not None:
                return cached
        rows = store.list_injectable(user_id=host.user_id, namespace=host.namespace)
        pack = build_pack(
            rows,
            query=query,
            budget_tokens=budget_tokens,
            window_texts=window_texts,
            space_id=host.space_id,
        )
    except Exception:
        return unavailable_pack()
    if cache is not None:
        cache.put(key, pack)
    return pack


def chars_per_token() -> int:
    return CHARS_PER_TOKEN
