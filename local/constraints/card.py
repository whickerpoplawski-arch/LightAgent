"""JSON constraint card. Supersede in place; injection sees only ``active`` rows."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Same-theme foods. A later utterance about one member replaces the active row.
TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("seafood", ("海鲜", "虾", "蟹", "鱼", "贝", "蛤", "蚝", "鱿鱼", "生蚝")),
    ("peanut", ("花生",)),
    ("dairy", ("牛奶", "乳糖", "奶制品", "奶酪")),
    ("gluten", ("麸质", "小麦", "面筋")),
    ("cilantro", ("香菜",)),
    ("spicy", ("辣椒",)),
    ("alcohol", ("酒精", "白酒", "啤酒")),
)


def topic_key(text: str) -> str | None:
    blob = text or ""
    for key, words in TOPICS:
        if any(word in blob for word in words):
            return key
    return None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_id(card: "ConstraintCard") -> str:
    used = {item.id for item in card.items}
    while True:
        candidate = uuid.uuid4().hex[:8]
        if candidate not in used:
            return candidate


@dataclass
class ConstraintItem:
    id: str
    text: str
    status: str = "active"
    updated_at: str = ""
    supersedes: str | None = None
    topic: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status,
            "updated_at": self.updated_at,
            "supersedes": self.supersedes,
            "topic": self.topic,
        }


@dataclass
class ConstraintCard:
    items: list[ConstraintItem] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    source: list[str] = field(default_factory=lambda: ["explicit"])

    def to_dict(self) -> dict:
        return {
            "items": [item.to_dict() for item in self.items],
            "open_questions": list(self.open_questions),
            "source": list(self.source or ["explicit"]),
        }


def card_from_dict(data: dict | None) -> ConstraintCard:
    if not isinstance(data, dict):
        return ConstraintCard()
    items: list[ConstraintItem] = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        status = str(raw.get("status") or "active")
        if status not in ("active", "superseded"):
            status = "active"
        items.append(
            ConstraintItem(
                id=str(raw.get("id") or uuid.uuid4().hex[:8]),
                text=text,
                status=status,
                updated_at=str(raw.get("updated_at") or ""),
                supersedes=raw.get("supersedes") or None,
                topic=raw.get("topic") or topic_key(text),
            )
        )
    questions = [str(item) for item in (data.get("open_questions") or []) if str(item).strip()]
    source = [str(item) for item in (data.get("source") or ["explicit"]) if str(item).strip()]
    return ConstraintCard(items=items, open_questions=questions, source=source or ["explicit"])


def active_texts(card: ConstraintCard) -> list[str]:
    return [item.text for item in card.items if item.status == "active" and item.text.strip()]


def _find(card: ConstraintCard, needle: str) -> ConstraintItem | None:
    text = (needle or "").strip()
    if not text:
        return None
    for item in card.items:
        if item.status == "active" and (item.id == text or item.text == text):
            return item
    topic = topic_key(text)
    if topic:
        for item in card.items:
            if item.status == "active" and (item.topic or topic_key(item.text)) == topic:
                return item
    for item in card.items:
        if item.status != "active":
            continue
        if text in item.text or item.text in text:
            return item
    return None


def remember(card: ConstraintCard, text: str) -> ConstraintCard:
    """Add an active row. The same theme replaces the previous active row."""
    cleaned = (text or "").strip()
    if not cleaned:
        return card
    if any(item.status == "active" and item.text == cleaned for item in card.items):
        return card
    topic = topic_key(cleaned)
    if topic:
        for item in card.items:
            if item.status == "active" and (item.topic or topic_key(item.text)) == topic:
                return supersede(card, old_id_or_text=item.id, new_text=cleaned)
    now = _now()
    card.items.append(
        ConstraintItem(
            id=_new_id(card),
            text=cleaned,
            status="active",
            updated_at=now,
            supersedes=None,
            topic=topic,
        )
    )
    if "explicit" not in card.source:
        card.source.append("explicit")
    return card


def retire(card: ConstraintCard, item_id: str) -> ConstraintCard:
    """Mark one active row superseded and keep it on the card."""
    needle = (item_id or "").strip()
    if not needle:
        return card
    now = _now()
    for item in card.items:
        if item.id == needle and item.status == "active":
            item.status = "superseded"
            item.updated_at = now
            break
    return card


def supersede(card: ConstraintCard, *, old_id_or_text: str, new_text: str) -> ConstraintCard:
    """Mark the old active row superseded and keep only the new text injectable."""
    cleaned = (new_text or "").strip()
    if not cleaned:
        return card
    target = _find(card, old_id_or_text)
    if target is not None and target.text == cleaned:
        return card
    now = _now()
    if target is not None:
        target.status = "superseded"
        target.updated_at = now
    if any(item.status == "active" and item.text == cleaned for item in card.items):
        return card
    card.items.append(
        ConstraintItem(
            id=_new_id(card),
            text=cleaned,
            status="active",
            updated_at=now,
            supersedes=None if target is None else target.id,
            topic=topic_key(cleaned),
        )
    )
    return card


def forget(card: ConstraintCard, old_id_or_text: str) -> ConstraintCard:
    """Hard-delete the matching row so it cannot be injected. ProfileStore.forget stays separate."""
    needle = (old_id_or_text or "").strip()
    if not needle:
        return card
    topic = topic_key(needle)
    kept: list[ConstraintItem] = []
    for item in card.items:
        if item.id == needle or item.text == needle or (needle in item.text and needle):
            continue
        if topic and item.status == "active" and (item.topic or topic_key(item.text)) == topic:
            continue
        kept.append(item)
    card.items = kept
    return card


def render_constraints_markdown(card: ConstraintCard) -> str:
    texts = active_texts(card)
    if not texts:
        return ""
    lines = ["忌口与硬限制（仅 active）：", *[f"- {text}" for text in texts]]
    return "\n".join(lines)


def merge_constraint_block(ephemeral: str, block: str | None = None, *, workspace: Path | None = None) -> str:
    """Put the active card inside the memory-context lane. Missing card is a no-op."""
    if block is None:
        block = load_constraint_block(workspace)
    block = (block or "").strip()
    if not block:
        return ephemeral or ""
    current = ephemeral or ""
    if "</memory-context>" in current:
        return current.replace("</memory-context>", f"\n{block}\n</memory-context>", 1)
    return f"<memory-context>\n{block}\n</memory-context>"


def resolve_workspace(workspace: Path | str | None = None) -> Path | None:
    if workspace:
        return Path(workspace)
    raw = os.environ.get("LIGHTAGENT_WORKSPACE")
    if raw:
        return Path(raw)
    return None


def load_constraint_block(workspace: Path | str | None = None) -> str:
    root = resolve_workspace(workspace)
    if root is None:
        return ""
    try:
        return render_constraints_markdown(ConstraintStore(root).load())
    except Exception:
        return ""


class ConstraintStore:
    """``{workspace}/constraints/card.json``."""

    def __init__(self, workspace: Path | str):
        self.workspace = Path(workspace)
        self.path = self.workspace / "constraints" / "card.json"

    def load(self) -> ConstraintCard:
        if not self.path.exists():
            return ConstraintCard()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ConstraintCard()
        return card_from_dict(data)

    def save(self, card: ConstraintCard) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(card.to_dict(), ensure_ascii=False, indent=2)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.path)

    def remember(self, text: str) -> ConstraintCard:
        card = remember(self.load(), text)
        self.save(card)
        return card

    def supersede(self, *, old_id_or_text: str, new_text: str) -> ConstraintCard:
        card = supersede(self.load(), old_id_or_text=old_id_or_text, new_text=new_text)
        self.save(card)
        return card

    def forget(self, old_id_or_text: str) -> ConstraintCard:
        card = forget(self.load(), old_id_or_text)
        self.save(card)
        return card

    def active_texts(self) -> list[str]:
        return active_texts(self.load())
