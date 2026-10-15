"""Explicit routine phrases. Questions and plain chat do not create one."""

from __future__ import annotations

_TIMEZONE = "America/Martinique"
_VERBS = ("到点告诉我", "提醒我", "叫我", "喊我")


def _has_trigger(body: str, cleaned: str) -> bool:
    if cleaned.startswith("/routine"):
        return True
    if any(verb in body for verb in _VERBS):
        return True
    return "提醒" in body


def parse_routine(text: str) -> dict | None:
    """Return a create payload, or None when the sentence is not an explicit routine."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return None
    if any(mark in cleaned for mark in ("什么", "吗", "？", "?")):
        return None
    body = cleaned[9:].strip() if cleaned.startswith("/routine") else cleaned
    triggered = _has_trigger(body, cleaned)
    if "每周" in body:
        cadence = "weekly"
    elif "每天" in body or "每日" in body:
        cadence = "daily_window"
    elif "一次" in body and triggered:
        cadence = "once"
    else:
        return None
    if not triggered:
        return None
    title = body
    for verb in _VERBS:
        if verb in body:
            title = body.split(verb, 1)[1].strip() or body
            break
    title = title[:24]
    return {
        "title": title,
        "instruction": body,
        "cadence": cadence,
        "timezone": _TIMEZONE,
    }


_CONFIRM = ("确认提醒", "跑一下提醒")


def routine_action(text: str) -> tuple[str, str] | None:
    """Confirm, pause, or delete. The second value is the title fragment."""
    cleaned = " ".join((text or "").split())
    if cleaned in _CONFIRM:
        return ("confirm", "")
    for verb, prefix in (("pause", "暂停提醒"), ("delete", "删除提醒"), ("delete", "删掉提醒")):
        if cleaned == prefix or cleaned.startswith(prefix):
            return (verb, cleaned[len(prefix):].strip(" ：:"))
    return None
