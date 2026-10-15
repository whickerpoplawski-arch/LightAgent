"""Host identity for profile writes.

The model may pass ``user_id`` / ``namespace`` / ``reach``. Those values are
discarded. The host stamps the scope before any store call.
"""

from __future__ import annotations

import contextvars
import os
from dataclasses import dataclass
from typing import Any

DEFAULT_USER_ID = os.environ.get("LIGHTAGENT_USER_ID", "local-user")
DEFAULT_NAMESPACE = "profile"

_HOST: contextvars.ContextVar["MemoryHost | None"] = contextvars.ContextVar(
    "lightagent_memory_host",
    default=None,
)
_process_host: MemoryHost | None = None

_MODEL_SCOPE_KEYS = ("user_id", "namespace", "reach", "memory_user_id", "agent_id", "session_id", "space_id")


@dataclass(frozen=True)
class MemoryHost:
    user_id: str
    namespace: str = DEFAULT_NAMESPACE
    session_id: str | None = None
    agent_id: str | None = None
    space_id: str | None = None

    def stamp(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return payload with host scope, ignoring model-supplied scope keys."""
        data = dict(payload or {})
        for key in _MODEL_SCOPE_KEYS:
            data.pop(key, None)
        data["user_id"] = self.user_id
        data["namespace"] = self.namespace
        data["session_id"] = self.session_id
        data["agent_id"] = self.agent_id
        data["space_id"] = self.space_id
        data["source"] = "user"
        data["trust_level"] = "owner"
        return data


def bind_host(host: MemoryHost) -> contextvars.Token:
    """Bind the host for this context and as the process fallback.

    Tool calls may run on a worker thread that does not copy contextvars.
    The process fallback keeps a single-user local assistant consistent.
    Tests reset it.
    """
    global _process_host
    _process_host = host
    return _HOST.set(host)


def reset_host(token: contextvars.Token | None = None) -> None:
    global _process_host
    _process_host = None
    if token is not None:
        _HOST.reset(token)


def current_host() -> MemoryHost:
    host = _HOST.get()
    if host is not None:
        return host
    if _process_host is not None:
        return _process_host
    return MemoryHost(user_id=DEFAULT_USER_ID, namespace=DEFAULT_NAMESPACE)