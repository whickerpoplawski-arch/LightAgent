"""Ephemeral memory-pack injection.

The pack is appended to the system/instruction lane for the current model
request. It is never concatenated onto the user question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .host import MemoryHost, current_host
from .pack import PackCache, build_for_turn
from .persona import persona_system_block
from .store import ProfileStore, get_store
from .types import MemoryPack

_EPHEMERAL_RE = re.compile(r"<memory-context>.*?</memory-context>\s*", re.DOTALL)


@dataclass(frozen=True)
class PreparedTurn:
    messages: list[dict]
    user_text: str
    ephemeral: str
    pack: MemoryPack
    detail: str


def render_ephemeral(pack: MemoryPack) -> str:
    return pack.injection()


def strip_ephemeral(messages: list[dict]) -> list[dict]:
    """Drop memory-context blocks from a transcript copy."""
    cleaned: list[dict] = []
    for message in messages:
        item = dict(message)
        content = item.get("content")
        if isinstance(content, str) and "<memory-context>" in content:
            item["content"] = _EPHEMERAL_RE.sub("", content).strip()
        cleaned.append(item)
    return cleaned


def user_text_contains_pack(messages: list[dict]) -> bool:
    for message in messages:
        if message.get("role") == "user" and "<memory-context>" in str(message.get("content") or ""):
            return True
    return False


def turn_index(committed_turns: int) -> tuple[int, int]:
    """Stable indexes: user = 2n, reply = 2n+1, relative to committed turns."""
    count = int(committed_turns)
    if count < 0:
        raise ValueError("committed_turns must be >= 0")
    return 2 * count, 2 * count + 1


def _window_texts(history: list[dict], user_text: str) -> list[str]:
    texts = [user_text]
    for message in history:
        if message.get("role") == "system":
            continue
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
    return texts


def compose_system(system: str, persona: str, identity_block: str, ephemeral: str) -> str:
    """Order: base system, persona, identity, memory pack. All ephemeral."""
    parts = [part.strip() for part in (system, persona, identity_block, ephemeral) if part and part.strip()]
    return "\n\n".join(parts)


def prepare_turn(
    *,
    system: str,
    history: list[dict] | None,
    user_text: str,
    host: MemoryHost | None = None,
    store: ProfileStore | None = None,
    budget_tokens: int | None = None,
    cache: PackCache | None = None,
    persona_text: str | None = None,
    identity_block: str | None = None,
    share_user_profile: bool = True,
) -> PreparedTurn:
    """Build the model request. ``user_text`` is appended unchanged.

    ``persona_text=None`` loads the global persona files. A string replaces
    them (override). ``identity_block`` is the per-bot role and is never
    written to the profile store. ``share_user_profile=False`` skips the pack.
    """
    host = host or current_host()
    store = store or get_store()
    history = list(history or [])
    if share_user_profile:
        kwargs = {}
        if budget_tokens is not None:
            kwargs["budget_tokens"] = budget_tokens
        pack = build_for_turn(
            store,
            host,
            query=user_text,
            window_texts=_window_texts(history, user_text),
            cache=cache,
            **kwargs,
        )
        ephemeral = render_ephemeral(pack)
    else:
        pack = MemoryPack(markdown="", tokens=0)
        ephemeral = ""
    if share_user_profile:
        try:
            from local.constraints.card import merge_constraint_block

            ephemeral = merge_constraint_block(ephemeral)
        except Exception:
            pass
        try:
            from local.goals.inject import merge_goal_line

            ephemeral = merge_goal_line(ephemeral, space_id=getattr(host, "space_id", None))
        except Exception:
            pass
    if persona_text is None:
        persona = persona_system_block()
    else:
        persona = persona_system_block(persona_text) if str(persona_text).strip() else ""
    system_content = compose_system(system or "", persona, identity_block or "", ephemeral)

    messages: list[dict] = [{"role": "system", "content": system_content}]
    for message in history:
        if message.get("role") == "system":
            continue
        messages.append({
            "role": message.get("role", "user"),
            "content": message.get("content", ""),
        })
    messages.append({"role": "user", "content": user_text})

    if pack.unavailable:
        detail = pack.notice or "memory unavailable"
    elif ephemeral:
        detail = "memory pack 注入 system/instruction，未写入 user 消息。"
    else:
        detail = "本轮没有可注入的画像。"
    if (identity_block or "").strip():
        detail = f"{detail} 身份块已注入 system，未写入用户画像。"
    return PreparedTurn(
        messages=messages,
        user_text=user_text,
        ephemeral=ephemeral,
        pack=pack,
        detail=detail,
    )


def attach_profile_memory(
    agent,
    *,
    user_id: str | None = None,
    namespace: str = "profile",
    session_id: str | None = None,
    agent_id: str | None = None,
    space_id: str | None = None,
    store: ProfileStore | None = None,
    persona_text: str | None = None,
    identity_block: str | None = None,
    share_user_profile: bool = True,
    context_getter=None,
):
    """Install a provider the LightAgent runtime calls before each model request.

    The provider closes over the host. A ``user_id`` argument from the run
    cannot retarget the profile.
    """
    from .host import DEFAULT_USER_ID, bind_host

    host = MemoryHost(
        user_id=user_id or DEFAULT_USER_ID,
        namespace=namespace,
        session_id=session_id,
        agent_id=agent_id or getattr(agent, "name", None),
        space_id=space_id,
    )
    bind_host(host)
    profile_store = store or get_store()
    cache = PackCache()

    def provider(*, query: str, user_id: str, history: list) -> str:
        del user_id  # host stamp wins over the run/model user id
        extra = context_getter() if context_getter else {}
        prepared = prepare_turn(
            system="",
            history=history,
            user_text=query,
            host=host,
            store=profile_store,
            cache=cache,
            persona_text=extra.get("persona_text", persona_text),
            identity_block=extra.get("identity_block", identity_block),
            share_user_profile=extra.get("share_user_profile", share_user_profile),
        )
        # System lane only. prepare_turn already kept the user sentence intact.
        return prepared.messages[0]["content"] if prepared.messages else ""

    agent.ephemeral_context_provider = provider
    agent._profile_memory_host = host
    return host