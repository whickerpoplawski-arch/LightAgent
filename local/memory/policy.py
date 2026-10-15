"""Life-assistant MemoryPolicy preset.

Reuses LightAgent admission: pattern rejection, duplicate fingerprints,
write caps, and an explicit scrub admission. Internal reflection still
requires promotion and is not a profile write.
"""

from __future__ import annotations

from LightAgent import MemoryAdmissionDecision, MemoryPolicy

from .scrub import scrub_text

# Prompt-injection phrases. Ordinary preferences must not look like these.
_REJECT_PATTERNS = (
    r"(?i)ignore (all |any )?(previous|prior) (instructions|prompts)",
    r"(?i)disregard (all |any )?(previous|prior) (instructions|prompts)",
    r"忽略(之前|以上|前面)(的)?(所有)?(指令|提示|规则)",
)


def admit_profile_write(data: str, context: dict | None = None) -> MemoryAdmissionDecision:
    """Admission hook: scrub, then approve the redacted text or refuse."""
    del context  # scope is stamped by the host before this runs
    result = scrub_text(data)
    if not result.allowed:
        return MemoryAdmissionDecision(allowed=False, reason=result.reason)
    return MemoryAdmissionDecision(allowed=True, value=result.text)


def life_assistant_policy() -> MemoryPolicy:
    return MemoryPolicy(
        namespace="profile",
        allow_unattributed_results=False,
        allowed_sources=("user", "owner"),
        allowed_scopes=("user", "profile"),
        allowed_trust_levels=("owner", "verified"),
        max_writes_per_run=32,
        reject_duplicate_writes=True,
        min_write_length=2,
        reject_write_patterns=_REJECT_PATTERNS,
        require_write_admission=True,
        memory_write_admission=admit_profile_write,
        require_promotion_for_internal_memory=True,
    )