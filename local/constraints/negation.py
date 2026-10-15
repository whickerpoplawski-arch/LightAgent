"""Offline negation for life turns. No model call.

「别记」不写画像，「别搜」禁止联网工具，「别改忌口」不动忌口卡。
「别再给我花生」这类忌口句不是否定遵指，仍走记住。
"""

from __future__ import annotations

_DONT_REMEMBER = (
    "别记",
    "不要记",
    "别记住",
    "不要记住",
    "不用记",
    "不要写入记忆",
    "别写进记忆",
    "别记东西",
)
_DONT_SEARCH = (
    "别搜",
    "不要搜",
    "别查网",
    "不要查网",
    "不要网页搜索",
    "别上网查",
    "不要搜索",
)
_DONT_CHANGE_DIET = (
    "别改忌口",
    "不要改忌口",
    "别动忌口",
    "不要改我的忌口",
    "忌口别改",
    "别改饮食限制",
    "别改我的忌口",
)


def refusal_flags(text: str) -> dict[str, bool]:
    raw = text or ""
    return {
        "dont_remember": any(phrase in raw for phrase in _DONT_REMEMBER),
        "dont_search": any(phrase in raw for phrase in _DONT_SEARCH),
        "dont_change_diet": any(phrase in raw for phrase in _DONT_CHANGE_DIET),
    }


def plan_tools(text: str) -> list[str]:
    """Tools this turn must not call. Offline heuristic, not a live agent."""
    flags = refusal_flags(text)
    forbid: list[str] = []
    if flags["dont_search"]:
        forbid.extend(["web_search", "web_fetch"])
    if flags["dont_remember"]:
        forbid.append("memory_learn")
    return forbid
