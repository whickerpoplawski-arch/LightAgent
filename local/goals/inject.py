"""One ephemeral line: objective, current step, active constraints. Not the history."""

from __future__ import annotations

from pathlib import Path

from local.constraints.card import merge_constraint_block, resolve_workspace

from .store import LifeGoal, get_active_goal


def current_step_title(goal: LifeGoal) -> str:
    for step in goal.steps:
        if step.status == "in_progress":
            return step.title
    for step in goal.steps:
        if step.status == "pending":
            return step.title
    return "（无进行中步骤）"


def render_goal_line(goal: LifeGoal, constraints: list[str] | None = None) -> str:
    line = f"当前目标：{goal.objective}；这一步：{current_step_title(goal)}"
    texts = list(constraints) if constraints is not None else list(goal.constraints_ref)
    if texts:
        line += "；忌口：" + "、".join(texts)
    return line


def merge_goal_line(ephemeral: str, *, space_id: str | None, workspace: Path | str | None = None) -> str:
    if not space_id:
        return ephemeral or ""
    root = resolve_workspace(workspace)
    if root is None:
        return ephemeral or ""
    try:
        goal = get_active_goal(root, space_id)
    except Exception:
        return ephemeral or ""
    if goal is None:
        return ephemeral or ""
    return merge_constraint_block(ephemeral or "", render_goal_line(goal))
