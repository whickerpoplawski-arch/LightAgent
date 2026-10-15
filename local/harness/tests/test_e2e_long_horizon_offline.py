"""Offline walk through the long-horizon minimum set. No network."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from local.checkpoints.store import is_resume_request, latest_checkpoint, record_run_event, resume
from local.constraints.card import ConstraintStore
from local.goals.store import GoalStore, get_active_goal, maybe_open_goal, set_step_status
from local.harness.ephemeral import assert_transcript_clean, clean_persisted_text, sanitize_transcript
from local.memory.host import MemoryHost
from local.memory.inject import prepare_turn
from local.openrouter_config import NETWORK_CALLS
from local.rooms.digest import prepare_room_transcript
from local.rooms.host_summary import render_host_summary
from local.rooms.types import RoomMessage
from local.routines.detect import parse_routine
from local.routines.due import confirm_first_due, due_routines
from local.routines.store import RoutineStore
from local.tui.backend import MockBackend, TurnContext


def _user(index: int, content: str) -> RoomMessage:
    return RoomMessage(
        id=f"u{index}",
        role="user",
        speaker="user",
        speaker_label="用户",
        content=content,
        ts=index,
    )


def _bot(index: int, content: str) -> RoomMessage:
    return RoomMessage(
        id=f"b{index}",
        role="assistant",
        speaker="bot:c1",
        speaker_label="习惯教练",
        content=content,
        ts=index,
    )


def test_same_day_goal_cancel_resume_and_clean_transcript(tmp_path, env, monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_WORKSPACE", str(tmp_path))
    ConstraintStore(tmp_path).remember("忌口：海鲜")
    goal = maybe_open_goal(tmp_path, "life", "帮我制定一周健身与饮食计划")
    assert goal is not None
    assert "忌口：海鲜" in goal.constraints_ref
    assert sum(step.status == "in_progress" for step in goal.steps) == 1

    backend = MockBackend(delay=0)
    history: list[dict] = []
    turn = TurnContext(session_id="life", space_id="life", collaboration_enabled=False)
    for prompt in ("帮我制定一周健身与饮食计划", "定训练日：周一三五"):
        reply = backend.chat(history, prompt, turn=turn)
        history.append({"role": "user", "content": clean_persisted_text(prompt)})
        history.append({"role": "assistant", "content": clean_persisted_text(reply.content)})
    assert_transcript_clean(history)
    assert "<memory-context>" not in reply.content

    finished = set_step_status(tmp_path, goal.goal_id, "s1", "completed")
    assert [step.status for step in finished.steps if step.status == "in_progress"] == []
    assert finished.steps[0].status == "completed"

    record_run_event("life", "user_cancel", detail="已展示三分训练草案")
    paused = get_active_goal(tmp_path, "life")
    assert paused is not None
    assert paused.goal_id == goal.goal_id
    assert paused.status == "paused"
    checkpoint = latest_checkpoint(tmp_path, goal.goal_id)
    assert checkpoint is not None
    assert checkpoint.reason == "user_cancel"

    assert is_resume_request("继续")
    before = {item.goal_id for item in GoalStore(tmp_path).list_goals()}
    plan = resume(tmp_path, "life")
    assert plan is not None
    assert plan.goal_id == goal.goal_id
    assert "定训练日" in plan.completed_titles
    assert "半执行" in plan.notice
    restored = get_active_goal(tmp_path, "life")
    assert restored is not None
    assert restored.goal_id == goal.goal_id
    assert restored.status == "active"
    assert restored.steps[0].status == "completed"
    assert sum(step.status == "in_progress" for step in restored.steps) <= 1
    after = {item.goal_id for item in GoalStore(tmp_path).list_goals()}
    assert after == before


def test_group_compact_keeps_the_diet_and_host_does_not_echo(tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_ROOM_HOST_LLM", "1")
    before = NETWORK_CALLS
    long_reply = "子Bot长文" + ("不要整段回声" * 30)
    messages = [_user(0, "忌口：海鲜")]
    messages.extend(_bot(index + 1, long_reply) for index in range(50))
    saved = prepare_room_transcript(messages, workspace=tmp_path, room_id="r1", keep=40)
    assert any("忌口：海鲜" in item.content for item in saved)
    assert len(saved) < len(messages)
    assert len(saved) <= 40 + 10 + 8
    assert ConstraintStore(tmp_path).active_texts() == ["忌口：海鲜"]
    named = [item for item in saved if item.speaker.startswith("bot:")]
    summary = render_host_summary(named[:2], constraints=["忌口：海鲜"], next_step="定训练日")
    assert summary.splitlines()[0].startswith("动作：")
    assert "忌口：忌口：海鲜" in summary
    assert summary.splitlines()[-1] == "下一步：定训练日"
    assert long_reply not in summary
    assert NETWORK_CALLS == before


def test_routine_due_pause_and_confirm_do_not_steal_a_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "local.openrouter_config.make_agent",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("make_agent")),
    )
    before = NETWORK_CALLS
    parsed = parse_routine("每周一提醒我称重")
    assert parsed is not None
    now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    routine = RoutineStore(tmp_path).create(
        title=parsed["title"],
        instruction=parsed["instruction"],
        cadence=parsed["cadence"],
        owner_space="life",
        timezone_name=parsed["timezone"],
        now=now,
    )
    assert due_routines(tmp_path, now=now) == []
    RoutineStore(tmp_path).set_next_due(routine.id, now - timedelta(days=3))
    assert [item.id for item in due_routines(tmp_path, now=now)] == [routine.id]
    RoutineStore(tmp_path).pause(routine.id)
    assert due_routines(tmp_path, now=now) == []
    RoutineStore(tmp_path).pause(routine.id, paused=False)
    RoutineStore(tmp_path).set_next_due(routine.id, now - timedelta(days=3))

    def runner(instruction, *, budget_limits, cancellation_token):
        assert budget_limits.model_calls == 8
        assert budget_limits.seconds == 120
        assert cancellation_token is not None
        return "已确认提醒，这次不调用模型：" + instruction

    result = confirm_first_due(tmp_path, space_id="life", runner=runner, now=now)
    assert result["ok"] is True
    assert due_routines(tmp_path, now=now, space_id="life") == []
    assert NETWORK_CALLS == before


def test_ephemeral_pack_is_stripped_before_persist(env, tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_WORKSPACE", str(tmp_path))
    ConstraintStore(tmp_path).remember("忌口：海鲜")
    maybe_open_goal(tmp_path, "life", "帮我制定一周健身与饮食计划")
    prepared = prepare_turn(
        system="助手",
        history=[],
        user_text="帮我制定一周健身与饮食计划",
        host=MemoryHost(user_id="alice", session_id="s1", space_id="life"),
        share_user_profile=True,
    )
    assert prepared.user_text == "帮我制定一周健身与饮食计划"
    assert "<memory-context>" in (prepared.ephemeral or "")
    history = sanitize_transcript([
        {"role": "user", "content": prepared.user_text + (prepared.ephemeral or "")},
        {"role": "assistant", "content": prepared.ephemeral or ""},
    ])
    assert_transcript_clean(history)
    assert all("<memory-context>" not in item["content"] for item in history)
