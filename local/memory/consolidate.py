"""Zero-LLM fold for profile learnings and the diet card.

Topic identity comes from ``local.constraints.card.topic_key``. Rows that are
not the same normalized text and not the same topic stay as they are.
"""

from __future__ import annotations

import re

from local.constraints.card import ConstraintCard, retire, supersede, topic_key
from local.memory.types import Learning

_PIN_MARK = "[PINNED]"


def normalize_text(text: str) -> str:
    """Collapse whitespace and treat fullwidth punctuation as the same mark."""
    folded = (text or "").replace("\u3000", " ")
    for src, dst in (("：", ":"), ("，", ","), ("。", "."), ("；", ";")):
        folded = folded.replace(src, dst)
    folded = " ".join(folded.split()).strip().lower()
    return re.sub(r"\s*([:,.;])\s*", r"\1", folded)


def _blank_diff() -> dict[str, list]:
    return {"merged": [], "superseded": [], "kept": [], "skipped": []}


def _stamp(item_id: str, text: str, reason: str) -> dict[str, str]:
    return {"id": item_id, "text": text, "reason": reason}


def learning_skip_reason(row: Learning) -> str | None:
    if row.status == "superseded":
        return "already_superseded"
    if row.pinned or _PIN_MARK in (row.text or ""):
        return "pinned"
    if row.status != "active" or not row.injectable or not row.confirmed:
        return "not_active"
    return None


def _by_time(row: Learning) -> tuple[str, str]:
    return (row.updated_at or "", row.id)


def plan_learnings(rows: list[Learning]) -> dict[str, list]:
    """Decide which active rows to retire. The keeper row is not edited."""
    diff = _blank_diff()
    pinned = [row for row in rows if learning_skip_reason(row) == "pinned" and row.status == "active"]
    candidates: list[Learning] = []
    for row in rows:
        reason = learning_skip_reason(row)
        if reason == "already_superseded":
            continue
        if reason:
            diff["skipped"].append(_stamp(row.id, row.text, reason))
            if row.status == "active":
                diff["kept"].append({"id": row.id, "text": row.text})
            continue
        candidates.append(row)

    pin_by_norm = {normalize_text(row.text): row for row in pinned}
    pin_topics = {topic_key(row.text) for row in pinned}
    pin_topics.discard(None)
    groups: dict[str, list[Learning]] = {}
    for row in candidates:
        groups.setdefault(normalize_text(row.text), []).append(row)

    consumed: set[str] = set()
    for norm, group in groups.items():
        ordered = sorted(group, key=_by_time)
        pin = pin_by_norm.get(norm)
        if pin is not None:
            drop = ordered
            keeper_id = pin.id
            keeper_text = pin.text
        elif len(ordered) >= 2:
            keeper = ordered[-1]
            drop = ordered[:-1]
            keeper_id = keeper.id
            keeper_text = keeper.text
            consumed.add(keeper.id)
        else:
            continue
        for old in drop:
            consumed.add(old.id)
            diff["merged"].append({
                "id": old.id,
                "kept_id": keeper_id,
                "text": keeper_text,
                "kind": "merge",
            })

    remaining = [row for row in candidates if row.id not in consumed]
    by_topic: dict[str, list[Learning]] = {}
    for row in remaining:
        topic = topic_key(row.text)
        if topic and topic in pin_topics:
            diff["skipped"].append(_stamp(row.id, row.text, "pinned_topic"))
            diff["kept"].append({"id": row.id, "text": row.text})
            continue
        if not topic:
            diff["skipped"].append(_stamp(row.id, row.text, "distinct"))
            diff["kept"].append({"id": row.id, "text": row.text})
            continue
        by_topic.setdefault(topic, []).append(row)

    for topic, group in by_topic.items():
        ordered = sorted(group, key=_by_time)
        if len(ordered) == 1:
            diff["kept"].append({"id": ordered[0].id, "text": ordered[0].text})
            continue
        keeper = ordered[-1]
        for old in ordered[:-1]:
            diff["superseded"].append({
                "id": old.id,
                "kept_id": keeper.id,
                "text": keeper.text,
                "topic": topic,
                "kind": "topic",
            })
        diff["kept"].append({"id": keeper.id, "text": keeper.text})
    return diff


def _item_key(item) -> tuple[str, str]:
    return (item.updated_at or "", item.id)


def fold_card(card: ConstraintCard, *, pinned_texts: set[str] | None = None) -> dict[str, list]:
    """Fold active diet rows in place. Superseded rows stay on the card."""
    diff = _blank_diff()
    pinned_norms = {normalize_text(text) for text in (pinned_texts or set()) if normalize_text(text)}
    active = [item for item in card.items if item.status == "active"]
    protected_ids: set[str] = set()
    for item in active:
        if _PIN_MARK in item.text or normalize_text(item.text) in pinned_norms:
            protected_ids.add(item.id)
            diff["skipped"].append(_stamp(item.id, item.text, "pinned"))
            diff["kept"].append({"id": item.id, "text": item.text})

    protected_norms = {normalize_text(item.text) for item in active if item.id in protected_ids}
    protected_topics = {
        item.topic or topic_key(item.text)
        for item in active
        if item.id in protected_ids and (item.topic or topic_key(item.text))
    }
    candidates = []
    for item in active:
        if item.id in protected_ids:
            continue
        if normalize_text(item.text) in protected_norms:
            retire(card, item.id)
            diff["merged"].append({
                "id": item.id,
                "kept_id": "pinned",
                "text": item.text,
                "kind": "merge",
            })
            continue
        candidates.append(item)

    groups: dict[str, list] = {}
    for item in candidates:
        if item.status != "active":
            continue
        groups.setdefault(normalize_text(item.text), []).append(item)
    for group in groups.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=_item_key)
        keeper = ordered[-1]
        for old in ordered[:-1]:
            retire(card, old.id)
            diff["merged"].append({
                "id": old.id,
                "kept_id": keeper.id,
                "text": keeper.text,
                "kind": "merge",
            })

    remaining = [
        item for item in card.items
        if item.status == "active" and item.id not in protected_ids and _PIN_MARK not in item.text
    ]
    by_topic: dict[str, list] = {}
    for item in remaining:
        topic = item.topic or topic_key(item.text)
        if topic and topic in protected_topics:
            diff["skipped"].append(_stamp(item.id, item.text, "pinned_topic"))
            diff["kept"].append({"id": item.id, "text": item.text})
            continue
        if not topic:
            diff["skipped"].append(_stamp(item.id, item.text, "distinct"))
            diff["kept"].append({"id": item.id, "text": item.text})
            continue
        by_topic.setdefault(topic, []).append(item)

    for topic, group in by_topic.items():
        ordered = sorted(group, key=_item_key)
        if len(ordered) == 1:
            diff["kept"].append({"id": ordered[0].id, "text": ordered[0].text})
            continue
        keeper = ordered[-1]
        for old in ordered[:-1]:
            if old.text == keeper.text:
                retire(card, old.id)
            else:
                supersede(card, old_id_or_text=old.id, new_text=keeper.text)
                if any(item.id == old.id and item.status == "active" for item in card.items):
                    retire(card, old.id)
            diff["superseded"].append({
                "id": old.id,
                "kept_id": keeper.id,
                "text": keeper.text,
                "topic": topic,
                "kind": "topic",
            })
        diff["kept"].append({"id": keeper.id, "text": keeper.text})
    return diff
