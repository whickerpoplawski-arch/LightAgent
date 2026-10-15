"""E2 prompt shape, threshold, and /compact parsing."""

from __future__ import annotations

from local.compact.chat_commands import parse_compact_command
from local.compact.policy import (
    AUTO_COMPACT_RATIO,
    select_template,
    should_auto_compact,
    summarizer_prompt,
)
from local.compact.prompts import AUTO_SHORT, FULL_LIFE, HARD_CONSTRAINTS, ZERO_LLM_POLICY
from local.compact.types import CompactTrigger


def test_auto_threshold_is_strictly_above_85_percent():
    assert AUTO_COMPACT_RATIO == 0.85
    assert should_auto_compact(0.85) is False
    assert should_auto_compact(0.8501) is True
    assert should_auto_compact(0.5) is False


def test_auto_template_is_short_and_manual_is_full():
    assert select_template(CompactTrigger.AUTO) == AUTO_SHORT
    assert select_template("manual") == FULL_LIFE
    assert "极短中文摘要" in AUTO_SHORT
    assert "已确认偏好" in FULL_LIFE
    assert "ZERO_LLM" in ZERO_LLM_POLICY
    auto = summarizer_prompt("auto", focus="应被忽略", space_id="home")
    assert AUTO_SHORT in auto
    assert "已确认偏好" not in auto
    assert "Exact identifiers" not in auto
    assert HARD_CONSTRAINTS in auto
    assert "当前 space_id：home" in auto
    manual = summarizer_prompt("manual", focus="下周东京行程的预算上限", space_id="home")
    assert FULL_LIFE in manual
    assert "下周东京行程的预算上限" in manual
    assert "焦点不能删除「禁止事项」" in manual
    assert "不可信" in manual
    assert ZERO_LLM_POLICY not in manual


def test_parse_compact_command():
    assert parse_compact_command("你好") is None
    assert parse_compact_command("/compacted now") is None
    plain = parse_compact_command("/compact")
    assert plain is not None and plain.focus is None
    focused = parse_compact_command("/compact 焦点：下周东京")
    assert focused is not None and focused.focus == "下周东京"
    labeled = parse_compact_command("/compact focus: budget")
    assert labeled is not None and labeled.focus == "budget"
    free = parse_compact_command("/compact 只留下周预算")
    assert free is not None and free.focus == "只留下周预算"
