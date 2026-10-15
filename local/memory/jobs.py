"""Background consolidate queue.

P0 only records jobs. Nothing here calls a model or merges memories.
"""

from __future__ import annotations

from typing import Any

from .store import ProfileStore


def enqueue(store: ProfileStore, kind: str = "consolidate", payload: dict[str, Any] | None = None) -> str:
    return store.enqueue_job(kind=kind, payload=payload or {})


def run_due(store: ProfileStore) -> list[dict[str, Any]]:
    """P0 stub: due jobs stay queued. Consolidation is intentionally empty."""
    del store
    return []