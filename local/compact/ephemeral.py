"""Strip and re-inject ephemeral identity / persona / memory packs.

The patterns match ``LightAgent.core._strip_ephemeral_memory``. Compact reads
a stripped copy; the authoritative blocks are attached again afterwards.
"""

from __future__ import annotations

import re
from typing import Any

_MEMORY_RE = re.compile(r"<memory-context>(.*?)</memory-context>", re.DOTALL)
_PERSONA_RE = re.compile(r"<persona>(.*?)</persona>", re.DOTALL)
_IDENTITY_RE = re.compile(r"<identity\b[^>]*>(.*?)</identity>", re.DOTALL)
_BLOCK_RES = (
    re.compile(r"<memory-context>.*?</memory-context>", re.DOTALL),
    re.compile(r"<persona>.*?</persona>", re.DOTALL),
    re.compile(r"<identity\b[^>]*>.*?</identity>", re.DOTALL),
)


def strip_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deep-enough copy with ephemeral bodies removed. Uses the kernel stripper."""
    from copy import deepcopy

    from LightAgent.core import _strip_ephemeral_memory

    return _strip_ephemeral_memory(deepcopy(messages))


def ephemeral_bodies(messages: list[dict[str, Any]]) -> list[str]:
    """Inner text of identity / persona / memory packs, for the quality gate."""
    bodies: list[str] = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        for pattern in (_MEMORY_RE, _PERSONA_RE, _IDENTITY_RE):
            for match in pattern.finditer(content):
                inner = match.group(1).strip()
                if inner:
                    bodies.append(inner)
    return bodies


def ephemeral_blocks(messages: list[dict[str, Any]]) -> list[str]:
    """Full tags, in order, so a later turn can attach the authoritative pack."""
    found: list[str] = []
    seen: set[str] = set()
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        for pattern in _BLOCK_RES:
            for match in pattern.finditer(content):
                block = match.group(0).strip()
                if block and block not in seen:
                    seen.add(block)
                    found.append(block)
    return found


def reinject_blocks(messages: list[dict[str, Any]], blocks: list[str]) -> list[dict[str, Any]]:
    """Append any missing authoritative blocks onto the head system message."""
    if not blocks:
        return messages
    updated: list[dict[str, Any]] = []
    injected = False
    for message in messages:
        item = dict(message) if isinstance(message, dict) else message
        if not injected and isinstance(item, dict) and item.get("role") == "system":
            content = item.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            missing = [block for block in blocks if block not in content]
            if missing:
                item["content"] = (content.rstrip() + "\n\n" + "\n\n".join(missing)).strip()
            injected = True
        updated.append(item)
    if not injected:
        updated.insert(0, {"role": "system", "content": "\n\n".join(blocks)})
    return updated
