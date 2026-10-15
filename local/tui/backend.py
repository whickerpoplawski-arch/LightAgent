"""TUI 后端：真实后端（默认 MX / 可选 OpenRouter，经 openrouter_config 限额保护）和 mock 后端。

二开时只需实现同样的 `chat(history, prompt) -> Reply` 接口即可替换。
Reply.steps 供轨迹页可视化；tokens_* / duration_ms / cache_hit_pct 供底部统计条。
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field

from local import openrouter_config as orc
from local.tui.tools import TOOLS
from local.tui.trace import TraceStep


def _merged_tools():
    """Built-in TUI tools + enabled plugin tools (hot-read enabled.json)."""
    from local.tui.tools import TOOLS

    tools = list(TOOLS)
    try:
        from local.plugins_system import load_enabled_plugins

        loaded = load_enabled_plugins()
        tools.extend(loaded.tools)
    except Exception:
        pass
    return tools


@dataclass
class Reply:
    model: str
    content: str
    tool_calls: list[str] = field(default_factory=list)  # 形如 "get_weather(上海)"，对话页胶囊用
    steps: list[TraceStep] = field(default_factory=list)  # 完整轨迹步骤
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    cache_hit_pct: float = 0.0


@dataclass
class TurnContext:
    """Per-turn identity and collaboration. The user sentence stays in ``prompt``."""

    identity_block: str = ""
    persona_text: str | None = None
    share_user_profile: bool = True
    session_id: str | None = None
    agent_id: str | None = None
    space_id: str | None = None
    collaboration_enabled: bool = True
    roster: list = field(default_factory=list)
    quota: object | None = None


def _fmt_call(call: dict) -> str:
    args = call.get("arguments") or ""
    try:
        args = ", ".join(str(v) for v in json.loads(args).values())
    except Exception:
        pass
    return f"{call.get('name')}({args})"


class RunControlMixin:
    """Holds the in-flight CancellationToken so the TUI can stop a turn."""

    def begin_run(self):
        from local.harness.run_control import make_run_token

        self._active_token = make_run_token()
        return self._active_token

    def cancel_active(self, reason: str = "user_cancel") -> bool:
        from local.harness.run_control import make_run_token

        token = getattr(self, "_active_token", None)
        if token is None:
            token = make_run_token()
            self._active_token = token
        return token.cancel(reason=reason)

    def active_token(self):
        return getattr(self, "_active_token", None)


def _cancelled_reply(model: str) -> Reply:
    from local.harness.run_control import USER_CANCEL_NOTICE

    return Reply(model=model, content=USER_CANCEL_NOTICE)


def _note_stop(turn: TurnContext | None, event: str) -> None:
    from local.harness.run_control import BUDGET_REACHED_NOTICE, USER_CANCEL_NOTICE
    from local.checkpoints.store import record_run_event

    detail = USER_CANCEL_NOTICE if event == "user_cancel" else BUDGET_REACHED_NOTICE
    space = None if turn is None else (turn.space_id or turn.session_id)
    try:
        record_run_event(space, event, detail=detail)
    except Exception:
        return


class MockBackend(RunControlMixin):
    """不发任何网络请求：回显 + 多步假轨迹（模型→工具→工具→模型）。"""

    name = "mock-echo:free"

    def __init__(self, *, delay: float = 0.55) -> None:
        self._mock_used = 0  # 仅展示用，不碰 OpenRouter 计数
        self._delay = delay
        self.plugin_tool_names: list[str] = []
        self.reload_plugins()

    def reload_plugins(self) -> None:
        """热读 enabled 插件工具名（mock 不真正调工具，只记清单）。"""
        names: list[str] = []
        try:
            from local.plugins_system import load_enabled_plugins

            for t in load_enabled_plugins().tools:
                names.append(
                    t.tool_info.get("tool_name")
                    if getattr(t, "tool_info", None)
                    else getattr(t, "__name__", "?")
                )
        except Exception:
            pass
        self.plugin_tool_names = names

    def usage(self) -> int:
        return self._mock_used

    def chat(self, history: list[dict], prompt: str, turn: TurnContext | None = None) -> Reply:
        if self.active_token() is not None and self.active_token().cancelled:
            _note_stop(turn or TurnContext(), "user_cancel")
            return _cancelled_reply(self.name)
        # 模拟“流式思考”耗时，方便 UI 刷 tok/s
        if self._delay:
            time.sleep(self._delay)
        if self.active_token() is not None and self.active_token().cancelled:
            _note_stop(turn or TurnContext(), "user_cancel")
            return _cancelled_reply(self.name)
        self._mock_used += 1
        t0 = 420 + random.randint(0, 180)
        steps: list[TraceStep] = []
        calls: list[str] = []
        turn = turn or TurnContext()

        # 上下文快照。mock 不发请求，但按正式路径组装 ephemeral pack，且不改用户原话。
        from local.memory.host import MemoryHost
        from local.memory.inject import prepare_turn

        prepared = prepare_turn(
            system="LightAgent 中文助手",
            history=history,
            user_text=prompt,
            host=MemoryHost(
                user_id="local-user",
                session_id=turn.session_id,
                agent_id=turn.agent_id,
                space_id=turn.space_id,
            ),
            persona_text=turn.persona_text,
            identity_block=turn.identity_block,
            share_user_profile=turn.share_user_profile,
        )
        if prepared.user_text != prompt:
            raise RuntimeError("identity injection changed the user message")
        delegate_steps, delegate_content = maybe_delegate(prompt, turn, prepared.ephemeral)
        steps.append(
            TraceStep(
                kind="context",
                summary=f"会话上下文 · 历史 {len(history)} 条 · ephemeral pack",
                detail=prepared.detail,
                tokens=80 + len(history) * 12,
                duration_ms=8,
                lane="other",
            )
        )
        if delegate_content is not None:
            steps.extend(delegate_steps)
            steps.append(
                TraceStep(
                    kind="assistant",
                    summary=delegate_content.replace("\n", " ")[:48],
                    detail=delegate_content,
                    tokens=48,
                    duration_ms=40,
                    lane="model",
                )
            )
            return Reply(
                model=self.name,
                content=delegate_content,
                tool_calls=["delegate_to_bot"] if any(step.kind == "delegate" for step in delegate_steps) else [],
                steps=steps,
                tokens_in=80,
                tokens_out=48,
                duration_ms=max(t0, 200),
                cache_hit_pct=0.0,
            )

        if "天气" in prompt:
            # 模型思考
            steps.append(
                TraceStep(
                    kind="model",
                    summary="规划：调用天气工具",
                    detail="decide tool=get_weather",
                    tokens=96,
                    duration_ms=140,
                    lane="model",
                )
            )
            # 工具 1
            calls.append("get_weather(上海)")
            steps.append(
                TraceStep(
                    kind="tool",
                    summary="get_weather",
                    detail="city_name=上海",
                    tool_name="get_weather",
                    tool_args='{"city_name": "上海"}',
                    tool_result="Query result: 上海 is sunny, 22°C.",
                    tokens=24,
                    duration_ms=55,
                    lane="tool",
                )
            )
            # 工具 2（伪造二次查询，让轨迹更丰富）
            calls.append("web_search(上海 今日天气)")
            steps.append(
                TraceStep(
                    kind="tool",
                    summary="web_search",
                    detail="query=上海 今日天气",
                    tool_name="web_search",
                    tool_args='{"query": "上海 今日天气"}',
                    tool_result="命中 3 条：晴，22°C，微风",
                    tokens=32,
                    duration_ms=90,
                    lane="tool",
                )
            )
            # 模型汇总
            content = (
                "上海今天 **晴**，气温约 **22°C**。\n\n"
                "适合出门散步 🌤"
            )
            steps.append(
                TraceStep(
                    kind="assistant",
                    summary=content.replace("\n", " ")[:48],
                    detail=content,
                    tokens=64,
                    duration_ms=120,
                    lane="model",
                )
            )
            tokens_in, tokens_out = 210, 96
            cache = 72.0
        elif "报错" in prompt or "错误" in prompt:
            steps.append(
                TraceStep(
                    kind="model",
                    summary="尝试调用 web_fetch",
                    tokens=48,
                    duration_ms=80,
                    lane="model",
                )
            )
            calls.append("web_fetch(https://example.invalid)")
            steps.append(
                TraceStep(
                    kind="tool",
                    summary="web_fetch",
                    detail="url=https://example.invalid",
                    tool_name="web_fetch",
                    tool_args='{"url": "https://example.invalid"}',
                    tool_result="DNS_OR_HTTP_ERROR: example.invalid",
                    status="error",
                    tokens=12,
                    duration_ms=40,
                    lane="tool",
                )
            )
            content = "工具调用失败：无法解析 `example.invalid`。请换真实 URL，或改用 `web_search`。"
            steps.append(
                TraceStep(
                    kind="assistant",
                    summary=content[:48],
                    detail=content,
                    tokens=40,
                    duration_ms=70,
                    lane="model",
                )
            )
            tokens_in, tokens_out = 160, 52
            cache = 41.0
        else:
            steps.append(
                TraceStep(
                    kind="model",
                    summary="直接回答（无工具）",
                    tokens=64,
                    duration_ms=110,
                    lane="model",
                )
            )
            content = (
                f"（mock）你说的是：`{prompt}`\n\n"
                f"当前会话已有 **{len(history)}** 条历史消息。"
            )
            steps.append(
                TraceStep(
                    kind="assistant",
                    summary=content.replace("\n", " ")[:48],
                    detail=content,
                    tokens=48,
                    duration_ms=95,
                    lane="model",
                )
            )
            tokens_in, tokens_out = 120 + len(prompt), 48
            cache = 55.0 + random.random() * 20

        step_ms = t0 + sum(s.duration_ms for s in steps)
        # 让 tok/s 落在参考 UI 附近（约 40–70），避免 step 毫秒过短导致数百 tok/s
        turn_tok = tokens_in + tokens_out
        dur = max(step_ms, int(turn_tok / 55 * 1000))
        return Reply(
            model=self.name,
            content=content,
            tool_calls=calls,
            steps=steps,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=dur,
            cache_hit_pct=round(cache, 1),
        )

def maybe_delegate(prompt: str, turn: TurnContext, ephemeral: str, *, mode: str = "mock"):
    """Resolve ``@角色``. Disabled collaboration leaves the sentence as text."""
    from local.conversations.collaborate import DelegateError, plan_mention, run_delegation

    plan = plan_mention(prompt, list(turn.roster or []), enabled=turn.collaboration_enabled)
    if plan.notice and not plan.should_call:
        return [
            TraceStep(
                kind="context",
                summary=plan.notice,
                detail=prompt,
                lane="other",
            )
        ], f"（mock）你说的是：`{prompt}`\n\n{plan.notice}"
    if not plan.should_call or plan.target is None:
        return [], None
    parent_messages: list[dict] = []
    try:
        outcome = run_delegation(
            roster=list(turn.roster),
            bot_id=plan.target.id,
            task=plan.task,
            context_summary="",
            quota=turn.quota,
            profile_block=ephemeral if turn.share_user_profile else "",
            parent_messages=parent_messages,
            mode=mode,
        )
    except DelegateError as exc:
        return [
            TraceStep(
                kind="error",
                summary=str(exc)[:80],
                detail=str(exc),
                status="error",
                lane="other",
            )
        ], f"派发失败：{exc}"
    for message in parent_messages:
        blob = str(message.get("content") or "")
        if "<memory-context>" in blob or "<identity>" in blob:
            raise RuntimeError("delegate wrote pack or identity into the parent transcript")
    step = TraceStep(
        kind="delegate",
        summary=f"派发 · {plan.target.identity.role_title or plan.target.title}",
        detail=outcome.result,
        tool_name="delegate_to_bot",
        tool_args=plan.task,
        tool_result=outcome.parent_tool_result,
        lane="other",
    )
    return [step], f"（mock）{outcome.result}"


class OpenRouterBackend(RunControlMixin):
    """真实模型后端（默认 MX；也可 LIGHTAGENT_PROVIDER=openrouter）。每次调用前经 openrouter_config 本地计数。"""

    def __init__(self, instructions: str = "你是 LightAgent，一个乐于助人的中文 AI 助手。"):
        self.instructions = instructions
        self.name = orc.DEFAULT_MODEL
        self._tools = _merged_tools()

    def reload_plugins(self) -> None:
        self._tools = _merged_tools()

    def usage(self) -> int:
        return orc.usage_today()

    def chat(self, history: list[dict], prompt: str, turn: TurnContext | None = None) -> Reply:
        import os

        from local.harness.ephemeral import prepare_model_inputs
        from local.harness.run_control import BUDGET_REACHED_NOTICE, execute_controlled

        turn = turn or TurnContext()
        if self.active_token() is not None and self.active_token().cancelled:
            _note_stop(turn, "user_cancel")
            return _cancelled_reply(self.name)
        child_mode = "live" if os.environ.get("LIGHTAGENT_ALLOW_OPENROUTER") == "1" else "mock"
        delegate_steps, delegate_content = maybe_delegate(prompt, turn, "", mode=child_mode)
        if delegate_content and delegate_content.startswith("派发失败"):
            return Reply(
                model=self.name,
                content=delegate_content,
                steps=delegate_steps,
            )
        run_history = list(history)
        if delegate_content:
            run_history.append({"role": "assistant", "content": delegate_content})
        run_history, prompt = prepare_model_inputs(run_history, prompt)
        token = self.active_token() or self.begin_run()
        if token.cancelled:
            _note_stop(turn, "user_cancel")
            return _cancelled_reply(self.name)
        last = None
        t_start = time.time()
        for model in orc.FREE_MODELS:
            orc._assert_free(model)
            orc._check_and_count()  # 超过本地上限会直接抛错，不发请求
            try:
                self._tools = _merged_tools()  # 每次对话热加载插件工具
                # Drop the delegate tool when this call is itself a child (depth >= 1).
                from local.conversations.collaborate import child_delegate_tools_allowed, get_runtime

                tools = self._tools
                if not child_delegate_tools_allowed(get_runtime().depth):
                    tools = [tool for tool in tools if getattr(tool, "__name__", "") != "delegate_to_bot"]
                agent = orc.make_agent(
                    model=model,
                    instructions=self.instructions,
                    tree_of_thought=False,
                    persona_text=turn.persona_text,
                    identity_block=turn.identity_block,
                    share_user_profile=turn.share_user_profile,
                    session_id=turn.session_id,
                    agent_id=turn.agent_id,
                    space_id=turn.space_id,
                )
                def _on_run_event(name, payload):
                    del payload
                    _note_stop(turn, name)

                outcome = execute_controlled(
                    agent,
                    prompt,
                    cancellation_token=token,
                    tools=tools,
                    history=run_history,
                    result_format="object",
                    user_id="local-user",
                    on_event=_on_run_event,
                )
                if outcome.cancelled:
                    return _cancelled_reply(model)
                if outcome.budget_reached:
                    return Reply(model=model, content=BUDGET_REACHED_NOTICE)
                res = outcome.raw
                text = (getattr(res, "content", None) or getattr(res, "error", None) or outcome.content or "")
                calls_raw = list(res.tool_calls or [])
                if calls_raw:
                    # 工具轮会多一次模型请求，把它也记进本地额度
                    orc._check_and_count()
                if any(h in text.lower() for h in orc._FALLBACK_HINTS) and len(text) < 400:
                    last = text
                    continue
                self.name = model
                steps: list[TraceStep] = [
                    TraceStep(
                        kind="context",
                        summary=f"会话上下文 · 历史 {len(history)} 条",
                        tokens=0,
                        lane="other",
                    ),
                    *delegate_steps,
                ]
                if calls_raw:
                    steps.append(
                        TraceStep(
                            kind="model",
                            summary="规划工具调用",
                            tokens=0,
                            lane="model",
                        )
                    )
                    for c in calls_raw:
                        steps.append(
                            TraceStep(
                                kind="tool",
                                summary=c.get("name") or "tool",
                                detail=_fmt_call(c),
                                tool_name=c.get("name") or "",
                                tool_args=str(c.get("arguments") or ""),
                                tool_result="(已执行)",
                                lane="tool",
                            )
                        )
                steps.append(
                    TraceStep(
                        kind="assistant",
                        summary=(text or "")[:48].replace("\n", " "),
                        detail=text,
                        lane="model",
                    )
                )
                # OpenRouter 免费层通常不回传准确 usage；用启发式估算
                tin = 80 + sum(len(str(m.get("content", ""))) for m in history) // 3 + len(prompt) // 3
                tout = max(16, len(text) // 3)
                dur = int((time.time() - t_start) * 1000)
                return Reply(
                    model=model,
                    content=text,
                    tool_calls=[_fmt_call(c) for c in calls_raw],
                    steps=steps,
                    tokens_in=tin,
                    tokens_out=tout,
                    duration_ms=dur,
                    cache_hit_pct=0.0,  # 真实模式未知
                )
            except Exception as e:  # 限额/下线 -> 换下一个免费模型
                last = e
                if any(h in str(e).lower() for h in orc._FALLBACK_HINTS):
                    continue
                raise
        raise RuntimeError(f"所有免费模型都不可用：{last}")
