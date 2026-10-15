"""``{workspace}/checkpoints/{checkpoint_id}.json``. No filesystem snapshot."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_REASONS = ("step_done", "user_cancel", "budget", "room_turn_end", "compact_pre", "user_revise")
_RESUME = {"继续", "继续吧", "接着", "接着来", "继续刚才", "继续刚才的"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Checkpoint:
    checkpoint_id: str
    goal_id: str
    step_id: str | None = None
    room_id: str | None = None
    constraints_snapshot: list[str] = field(default_factory=list)
    pending_side_effects: list[dict] = field(default_factory=list)
    reason: str = "user_cancel"
    ts: str = ""

    def to_dict(self) -> dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "goal_id": self.goal_id,
            "step_id": self.step_id,
            "room_id": self.room_id,
            "constraints_snapshot": list(self.constraints_snapshot),
            "pending_side_effects": list(self.pending_side_effects),
            "reason": self.reason,
            "ts": self.ts,
        }


def checkpoint_from_dict(data: dict) -> Checkpoint:
    effects = []
    for item in data.get("pending_side_effects") or []:
        if isinstance(item, dict) and item.get("kind"):
            effects.append({"kind": str(item.get("kind")), "detail": str(item.get("detail") or "")})
    return Checkpoint(
        checkpoint_id=str(data.get("checkpoint_id") or uuid.uuid4().hex[:12]),
        goal_id=str(data.get("goal_id") or ""),
        step_id=data.get("step_id") or None,
        room_id=data.get("room_id") or None,
        constraints_snapshot=[str(item) for item in (data.get("constraints_snapshot") or []) if str(item).strip()],
        pending_side_effects=effects,
        reason=str(data.get("reason") or "user_cancel"),
        ts=str(data.get("ts") or ""),
    )


def _dir(workspace: Path | str) -> Path:
    return Path(workspace) / "checkpoints"


def write_checkpoint(
    workspace: Path | str,
    *,
    goal_id: str,
    step_id: str | None = None,
    reason: str = "user_cancel",
    room_id: str | None = None,
    constraints_snapshot: list[str] | None = None,
    pending_side_effects: list[dict] | None = None,
) -> Checkpoint:
    if reason not in _REASONS:
        reason = "user_cancel"
    checkpoint = Checkpoint(
        checkpoint_id=uuid.uuid4().hex[:12],
        goal_id=goal_id,
        step_id=step_id,
        room_id=room_id,
        constraints_snapshot=list(constraints_snapshot or []),
        pending_side_effects=list(pending_side_effects or []),
        reason=reason,
        ts=_now(),
    )
    folder = _dir(workspace)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{checkpoint.checkpoint_id}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return checkpoint


def list_checkpoints(workspace: Path | str) -> list[Checkpoint]:
    folder = _dir(workspace)
    if not folder.is_dir():
        return []
    found: list[Checkpoint] = []
    for path in folder.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("goal_id"):
            found.append(checkpoint_from_dict(data))
    found.sort(key=lambda item: item.ts)
    return found


def latest_checkpoint(workspace: Path | str, goal_id: str | None = None) -> Checkpoint | None:
    rows = list_checkpoints(workspace)
    if goal_id:
        rows = [item for item in rows if item.goal_id == goal_id]
    if not rows:
        return None
    return rows[-1]


def _current_step_id(goal) -> str | None:
    for step in goal.steps:
        if step.status == "in_progress":
            return step.id
    for step in goal.steps:
        if step.status == "pending":
            return step.id
    return None


def write_checkpoint_for_space(
    workspace: Path | str,
    space_id: str,
    *,
    reason: str,
    detail: str = "",
    room_id: str | None = None,
    kind: str = "advice_shown",
) -> Checkpoint | None:
    """Write only when this space already has an open goal."""
    from local.goals.store import get_active_goal

    goal = get_active_goal(workspace, space_id)
    if goal is None:
        return None
    effects = [{"kind": kind, "detail": detail}] if detail else []
    snapshot = list(goal.constraints_ref)
    if not snapshot:
        try:
            from local.constraints.card import ConstraintStore

            snapshot = ConstraintStore(workspace).active_texts()
        except Exception:
            snapshot = []
    return write_checkpoint(
        workspace,
        goal_id=goal.goal_id,
        step_id=_current_step_id(goal),
        reason=reason,
        room_id=room_id,
        constraints_snapshot=snapshot,
        pending_side_effects=effects,
    )


def record_run_event(space_id: str | None, event: str, *, detail: str = "") -> None:
    """Pause or mark budget on the open goal, then store a checkpoint. Fail-open."""
    root = os.environ.get("LIGHTAGENT_WORKSPACE")
    if not root or not space_id:
        return
    if event == "user_cancel":
        reason = "user_cancel"
    elif event == "budget_reached":
        reason = "budget"
    else:
        return
    try:
        from local.goals.store import apply_run_event

        apply_run_event(root, space_id, event)
    except Exception:
        pass
    try:
        write_checkpoint_for_space(root, space_id, reason=reason, detail=detail)
    except Exception:
        return


def is_resume_request(text: str) -> bool:
    return " ".join((text or "").split()) in _RESUME


@dataclass
class ResumePlan:
    goal_id: str
    objective: str
    step_id: str | None
    completed_titles: list[str]
    pending_titles: list[str]
    notice: str
    checkpoint: Checkpoint | None = None


def resume(workspace: Path | str, space_id: str) -> ResumePlan | None:
    """Re-open the same goal. Completed steps stay completed. No new goal id."""
    from local.goals.store import GoalStore, get_active_goal

    before = {goal.goal_id for goal in GoalStore(workspace).list_goals()}
    goal = get_active_goal(workspace, space_id)
    if goal is None:
        return None
    if goal.goal_id not in before:
        return None
    checkpoint = latest_checkpoint(workspace, goal.goal_id)
    if goal.status in ("paused", "budget_reached"):
        goal.status = "active"
        GoalStore(workspace).save(goal)
    completed = [step.title for step in goal.steps if step.status == "completed"]
    pending = [step.title for step in goal.steps if step.status != "completed"]
    step_id = _current_step_id(goal)
    lines = []
    if pending:
        lines.append(f"从「{pending[0]}」继续。")
    else:
        lines.append("这个目标的步骤都完成了。")
    if completed:
        lines.append("已完成：" + "、".join(completed))
    if checkpoint:
        for effect in checkpoint.pending_side_effects:
            detail = str(effect.get("detail") or "").strip()
            if effect.get("kind") == "advice_shown" and detail:
                lines.append(f"半执行：{detail}")
            elif effect.get("kind") == "routine_due_listed" and detail:
                lines.append(f"待确认：{detail}")
    after = {item.goal_id for item in GoalStore(workspace).list_goals()}
    if after - before:
        raise RuntimeError("resume created a new goal")
    return ResumePlan(
        goal_id=goal.goal_id,
        objective=goal.objective,
        step_id=step_id,
        completed_titles=completed,
        pending_titles=pending,
        notice="\n".join(lines),
        checkpoint=checkpoint,
    )
