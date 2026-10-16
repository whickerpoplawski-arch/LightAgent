"""Shared list / learn / edit / forget / pin operations for the CLI and TUI."""

from __future__ import annotations

from .host import MemoryHost, current_host
from .store import ProfileStore, get_store
from .types import LearnResult, Learning


class MemoryEditor:
    def __init__(self, store: ProfileStore | None = None, host: MemoryHost | None = None) -> None:
        self.store = store or get_store()
        self.host = host or current_host()

    def _scope(self, user_id: str | None = None, namespace: str | None = None) -> dict[str, str]:
        stamped = self.host.stamp({"user_id": user_id, "namespace": namespace})
        return {"user_id": stamped["user_id"], "namespace": stamped["namespace"]}

    def list_rows(self, *, lane: str = "") -> list[dict]:
        scope = self._scope()
        rows = self.store.list_learnings(
            user_id=scope["user_id"],
            namespace=scope["namespace"],
            lane=lane or None,
            include_candidates=True,
        )
        return [self._row(item) for item in rows if item.status != "superseded"]

    def learn(
        self,
        text: str,
        *,
        lane: str = "general",
        facet: str = "identity",
        kind: str = "preference",
        topics: list[str] | None = None,
        user_id: str | None = None,
        namespace: str | None = None,
    ) -> LearnResult:
        scope = self._scope(user_id, namespace)
        return self.store.learn(
            text,
            user_id=scope["user_id"],
            namespace=scope["namespace"],
            lane=lane,
            facet=facet,
            kind=kind,
            topics=topics or [],
            space_id=self.host.space_id,
        )

    def edit(self, learning_id: str, text: str, *, user_id: str | None = None, namespace: str | None = None) -> LearnResult:
        scope = self._scope(user_id, namespace)
        return self.store.edit(learning_id, text, user_id=scope["user_id"], namespace=scope["namespace"])

    def forget(self, target: str, *, user_id: str | None = None, namespace: str | None = None) -> list[str]:
        scope = self._scope(user_id, namespace)
        removed = self.store.forget(
            user_id=scope["user_id"],
            namespace=scope["namespace"],
            learning_id=target,
        )
        if removed:
            return removed
        return self.store.forget(
            user_id=scope["user_id"],
            namespace=scope["namespace"],
            query=target,
        )

    def pin(self, learning_id: str, *, pinned: bool = True, user_id: str | None = None, namespace: str | None = None) -> Learning | None:
        scope = self._scope(user_id, namespace)
        return self.store.pin(learning_id, user_id=scope["user_id"], namespace=scope["namespace"], pinned=pinned)

    def confirm(self, learning_id: str, *, user_id: str | None = None, namespace: str | None = None) -> Learning | None:
        scope = self._scope(user_id, namespace)
        return self.store.confirm(learning_id, user_id=scope["user_id"], namespace=scope["namespace"])

    @staticmethod
    def _row(item: Learning) -> dict:
        flags = []
        if item.pinned:
            flags.append("钉")
        if item.needs_confirm or item.status == "candidate":
            flags.append("待确认")
        prefix = f"[{' '.join(flags)}] " if flags else ""
        return {
            "id": item.id,
            "text": item.text,
            "lane": item.lane,
            "facet": item.facet,
            "kind": item.kind,
            "pinned": item.pinned,
            "needs_confirm": item.needs_confirm or item.status == "candidate",
            "label": f"{prefix}{item.lane}/{item.facet}  {item.text}",
        }