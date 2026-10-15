"""Deterministic extractive summarizer.

This is the default compact path. It fills the required template from the
removed messages and does not call OpenRouter. A real ``:free`` model is
opt-in via ``LIGHTAGENT_COMPACT_LLM=1`` and is never used by tests.
"""

from __future__ import annotations

import os
import re
from typing import Any


def _user_texts(removed: list[dict[str, Any]]) -> list[str]:
    texts = []
    for message in removed:
        if message.get("role") != "user":
            continue
        content = str(message.get("content") or "").strip()
        if content:
            texts.append(content)
    return texts


def _quote_block(items: list[str]) -> str:
    if not items:
        return "无"
    lines = []
    for item in items[:6]:
        quote = re.sub(r"\s+", " ", item).strip()
        if len(quote) > 180:
            quote = quote[:180] + "…"
        lines.append(f"- 「{quote}」")
    return "\n".join(lines)


def _refs(removed: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for message in removed:
        if message.get("role") != "tool":
            continue
        metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
        reference = metadata.get("content_reference")
        if reference:
            found.append(str(reference))
            continue
        content = str(message.get("content") or "")
        if content.startswith("[Tool result stored"):
            found.append(content[:180])
    return found


def _pick(texts: list[str], needles: tuple[str, ...]) -> list[str]:
    return [text for text in texts if any(needle in text for needle in needles)]


def local_summarizer(prompt: str, removed: list[dict[str, Any]]) -> str:
    """Fill either the short auto template or the full life template."""
    full = "已确认偏好" in prompt and "Exact identifiers" in prompt
    users = _user_texts(removed)
    pending = [text for text in users if "？" in text or "?" in text]
    veto = _pick(users, ("不要", "忌口", "过敏", "别再", "Never", "never", "素食", "用药", "不能吃"))
    decisions = _pick(users, ("就订", "预算", "决定", "拍板", "上限", "定为", "选"))
    goals = users[:1]
    identifiers = []
    for text in users:
        if re.search(r"\d{1,2}[:：]\d{2}|\d+\s*元|周[一二三四五六日天]", text):
            identifiers.append(text)
    refs = _refs(removed)
    space_match = re.search(r"当前 space_id：(\S+)", prompt)
    space_line = space_match.group(1) if space_match else "无"
    if full:
        sections = [
            ("## 当前目标", _quote_block(goals)),
            ("## 已确认偏好（仅 learning_id + 一句 verbatim；细节以 Memory 为准）", "无"),
            ("## 禁止事项（Never / 否决 / 忌口 / 用药边界）", _quote_block(veto)),
            ("## 近期承诺与日程（含精确时间地点数字；不确定则标注不确定）", _quote_block(identifiers)),
            ("## 未决问题（用户尚未回答的问句；不得标成已完成）", _quote_block(pending)),
            ("## 本会话进度（已完成 / 进行中）", "无"),
            ("## Exact identifiers（日期、时间、金额、地点专名、订单号、人名称呼——字面保留）", _quote_block(identifiers)),
            ("## 工具与外置指针（spill ref / 需重查的查询，禁止正文）", _quote_block(refs) if refs else "无"),
            ("## Space（当前 space_id；禁止引入其他 Space 事实）", space_line),
        ]
    else:
        sections = [
            ("## 当前目标", _quote_block(goals)),
            ("## 未决问题（必须逐条保留用户原问意图）", _quote_block(pending)),
            ("## 近期拍板（尽量 verbatim 引用用户原句中的时间/数字/专名）", _quote_block(decisions)),
            ("## 禁止事项（否决、Never、忌口——宁缺勿写错）", _quote_block(veto)),
            ("## 工具指针（仅 ref/sha，禁止粘贴网页正文）", _quote_block(refs) if refs else "无"),
        ]
    return "\n".join(part for pair in sections for part in pair)


def maybe_free_summarizer(prompt: str, removed: list[dict[str, Any]]) -> str:
    """Opt-in ``:free`` call. Off unless ``LIGHTAGENT_COMPACT_LLM=1``."""
    if os.environ.get("LIGHTAGENT_COMPACT_LLM") != "1":
        raise RuntimeError("compact LLM is off; set LIGHTAGENT_COMPACT_LLM=1 to use a :free model")
    from local.openrouter_config import run_free

    rendered = []
    for message in removed:
        rendered.append(f"{message.get('role')}: {message.get('content')}")
    _model, output = run_free(prompt + "\n\n" + "\n".join(rendered))
    return str(output)
