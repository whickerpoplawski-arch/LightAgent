"""Gap B: a spoken done-phrase completes the current step and starts the next."""

from __future__ import annotations

from local.goals.advance import maybe_advance_goal
from local.goals.inject import current_step_title, render_goal_line
from local.goals.store import get_active_goal, maybe_open_goal, set_step_status


def _open(tmp_path):
    goal = maybe_open_goal(tmp_path, "life", "帮我制定一周健身与饮食计划")
    assert goal is not None
    assert [step.status for step in goal.steps] == ["in_progress", "pending"]
    return goal


def test_b_t1_training_day_done_moves_to_meals(tmp_path):
    goal = _open(tmp_path)
    updated = maybe_advance_goal(tmp_path, "life", "训练日定好了")
    assert updated is not None
    assert updated.goal_id == goal.goal_id
    by_id = {step.id: step.status for step in updated.steps}
    assert by_id["s1"] == "completed"
    assert by_id["s2"] == "in_progress"
    assert sum(status == "in_progress" for status in by_id.values()) == 1


def test_b_t2_second_step_completes_the_goal(tmp_path):
    _open(tmp_path)
    maybe_advance_goal(tmp_path, "life", "训练日定好了")
    updated = maybe_advance_goal(tmp_path, "life", "一日三餐配好了")
    assert updated is not None
    assert updated.status == "completed"
    assert all(step.status == "completed" for step in updated.steps)
    assert get_active_goal(tmp_path, "life") is None

    other = maybe_open_goal(tmp_path, "other", "帮我制定一周健身与饮食计划")
    assert other is not None
    maybe_advance_goal(tmp_path, "other", "这步完成了")
    mid = get_active_goal(tmp_path, "other")
    assert mid is not None and mid.steps[0].status == "completed" and mid.steps[1].status == "in_progress"
    done = maybe_advance_goal(tmp_path, "other", "这步完成了")
    assert done is not None and done.status == "completed"


def test_b_t3_short_questions_do_not_move_the_step(tmp_path):
    goal = _open(tmp_path)
    assert maybe_advance_goal(tmp_path, "life", "今天吃什么") is None
    assert maybe_advance_goal(tmp_path, "life", "现在几点") is None
    again = get_active_goal(tmp_path, "life")
    assert again is not None
    assert [step.status for step in again.steps] == [step.status for step in goal.steps]


def test_b_t4_no_goal_does_not_create_one(tmp_path):
    assert maybe_advance_goal(tmp_path, "life", "训练日定好了") is None
    assert list((tmp_path / "goals").glob("*.json")) == []


def test_b_t5_direct_set_step_status_still_keeps_one_in_progress(tmp_path):
    goal = _open(tmp_path)
    updated = set_step_status(tmp_path, goal.goal_id, "s2", "in_progress")
    assert [step.id for step in updated.steps if step.status == "in_progress"] == ["s2"]
    assert updated.steps[0].status == "pending"


def test_b_t6_goal_line_follows_the_new_in_progress_title(tmp_path):
    goal = _open(tmp_path)
    assert current_step_title(goal) == "定训练日"
    updated = maybe_advance_goal(tmp_path, "life", "训练日定好了")
    assert updated is not None
    assert current_step_title(updated) == "配一日三餐"
    assert "配一日三餐" in render_goal_line(updated)
    assert "定训练日" not in render_goal_line(updated).split("这一步：", 1)[1]
