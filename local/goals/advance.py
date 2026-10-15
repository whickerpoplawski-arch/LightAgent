"""Mark the current life-goal step done from a spoken sentence. No model call."""

from __future__ import annotations

from pathlib import Path

from .store import LifeGoal, get_active_goal, set_step_status

_QUESTION = ("什么", "吗", "？", "?")
_SHORT = ("今天吃什么", "吃什么好", "今天天气呢", "现在几点")
_PHRASES = (
    "训练日定好了",
    "这步完成了",
    "好了，下一步",
    "好了,下一步",
    "继续下一步",
    "定好了",
    "完成了",
    "下一步",
)
_MARKERS = ("定好", "好了", "完成", "定了")


def _title_keyword_hit(title: str, text: str) -> bool:
    compact = "".join((title or "").split())
    if len(compact) < 2 or not any(mark in text for mark in _MARKERS):
        return False
    if compact in text:
        return True
    for size in range(len(compact) - 1, 1, -1):
        for start in range(0, len(compact) - size + 1):
            piece = compact[start:start + size]
            if piece in text:
                return True
    return False


def parse_step_advance(user_text: str, *, step_title: str = "") -> str | None:
    """``complete_current`` when the sentence closes the step. Questions do not."""
    text = " ".join((user_text or "").split())
    if not text or any(mark in text for mark in _QUESTION):
        return None
    if any(phrase in text for phrase in _SHORT):
        return None
    if _title_keyword_hit(step_title, text):
        return "complete_current"
    if any(phrase in text for phrase in _PHRASES):
        return "complete_current"
    return None


def maybe_advance_goal(workspace: Path | str, space_id: str, user_text: str) -> LifeGoal | None:
    """Complete the in-progress step and start the next pending one. No goal, no change."""
    goal = get_active_goal(workspace, space_id)
    if goal is None:
        return None
    current = next((step for step in goal.steps if step.status == "in_progress"), None)
    if current is None or parse_step_advance(user_text, step_title=current.title) is None:
        return None
    updated = set_step_status(workspace, goal.goal_id, current.id, "completed")
    if updated.status == "completed":
        return updated
    nxt = next((step for step in updated.steps if step.status == "pending"), None)
    if nxt is None:
        return updated
    return set_step_status(workspace, updated.goal_id, nxt.id, "in_progress")
