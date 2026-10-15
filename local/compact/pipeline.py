"""Compact pipeline: flush, strip, spill, user-turn window, summarize, route.

Summary failure keeps the stripped and pruned window. It does not wipe history.
The default summarizer is local and does not call the network.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Callable

from LightAgent.session import ContextBudget, ContextCompactor, is_never_compact

from .ephemeral import ephemeral_bodies, strip_messages
from .extract import extract_after_compact
from .flush import memory_flush
from .messages import ensure_metadata, in_space
from .policy import (
    KEEP_USER_TURNS,
    MAX_INLINE_TOOL_CHARS,
    MIN_KEEP_TOOL_STEPS,
    clamp_focus,
    summarizer_prompt,
)
from .quality import audit_summary
from .recall_spill import SpillStore, get_spill_store
from .summarize_local import local_summarizer
from .types import CompactOutcome, CompactTrigger

Summarizer = Callable[[str, list[dict[str, Any]]], str]


def _scrub_removed(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from local.memory.scrub import scrub_text

    cleaned: list[dict[str, Any]] = []
    for message in messages:
        item = deepcopy(message)
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            result = scrub_text(content)
            if not result.allowed:
                item["content"] = "[redacted-secret]"
            else:
                item["content"] = result.text
        metadata = item.get("metadata")
        if isinstance(metadata, dict):
            metadata.pop("compact_stamp", None)
        cleaned.append(item)
    return cleaned


def _shrink_to_budget(
    messages: list[dict[str, Any]],
    budget: ContextBudget,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Drop oldest non-user messages first, then oldest user turns, never pins."""
    if budget.fits(messages):
        return list(messages), []
    kept = list(messages)
    extra: list[dict[str, Any]] = []

    def drop_first(predicate) -> bool:
        for index, message in enumerate(kept):
            if predicate(message, index):
                extra.append(kept.pop(index))
                return True
        return False

    def disposable(message: dict[str, Any], index: int) -> bool:
        if index == 0 and message.get("role") == "system":
            return False
        if is_never_compact(message):
            return False
        metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
        if metadata.get("compacted"):
            return False
        return message.get("role") != "user"

    while not budget.fits(kept) and drop_first(disposable):
        continue
    while not budget.fits(kept):
        user_indexes = [
            index for index, message in enumerate(kept)
            if message.get("role") == "user" and not is_never_compact(message)
        ]
        if len(user_indexes) <= 1:
            break
        extra.append(kept.pop(user_indexes[0]))
    return kept, extra


def _install_summary(
    messages: list[dict[str, Any]],
    summary: str,
    *,
    trigger: CompactTrigger,
    space_id: str | None,
    removed_count: int,
) -> list[dict[str, Any]]:
    body = []
    for message in messages:
        metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
        if message.get("role") == "system" and metadata.get("compacted"):
            continue
        body.append(message)
    summary_message = {
        "role": "system",
        "content": f"Previous conversation summary:\n{summary}",
        "metadata": {
            "compacted": True,
            "trigger": trigger.value,
            "space_id": space_id,
            "removed_count": removed_count,
        },
    }
    if body and body[0].get("role") == "system":
        return [body[0], summary_message, *body[1:]]
    return [summary_message, *body]


def _stamp(messages: list[dict[str, Any]]) -> None:
    for index, message in enumerate(messages):
        if isinstance(message, dict):
            ensure_metadata(message)["compact_stamp"] = index


def _sync_flags(source: list[dict[str, Any]], *targets: list[dict[str, Any]]) -> None:
    flags: dict[Any, dict[str, Any]] = {}
    for message in source:
        if not isinstance(message, dict):
            continue
        metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
        stamp = metadata.get("compact_stamp")
        if stamp is None:
            continue
        flags[stamp] = {
            "compact": metadata.get("compact"),
            "memory_flushed": metadata.get("memory_flushed"),
            "compact_extracted": metadata.get("compact_extracted"),
        }
    groups = [source, *targets]
    for group in groups:
        for message in group:
            if not isinstance(message, dict):
                continue
            metadata = ensure_metadata(message)
            stamp = metadata.pop("compact_stamp", None)
            saved = flags.get(stamp)
            if not saved:
                continue
            for key, value in saved.items():
                if value is not None:
                    metadata[key] = value


def _notice(trigger: CompactTrigger, *, fallback: bool, focus: str | None, removed_count: int) -> str:
    if fallback:
        if trigger is CompactTrigger.MANUAL:
            return "已裁剪未摘要（摘要失败，已保留最近对话）"
        return "已裁剪未摘要"
    if removed_count <= 0:
        return "没有可移出的旧消息" if trigger is CompactTrigger.MANUAL else "上下文未超过需要摘要的部分"
    if trigger is CompactTrigger.AUTO:
        return "上下文已压缩"
    text = "已按 /compact 整理会话"
    if focus:
        text += f"（焦点：{focus[:40]}）"
    return text


