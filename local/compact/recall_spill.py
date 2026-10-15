"""Recall tool results that compaction moved out of the context window."""

from __future__ import annotations

import threading
from typing import Any


class SpillStore:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def add_many(self, spilled: list[dict[str, Any]]) -> None:
        with self._lock:
            for item in spilled:
                reference = item.get("reference")
                if reference:
                    self._items[str(reference)] = dict(item)

    def recall(self, reference: str, *, query: str = "", max_chars: int = 800) -> str:
        key = (reference or "").strip()
        if not key:
            return ""
        with self._lock:
            item = self._items.get(key)
            if item is None:
                for stored_key, stored in self._items.items():
                    if key in stored_key or stored.get("sha256") == key:
                        item = stored
                        break
        if item is None:
            return ""
        content = str(item.get("content") or "")
        limit = max(1, int(max_chars))
        if query and query in content:
            index = content.index(query)
            start = max(0, index - 40)
            return content[start:start + limit]
        return content[:limit]


_STORE = SpillStore()


def get_spill_store() -> SpillStore:
    return _STORE


def reset_spill_store() -> None:
    global _STORE
    _STORE = SpillStore()


def recall_spilled(reference: str, query: str = "", max_chars: int = 800) -> str:
    """取回被压缩外置的工具结果片段。找不到时返回说明，不抛错。"""
    text = get_spill_store().recall(reference, query=query, max_chars=max_chars)
    if text:
        return text
    return f"未找到外置结果：{reference}"


recall_spilled.tool_info = {
    "tool_name": "recall_spilled",
    "tool_description": "取回压缩时外置的工具结果片段。传入 spill reference，可选用 query 定位原文。",
    "tool_params": [
        {"name": "reference", "description": "tool-result:sha256:... 指针", "type": "string", "required": True},
        {"name": "query", "description": "可选，原文中的定位词", "type": "string", "required": False},
        {"name": "max_chars", "description": "返回片段的最大字符数", "type": "number", "required": False},
    ],
}
