"""M2: cancel writes a checkpoint; 继续 resumes the same goal."""

from __future__ import annotations

from local.checkpoints.store import (
    is_resume_request,
    latest_checkpoint,
    record_run_event,
    resume,
    write_checkpoint,
)
from local.goals.store import GoalStep, create_goal, get_active_goal, maybe_open_goal, set_step_status


def test_e3_cancel_writes_a_checkpoint_and_pauses(tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_WORKSPACE", str(tmp_path))
    goal = maybe_open_goal(tmp_path, "life", "帮我制定一周健身与饮食计划")
    assert goal is not None
    record_run_event("life", "user_cancel", detail="已展示三分训练草案")
    paused = get_active_goal(tmp_path, "life")
    assert paused is not None
    assert paused.status == "paused"
    assert paused.goal_id == goal.goal_id
    checkpoint = latest_checkpoint(tmp_path, goal.goal_id)
    assert checkpoint is not None
    assert checkpoint.reason == "user_cancel"
    assert checkpoint.step_id == "s1"
    assert checkpoint.pending_side_effects[0]["kind"] == "advice_shown"
    assert "三分训练草案" in checkpoint.pending_side_effects[0]["detail"]


def test_e4_resume_keeps_the_goal_and_completed_steps(tmp_path):
    goal = create_goal(
        tmp_path,
        space_id="life",
        objective="一周健身与饮食",
        constraints_ref=["忌口：海鲜"],
        steps=[
            GoalStep("s1", "定训练日", "completed"),
            GoalStep("s2", "配一日三餐", "in_progress"),
        ],
    )
    set_step_status(tmp_path, goal.goal_id, "s1", "completed")
    write_checkpoint(
        tmp_path,
        goal_id=goal.goal_id,
        step_id="s2",
        reason="user_cancel",
        constraints_snapshot=["忌口：海鲜"],
        pending_side_effects=[{"kind": "advice_shown", "detail": "已展示三分训练草案"}],
    )
    from local.goals.store import set_goal_status

    set_goal_status(tmp_path, goal.goal_id, "paused")
    before = goal.goal_id
    plan = resume(tmp_path, "life")
    assert plan is not None
    assert plan.goal_id == before
    assert is_resume_request("继续") is True
    assert is_resume_request("今天吃什么") is False
    reloaded = get_active_goal(tmp_path, "life")
    assert reloaded.goal_id == before
    assert reloaded.status == "active"
    by_id = {step.id: step.status for step in reloaded.steps}
    assert by_id["s1"] == "completed"
    assert by_id["s2"] == "in_progress"
    assert "配一日三餐" in plan.pending_titles
    assert "定训练日" in plan.completed_titles
    assert "三分训练草案" in plan.notice
    assert "半执行" in plan.notice
    assert len(list((tmp_path / "goals").glob("*.json"))) == 1


def test_budget_checkpoint_uses_the_budget_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_WORKSPACE", str(tmp_path))
    maybe_open_goal(tmp_path, "life", "开始追踪体重")
    record_run_event("life", "budget_reached", detail="本轮额度用尽")
    goal = get_active_goal(tmp_path, "life")
    assert goal.status == "budget_reached"
    checkpoint = latest_checkpoint(tmp_path, goal.goal_id)
    assert checkpoint.reason == "budget"
    plan = resume(tmp_path, "life")
    assert plan.goal_id == goal.goal_id
    assert "额度" in plan.notice


def test_room_turn_without_a_goal_does_not_write(tmp_path):
    from local.checkpoints.store import write_checkpoint_for_space

    assert write_checkpoint_for_space(tmp_path, "room-1", reason="room_turn_end") is None
    assert list((tmp_path / "checkpoints").glob("*.json")) == []
