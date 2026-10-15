"""Deterministic reply that cites only active ConstraintCard lines. No model."""

from __future__ import annotations

from .card import TOPICS


def grounded_reply(active_texts: list[str], ask: str = "") -> str:
    """Mention every active line. Refuse a food only when that word is on the card."""
    lines = [text.strip() for text in active_texts or [] if text and text.strip()]
    if not lines:
        return "忌口卡没有 active 记录，不编造限制。"
    refused: list[str] = []
    ask_text = ask or ""
    for _key, words in TOPICS:
        for word in words:
            if word in ask_text and any(word in line for line in lines) and word not in refused:
                refused.append(word)
    refuse = "".join(f"不推荐{word}。" for word in refused)
    cited = "；".join(lines)
    return f"按忌口卡：{cited}。{refuse}不另加卡上没有的限制。"
