"""M4: per-run budget and cooperative cancel, without a second limiter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from LightAgent.runtime import BudgetExceeded, BudgetLimits, BudgetManager
from local.harness.run_control import (
    BUDGET_REACHED_NOTICE,
    USER_CANCEL_NOTICE,
    ControlledRun,
    default_budget_limits,
    execute_controlled,
    make_run_token,
)


def test_default_budget_is_8_calls_and_120_seconds(monkeypatch):
    monkeypatch.delenv("LIGHTAGENT_RUN_MODEL_CALLS", raising=False)
    monkeypatch.delenv("LIGHTAGENT_RUN_SECONDS", raising=False)
    limits = default_budget_limits()
    assert limits.model_calls == 8
    assert limits.seconds == 120

    monkeypatch.setenv("LIGHTAGENT_RUN_MODEL_CALLS", "3")
    monkeypatch.setenv("LIGHTAGENT_RUN_SECONDS", "30")
    overridden = default_budget_limits()
    assert overridden.model_calls == 3
    assert overridden.seconds == 30

    monkeypatch.setenv("LIGHTAGENT_RUN_MODEL_CALLS", "nope")
    monkeypatch.setenv("LIGHTAGENT_RUN_SECONDS", "")
    fallback = default_budget_limits()
    assert fallback.model_calls == 8
    assert fallback.seconds == 120


def test_cancel_notice_states_the_cooperative_boundary():
    assert "已停止" in USER_CANCEL_NOTICE
    assert "协作边界" in USER_CANCEL_NOTICE
    assert "界面已显示内容为准" in USER_CANCEL_NOTICE
    assert "勿假定未执行" in USER_CANCEL_NOTICE
    assert "半执行" in USER_CANCEL_NOTICE
    assert "继续" in BUDGET_REACHED_NOTICE


def test_e5_tight_budget_becomes_a_visible_notice():
    manager = BudgetManager(BudgetLimits(model_calls=0))
    with pytest.raises(BudgetExceeded):
        manager.consume(model_calls=1)

    class TightAgent:
        def run(self, prompt, cancellation_token=None, **kwargs):
            del prompt, kwargs
            self.token = cancellation_token
            raise BudgetExceeded("model_calls", 0, 1)

    events = []
    agent = TightAgent()
    outcome = execute_controlled(agent, "今天吃什么", on_event=lambda name, payload: events.append((name, payload)))
    assert isinstance(outcome, ControlledRun)
    assert outcome.budget_reached is True
    assert outcome.cancelled is False
    assert outcome.content == BUDGET_REACHED_NOTICE
    assert events and events[0][0] == "budget_reached"
    assert outcome.token is agent.token


def test_e5_kernel_budget_string_is_translated(monkeypatch):
    from LightAgent import LightAgent

    agent = LightAgent(
        name="life",
        model="gpt-4o-mini",
        api_key="test-key",
        base_url="http://127.0.0.1:9/v1",
        auto_discover_skills=False,
        log_level="ERROR",
        budget_limits=BudgetLimits(model_calls=0),
        tree_of_thought=False,
    )
    called = {"n": 0}

    class Boom:
        def create(self, **params):
            called["n"] += 1
            raise AssertionError("budget gate should stop before the model client")

    agent.client = SimpleNamespace(chat=SimpleNamespace(completions=Boom()))
    outcome = execute_controlled(agent, "今天吃什么", result_format="object")
    assert outcome.budget_reached is True
    assert outcome.content == BUDGET_REACHED_NOTICE
    assert "LA-BUDGET" not in outcome.content
    assert called["n"] == 0


def test_e3_cancel_passes_the_token_and_returns_the_notice():
    class StubAgent:
        def __init__(self):
            self.token = None

        def run(self, prompt, cancellation_token=None, **kwargs):
            del prompt, kwargs
            self.token = cancellation_token
            if cancellation_token is not None and cancellation_token.cancelled:
                return SimpleNamespace(content="[LA-CANCELLED] stop", error="[LA-CANCELLED] stop")
            return SimpleNamespace(content="不该执行到这里", error=None)

    token = make_run_token()
    assert token.cancel(reason="user_cancel") is True
    stub = StubAgent()
    events = []
    outcome = execute_controlled(
        stub,
        "继续",
        cancellation_token=token,
        on_event=lambda name, payload: events.append(name),
    )
    assert stub.token is token
    assert stub.token.reason == "user_cancel"
    assert outcome.cancelled is True
    assert outcome.content == USER_CANCEL_NOTICE
    assert "user_cancel" in events


def test_e3_kernel_cancel_does_not_call_the_model():
    from LightAgent import LightAgent

    agent = LightAgent(
        name="life",
        model="gpt-4o-mini",
        api_key="test-key",
        base_url="http://127.0.0.1:9/v1",
        auto_discover_skills=False,
        log_level="ERROR",
        budget_limits=default_budget_limits(),
        tree_of_thought=False,
    )

    class Boom:
        def create(self, **params):
            raise AssertionError("cancelled run must not call the model")

    agent.client = SimpleNamespace(chat=SimpleNamespace(completions=Boom()))
    token = make_run_token()
    token.cancel(reason="user_cancel")
    outcome = execute_controlled(agent, "今天吃什么", cancellation_token=token, result_format="object")
    assert outcome.cancelled is True
    assert outcome.content == USER_CANCEL_NOTICE


def test_unrelated_errors_still_propagate():
    class StubAgent:
        def run(self, prompt, cancellation_token=None, **kwargs):
            del prompt, cancellation_token, kwargs
            raise RuntimeError("disk full")

    with pytest.raises(RuntimeError, match="disk full"):
        execute_controlled(StubAgent(), "hi")


def test_make_agent_installs_default_budget_and_keeps_the_forbid_gate(monkeypatch):
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.name = "fake"

    monkeypatch.setattr("local.memory.inject.attach_profile_memory", lambda agent, **kwargs: None)
    import LightAgent as lightagent_pkg

    monkeypatch.setattr(lightagent_pkg, "LightAgent", FakeAgent)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.delenv("LIGHTAGENT_FORBID_OPENROUTER", raising=False)

    from local.openrouter_config import make_agent

    make_agent(model="google/gemma-4-31b-it:free")
    assert captured["budget_limits"].model_calls == 8
    assert captured["budget_limits"].seconds == 120
    assert captured["tree_of_thought"] is False

    custom = BudgetLimits(model_calls=1, seconds=5)
    captured.clear()
    make_agent(model="google/gemma-4-31b-it:free", budget_limits=custom)
    assert captured["budget_limits"] is custom

    monkeypatch.setenv("LIGHTAGENT_FORBID_OPENROUTER", "1")
    with pytest.raises(RuntimeError, match="FORBID_OPENROUTER"):
        make_agent(model="google/gemma-4-31b-it:free")


def test_backend_passes_the_token_and_strips_history(monkeypatch):
    seen = {}

    class Stub:
        def run(self, prompt, cancellation_token=None, **kwargs):
            seen["prompt"] = prompt
            seen["token"] = cancellation_token
            seen["history"] = kwargs.get("history")
            return SimpleNamespace(content="好的", error=None, tool_calls=[])

    def fake_make_agent(**kwargs):
        seen["make_kwargs"] = kwargs
        return Stub()

    monkeypatch.setattr("local.openrouter_config._check_and_count", lambda: None)
    monkeypatch.setattr("local.openrouter_config.make_agent", fake_make_agent)
    monkeypatch.setattr("local.openrouter_config.FREE_MODELS", ["stub:free"])
    monkeypatch.setattr("local.openrouter_config._assert_free", lambda model: None)

    from local.tui.backend import OpenRouterBackend

    backend = OpenRouterBackend()
    token = backend.begin_run()
    history = [{"role": "user", "content": "hi <memory-context>SECRET</memory-context> there"}]
    reply = backend.chat(history, "问 <memory-context>PACK</memory-context> 题")
    assert seen["token"] is token
    assert "<memory-context>" not in str(seen["history"])
    assert "SECRET" not in str(seen["history"])
    assert "there" in str(seen["history"])
    assert "<memory-context>" not in seen["prompt"]
    assert "题" in seen["prompt"]
    assert reply.content == "好的"


def test_backend_pre_cancel_skips_the_model_and_shows_the_notice(monkeypatch):
    called = {"n": 0}

    def fake_make_agent(**kwargs):
        called["n"] += 1
        raise AssertionError("cancelled turn must not build an agent")

    monkeypatch.setattr("local.openrouter_config.make_agent", fake_make_agent)
    monkeypatch.setattr("local.openrouter_config._check_and_count", lambda: (_ for _ in ()).throw(AssertionError("quota")))

    from local.tui.backend import OpenRouterBackend

    backend = OpenRouterBackend()
    backend.begin_run()
    assert backend.cancel_active(reason="user_cancel") is True
    reply = backend.chat([], "今天吃什么")
    assert reply.content == USER_CANCEL_NOTICE
    assert called["n"] == 0


def test_mock_backend_honors_cancel():
    from local.tui.backend import MockBackend

    backend = MockBackend(delay=0)
    backend.begin_run()
    backend.cancel_active(reason="user_cancel")
    reply = backend.chat([], "今天天气呢")
    assert reply.content == USER_CANCEL_NOTICE
