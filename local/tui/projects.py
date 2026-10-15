"""项目 / 会话组织（进程内内存持久）。"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


def _id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class Project:
    name: str
    id: str = field(default_factory=_id)
    expanded: bool = True
    session_ids: list[str] = field(default_factory=list)  # 顺序：新→旧由 App 排序时重排


def touch(session) -> None:
    session.updated_at = time.time()


def fmt_ago(ts: float, now: float | None = None) -> str:
    now = now if now is not None else time.time()
    d = max(0, int(now - ts))
    if d < 60:
        return f"{d}s"
    if d < 3600:
        return f"{d // 60}m"
    if d < 86400:
        return f"{d // 3600}h"
    return f"{d // 86400}d"