def run_compact(
    messages: list[dict[str, Any]] | None,
    *,
    trigger: CompactTrigger | str,
    focus: str | None = None,
    summarizer: Summarizer | None = None,
    store: Any = None,
    host: Any = None,
    space_id: str | None = None,
    budget: ContextBudget | None = None,
    spill_store: SpillStore | None = None,
    today: date | None = None,
    keep_user_turns: int = KEEP_USER_TURNS,
) -> CompactOutcome:
    """Run the life-assistant compact pipeline on ``messages``.

    ``messages`` is mutated for pins and flush/extract flags. The returned
    ``messages`` are the new model view (stripped, windowed, maybe summarized).
    """
    kind = CompactTrigger(trigger)
    focus_text = clamp_focus(focus) if kind is CompactTrigger.MANUAL else None
    source = list(messages or [])
    if host is None and store is not None:
        from local.memory.host import MemoryHost

        host = MemoryHost(user_id="local-user", namespace="profile", space_id=space_id)
    _stamp(source)
    seen: set[str] = set()
    try:
        flush_report = memory_flush(
            source,
            store=store,
            host=host,
            space_id=space_id,
            today=today,
            seen_texts=seen,
        )
    except Exception as exc:
        flush_report = {"written": [], "pinned_count": 0, "notes": [f"flush failed: {type(exc).__name__}: {exc}"]}

    bodies = ephemeral_bodies(source)
    try:
        working = strip_messages(source)
    except Exception:
        working = [dict(message) if isinstance(message, dict) else message for message in source]

    compactor = ContextCompactor(
        max_inline_tool_chars=MAX_INLINE_TOOL_CHARS,
        min_keep_tool_steps=MIN_KEEP_TOOL_STEPS,
        defer_error_tool_results=True,
    )
    try:
        compacted = compactor.compact(working, keep_user_turns=keep_user_turns)
        messages_out = list(compacted.messages)
        removed = list(compacted.removed)
        spilled = list(compacted.spilled)
        # Prefer dropping assistant/tool text before user turns when the window is over budget.
        if budget is not None and not budget.fits(messages_out):
            messages_out, extra = _shrink_to_budget(messages_out, budget)
            removed = removed + extra
    except Exception as exc:
        messages_out = working or list(source)
        removed = []
        spilled = []
        flush_report.setdefault("notes", []).append(f"window failed: {type(exc).__name__}: {exc}")

    summary_source = _scrub_removed([message for message in removed if isinstance(message, dict) and in_space(message, space_id)])
    prompt = summarizer_prompt(kind, focus=focus_text, space_id=space_id) if summary_source else ""
    summary: str | None = None
    fallback = False
    fallback_reason = ""
    if summary_source:
        runner = summarizer or local_summarizer
        try:
            raw = runner(prompt, summary_source)
        except Exception as exc:
            raw = None
            fallback = True
            fallback_reason = f"{type(exc).__name__}: {exc}"
        if not fallback:
            ok, why = audit_summary(
                raw,
                original_messages=source,
                removed=summary_source,
                space_id=space_id,
                ephemeral_bodies=bodies,
            )
            if ok:
                summary = str(raw).strip()
            else:
                fallback = True
                fallback_reason = why
    if summary:
        messages_out = _install_summary(
            messages_out,
            summary,
            trigger=kind,
            space_id=space_id,
            removed_count=len(removed),
        )
    elif fallback and not messages_out:
        messages_out = working or list(source)
        fallback_reason = fallback_reason or "empty history"

    try:
        extracted = extract_after_compact(
            working,
            store=store,
            host=host,
            space_id=space_id,
            seen_texts=seen,
        )
    except Exception as exc:
        extracted = {"written": [], "procedural": [], "notes": [f"extract failed: {type(exc).__name__}: {exc}"]}

    _sync_flags(working, messages_out, source, removed)
    spill_target = spill_store or get_spill_store()
    try:
        spill_target.add_many(spilled)
    except Exception:
        pass

    notes = list(flush_report.get("notes") or []) + list(extracted.get("notes") or [])
    if fallback_reason:
        notes.append(fallback_reason)
    written = list(flush_report.get("written") or []) + list(extracted.get("written") or [])
    outcome = CompactOutcome(
        messages=messages_out,
        removed_count=len(removed),
        summary=summary,
        spilled=spilled,
        trigger=kind,
        fallback=fallback,
        notice=_notice(kind, fallback=fallback, focus=focus_text, removed_count=len(removed)),
        memories_written=written,
        procedural_pending=list(extracted.get("procedural") or []),
        pinned_count=int(flush_report.get("pinned_count") or 0),
        notes=notes,
        space_id=space_id,
        prompt=prompt,
        summarizer_input=summary_source,
        removed=removed,
    )
    if not outcome.messages:
        outcome.messages = [message for message in source if isinstance(message, dict)] or [
            {"role": "system", "content": "Previous conversation summary:\n（空）"}
        ]
        outcome.fallback = True
        outcome.summary = None
        outcome.notice = "已裁剪未摘要"
    return outcome


def maybe_auto_compact(
    messages: list[dict[str, Any]],
    budget: ContextBudget,
    **kwargs: Any,
) -> CompactOutcome | None:
    """Compact only when the budget ratio is above 85%."""
    ratio = budget.usage_ratio(messages)
    from .policy import should_auto_compact

    if not should_auto_compact(ratio):
        return None
    return run_compact(messages, trigger=CompactTrigger.AUTO, budget=budget, **kwargs)
