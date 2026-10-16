"""Rule-based host wrap-up. No selector model and no network.

``LIGHTAGENT_ROOM_HOST_LLM`` is ignored. This minimum set does not grow an
LLM branch for the host line.
"""

from __future__ import annotations

from .types import RoomMessage

_FALLBACK = "可以说「今日健身和饮食」，或 @某位成员。"
_MENTION_MISS = "没有在本群成员里找到这个 @。可以说「今日健身和饮食」，或 @一位成员。"


def _one_action(label: str, content: str) -> str:
    """Name who spoke. Their sentence stays in their own bubble."""
    del content
    name = (label or "成员").strip() or "成员"
    return f"{name}已给出建议"


def render_host_summary(
    bubbles: list[RoomMessage],
    *,
    user_text: str = "",
    constraints: list[str] | None = None,
    next_step: str | None = None,
) -> str:
    """Three lines: action, active constraints, next step. No full child paste."""
    named = [item for item in bubbles if item.speaker.startswith("bot:") and item.kind == "chat"]
    if not named:
        errors = [item.content for item in bubbles if item.kind == "error"]
        if errors:
            return f"这轮没能请到成员。{errors[0]}"
        if "@" in (user_text or ""):
            return _MENTION_MISS
        return _FALLBACK
    actions: list[str] = []
    seen: set[str] = set()
    for item in named[:6]:
        clause = _one_action(item.speaker_label, item.content)
        if clause in seen:
            continue
        seen.add(clause)
        actions.append(clause)
    diet_items = [str(text).strip() for text in (constraints or []) if str(text).strip()]
    diet = "、".join(diet_items) if diet_items else "（无）"
    step = " ".join((next_step or "").split()) or _FALLBACK
    user_norm = " ".join((user_text or "").split())
    if len(user_norm) >= 8 and user_norm in step:
        step = _FALLBACK
    summary = "\n".join([
        "动作：" + "；".join(actions),
        "忌口：" + diet,
        "下一步：" + step,
    ])
    if len(user_norm) >= 8 and summary.count(user_norm) > 1:
        summary = summary.replace(user_norm, "", 1)
    return summary
