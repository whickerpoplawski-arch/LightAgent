"""Rule extractor for diet limits. No model calls."""

from __future__ import annotations

from pathlib import Path

from .card import ConstraintCard, ConstraintStore, forget, remember, supersede, topic_key

_REMEMBER = (
    "忌口",
    "过敏",
    "不能吃",
    "不要吃",
    "别吃",
    "硬限制",
    "禁忌",
    "千万别再",
    "千万别",
    "别再给",
    "不要再",
    "别给我",
    "以后别",
)
_LIFT = ("其实可以", "可以吃了", "现在可以吃", "不再忌", "不用忌", "取消忌", "不忌了", "能吃了", "改成可以")
_FORGET = ("忘掉忌口", "忘记忌口", "删掉忌口", "不要记住忌口", "清除忌口")


def _is_question(text: str) -> bool:
    return any(mark in text for mark in ("什么", "吗", "？", "?"))


def classify_utterance(text: str) -> str | None:
    """``remember``, ``supersede``, ``forget``, or None. Questions are not constraints."""
    cleaned = (text or "").strip()
    if not cleaned or _is_question(cleaned):
        return None
    if any(phrase in cleaned for phrase in _FORGET):
        return "forget"
    if any(phrase in cleaned for phrase in _LIFT):
        return "supersede"
    if any(phrase in cleaned for phrase in _REMEMBER):
        return "remember"
    return None


def apply_utterance(card: ConstraintCard, text: str) -> ConstraintCard | None:
    """Update ``card`` in place when the sentence is a constraint op. None means ignored."""
    kind = classify_utterance(text)
    if kind == "remember":
        return remember(card, text)
    if kind == "forget":
        return forget(card, text)
    if kind == "supersede":
        target_hint = text
        # Prefer an existing same-theme row over treating the lift sentence as its own id.
        if topic_key(text):
            return supersede(card, old_id_or_text=target_hint, new_text=text.strip())
        return supersede(card, old_id_or_text=text, new_text=text.strip())
    return None


def absorb_user_text(workspace: Path | str, text: str) -> ConstraintCard:
    """1:1 user sentence. Same card path as a single user bubble. No model call."""
    return absorb_messages(workspace, [{"role": "user", "content": text or ""}])


def absorb_messages(workspace: Path | str, messages: list) -> ConstraintCard:
    """Replay user bubbles into the card. Failures leave the file untouched."""
    store = ConstraintStore(workspace)
    card = store.load()
    changed = False
    for message in messages or []:
        speaker = getattr(message, "speaker", None)
        role = getattr(message, "role", None)
        if isinstance(message, dict):
            speaker = message.get("speaker", speaker)
            role = message.get("role", role)
            content = message.get("content")
        else:
            content = getattr(message, "content", None)
        if role != "user" and speaker != "user":
            continue
        if not isinstance(content, str):
            continue
        updated = apply_utterance(card, content)
        if updated is not None:
            card = updated
            changed = True
    if changed:
        store.save(card)
    return card
