"""Write-path scrub for secrets and obvious PII.

Secrets reject the whole write. Contact-style PII is redacted. Sensitive life
facts stay allowed but are marked ``needs_confirm`` so they are not injected
until a person confirms them.
"""

from __future__ import annotations

import re

from .types import ScrubResult

# Obvious credentials and payment numbers. A hit rejects the write.
_SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private-key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "aws-key"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "github-token"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", "slack-token"),
    (r"(?i)\bsk-[A-Za-z0-9_\-]{12,}\b", "api-key"),
    (r"(?i)\b(api[_-]?key|secret|access[_-]?token|password|passwd|pwd)\b\s*[:=]\s*\S+", "credential-assignment"),
    (r"\b(?:\d{4}[ -]){3}\d{4}\b", "card-number"),
)

_PII_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "email"),
    (r"\b1[3-9]\d{9}\b", "phone"),
    (r"\b\d{17}[\dXx]\b", "cn-id"),
)

# Health / money facts can be stored only as non-injectable candidates.
_SENSITIVE = re.compile(
    r"过敏|病史|诊断|处方|抑郁|银行卡|信用卡|工资|月薪|病历|allergy|diagnos|prescription|salary",
    re.IGNORECASE,
)

_REDACTION_TOKEN = re.compile(r"\[redacted-[a-z\-]+\]")


def scrub_text(text: str) -> ScrubResult:
    raw = (text or "").strip()
    if not raw:
        return ScrubResult(allowed=False, text="", reason="empty")

    for pattern, label in _SECRET_PATTERNS:
        if re.search(pattern, raw):
            return ScrubResult(
                allowed=False,
                text="",
                reason=f"rejected secret: {label}",
                redactions=(label,),
            )

    cleaned = raw
    redactions: list[str] = []
    for pattern, label in _PII_PATTERNS:
        if re.search(pattern, cleaned):
            cleaned = re.sub(pattern, f"[redacted-{label}]", cleaned)
            redactions.append(label)

    residue = _REDACTION_TOKEN.sub("", cleaned).strip(" ，,;；")
    if not residue:
        return ScrubResult(
            allowed=False,
            text="",
            reason="rejected: only PII",
            redactions=tuple(redactions),
        )

    needs_confirm = _SENSITIVE.search(cleaned) is not None
    return ScrubResult(
        allowed=True,
        text=cleaned.strip(),
        redactions=tuple(redactions),
        needs_confirm=needs_confirm,
    )