"""``{workspace}/goals/{goal_id}.json``. At most one in-progress step."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_OPEN = ("active", "paused", "budget_reached")
_STEP_STATUS = ("pending", "in_progress", "completed")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class GoalStep:
    id: str
    title: str
    status: str = "pending"

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "status": self.status}


@dataclass
class LifeGoal:
    goal_id: str
    space_id: str
    objective: str
    constraints_ref: list[str] = field(default_factory=list)
    steps: list[GoalStep] = field(default_factory=list)
    status: str = "active"
    acceptance: list[str] = field(default_factory=list)
    updated_at: str = ""
    source: str = "explicit_user"

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "space_id": self.space_id,
            "objective": self.objective,
            "constraints_ref": list(self.constraints_ref),
            "steps": [step.to_dict() for step in self.steps],
            "status": self.status,
            "acceptance": list(self.acceptance),
            "updated_at": self.updated_at,
            "source": self.source,
        }


def _normalize_steps(steps: list[GoalStep]) -> list[GoalStep]:
    """Keep the latest in-progress step and demote any earlier one."""
    chosen: str | None = None
    for step in steps:
        if step.status == "in_progress":
            chosen = step.id
    if chosen is None:
        return steps
    for step in steps:
        if step.status == "in_progress" and step.id != chosen:
            step.status = "pending"
    return steps


def goal_from_dict(data: dict) -> LifeGoal:
    steps = []
    for raw in data.get("steps") or []:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or "pending")
        if status not in _STEP_STATUS:
            status = "pending"
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        steps.append(GoalStep(id=str(raw.get("id") or _new_id()), title=title, status=status))
    _normalize_steps(steps)
    return LifeGoal(
        goal_id=str(data.get("goal_id") or _new_id()),
        space_id=str(data.get("space_id") or ""),
        objective=str(data.get("objective") or "").strip(),
        constraints_ref=[str(item) for item in (data.get("constraints_ref") or []) if str(item).strip()],
        steps=steps,
        status=str(data.get("status") or "active"),
        acceptance=[str(item) for item in (data.get("acceptance") or []) if str(item).strip()],
        updated_at=str(data.get("updated_at") or ""),
        source=str(data.get("source") or "explicit_user"),
    )


def _goals_dir(workspace: Path | str) -> Path:
    return Path(workspace) / "goals"


def _path(workspace: Path | str, goal_id: str) -> Path:
    return _goals_dir(workspace) / f"{goal_id}.json"


def default_steps(objective: str) -> list[GoalStep]:
    if "健身" in objective and ("饮食" in objective or "餐" in objective):
        return [
            GoalStep("s1", "定训练日", "in_progress"),
            GoalStep("s2", "配一日三餐", "pending"),
        ]
    return [GoalStep("s1", "明确下一步", "in_progress")]


def _acceptance(objective: str) -> list[str]:
    if "健身" in objective or "饮食" in objective:
        return ["有可执行训练计划", "有忌口合规菜单"]
    return []


def _objective_from(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if cleaned.startswith("/goal"):
        cleaned = cleaned[5:].strip()
    return cleaned[:80]


def _snapshot_constraints(workspace: Path | str) -> list[str]:
    try:
        from local.constraints.card import ConstraintStore

        return ConstraintStore(workspace).active_texts()
    except Exception:
        return []


class GoalStore:
    def __init__(self, workspace: Path | str):
        self.workspace = Path(workspace)

    def load(self, goal_id: str) -> LifeGoal | None:
        path = _path(self.workspace, goal_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return goal_from_dict(data)

    def save(self, goal: LifeGoal) -> LifeGoal:
        _normalize_steps(goal.steps)
        goal.updated_at = _now()
        folder = _goals_dir(self.workspace)
        folder.mkdir(parents=True, exist_ok=True)
        path = _path(self.workspace, goal.goal_id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(goal.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return goal

    def list_goals(self) -> list[LifeGoal]:
        folder = _goals_dir(self.workspace)
        if not folder.is_dir():
            return []
        found: list[LifeGoal] = []
        for path in sorted(folder.glob("*.json")):
            goal = self.load(path.stem)
            if goal is not None and goal.objective:
                found.append(goal)
        return found


def create_goal(
    workspace: Path | str,
    *,
    space_id: str,
    objective: str,
    source: str = "explicit_user",
    steps: list[GoalStep] | None = None,
    constraints_ref: list[str] | None = None,
) -> LifeGoal:
    goal = LifeGoal(
        goal_id=_new_id(),
        space_id=space_id,
        objective=objective.strip(),
        constraints_ref=list(constraints_ref) if constraints_ref is not None else _snapshot_constraints(workspace),
        steps=list(steps) if steps is not None else default_steps(objective),
        status="active",
        acceptance=_acceptance(objective),
        updated_at=_now(),
        source=source,
    )
    _normalize_steps(goal.steps)
    return GoalStore(workspace).save(goal)


def get_active_goal(workspace: Path | str, space_id: str) -> LifeGoal | None:
    rank = {name: index for index, name in enumerate(_OPEN)}
    matches = [
        goal for goal in GoalStore(workspace).list_goals()
        if goal.space_id == space_id and goal.status in rank
    ]
    if not matches:
        return None
    best = min(rank[goal.status] for goal in matches)
    pool = [goal for goal in matches if rank[goal.status] == best]
    pool.sort(key=lambda goal: goal.updated_at, reverse=True)
    return pool[0]


def set_step_status(workspace: Path | str, goal_id: str, step_id: str, status: str) -> LifeGoal:
    if status not in _STEP_STATUS:
        raise ValueError(f"status must be one of {_STEP_STATUS}")
    store = GoalStore(workspace)
    goal = store.load(goal_id)
    if goal is None:
        raise KeyError(goal_id)
    found = False
    for step in goal.steps:
        if step.id == step_id:
            step.status = status
            found = True
        elif status == "in_progress" and step.status == "in_progress":
            step.status = "pending"
    if not found:
        raise KeyError(step_id)
    _normalize_steps(goal.steps)
    if goal.steps and all(step.status == "completed" for step in goal.steps):
        goal.status = "completed"
    return store.save(goal)


def set_goal_status(workspace: Path | str, goal_id: str, status: str) -> LifeGoal:
    store = GoalStore(workspace)
    goal = store.load(goal_id)
    if goal is None:
        raise KeyError(goal_id)
    goal.status = status
    return store.save(goal)


def apply_run_event(workspace: Path | str, space_id: str, event: str) -> LifeGoal | None:
    """Map a run-control event onto the open goal. Missing goal is a no-op."""
    goal = get_active_goal(workspace, space_id)
    if goal is None:
        return None
    if event == "budget_reached":
        goal.status = "budget_reached"
    elif event == "user_cancel":
        goal.status = "paused"
    else:
        return goal
    return GoalStore(workspace).save(goal)


def maybe_open_goal(
    workspace: Path | str,
    space_id: str,
    user_text: str,
    *,
    room_scenario: str | None = None,
) -> LifeGoal | None:
    """Create at most one open goal. Short questions leave the folder empty."""
    from .detect import should_create_goal

    if not should_create_goal(user_text, room_scenario=room_scenario):
        return None
    existing = get_active_goal(workspace, space_id)
    if existing is not None:
        return existing
    source = "explicit_user"
    if room_scenario == "fitness_diet" and not user_text.strip().startswith("/goal") and "帮我制定" not in user_text:
        source = "room_template"
    return create_goal(
        workspace,
        space_id=space_id,
        objective=_objective_from(user_text),
        source=source,
    )


def ensure_goal_for_room(workspace: Path | str, room, user_text: str) -> LifeGoal | None:
    hints = list(getattr(room, "scenario_hints", None) or [])
    title = str(getattr(room, "title", "") or "")
    scenario = "fitness_diet" if "fitness_diet" in hints or "健身" in title else None
    space_id = getattr(room, "space_id", None) or getattr(room, "id", None) or "room"
    return maybe_open_goal(workspace, str(space_id), user_text, room_scenario=scenario)
