"""E1–E4: TurnPlan is a pure function."""

from __future__ import annotations

from local.conversations.collaborate import DelegateQuota
from local.conversations.models import BotIdentity, ConversationMeta
from local.rooms.plan import build_turn_plan
from local.rooms.types import GroupRoom
from local.rooms.utterance import run_room_utterance


def _coach() -> ConversationMeta:
    return ConversationMeta(
        id="c1",
        title="习惯教练",
        identity=BotIdentity(
            role_title="习惯教练",
            job_description="陪用户看运动习惯，给很小的下一步。",
            template_id="habit_coach",
        ),
        agent_id="bot-c1",
    )


def _diet() -> ConversationMeta:
    return ConversationMeta(
        id="d1",
        title="饮食顾问",
        identity=BotIdentity(
            role_title="饮食顾问",
            job_description="按忌口给配餐建议，不诊疗。",
            template_id="nutrition_advisor",
        ),
        agent_id="bot-d1",
    )


def _room(*members: str, **kwargs) -> GroupRoom:
    return GroupRoom(
        id="r1",
        title="健康日常",
        member_bot_ids=list(members),
        created_at=1,
        updated_at=1,
        **kwargs,
    )


def test_e1_mention_selects_only_the_named_member():
    roster = [_coach(), _diet()]
    plan = build_turn_plan("@习惯教练 只改今晚训练", _room("c1", "d1"), roster)
    assert plan.speakers == ["c1"]
    assert plan.reason == "mention"
    assert "d1" in plan.silent_member_ids
    assert plan.include_host_summary is False


def test_e2_fitness_diet_template_orders_coach_then_advisor():
    roster = [_diet(), _coach()]
    plan = build_turn_plan("安排今日健身和饮食", _room("c1", "d1"), roster)
    assert plan.speakers == ["c1", "d1"]
    assert "fitness_diet" in plan.reason
    assert plan.silent_member_ids == []
    assert plan.include_host_summary is True


def test_e3_idle_chat_falls_back_to_host():
    roster = [_coach(), _diet()]
    plan = build_turn_plan("今天天气不错，我们随便聊聊", _room("c1", "d1"), roster)
    assert plan.speakers == []
    assert plan.reason == "fallback_host_only"
    assert plan.include_host_summary is True
    assert set(plan.silent_member_ids) == {"c1", "d1"}


def test_e3_single_topic_does_not_pull_everyone():
    roster = [_coach(), _diet()]
    room = _room("c1", "d1")
    diet_only = build_turn_plan("今晚吃什么", room, roster)
    move_only = build_turn_plan("今天想健身", room, roster)
    assert diet_only.speakers == []
    assert move_only.speakers == []
    assert diet_only.reason == "fallback_host_only"


def test_e4_max_speakers_runs_one_child():
    roster = [_coach(), _diet()]
    room = _room("c1", "d1", max_speakers=1)
    plan = build_turn_plan("安排今日健身和饮食，忌深蹲", room, roster)
    assert plan.speakers == ["c1"]
    assert "d1" in plan.silent_member_ids
    quota = DelegateQuota()
    bubbles = []
    for bot_id in plan.speakers:
        bubbles.append(
            run_room_utterance(
                room,
                bot_id,
                "安排今日健身和饮食，忌深蹲",
                "",
                roster,
                quota,
                "mock",
                turn_id=plan.turn_id,
            )
        )
    assert [item.speaker for item in bubbles] == ["bot:c1"]
    assert quota.used == 1
