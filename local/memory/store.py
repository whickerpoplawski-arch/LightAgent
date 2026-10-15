"""SQLite profile store. Persona files are not stored here.

Callers must pass host-stamped ``user_id`` and ``namespace``. This module does
not read model tool arguments.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .policy import life_assistant_policy
from .scrub import scrub_text
from .types import LearnResult, Learning, normalize_facet, normalize_kind, normalize_lane

_UNTRUSTED = {"untrusted", "web", "tool"}
_NOT_PROFILE_SOURCES = {"reflection", "self_learning", "agent", "derived"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS learnings (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    text TEXT NOT NULL,
    kind TEXT NOT NULL,
    lane TEXT NOT NULL,
    facet TEXT NOT NULL,
    confidence REAL NOT NULL,
    pinned INTEGER NOT NULL DEFAULT 0,
    needs_confirm INTEGER NOT NULL DEFAULT 0,
    confirmed INTEGER NOT NULL DEFAULT 1,
    topics TEXT NOT NULL DEFAULT '[]',
    space_id TEXT,
    source TEXT NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'active',
    injectable INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    evidence TEXT
);
CREATE INDEX IF NOT EXISTS idx_learnings_scope
    ON learnings (user_id, namespace, status);
CREATE TABLE IF NOT EXISTS consolidate_runs (
    user_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    last_done_at TEXT NOT NULL,
    PRIMARY KEY (user_id, namespace)
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def default_store_path() -> Path:
    override = os.environ.get("LIGHTAGENT_PROFILE_DB")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "store" / "profile.sqlite"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_learning(row: sqlite3.Row) -> Learning:
    topics = json.loads(row["topics"] or "[]")
    return Learning(
        id=row["id"],
        user_id=row["user_id"],
        namespace=row["namespace"],
        text=row["text"],
        kind=row["kind"],
        lane=row["lane"],
        facet=row["facet"],
        confidence=float(row["confidence"]),
        pinned=bool(row["pinned"]),
        needs_confirm=bool(row["needs_confirm"]),
        confirmed=bool(row["confirmed"]),
        topics=tuple(str(item) for item in topics),
        space_id=row["space_id"],
        source=row["source"],
        status=row["status"],
        injectable=bool(row["injectable"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        evidence=row["evidence"],
    )


class ProfileStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Re-entrant so a consolidate pass can hold the lock across store calls.
        self._lock = threading.RLock()
        self._policy = life_assistant_policy()
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            self._ensure_job_columns(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def revision(self) -> str:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c, COALESCE(MAX(updated_at), '') AS m FROM learnings"
            ).fetchone()
        return f"{row['c']}:{row['m']}"

    def learn(
        self,
        text: str,
        *,
        user_id: str,
        namespace: str,
        lane: str = "general",
        facet: str = "identity",
        kind: str = "preference",
        topics: list[str] | tuple[str, ...] | None = None,
        space_id: str | None = None,
        source: str = "user",
        trust_level: str = "owner",
        confidence: float = 0.8,
        evidence: str | None = None,
        pinned: bool = False,
    ) -> LearnResult:
        if str(trust_level).lower() in _UNTRUSTED:
            return LearnResult(None, "rejected", "untrusted content cannot enter the user profile")
        if str(source).lower() in _NOT_PROFILE_SOURCES:
            return LearnResult(None, "rejected", "self_learning/reflection is not the user profile")

        try:
            lane_n = normalize_lane(lane)
            facet_n = normalize_facet(facet)
            kind_n = normalize_kind(kind)
        except ValueError as exc:
            return LearnResult(None, "rejected", str(exc))

        scrubbed = scrub_text(text)
        if not scrubbed.allowed:
            return LearnResult(None, "rejected", scrubbed.reason)

        decision = self._policy.allows_write(
            scrubbed.text,
            {
                "user_id": user_id,
                "source": source,
                "scope": "profile",
                "trust_level": trust_level,
            },
        )
        if not decision.allowed:
            return LearnResult(None, "rejected", decision.reason)
        stored_text = decision.value if decision.value is not None else scrubbed.text

        topic_list = tuple(dict.fromkeys(str(item).strip() for item in (topics or []) if str(item).strip()))
        needs_confirm = scrubbed.needs_confirm
        status = "candidate" if needs_confirm else "active"
        injectable = not needs_confirm
        confirmed = not needs_confirm
        now = _now()
        learning_id = uuid.uuid4().hex[:12]
        confidence = max(0.0, min(1.0, float(confidence)))

        with self._lock, self._connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM learnings
                WHERE user_id = ? AND namespace = ? AND text = ?
                """,
                (user_id, namespace, stored_text),
            ).fetchone()
            if existing is not None:
                current = self._get_conn(conn, existing["id"], user_id, namespace)
                return LearnResult(current, "duplicate", "already stored")

            conn.execute(
                """
                INSERT INTO learnings (
                    id, user_id, namespace, text, kind, lane, facet, confidence,
                    pinned, needs_confirm, confirmed, topics, space_id, source,
                    status, injectable, created_at, updated_at, evidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    learning_id,
                    user_id,
                    namespace,
                    stored_text,
                    kind_n,
                    lane_n,
                    facet_n,
                    confidence,
                    int(pinned),
                    int(needs_confirm),
                    int(confirmed),
                    json.dumps(list(topic_list), ensure_ascii=False),
                    space_id,
                    source,
                    status,
                    int(injectable),
                    now,
                    now,
                    evidence,
                ),
            )
            conn.commit()
            saved = self._get_conn(conn, learning_id, user_id, namespace)
        result_status = "needs_confirm" if needs_confirm else "saved"
        return LearnResult(saved, result_status, scrubbed.reason)

    def _get_conn(
        self,
        conn: sqlite3.Connection,
        learning_id: str,
        user_id: str,
        namespace: str,
    ) -> Learning | None:
        row = conn.execute(
            """
            SELECT * FROM learnings
            WHERE id = ? AND user_id = ? AND namespace = ?
            """,
            (learning_id, user_id, namespace),
        ).fetchone()
        return None if row is None else _row_to_learning(row)

    def get(self, learning_id: str, *, user_id: str, namespace: str) -> Learning | None:
        with self._lock, self._connect() as conn:
            return self._get_conn(conn, learning_id, user_id, namespace)

    def list_learnings(
        self,
        *,
        user_id: str,
        namespace: str,
        lane: str | None = None,
        include_candidates: bool = True,
    ) -> list[Learning]:
        sql = "SELECT * FROM learnings WHERE user_id = ? AND namespace = ?"
        params: list[Any] = [user_id, namespace]
        if not include_candidates:
            sql += " AND status = 'active' AND injectable = 1 AND confirmed = 1"
        if lane:
            sql += " AND lane = ?"
            params.append(normalize_lane(lane))
        sql += " ORDER BY pinned DESC, updated_at DESC"
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_learning(row) for row in rows]

    def list_injectable(self, *, user_id: str, namespace: str) -> list[Learning]:
        return self.list_learnings(
            user_id=user_id,
            namespace=namespace,
            include_candidates=False,
        )

    def forget(self, *, user_id: str, namespace: str, learning_id: str = "", query: str = "") -> list[str]:
        """Hard-delete rows inside the stamped scope. Returns removed ids."""
        with self._lock, self._connect() as conn:
            if learning_id:
                row = conn.execute(
                    "SELECT id FROM learnings WHERE id = ? AND user_id = ? AND namespace = ?",
                    (learning_id, user_id, namespace),
                ).fetchone()
                if row is None:
                    return []
                conn.execute(
                    "DELETE FROM learnings WHERE id = ? AND user_id = ? AND namespace = ?",
                    (learning_id, user_id, namespace),
                )
                conn.commit()
                return [learning_id]
            if not query.strip():
                return []
            needle = f"%{query.strip()}%"
            rows = conn.execute(
                """
                SELECT id FROM learnings
                WHERE user_id = ? AND namespace = ? AND text LIKE ?
                """,
                (user_id, namespace, needle),
            ).fetchall()
            ids = [row["id"] for row in rows]
            conn.execute(
                """
                DELETE FROM learnings
                WHERE user_id = ? AND namespace = ? AND text LIKE ?
                """,
                (user_id, namespace, needle),
            )
            conn.commit()
            return ids

    def pin(self, learning_id: str, *, user_id: str, namespace: str, pinned: bool = True) -> Learning | None:
        now = _now()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE learnings SET pinned = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND namespace = ?
                """,
                (int(pinned), now, learning_id, user_id, namespace),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            return self._get_conn(conn, learning_id, user_id, namespace)

    def edit(
        self,
        learning_id: str,
        text: str,
        *,
        user_id: str,
        namespace: str,
    ) -> LearnResult:
        current = self.get(learning_id, user_id=user_id, namespace=namespace)
        if current is None:
            return LearnResult(None, "rejected", "not found in this user scope")
        scrubbed = scrub_text(text)
        if not scrubbed.allowed:
            return LearnResult(current, "rejected", scrubbed.reason)
        decision = self._policy.allows_write(scrubbed.text, {"user_id": user_id, "source": "user", "scope": "profile"})
        if not decision.allowed:
            return LearnResult(current, "rejected", decision.reason)
        stored_text = decision.value if decision.value is not None else scrubbed.text
        needs_confirm = scrubbed.needs_confirm
        now = _now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE learnings
                SET text = ?, needs_confirm = ?, confirmed = ?, injectable = ?,
                    status = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND namespace = ?
                """,
                (
                    stored_text,
                    int(needs_confirm),
                    int(not needs_confirm),
                    int(not needs_confirm),
                    "candidate" if needs_confirm else "active",
                    now,
                    learning_id,
                    user_id,
                    namespace,
                ),
            )
            conn.commit()
            saved = self._get_conn(conn, learning_id, user_id, namespace)
        status = "needs_confirm" if needs_confirm else "saved"
        return LearnResult(saved, status, None)

    def confirm(self, learning_id: str, *, user_id: str, namespace: str) -> Learning | None:
        now = _now()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE learnings
                SET confirmed = 1, injectable = 1, needs_confirm = 0, status = 'active', updated_at = ?
                WHERE id = ? AND user_id = ? AND namespace = ?
                """,
                (now, learning_id, user_id, namespace),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            return self._get_conn(conn, learning_id, user_id, namespace)

    def _ensure_job_columns(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "user_id" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
        if "updated_at" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")

    def enqueue_job(self, *, kind: str, payload: dict[str, Any], user_id: str) -> str:
        scoped = str(user_id or "").strip()
        if not scoped:
            raise ValueError("life user_id is required")
        job_id = uuid.uuid4().hex[:12]
        now = _now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, kind, payload, status, created_at, user_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, kind, json.dumps(payload, ensure_ascii=False), "queued", now, scoped, now),
            )
            conn.commit()
        return job_id

    def complete_job(self, job_id: str, *, status: str, payload: dict[str, Any], user_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, payload = ?, user_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, json.dumps(payload, ensure_ascii=False), user_id, _now(), job_id),
            )
            conn.commit()

    def mark_learnings_superseded(
        self,
        links: list[dict[str, str]],
        *,
        user_id: str,
        namespace: str,
    ) -> int:
        """Keep the row, but stop injecting it. Pinned text is never rewritten."""
        now = _now()
        changed = 0
        with self._lock, self._connect() as conn:
            for link in links:
                learning_id = str(link.get("id") or "")
                kept_id = str(link.get("kept_id") or "")
                row = conn.execute(
                    """
                    SELECT evidence FROM learnings
                    WHERE id = ? AND user_id = ? AND namespace = ? AND pinned = 0
                      AND status = 'active' AND instr(text, '[PINNED]') = 0
                    """,
                    (learning_id, user_id, namespace),
                ).fetchone()
                if row is None:
                    continue
                previous = str(row["evidence"] or "")
                note = f"superseded_by:{kept_id}" if kept_id else "superseded"
                evidence = f"{previous}\n{note}".strip() if previous else note
                cur = conn.execute(
                    """
                    UPDATE learnings
                    SET status = 'superseded', injectable = 0, updated_at = ?, evidence = ?
                    WHERE id = ? AND user_id = ? AND namespace = ? AND pinned = 0
                      AND status = 'active' AND instr(text, '[PINNED]') = 0
                    """,
                    (now, evidence, learning_id, user_id, namespace),
                )
                changed += cur.rowcount
            conn.commit()
        return changed

    def restore_learnings(self, snapshot: list[dict[str, Any]], *, user_id: str, namespace: str) -> None:
        """Put snapshotted rows back. This does not insert or delete."""
        with self._lock, self._connect() as conn:
            for item in snapshot:
                conn.execute(
                    """
                    UPDATE learnings
                    SET status = ?, injectable = ?, confirmed = ?, needs_confirm = ?,
                        pinned = ?, updated_at = ?, evidence = ?
                    WHERE id = ? AND user_id = ? AND namespace = ?
                    """,
                    (
                        item.get("status") or "active",
                        int(bool(item.get("injectable"))),
                        int(bool(item.get("confirmed", True))),
                        int(bool(item.get("needs_confirm"))),
                        int(bool(item.get("pinned"))),
                        item.get("updated_at") or "",
                        item.get("evidence"),
                        item.get("id"),
                        user_id,
                        namespace,
                    ),
                )
            conn.commit()

    def last_consolidate_at(self, user_id: str, namespace: str) -> str:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT last_done_at FROM consolidate_runs
                WHERE user_id = ? AND namespace = ?
                """,
                (user_id, namespace),
            ).fetchone()
        return "" if row is None else str(row["last_done_at"] or "")

    def record_consolidate(self, user_id: str, namespace: str, when: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO consolidate_runs (user_id, namespace, last_done_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, namespace) DO UPDATE SET last_done_at = excluded.last_done_at
                """,
                (user_id, namespace, when),
            )
            conn.commit()

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]


_store: ProfileStore | None = None
_store_lock = threading.Lock()


def get_store() -> ProfileStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = ProfileStore()
        return _store


def set_store(store: ProfileStore | None) -> None:
    global _store
    with _store_lock:
        _store = store
