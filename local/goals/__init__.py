"""Life goals: one completion contract per space, separate from profile learnings."""

from .detect import should_create_goal
from .store import GoalStore, create_goal, get_active_goal, maybe_open_goal, set_step_status

__all__ = [
    "GoalStore",
    "create_goal",
    "get_active_goal",
    "maybe_open_goal",
    "set_step_status",
    "should_create_goal",
]
