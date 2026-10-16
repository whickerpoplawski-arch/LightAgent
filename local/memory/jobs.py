"""Life-assistant consolidate queue.

Diet lines are written by the 1:1 send hook (``absorb_user_text``). ``run_due``
only folds rows already stored. It does not call a model and does not look up
the process-wide store.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local.constraints.card import ConstraintStore

from .consolidate import fold_card, plan_learnings
from .consolidate_config import ConsolidateGate
from .store import ProfileStore


def enqueue(
    store: ProfileStore,
    kind: str = "consolidate",
    payload: dict[str, Any] | None = None,
    *,
    user_id: str,
    namespace: str = "profile",
) -> str:
    scoped = str(user_id or "").strip()
    if not scoped:
        raise ValueError("life user_id is required")
    scope_name = str(namespace or "profile").strip() or "profile"
    body = dict(payload or {})
    body["user_id"] = scoped
    body["namespace"] = scope_name
    return store.enqueue_job(kind=kind, payload=body, user_id=scoped)


def run_due(
    store: ProfileStore,
    *,
    workspace: str | Path | None = None,
    now: datetime | None = None,
    gate: ConsolidateGate | None = None,
) -> list[dict[str, Any]]:
    """Fold queued consolidate jobs for the store the caller passed in.

    The store lock covers the gate check and the write, so a second caller
    waits and then becomes a no-op.
    """
    root = _workspace(workspace)
    clock = _clock(now)
    rules = gate or ConsolidateGate()
    results: list[dict[str, Any]] = []
    with store._lock:
        for job in store.list_jobs():
            if job.get("status") != "queued" or job.get("kind") != "consolidate":
                continue
            results.append(_run_one(store, job, root, clock=clock, gate=rules))
    return results


def _workspace(workspace: str | Path | None) -> Path | None:
    if workspace is not None and str(workspace).strip():
        return Path(workspace)
    raw = os.environ.get("LIGHTAGENT_WORKSPACE")
    if raw:
        return Path(raw)
    return None


def _payload(job: dict[str, Any]) -> dict[str, Any]:
    raw = job.get("payload") or "{}"
    if isinstance(raw, dict):
        return dict(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _learning_snapshot(rows) -> list[dict[str, Any]]:
    return [
        {
            "id": row.id,
            "text": row.text,
            "status": row.status,
            "pinned": row.pinned,
            "injectable": row.injectable,
            "confirmed": row.confirmed,
            "needs_confirm": row.needs_confirm,
            "updated_at": row.updated_at,
            "evidence": row.evidence,
        }
        for row in rows
    ]


def _card_snapshot(card) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "text": item.text,
            "status": item.status,
            "topic": item.topic,
            "supersedes": item.supersedes,
        }
        for item in card.items
    ]


def _empty_diff() -> dict[str, list]:
    return {"merged": [], "superseded": [], "kept": [], "skipped": []}


def _finish(
    store: ProfileStore,
    job: dict[str, Any],
    payload: dict[str, Any],
    *,
    status: str,
    reason: str,
    diff: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    stored = dict(payload)
    stored["user_id"] = user_id
    stored["reason"] = reason
    stored["diff"] = diff
    stored["before"] = before
    stored["after"] = after
    store.complete_job(job["id"], status=status, payload=stored, user_id=user_id)
    return {
        "job_id": job["id"],
        "user_id": user_id,
        "status": status,
        "reason": reason,
        "diff": diff,
    }


def _clock(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc).replace(microsecond=0)
    return now.astimezone(timezone.utc).replace(microsecond=0)


def _parse_time(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_newer(updated_at: str, since: datetime | None) -> bool:
    if since is None:
        return True
    stamped = _parse_time(updated_at)
    if stamped is None:
        return False
    return stamped > since


def _count_new(rows, card, since: datetime | None) -> int:
    total = 0
    for row in rows:
        if row.status == "active" and _is_newer(row.updated_at, since):
            total += 1
    if card is not None:
        for item in card.items:
            if item.status == "active" and _is_newer(item.updated_at, since):
                total += 1
    return total


def _run_one(
    store: ProfileStore,
    job: dict[str, Any],
    root: Path | None,
    *,
    clock: datetime,
    gate: ConsolidateGate,
) -> dict[str, Any]:
    payload = _payload(job)
    user_id = str(job.get("user_id") or payload.get("user_id") or "").strip()
    namespace = str(payload.get("namespace") or "profile").strip() or "profile"
    before: dict[str, Any] = {"learnings": [], "constraints": []}
    after: dict[str, Any] = {"learnings": [], "constraints": []}
    if not user_id:
        diff = {"learnings": _empty_diff(), "constraints": _empty_diff()}
        return _finish(
            store,
            job,
            payload,
            status="skipped",
            reason="missing_user_id",
            diff=diff,
            before=before,
            after=after,
            user_id="",
        )

    rows = store.list_learnings(user_id=user_id, namespace=namespace)
    learning_snapshot = _learning_snapshot(rows)
    before["learnings"] = learning_snapshot
    card_store = ConstraintStore(root) if root is not None else None
    card = card_store.load() if card_store is not None else None
    if card is not None:
        before["constraints"] = _card_snapshot(card)
    last_done = _parse_time(store.last_consolidate_at(user_id, namespace))
    fresh = _count_new(rows, card, last_done)
    gate_info = {
        "new_memories": fresh,
        "min_new_memories": gate.min_new_memories,
        "min_interval_hours": gate.min_interval_hours,
    }
    if last_done is not None:
        elapsed = (clock - last_done).total_seconds()
        if elapsed < gate.min_interval_hours * 3600:
            diff = {"learnings": _empty_diff(), "constraints": _empty_diff(), "gate": gate_info}
            after = {"learnings": learning_snapshot, "constraints": before["constraints"]}
            return _finish(
                store,
                job,
                payload,
                status="skipped",
                reason="min_interval",
                diff=diff,
                before=before,
                after=after,
                user_id=user_id,
            )
    if fresh < gate.min_new_memories:
        diff = {"learnings": _empty_diff(), "constraints": _empty_diff(), "gate": gate_info}
        after = {"learnings": learning_snapshot, "constraints": before["constraints"]}
        return _finish(
            store,
            job,
            payload,
            status="skipped",
            reason="min_new_memories",
            diff=diff,
            before=before,
            after=after,
            user_id=user_id,
        )

    learning_diff = plan_learnings(rows)
    links = [*learning_diff["merged"], *learning_diff["superseded"]]

    if card is not None:
        pinned_texts = {
            row.text
            for row in rows
            if row.pinned or "[PINNED]" in (row.text or "")
        }
        card_diff = fold_card(card, pinned_texts=pinned_texts)
    else:
        card_diff = _empty_diff()
        card_diff["skipped"].append({"id": "", "text": "", "reason": "no_workspace"})

    card_changed = bool(card_diff["merged"] or card_diff["superseded"])
    learning_changed = bool(links)
    diff = {"learnings": learning_diff, "constraints": card_diff}
    if not learning_changed and not card_changed:
        after["learnings"] = learning_snapshot
        after["constraints"] = before["constraints"]
        return _finish(
            store,
            job,
            payload,
            status="skipped",
            reason="nothing_to_fold",
            diff=diff,
            before=before,
            after=after,
            user_id=user_id,
        )

    marked = False
    try:
        if links:
            store.mark_learnings_superseded(links, user_id=user_id, namespace=namespace)
            marked = True
        if card_changed and card_store is not None and card is not None:
            card_store.save(card)
    except Exception as exc:
        if marked:
            store.restore_learnings(learning_snapshot, user_id=user_id, namespace=namespace)
        after["learnings"] = _learning_snapshot(
            store.list_learnings(user_id=user_id, namespace=namespace)
        )
        if card_store is not None:
            after["constraints"] = _card_snapshot(card_store.load())
        return _finish(
            store,
            job,
            payload,
            status="failed",
            reason=f"failed: {type(exc).__name__}",
            diff=diff,
            before=before,
            after=after,
            user_id=user_id,
        )

    after["learnings"] = _learning_snapshot(store.list_learnings(user_id=user_id, namespace=namespace))
    if card_store is not None:
        after["constraints"] = _card_snapshot(card_store.load())
    store.record_consolidate(user_id, namespace, clock.isoformat())
    return _finish(
        store,
        job,
        payload,
        status="done",
        reason="folded",
        diff=diff,
        before=before,
        after=after,
        user_id=user_id,
    )
