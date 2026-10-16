"""Grapheme preview: 15 clusters, not a byte slice, and not the avatar id."""

from __future__ import annotations

import pytest

from local.rooms.types import RoomMessage
from local.rooms.ui import room_preview
from local.tui.preview_text import (
    EMPTY_PREVIEW,
    PREVIEW_GRAPHEMES,
    grapheme_clusters,
    grapheme_len,
    latest_message_text,
    message_preview,
    plain_message,
    truncate_graphemes,
)


def test_chinese_preview_is_fifteen_graphemes_not_a_byte_slice():
    text = "甲" * 20
    assert grapheme_len(text) == 20
    assert truncate_graphemes(text, PREVIEW_GRAPHEMES) == "甲" * 15
    raw = text.encode("utf-8")
    with pytest.raises(UnicodeDecodeError):
        raw[:5].decode("utf-8")
    assert truncate_graphemes(text, 15).encode("utf-8").decode("utf-8") == "甲" * 15


def test_combining_mark_zwj_flag_skin_and_keycap_stay_whole():
    acute = "e\u0301"
    assert grapheme_clusters(acute) == [acute]
    assert truncate_graphemes(acute * 4, 2) == acute * 2

    family = "👩\u200d👩\u200d👧"
    assert grapheme_len(family) == 1
    assert truncate_graphemes(family + "甲乙", 1) == family

    assert grapheme_len("🇨🇳") == 1
    assert grapheme_len("👍🏽") == 1
    assert grapheme_len("1️⃣") == 1
    assert grapheme_clusters("a\r\nb") == ["a", "\n", "b"]


def test_latest_message_skips_tool_rows_and_empty_is_new_session():
    events = [("tool", "甲" * 30), ("notice", "系统"), ("agent", "**已改**成\n圆角气泡")]
    assert plain_message("**已改**成\n圆角气泡") == "已改成 圆角气泡"
    assert latest_message_text(events) == "已改成 圆角气泡"
    assert message_preview("") == EMPTY_PREVIEW
    assert message_preview("   ") == EMPTY_PREVIEW
    shot = "你好！这是一条新会话，头像已与其它会话区分。"
    assert message_preview(shot) == "你好！这是一条新会话，头像已与"
    assert grapheme_len(message_preview(shot)) == 15
    assert latest_message_text([("agent", shot)]) == shot


def test_room_preview_caps_the_whole_line_at_fifteen():
    assert room_preview([]) == "还没有人发言"
    message = RoomMessage(
        id="m1",
        role="assistant",
        speaker="bot",
        speaker_label="教练",
        content="甲" * 40,
        ts=1,
        kind="chat",
    )
    text = room_preview([message])
    assert grapheme_len(text) == 15
    assert text.startswith("教练：")
