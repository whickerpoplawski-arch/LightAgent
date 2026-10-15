"""Thin adapter used by ``LightAgent.core`` when the context window is tight."""

from __future__ import annotations

from typing import Any

from LightAgent.session import ContextBudget

from .pipeline import run_compact
from .types import CompactTrigger


def _store_for(agent: Any) -> Any:
    if agent is None:
        return None
    explicit = getattr(agent, "_compact_profile_store", None)
    if explicit is not None:
        return explicit
    if getattr(agent, "_profile_memory_host", None) is not None:
        from local.memory.store import get_store

        return get_store()
    return None


def compact_model_messages(
    messages: list[dict],
    *,
    budget: ContextBudget,
    agent: Any = None,
) -> tuple[list[dict], dict[str, Any]]:
    """Auto compact a stripped model transcript. Does not call OpenRouter."""
    host = getattr(agent, "_profile_memory_host", None) if agent is not None else None
    summarizer = getattr(agent, "_compact_summarizer", None) if agent is not None else None
    space_id = getattr(host, "space_id", None) if host is not None else None
    outcome = run_compact(
        messages,
        trigger=CompactTrigger.AUTO,
        summarizer=summarizer,
        store=_store_for(agent),
        host=host,
        space_id=space_id,
        budget=budget,
    )
    spills = [{key: value for key, value in item.items() if key != "content"} for item in outcome.spilled]
    event = {
        "removed_count": outcome.removed_count,
        "summary": outcome.summary,
        "spilled": spills,
        "trigger": "auto",
        "fallback": outcome.fallback,
        "notice": outcome.notice,
        "estimated_tokens": budget.estimate(outcome.messages),
    }
    return outcome.messages, event


def compact_session_life(
    messages: list[dict],
    *,
    focus: str | None,
    space_id: str | None,
    agent: Any = None,
) -> dict[str, Any]:
    """Manual life compact used by ``LightAgent.compact_session(..., life=True)``."""
    host = getattr(agent, "_profile_memory_host", None) if agent is not None else None
    summarizer = getattr(agent, "_compact_summarizer", None) if agent is not None else None
    resolved_space = space_id if space_id is not None else getattr(host, "space_id", None)
    outcome = run_compact(
        messages,
        trigger=CompactTrigger.MANUAL,
        focus=focus,
        summarizer=summarizer,
        store=_store_for(agent),
        host=host,
        space_id=resolved_space,
    )
    payload = outcome.to_public_dict()
    payload["spilled"] = outcome.spilled
    return payload
