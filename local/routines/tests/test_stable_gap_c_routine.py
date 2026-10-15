"""Gap C: call-me phrasing creates a routine. Questions and bare nudges do not."""

from __future__ import annotations

from local.routines.detect import parse_routine


def test_c_t3_weekly_call_me_is_a_routine():
    parsed = parse_routine("每周一叫我称重")
    assert parsed is not None
    assert parsed["cadence"] == "weekly"
    assert parsed["timezone"] == "America/Martinique"
    assert parse_routine("今天吃什么") is None


def test_c_routine_negatives_and_sibling_verbs():
    assert parse_routine("提醒我一下") is None
    assert parse_routine("叫我称重") is None
    assert parse_routine("每周一称重") is None
    daily = parse_routine("每天喊我喝水")
    assert daily is not None and daily["cadence"] == "daily_window"
    once = parse_routine("叫我一次称体重")
    assert once is not None and once["cadence"] == "once"
