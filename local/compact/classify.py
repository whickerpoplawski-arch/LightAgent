"""Split a user sentence into a profile fact or a procedural how-to.

Profile / preference / veto / diet facts are stable facts about the person.
Procedural text is a reusable sequence of steps. When a clause is ambiguous,
it stays procedural so it is confirmed before anything is stored.
"""

from __future__ import annotations

import re
import uuid

from .types import ExtractedMemory, ProceduralCandidate

_PROCEDURAL = re.compile(
    r"下次.{0,40}(按|照|步骤|流程)|按这[0-9一二三四五六七八九十]+步|(?:步骤|流程|套路).{0,12}\d|固定套路",
)
_NUMBERED = re.compile(r"(?:^|[\s：:])(?:\d+|[一二三四五六七八九十])[\.、\)]")
_DIET = re.compile(r"素食|吃素|忌口|过敏|用药|不能吃|不要吃|花生|晚上别催")
_PIN = re.compile(r"忌口|过敏|用药|不能吃|不要吃|花生|素食|吃素|永远不要|别催药|\bnever\b", re.IGNORECASE)
_VETO = re.compile(r"永远不要|别再|不要再|否决|方案.{0,8}不要|不要这个|不要用|别用")
_STYLE = re.compile(r"叫我|称呼我|短句回复|用中文回复|用英文回复")
_REMEMBER = re.compile(r"记住|以后都|请记得")
_SCHEDULE = re.compile(
    r"(周[一二三四五六日天]|明天|后天|下周|今天).{0,24}(\d{1,2}[:：点]\d{0,2}|体检|开会|约会|出发|买票)"
)
_QUESTION_TO_BOT = re.compile(r"^(你|请问)")


def is_procedural(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    if _PROCEDURAL.search(raw):
        return True
    numbered = _NUMBERED.findall(raw)
    if len(numbered) >= 2 and re.search(r"下次|以后|每次|步骤|流程", raw):
        return True
    return False


def parse_steps(text: str) -> list[str]:
    found = re.findall(
        r"(?:^|[\s：:，,；;])(?:\d+|[一二三四五六七八九十])[\.、\)]\s*([^\n。]+?)(?=(?:\s*(?:\d+|[一二三四五六七八九十])[\.、\)])|$)",
        text,
    )
    cleaned = []
    for item in found:
        step = re.sub(r"\s+", " ", item).strip(" ：:，,；;、")
        if step:
            cleaned.append(step)
    if len(cleaned) >= 2:
        return cleaned
    stripped = text.strip()
    return [stripped] if stripped else []


def _clauses(text: str) -> list[str]:
    parts = re.split(r"[。！？\n；;，]+", text)
    return [part.strip() for part in parts if part.strip()]


def _profile_hit(clause: str) -> ExtractedMemory | None:
    if not clause or is_procedural(clause):
        return None
    if _QUESTION_TO_BOT.match(clause) and ("？" in clause or "?" in clause):
        return None
    if _DIET.search(clause):
        return ExtractedMemory(
            text=clause,
            kind="preference",
            facet="life",
            pin=bool(_PIN.search(clause)),
        )
    if _VETO.search(clause):
        return ExtractedMemory(text=clause, kind="preference", facet="veto", pin=bool(_PIN.search(clause)))
    if _STYLE.search(clause):
        return ExtractedMemory(text=clause, kind="preference", facet="style", pin=False)
    if _REMEMBER.search(clause):
        return ExtractedMemory(text=clause, kind="fact", facet="identity", pin=False)
    if _SCHEDULE.search(clause):
        return ExtractedMemory(text=clause, kind="fact", facet="life", pin=False)
    return None


def _procedural_candidate(clause: str, *, space_id: str | None) -> ProceduralCandidate | None:
    if not is_procedural(clause):
        return None
    title_match = re.search(r"下次(.{1,16}?)按", clause)
    title = title_match.group(1).strip(" ：:") if title_match else "生活流程"
    if not title:
        title = "生活流程"
    steps = tuple(parse_steps(clause))
    return ProceduralCandidate(
        id=uuid.uuid4().hex[:12],
        title=title,
        description=clause.strip()[:200],
        steps=steps,
        source_text=clause.strip(),
        space_id=space_id,
    )


def classify_text(
    text: str,
    *,
    space_id: str | None = None,
) -> tuple[list[ExtractedMemory], list[ProceduralCandidate]]:
    """Return profile hits and procedural candidates for one user message."""
    raw = (text or "").strip()
    if not raw:
        return [], []
    memories: list[ExtractedMemory] = []
    procedural: list[ProceduralCandidate] = []
    seen: set[str] = set()
    for clause in _clauses(raw):
        if clause in seen:
            continue
        seen.add(clause)
        candidate = _procedural_candidate(clause, space_id=space_id)
        if candidate is not None:
            procedural.append(candidate)
            continue
        hit = _profile_hit(clause)
        if hit is not None:
            memories.append(hit)
    return memories, procedural


def should_pin_text(text: str) -> bool:
    return bool(_PIN.search(text or ""))
