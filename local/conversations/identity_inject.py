"""Build the ephemeral ``<identity>`` block. Never a profile learning."""

from __future__ import annotations

from xml.sax.saxutils import escape

from .models import BotIdentity, ConversationMeta


def _xml(text: str) -> str:
    return escape(text or "", {"'": "&apos;", '"': "&quot;"})


def identity_system_block(
    identity: BotIdentity | None,
    *,
    bot_id: str = "",
) -> str:
    """Render the per-bot role. Empty identity yields an empty string.

    The block is ephemeral: callers append it to the current system prompt
    and must not append it to the stored user message.
    """
    if identity is None or not identity.defined:
        return ""
    lines = [f'<identity bot_id="{_xml(bot_id)}">']
    if identity.display_name.strip():
        lines.append(f"称呼：{identity.display_name.strip()}")
    if identity.role_title.strip():
        lines.append(f"角色：{identity.role_title.strip()}")
    if identity.job_description.strip():
        lines.append(f"职责：{identity.job_description.strip()}")
    lines.append("</identity>")
    return "\n".join(lines)


def resolve_persona_text(identity: BotIdentity | None) -> str | None:
    """Persona argument for ``prepare_turn``.

    ``None`` means "load the global SOUL/IDENTITY files" (inherit).
    A string, including empty, means "use only this text" (override).
    """
    if identity is None or identity.persona_mode != "override":
        return None
    return identity.persona_text or ""


def blocks_for_meta(meta: ConversationMeta) -> tuple[str | None, str]:
    """``(persona_text, identity_block)`` for one conversation."""
    return (
        resolve_persona_text(meta.identity),
        identity_system_block(meta.identity, bot_id=meta.id),
    )
