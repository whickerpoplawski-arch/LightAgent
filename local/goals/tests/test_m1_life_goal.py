"""M1: explicit goals, one in-progress step, no goal for a short question."""

from __future__ import annotations

import json

from local.constraints.card import ConstraintStore
from local.goals.detect import should_create_goal
from local.goals.inject import render_goal_line
from local.goals.store import (
    GoalStep,
    apply_run_event,
    create_goal,
    get_active_goal,
    goal_from_dict,
    maybe_open_goal,
    set_step_status,
)
from local.harness.ephemeral import sanitize_transcript
from local.memory.host import MemoryHost
from local.memory.inject import prepare_turn


def test_e9_short_questions_do_not_create_a_goal(tmp_path):
    assert should_create_goal("今天吃什么") is False
    assert should_create_goal("今天天气呢") is False
    assert should_create_goal("吃什么好") is False
    assert should_create_goal("帮我制定一周健身与饮食计划") is True
    assert should_create_goal("/goal 一周健身") is True
    assert should_create_goal("今日健身和饮食", room_scenario="fitness_diet") is True
    assert should_create_goal("今日健身和饮食", room_scenario="travel") is False
    assert maybe_open_goal(tmp_path, "life", "今天吃什么") is None
    assert list((tmp_path / "goals").glob("*.json")) == []


def test_e1_explicit_goal_records_active_constraints(tmp_path):
    ConstraintStore(tmp_path).remember("忌口：海鲜")
    goal = maybe_open_goal(tmp_path, "life", "帮我制定一周健身与饮食计划")
    assert goal is not None
    path = tmp_path / "goals" / f"{goal.goal_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["objective"] == "帮我制定一周健身与饮食计划"
    assert data["space_id"] == "life"
    assert data["source"] == "explicit_user"
    assert data["status"] == "active"
    assert "忌口：海鲜" in data["constraints_ref"]
    assert get_active_goal(tmp_path, "life").goal_id == goal.goal_id
    again = maybe_open_goal(tmp_path, "life", "/goal 另一件事")
    assert again.goal_id == goal.goal_id
    assert len(list((tmp_path / "goals").glob("*.json"))) == 1


def test_e2_only_one_step_stays_in_progress(tmp_path):
    goal = create_goal(
        tmp_path,
        space_id="life",
        objective="一周健身与饮食",
        steps=[
            GoalStep("s1", "定训练日", "in_progress"),
            GoalStep("s2", "配一日三餐", "pending"),
        ],
    )
    updated = set_step_status(tmp_path, goal.goal_id, "s2", "in_progress")
    in_progress = [step.id for step in updated.steps if step.status == "in_progress"]
    assert in_progress == ["s2"]
    loaded = goal_from_dict({
        "goal_id": "g-two",
        "space_id": "life",
        "objective": "两步同时",
        "steps": [
            {"id": "s1", "title": "甲", "status": "in_progress"},
            {"id": "s2", "title": "乙", "status": "in_progress"},
        ],
    })
    assert [step.status for step in loaded.steps] == ["pending", "in_progress"]


def test_e5_budget_event_marks_the_goal(tmp_path):
    goal = maybe_open_goal(tmp_path, "life", "开始计划下周饮食")
    marked = apply_run_event(tmp_path, "life", "budget_reached")
    assert marked is not None
    assert marked.goal_id == goal.goal_id
    assert marked.status == "budget_reached"
    assert get_active_goal(tmp_path, "life").status == "budget_reached"
    paused = apply_run_event(tmp_path, "life", "user_cancel")
    assert paused.status == "paused"


def test_ephemeral_line_is_one_objective_not_the_history(env, tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_WORKSPACE", str(tmp_path))
    ConstraintStore(tmp_path).remember("忌口：海鲜")
    goal = maybe_open_goal(tmp_path, "life", "帮我制定一周健身与饮食计划")
    line = render_goal_line(goal)
    assert "一周健身与饮食" in line
    assert "定训练日" in line
    assert "忌口：海鲜" in line
    assert line.count("\n") == 0
    prepared = prepare_turn(
        system="你是助手。",
        history=[{"role": "user", "content": "很久以前的一句闲聊"}],
        user_text="继续这一步",
        host=MemoryHost(user_id="alice", namespace="profile", space_id="life"),
        store=env,
        persona_text="",
        identity_block="",
    )
    assert "定训练日" in prepared.ephemeral
    assert "很久以前的一句闲聊" not in prepared.ephemeral
    assert prepared.messages[-1]["content"] == "继续这一步"
    blob = "\n".join(item["content"] for item in sanitize_transcript(prepared.messages))
    assert "<memory-context>" not in blob
    assert "定训练日" not in blob
