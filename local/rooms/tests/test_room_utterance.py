"""E5–E6: one bubble, one delegation, no pack leak, no swarm run."""

from __future__ import annotations

import pytest

from local.conversations.collaborate import (
    DelegateError,
    DelegateQuota,
    child_delegate_tools_allowed,
    register_bots,
    run_delegation,
)
from local.conversations.models import BotIdentity, ConversationMeta
from local.rooms.types import GroupRoom
from local.rooms.utterance import run_room_utterance


def _roster() -> list[ConversationMeta]:
    return [
        ConversationMeta(
            id="c1",
            title="习惯教练",
            identity=BotIdentity(role_title="习惯教练", job_description="运动。", template_id="habit_coach"),
            agent_id="bot-c1",
            share_user_profile=True,
        )
    ]


def _room() -> GroupRoom:
    return GroupRoom(id="r1", title="健康日常", member_bot_ids=["c1"], created_at=1, updated_at=1)


def test_e5_mock_bubble_hides_identity_and_memory_pack():
    pack = "<memory-context>\n以后简称我小Q\n</memory-context>"
    bubble = run_room_utterance(
        _room(),
        "c1",
        "今晚练 20 分钟",
        "用户：昨晚睡得晚",
        _roster(),
        DelegateQuota(),
        "mock",
        turn_id="t1",
        profile_block=pack,
    )
    assert bubble.speaker == "bot:c1"
    assert bubble.speaker_label == "习惯教练"
    assert bubble.meta.get("via") == "run_delegation"
    assert "<identity" not in bubble.content
    assert "<memory-context>" not in bubble.content
    assert "<persona>" not in bubble.content
    assert "小Q" not in bubble.content
    assert "今晚练" in bubble.content


def test_e6_child_is_single_level_and_swarm_run_stays_unused(monkeypatch):
    from LightAgent import LightSwarm

    def _forbid_run(*_args, **_kwargs):
        raise AssertionError("LightSwarm.run")

    monkeypatch.setattr(LightSwarm, "run", _forbid_run)
    seen: dict = {}

    import local.rooms.utterance as utterance

    real = utterance.run_delegation

    def _spy(**kwargs):
        seen.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(utterance, "run_delegation", _spy)
    run_room_utterance(
        _room(),
        "习惯教练",
        "只改今晚训练",
        "",
        _roster(),
        DelegateQuota(),
        "mock",
        turn_id="t2",
    )
    assert seen["depth"] == 0
    assert child_delegate_tools_allowed(0) is True
    assert child_delegate_tools_allowed(1) is False
    swarm = register_bots(_roster())
    for agent in swarm.agents.values():
        assert agent.tree_of_thought is False
        assert "delegate_to_bot" not in (getattr(agent, "loaded_tools", {}) or {})
    with pytest.raises(DelegateError, match="一层"):
        run_delegation(roster=_roster(), bot_id="c1", task="再派发", depth=1, mode="mock")
