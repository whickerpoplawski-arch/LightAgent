"""Scenario templates for rule-based speaker selection. No selector LLM."""

from __future__ import annotations

from local.conversations.collaborate import resolve_bot
from local.conversations.models import ConversationMeta

# A room fires fitness_diet only when the user clearly asks for both sides,
# or uses an explicit combo phrase. One keyword alone stays host-only.
_MOVE = ("健身", "锻炼", "运动", "今日练")
_DIET = ("饮食", "配餐", "吃什么")
_EXPLICIT = ("健身和饮食", "运动和饮食", "锻炼和饮食")

# slot id, match keys (template_id / role_title / title)
_FITNESS_SLOTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("habit_coach", ("habit_coach", "习惯教练")),
    ("nutrition_advisor", ("nutrition_advisor", "饮食顾问")),
)

SLOT_LABEL = {
    "habit_coach": "习惯教练",
    "nutrition_advisor": "饮食顾问",
}


def match_fitness_diet(text: str) -> bool:
    """Pure trigger. Idle chat and a single topic do not pull the whole room."""
    folded = (text or "").casefold()
    if any(phrase in folded for phrase in _EXPLICIT):
        return True
    move = any(word in folded for word in _MOVE)
    diet = any(word in folded for word in _DIET)
    return move and diet


def member_matches(meta: ConversationMeta, keys: tuple[str, ...]) -> bool:
    haystacks = [
        meta.identity.template_id or "",
        meta.identity.role_title,
        meta.identity.display_name,
        meta.title,
    ]
    folded_keys = [key.casefold() for key in keys if key]
    for name in haystacks:
        folded = (name or "").casefold()
        if not folded:
            continue
        if folded in folded_keys or any(key in folded for key in folded_keys):
            return True
    return False


def assign_scenario_speakers(
    roster: list[ConversationMeta],
    member_ids: list[str],
    *,
    scenario_id: str,
) -> tuple[list[str], list[str]]:
    """Return (speaker ids, Chinese notices for missing slots)."""
    if scenario_id != "fitness_diet":
        return [], []
    members: list[ConversationMeta] = []
    for bot_id in member_ids:
        meta = resolve_bot(roster, bot_id)
        if meta is not None:
            members.append(meta)
    speakers: list[str] = []
    notices: list[str] = []
    used: set[str] = set()
    for slot, keys in _FITNESS_SLOTS:
        found = next((meta for meta in members if meta.id not in used and member_matches(meta, keys)), None)
        if found is None:
            notices.append(f"本群还没有{SLOT_LABEL[slot]}，这一轮已跳过。")
            continue
        used.add(found.id)
        speakers.append(found.id)
    return speakers, notices
