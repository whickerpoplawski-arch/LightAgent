"""Single-level delegate. Not a swarm debate and not tree-of-thought.

LightSwarm is used only as a registry of the visible bots. ``LightSwarm.run``
is not called: that path asks a model to detect "transfer to" and can chain
agents. The child reply is one mock (or explicitly allowed live) call, and the
child is not given ``delegate_to_bot``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .identity_inject import blocks_for_meta
from .models import ConversationMeta

_MENTION = re.compile(r"@([^\s@]{1,40})")
_PACK_MARKERS = ("<memory-context>", "<persona>", "<identity>")


class DelegateError(Exception):
    """Visible collaboration failure: missing bot, quota, or nested delegate."""


@dataclass
class MentionPlan:
    enabled: bool
    raw: str
    task: str
    target: ConversationMeta | None = None
    token: str = ""
    should_call: bool = False
    notice: str | None = None


@dataclass
class DelegateOutcome:
    ok: bool
    bot_id: str
    task: str
    context_summary: str
    result: str
    error: str | None = None
    step: dict = field(default_factory=dict)
    child_system: str = ""
    parent_tool_result: str = ""
    quota_used: int = 0

    @property
    def kind(self) -> str:
        return "delegate"


@dataclass
class DelegateQuota:
    limit: int = 45
    used: int = 0

    def charge(self) -> None:
        if self.used >= self.limit:
            raise DelegateError(f"今日协作额度已用完（{self.used}/{self.limit}）")
        self.used += 1


def collaboration_enabled_default() -> bool:
    return os.environ.get("LIGHTAGENT_COLLAB", "1") != "0"


def resolve_bot(roster: list[ConversationMeta], key: str) -> ConversationMeta | None:
    """Match id, agent_id, title, display name, or role title. Hidden bots stay reachable."""
    needle = (key or "").strip()
    if not needle:
        return None
    exact: list[tuple[int, ConversationMeta]] = []
    folded = needle.casefold()
    for meta in roster:
        names = [
            meta.id,
            meta.agent_id or "",
            meta.title,
            meta.identity.display_name,
            meta.identity.role_title,
        ]
        for rank, name in enumerate(names):
            if name and name.casefold() == folded:
                exact.append((rank, meta))
                break
    if not exact:
        return None
    exact.sort(key=lambda item: item[0])
    return exact[0][1]


def plan_mention(
    text: str,
    roster: list[ConversationMeta],
    *,
    enabled: bool,
) -> MentionPlan:
    """Parse a leading or inline ``@角色``. Disabled collaboration never calls."""
    match = _MENTION.search(text or "")
    if match is None:
        return MentionPlan(enabled=enabled, raw=text, task=text, should_call=False)
    token = match.group(1)
    target = resolve_bot(roster, token)
    task = (text[: match.start()] + text[match.end() :]).strip() or text
    if not enabled:
        notice = None
        if target is not None:
            notice = "协作未启用，这条 @ 当作普通文本，不会派发。"
        return MentionPlan(
            enabled=False,
            raw=text,
            task=text,
            target=target,
            token=token,
            should_call=False,
            notice=notice,
        )
    if target is None:
        return MentionPlan(
            enabled=True,
            raw=text,
            task=text,
            token=token,
            should_call=False,
        )
    return MentionPlan(
        enabled=True,
        raw=text,
        task=task,
        target=target,
        token=token,
        should_call=True,
    )


def mock_child_reply(meta: ConversationMeta, task: str, context_summary: str) -> str:
    role = meta.identity.role_title.strip() or meta.title
    extra = f"（背景：{context_summary}）" if context_summary else ""
    return f"{role}：已看过「{task}」{extra}".strip()


def _child_system(meta: ConversationMeta, *, profile_block: str) -> str:
    persona_text, identity_block = blocks_for_meta(meta)
    parts = [
        "你是被主对话请来的一次性助手。只回答交给你的任务。不要再派发给其他 Bot。",
    ]
    if meta.identity.persona_mode == "override":
        if persona_text:
            parts.append(f"<persona>\n{persona_text}\n</persona>")
    if identity_block:
        parts.append(identity_block)
    if meta.share_user_profile and profile_block:
        parts.append(profile_block)
    return "\n\n".join(parts)


def _assert_no_tot(agent) -> None:
    if getattr(agent, "tree_of_thought", False):
        raise DelegateError("子 Bot 禁止 Tree-of-Thought")


def register_bots(roster: list[ConversationMeta]):
    """Register non-hidden bots on a LightSwarm. Does not run them."""
    from LightAgent import LightAgent, LightSwarm

    swarm = LightSwarm()
    for meta in roster:
        if meta.hidden:
            continue
        persona_text, identity_block = blocks_for_meta(meta)
        instructions = identity_block or meta.title
        if meta.identity.persona_mode == "override" and persona_text:
            instructions = f"{persona_text}\n\n{instructions}".strip()
        agent = LightAgent(
            name=meta.agent_id or f"bot-{meta.id}",
            instructions=instructions or "你是一个助手。",
            role=meta.identity.role_title or meta.title,
            model="offline-mock",
            api_key="offline",
            base_url="http://127.0.0.1:9/v1",
            tree_of_thought=False,
            auto_discover_skills=False,
            log_level="ERROR",
        )
        _assert_no_tot(agent)
        swarm.register_agent(agent)
    return swarm
def child_delegate_tools_allowed(depth: int) -> bool:
    """Depth 0 is the parent. The child (depth >= 1) cannot delegate again."""
    return depth < 1


def run_delegation(
    *,
    roster: list[ConversationMeta],
    bot_id: str,
    task: str,
    context_summary: str = "",
    depth: int = 0,
    quota: DelegateQuota | None = None,
    profile_block: str = "",
    parent_messages: list[dict] | None = None,
    mode: str = "mock",
    runner=None,
) -> DelegateOutcome:
    """Run one child and return a tool result safe to store on the parent.

    ``profile_block`` may be used to build the child system prompt. It is not
    copied into ``parent_tool_result`` or ``parent_messages``.
    """
    quota = quota or DelegateQuota()
    parent_messages = parent_messages if parent_messages is not None else []
    if not child_delegate_tools_allowed(depth):
        raise DelegateError("协作只允许一层：子 Bot 不能再派发。")

    target = resolve_bot(roster, bot_id)
    if target is None:
        raise DelegateError(f"找不到 Bot「{bot_id}」。请确认它已存在且未删除。")

    quota.charge()
    try:
        swarm = register_bots(roster)
    except DelegateError:
        raise
    except Exception as exc:
        raise DelegateError(f"无法登记 Bot：{exc}") from exc
    child = swarm.agents.get(target.agent_id or "")
    if child is not None:
        if getattr(child, "tree_of_thought", False):
            raise DelegateError("子 Bot 禁止 Tree-of-Thought")
        loaded = getattr(child, "loaded_tools", {}) or {}
        if "delegate_to_bot" in loaded:
            raise DelegateError("子 Bot 不能携带 delegate_to_bot")
    child_system = _child_system(target, profile_block=profile_block if target.share_user_profile else "")
    for marker in _PACK_MARKERS:
        if marker in (task or "") or marker in (context_summary or ""):
            raise DelegateError("任务正文里不能夹带记忆包或身份块")

    if mode == "live":
        reply = _live_child_reply(target, task, context_summary, child_system)
    elif runner is not None:
        reply = str(runner(target, task, context_summary))
    else:
        reply = mock_child_reply(target, task, context_summary)

    for marker in _PACK_MARKERS:
        if marker in reply:
            reply = reply.replace(marker, "")
    result = reply.strip()
    step = {
        "kind": "delegate",
        "bot_id": target.id,
        "agent_id": target.agent_id,
        "task": task,
        "context_summary": context_summary,
        "result": result,
        "status": "ok",
    }
    tool_result = result
    parent_messages.append(
        {
            "role": "tool",
            "name": "delegate_to_bot",
            "content": tool_result,
        }
    )
    return DelegateOutcome(
        ok=True,
        bot_id=target.id,
        task=task,
        context_summary=context_summary,
        result=result,
        step=step,
        child_system=child_system,
        parent_tool_result=tool_result,
        quota_used=quota.used,
    )


def _live_child_reply(meta: ConversationMeta, task: str, context_summary: str, child_system: str) -> str:
    """One child completion. Tests leave this path closed."""
    del child_system
    if os.environ.get("LIGHTAGENT_FORBID_OPENROUTER") == "1":
        raise DelegateError("OpenRouter 已被测试哨兵禁止")
    if os.environ.get("LIGHTAGENT_ALLOW_OPENROUTER") != "1":
        raise DelegateError("在线派发已关闭。测试与默认路径只用 mock，不调用 OpenRouter。")
    from local import openrouter_config as orc
    from local.conversations.identity_inject import blocks_for_meta

    persona_text, identity_block = blocks_for_meta(meta)
    orc._check_and_count()
    agent = orc.make_agent(
        instructions="你是被请来处理一件事的助手。只回答这件事，不要再派发，不要展开思维树。",
        role=meta.identity.role_title or meta.title,
        tree_of_thought=False,
        persona_text=persona_text,
        identity_block=identity_block,
        share_user_profile=meta.share_user_profile,
        agent_id=meta.agent_id,
        space_id=meta.space_id,
    )
    if getattr(agent, "tree_of_thought", False):
        raise DelegateError("子 Bot 禁止 Tree-of-Thought")
    query = task if not context_summary else f"{task}\n\n背景：{context_summary}"
    runtime = get_runtime()
    previous = runtime.depth
    runtime.depth = previous + 1
    try:
        from local.harness.run_control import execute_controlled

        result = execute_controlled(
            agent,
            query,
            tools=[],
            history=[],
            user_id="local-user",
            result_format="object",
        )
    finally:
        runtime.depth = previous
    return str(result.content or "")


_RUNTIME = None


@dataclass
class CollaborationRuntime:
    enabled: bool = True
    mode: str = "mock"
    depth: int = 0
    quota: DelegateQuota = field(default_factory=DelegateQuota)
    roster: list[ConversationMeta] = field(default_factory=list)
    profile_block: str = ""
    network_calls: int = 0

    def snapshot_roster(self) -> list[ConversationMeta]:
        return list(self.roster)


def get_runtime() -> CollaborationRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = CollaborationRuntime(enabled=collaboration_enabled_default())
    return _RUNTIME


def bind_runtime(runtime: CollaborationRuntime) -> None:
    global _RUNTIME
    _RUNTIME = runtime


def delegate_to_bot(bot_id: str, task: str, context_summary: str = "") -> str:
    """Host tool. The child runtime is entered at depth 1 and has no this tool."""
    runtime = get_runtime()
    if not runtime.enabled:
        return "协作未启用。这条请求当作普通文本，没有派发。"
    if not child_delegate_tools_allowed(runtime.depth):
        return "协作只允许一层：子 Bot 不能再派发。"
    try:
        outcome = run_delegation(
            roster=runtime.snapshot_roster(),
            bot_id=bot_id,
            task=task,
            context_summary=context_summary,
            depth=runtime.depth,
            quota=runtime.quota,
            profile_block=runtime.profile_block,
            mode=runtime.mode,
        )
    except DelegateError as exc:
        return f"派发失败：{exc}"
    return outcome.parent_tool_result


delegate_to_bot.tool_info = {
    "tool_name": "delegate_to_bot",
    "tool_description": (
        "Ask one existing identity bot to handle a single task and return its reply. "
        "One level only. Do not use for tree-of-thought or group chat."
    ),
    "tool_params": [
        {"name": "bot_id", "description": "Bot id, title, or role title", "type": "string", "required": True},
        {"name": "task", "description": "The task to hand to that bot", "type": "string", "required": True},
        {
            "name": "context_summary",
            "description": "Short context. Do not paste the whole chat or the memory pack.",
            "type": "string",
            "required": False,
        },
    ],
}
