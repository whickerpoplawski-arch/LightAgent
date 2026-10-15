"""Thresholds and template choice for life-assistant compaction."""

from __future__ import annotations

from .prompts import AUTO_SHORT, FULL_LIFE, ZERO_LLM_POLICY, build_summarizer_prompt
from .types import CompactTrigger

# User decision 2026-10-12. Auto and manual both call a summarizer.
AUTO_COMPACT_RATIO = 0.85
SOFT_FLUSH_RATIO = 0.75
KEEP_USER_TURNS = 6
MIN_KEEP_TOOL_STEPS = 1
MAX_INLINE_TOOL_CHARS = 12000
FOCUS_MAX_CHARS = 800


def should_auto_compact(usage_ratio: float, *, threshold: float = AUTO_COMPACT_RATIO) -> bool:
    """True when occupied tokens are strictly above the context window threshold."""
    return float(usage_ratio) > float(threshold)


def should_soft_flush(usage_ratio: float, *, threshold: float = SOFT_FLUSH_RATIO) -> bool:
    """True in the band where a rules flush is useful before a hard compact."""
    return float(usage_ratio) >= float(threshold)


def clamp_focus(focus: str | None) -> str | None:
    if focus is None:
        return None
    text = str(focus).strip()
    if not text:
        return None
    if len(text) > FOCUS_MAX_CHARS:
        text = text[:FOCUS_MAX_CHARS]
    return text


def select_template(trigger: CompactTrigger | str) -> str:
    """Return the summarizer template. Auto is the short one, never ZERO_LLM."""
    kind = CompactTrigger(trigger)
    if kind is CompactTrigger.AUTO:
        return AUTO_SHORT
    return FULL_LIFE


def summarizer_prompt(
    trigger: CompactTrigger | str,
    *,
    focus: str | None = None,
    space_id: str | None = None,
) -> str:
    kind = CompactTrigger(trigger)
    return build_summarizer_prompt(
        full=kind is CompactTrigger.MANUAL,
        focus=clamp_focus(focus) if kind is CompactTrigger.MANUAL else None,
        space_id=space_id,
    )


def fallback_policy_text() -> str:
    """Deterministic policy used only when the summarizer is discarded."""
    return ZERO_LLM_POLICY
