"""Single-run budget and cooperative cancel. No second budget implementation.

Defaults: ``BudgetLimits(model_calls=8, seconds=120)``. Override with
``LIGHTAGENT_RUN_MODEL_CALLS`` and ``LIGHTAGENT_RUN_SECONDS``, or pass
``budget_limits=`` into ``make_agent``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from LightAgent.cancellation import CancellationToken
from LightAgent.runtime import BudgetExceeded, BudgetLimits

# Q6A: stop is cooperative. Advice already on screen is not rolled back.
USER_CANCEL_NOTICE = (
    "已停止。已在协作边界停止；若刚才已展示建议，请以界面已显示内容为准，勿假定未执行（半执行）。"
)
BUDGET_REACHED_NOTICE = "本轮额度/时间用尽，已暂停。可稍后再说「继续」。"

DEFAULT_MODEL_CALLS = 8
DEFAULT_SECONDS = 120.0

_BUDGET_MARKERS = ("la-budget", "budget exceeded")
_CANCEL_MARKERS = ("la-cancelled",)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    if value < 0:
        return default
    return value


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip())
    except ValueError:
        return default
    if value < 0:
        return default
    return value


def default_budget_limits() -> BudgetLimits:
    """Tight per-run budget. The daily OpenRouter cap stays a separate gate."""
    return BudgetLimits(
        model_calls=_env_int("LIGHTAGENT_RUN_MODEL_CALLS", DEFAULT_MODEL_CALLS),
        seconds=_env_float("LIGHTAGENT_RUN_SECONDS", DEFAULT_SECONDS),
    )


def make_run_token(*, parent: CancellationToken | None = None) -> CancellationToken:
    if parent is not None:
        return parent.child()
    return CancellationToken()


@dataclass
class ControlledRun:
    content: str
    cancelled: bool = False
    budget_reached: bool = False
    raw: Any = None
    token: CancellationToken | None = None


def _emit(on_event: Callable[[str, dict], None] | None, name: str, **payload: Any) -> None:
    if on_event is None:
        return
    on_event(name, payload)


def _parts(raw: Any) -> tuple[str, str]:
    if raw is None:
        return "", ""
    if isinstance(raw, str):
        return raw, ""
    content = getattr(raw, "content", None)
    error = getattr(raw, "error", None)
    if content is None and error is None and not hasattr(raw, "content"):
        return str(raw), ""
    return str(content or ""), str(error or "")


def _is_budget(blob: str) -> bool:
    lowered = blob.lower()
    return any(marker in lowered for marker in _BUDGET_MARKERS)


def _is_cancel(blob: str) -> bool:
    lowered = blob.lower()
    return any(marker in lowered for marker in _CANCEL_MARKERS)


def notice_for_exception(exc: BaseException, token: CancellationToken | None = None) -> str | None:
    if isinstance(exc, BudgetExceeded) or _is_budget(str(exc)):
        return BUDGET_REACHED_NOTICE
    if (token is not None and token.cancelled) or _is_cancel(str(exc)):
        return USER_CANCEL_NOTICE
    return None


def execute_controlled(
    agent: Any,
    prompt: str,
    *,
    cancellation_token: CancellationToken | None = None,
    on_event: Callable[[str, dict], None] | None = None,
    **run_kwargs: Any,
) -> ControlledRun:
    """Call ``agent.run`` with a cancel token and translate budget/cancel.

    Other exceptions propagate. ``on_event`` receives ``budget_reached`` or
    ``user_cancel`` so a later goal store can pause without a second runner.
    """
    token = cancellation_token if cancellation_token is not None else make_run_token()
    try:
        raw = agent.run(prompt, cancellation_token=token, **run_kwargs)
    except BudgetExceeded:
        _emit(on_event, "budget_reached", notice=BUDGET_REACHED_NOTICE)
        return ControlledRun(
            content=BUDGET_REACHED_NOTICE,
            budget_reached=True,
            token=token,
        )
    except Exception as exc:
        notice = notice_for_exception(exc, token)
        if notice == BUDGET_REACHED_NOTICE:
            _emit(on_event, "budget_reached", notice=notice)
            return ControlledRun(content=notice, budget_reached=True, token=token)
        if notice == USER_CANCEL_NOTICE:
            _emit(on_event, "user_cancel", notice=notice, reason=token.reason)
            return ControlledRun(content=notice, cancelled=True, token=token)
        raise

    content, error = _parts(raw)
    blob = f"{content}\n{error}"
    if _is_budget(blob):
        _emit(on_event, "budget_reached", notice=BUDGET_REACHED_NOTICE)
        return ControlledRun(
            content=BUDGET_REACHED_NOTICE,
            budget_reached=True,
            raw=raw,
            token=token,
        )
    if token.cancelled or _is_cancel(blob):
        _emit(on_event, "user_cancel", notice=USER_CANCEL_NOTICE, reason=token.reason)
        # A finished answer that raced the cancel stays visible, with the notice.
        if content.strip() and not _is_cancel(content) and not content.strip().startswith("[LA-"):
            visible = f"{content.rstrip()}\n\n{USER_CANCEL_NOTICE}"
        else:
            visible = USER_CANCEL_NOTICE
        return ControlledRun(content=visible, cancelled=True, raw=raw, token=token)
    visible = content if content else error
    return ControlledRun(content=visible, raw=raw, token=token)
