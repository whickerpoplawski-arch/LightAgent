"""Explicit and template goal triggers. Short questions do not open a goal."""

from __future__ import annotations

_TEMPLATE_PHRASES = ("今日健身和饮食", "今天健身和饮食", "安排今日健身和饮食")


def should_create_goal(user_text: str, *, room_scenario: str | None = None) -> bool:
    """True only for an explicit plan request or a fitness-diet template confirmation."""
    text = " ".join((user_text or "").split())
    if not text:
        return False
    if text.startswith("/goal"):
        body = text[5:].strip()
        return bool(body)
    if any(phrase in text for phrase in ("吃什么", "天气", "吃什么好")) and "计划" not in text and "追踪" not in text:
        return False
    if "帮我制定" in text and "计划" in text:
        return True
    if "开始追踪" in text or "开始计划" in text:
        return True
    if any(phrase in text for phrase in ("制定一个计划", "做一个计划", "做个计划")):
        return True
    if ("做个" in text or "做一个" in text) and ("计划" in text or "安排" in text):
        return True
    if "安排一周" in text and any(word in text for word in ("健身", "饮食", "锻炼", "训练")):
        return True
    if "一周" in text and ("餐单" in text or "饮食计划" in text):
        return True
    if "帮我安排" in text and any(word in text for word in ("训练", "饮食", "健身", "锻炼")):
        return True
    template = any(phrase in text for phrase in _TEMPLATE_PHRASES)
    if not template:
        return False
    if any(phrase in text for phrase in ("吃什么", "天气")):
        return False
    return room_scenario in (None, "", "fitness_diet")
