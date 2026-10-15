"""M6: host progress is three rule lines and does not call a model."""

from __future__ import annotations

from local.conversations.models import BotIdentity, ConversationMeta
from local.goals.store import maybe_open_goal
from local.openrouter_config import NETWORK_CALLS
from local.rooms.host_summary import render_host_summary
from local.rooms.runtime import run_user_turn
from local.rooms.types import GroupRoom, RoomMessage


def _bubble(speaker: str, label: str, content: str) -> RoomMessage:
    return RoomMessage(
        id=speaker,
        role="assistant",
        speaker=speaker,
        speaker_label=label,
        content=content,
        ts=1,
        kind="chat",
    )


def test_e8_three_lines_use_active_constraints_and_skip_the_long_reply():
    long_reply = "子Bot长文" + ("不要整段回声" * 30)
    summary = render_host_summary(
        [
            _bubble("bot:c1", "习惯教练", long_reply),
            _bubble("bot:d1", "饮食顾问", "少油"),
        ],
        constraints=["忌口：海鲜"],
        next_step="配一日三餐",
    )
    lines = summary.splitlines()
    assert lines[0].startswith("动作：")
    assert lines[1] == "忌口：忌口：海鲜"
    assert lines[2] == "下一步：配一日三餐"
    assert long_reply not in summary
    assert "不要整段回声不要整段回声" not in summary
    assert "习惯教练已给出建议" in lines[0]
    assert "少油" in lines[0]


def test_e10_host_flag_does_not_call_out(monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_ROOM_HOST_LLM", "1")
    before = NETWORK_CALLS
    summary = render_host_summary(
        [_bubble("bot:c1", "习惯教练", "走一走")],
        constraints=[],
        next_step=None,
    )
    assert NETWORK_CALLS == before
    assert "动作：" in summary
    assert "忌口：（无）" in summary
    assert "openrouter" not in summary.lower()


def test_runtime_reads_the_card_and_the_goal(tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_WORKSPACE", str(tmp_path))
    from local.constraints.card import ConstraintStore

    ConstraintStore(tmp_path).remember("忌口：海鲜")
    room = GroupRoom(
        id="r1",
        title="健康日常",
        member_bot_ids=["c1", "d1"],
        scenario_hints=["fitness_diet"],
        space_id="r1",
    )
    maybe_open_goal(tmp_path, "r1", "今日健身和饮食", room_scenario="fitness_diet")
    roster = [
        ConversationMeta(
            id="c1",
            title="习惯教练",
            identity=BotIdentity(role_title="习惯教练", template_id="habit_coach"),
        ),
        ConversationMeta(
            id="d1",
            title="饮食顾问",
            identity=BotIdentity(role_title="饮食顾问", template_id="nutrition_advisor"),
        ),
    ]
    result = run_user_turn(room, "今日健身和饮食", roster, [])
    host = result.bubbles[-1].content
    assert "忌口：忌口：海鲜" in host
    assert "下一步：定训练日" in host
    for bubble in result.bubbles:
        if bubble.speaker.startswith("bot:"):
            assert bubble.content not in host
