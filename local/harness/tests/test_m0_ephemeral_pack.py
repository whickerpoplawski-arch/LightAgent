"""M0: a persisted turn never keeps <memory-context>."""

from __future__ import annotations

import pytest

from local.harness.ephemeral import (
    assert_transcript_clean,
    clean_persisted_text,
    prepare_model_inputs,
    sanitize_transcript,
    scrub_room_messages,
)
from local.memory.host import MemoryHost
from local.memory.inject import compose_system, prepare_turn, user_text_contains_pack
from local.rooms.digest import build_room_digest
from local.rooms.types import RoomMessage
from local.rooms.utterance import role_task


def test_e11_prepare_turn_persisted_copy_drops_the_pack(env):
    env.learn("以后简称我小Q", user_id="alice", namespace="profile", lane="general", facet="identity")
    host = MemoryHost(user_id="alice", namespace="profile", session_id="s1")
    prepared = prepare_turn(
        system="你是助手。",
        history=[{"role": "user", "content": "上一句"}, {"role": "assistant", "content": "上一答"}],
        user_text="今天晚饭吃什么",
        host=host,
        store=env,
    )
    assert "<memory-context>" in prepared.messages[0]["content"]
    assert prepared.messages[-1]["content"] == "今天晚饭吃什么"
    assert user_text_contains_pack(prepared.messages) is False

    persisted = sanitize_transcript(prepared.messages)
    blob = "\n".join(str(item.get("content") or "") for item in persisted)
    assert "<memory-context>" not in blob
    assert "</memory-context>" not in blob
    assert "今天晚饭吃什么" in blob
    assert_transcript_clean(persisted)


def test_dirty_user_message_is_stripped_before_persist():
    dirty = [
        {
            "role": "user",
            "content": "记住 <memory-context>\n秘密包\n</memory-context> 忌口：海鲜",
        }
    ]
    cleaned = sanitize_transcript(dirty)
    assert "<memory-context>" not in cleaned[0]["content"]
    assert "秘密包" not in cleaned[0]["content"]
    assert "忌口：海鲜" in cleaned[0]["content"]
    history, prompt = prepare_model_inputs(
        dirty,
        "问 <memory-context>PACK</memory-context> 今天吃什么",
    )
    assert "PACK" not in prompt
    assert "今天吃什么" in prompt
    assert "<memory-context>" not in history[0]["content"]
    assert_transcript_clean(history + [{"role": "user", "content": prompt}])


def test_assert_transcript_clean_rejects_a_dirty_user_message():
    with pytest.raises(AssertionError, match="memory-context"):
        assert_transcript_clean(
            [{"role": "user", "content": "x <memory-context>y</memory-context>"}]
        )


def test_untagged_text_is_unchanged():
    assert clean_persisted_text("  今天吃什么  ") == "  今天吃什么  "


def test_compose_system_order_is_base_persona_identity_pack():
    text = compose_system(
        "BASE",
        "PERSONA",
        "IDENTITY",
        "<memory-context>\npack\n</memory-context>",
    )
    assert text.index("BASE") < text.index("PERSONA") < text.index("IDENTITY") < text.index("<memory-context>")


def test_room_digest_and_delegate_task_strip_the_pack():
    message = RoomMessage(
        id="m1",
        role="user",
        speaker="user",
        speaker_label="用户",
        content="你好 <memory-context>秘密</memory-context> 尾句",
        ts=1,
    )
    digest = build_room_digest([message])
    assert "秘密" not in digest
    assert "<memory-context>" not in digest
    assert "尾句" in digest

    from local.conversations.models import BotIdentity, ConversationMeta
    from local.rooms.types import GroupRoom

    room = GroupRoom(id="r1", title="健康日常", member_bot_ids=["c1"])
    meta = ConversationMeta(
        id="c1",
        title="饮食顾问",
        identity=BotIdentity(role_title="饮食顾问", template_id="nutrition_advisor"),
    )
    task = role_task(room, meta, "用户原话 <memory-context>不要带去</memory-context>")
    assert "<memory-context>" not in task
    assert "不要带去" not in task


def test_scrub_room_messages_keeps_bubbles_and_drops_pack():
    message = RoomMessage(
        id="m1",
        role="assistant",
        speaker="bot:c1",
        speaker_label="教练",
        content="建议 <persona>内部人设</persona> 去散步",
        ts=1,
    )
    scrub_room_messages([message])
    assert "<persona>" not in message.content
    assert "内部人设" not in message.content
    assert "散步" in message.content


def test_pack_failure_is_fail_open_and_distinct_from_no_profile(env, monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(env, "revision", boom)
    host = MemoryHost(user_id="alice", namespace="profile", session_id="s1")
    failed = prepare_turn(
        system="你是助手。",
        history=[],
        user_text="今天吃什么",
        host=host,
        store=env,
    )
    assert failed.messages[-1]["content"] == "今天吃什么"
    assert "memory unavailable" in failed.messages[0]["content"]
    assert "<memory-context>" in failed.ephemeral

    skipped = prepare_turn(
        system="你是助手。",
        history=[],
        user_text="今天吃什么",
        host=host,
        store=env,
        share_user_profile=False,
    )
    assert skipped.ephemeral == ""
    assert "memory unavailable" not in skipped.messages[0]["content"]
    persisted = sanitize_transcript(failed.messages)
    assert "<memory-context>" not in "\n".join(item["content"] for item in persisted)
