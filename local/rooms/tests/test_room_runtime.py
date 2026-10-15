"""E8–E10: one turn writes an ordered transcript and survives quota or a missing bot."""

from __future__ import annotations

from local.conversations.collaborate import DelegateQuota
from local.conversations.models import BotIdentity, ConversationMeta
from local.rooms.runtime import run_user_turn
from local.rooms.types import GroupRoom


def _coach() -> ConversationMeta:
    return ConversationMeta(
        id="c1",
        title="习惯教练",
        identity=BotIdentity(role_title="习惯教练", job_description="运动。", template_id="habit_coach"),
        agent_id="bot-c1",
    )


def _diet() -> ConversationMeta:
    return ConversationMeta(
        id="d1",
        title="饮食顾问",
        identity=BotIdentity(role_title="饮食顾问", job_description="配餐，尊重忌口。", template_id="nutrition_advisor"),
        agent_id="bot-d1",
    )


def _room() -> GroupRoom:
    return GroupRoom(id="r1", title="健康日常", member_bot_ids=["c1", "d1"], created_at=1, updated_at=1)


def test_e8_fitness_turn_orders_user_coach_diet_host():
    messages = []
    statuses: list[str] = []
    trace: dict = {}
    room = _room()
    result = run_user_turn(
        room,
        "帮我安排今日健身和饮食（忌深蹲，晚饭少油）",
        [_coach(), _diet()],
        messages,
        status=statuses.append,
        trace=trace,
    )
    speakers = [item.speaker for item in result.bubbles]
    assert speakers == ["user", "bot:c1", "bot:d1", "host"]
    assert [item.speaker_label for item in result.bubbles] == ["用户", "习惯教练", "饮食顾问", "生活助手"]
    assert result.bubbles[-1].kind == "host_summary"
    host = result.bubbles[-1].content
    assert "动作：" in host and "忌口：" in host and "下一步：" in host
    assert "习惯教练" in host
    assert "饮食顾问" in host
    assert host.count("\n") <= 4
    assert result.bubbles[1].content not in host
    assert result.bubbles[2].content not in host
    diet = result.bubbles[2]
    assert "忌深蹲" in diet.content
    assert "<identity" not in diet.content
    assert any(item.startswith("正在请习惯教练") for item in statuses)
    assert statuses[-1] == ""
    assert trace["steps"][0]["bot_id"] == "c1"
    assert result.plan.silent_member_ids == []
    assert room.unread is True
    assert result.bubbles[0].turn_id == result.turn_id


def test_e9_quota_is_a_chinese_bubble():
    messages = []
    result = run_user_turn(
        _room(),
        "安排今日健身和饮食",
        [_coach(), _diet()],
        messages,
        quota=DelegateQuota(limit=0),
    )
    assert result.errors
    assert any(item.kind == "error" and "额度" in item.content for item in result.bubbles)
    assert all(item.speaker != "bot:c1" for item in result.bubbles)


def test_e10_missing_member_is_skipped():
    messages = []
    result = run_user_turn(
        _room(),
        "安排今日健身和饮食",
        [_coach()],
        messages,
    )
    text = "\n".join(item.content for item in result.bubbles)
    assert "饮食顾问" in text
    assert "跳过" in text
    assert any(item.speaker == "bot:c1" for item in result.bubbles)
    assert all(item.speaker != "bot:d1" for item in result.bubbles)
    assert result.bubbles[-1].kind == "host_summary"
