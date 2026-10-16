"""Defaults for the life-assistant consolidate gate.

A queued job folds only when both are true: at least ``MIN_INTERVAL_HOURS``
since the last fold that wrote, and at least ``MIN_NEW_MEMORIES`` active
learnings or diet-card rows newer than that fold (everything counts on the
first fold).
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_INTERVAL_HOURS = 6.0
MIN_NEW_MEMORIES = 2


@dataclass(frozen=True)
class ConsolidateGate:
    min_interval_hours: float = MIN_INTERVAL_HOURS
    min_new_memories: int = MIN_NEW_MEMORIES
