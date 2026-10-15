import local.openrouter_config as orc
from local.conversations.collaborate import (
    DelegateError,
    DelegateQuota,
    child_delegate_tools_allowed,
    delegate_to_bot,
    get_runtime,
    plan_mention,
    register_bots,
    run_delegation,
)
from local.conversations.models import BotIdentity, ConversationMeta
from local.tui.tools import TOOLS


def _roster() -> list[ConversationMeta]:
    return [
        ConversationMeta(
            id="main",
            title="主对话",
            identity=BotIdentity(role_title="个人生活助手", job_description="接住用户的话。"),
            agent_id="bot-main",
        ),
        ConversationMeta(
            id="sec",
            title="日程",
            identity=BotIdentity(role_title="日程秘书", job_description="只看下周冲突。"),
            agent_id="bot-sec",
        ),
    ]


def test_e15_delegate_writes_a_step_without_leaking_the_pack():
    roster = _roster()
    parent_messages = [{"role": "user", "content": "@日程秘书 帮我看下周是否冲突"}]
    pack = "<memory-context>\n以后简称我小Q\n</memory-context>"
    outcome = run_delegation(
        roster=roster,
        bot_id="日程秘书",
        task="帮我看下周是否冲突",
        context_summary="用户下周有两场会",
        profile_block=pack,
        parent_messages=parent_messages,
        mode="mock",
    )
    assert outcome.step["kind"] == "delegate"
    assert outcome.ok
    assert "日程秘书" in outcome.result
    assert parent_messages[-1]["role"] == "tool"
    assert parent_messages[-1]["content"] == outcome.parent_tool_result
    blob = "\n".join(str(item.get("content") or "") for item in parent_messages)
    assert "<memory-context>" not in blob
    assert "小Q" not in blob
    assert "<identity" not in blob
    assert "小Q" in outcome.child_system
    assert "<identity" in outcome.child_system
    swarm_agents = register_bots(roster)
    for agent in swarm_agents.agents.values():
        assert agent.tree_of_thought is False
        assert "delegate_to_bot" not in agent.loaded_tools


def test_e16_missing_bot_is_an_error():
    try:
        run_delegation(roster=_roster(), bot_id="不存在的顾问", task="看看", mode="mock")
    except DelegateError as exc:
        assert "找不到" in str(exc)
    else:
        raise AssertionError("missing bot should fail")
    runtime = get_runtime()
    runtime.enabled = True
    runtime.roster = _roster()
    runtime.mode = "mock"
    runtime.depth = 0
    text = delegate_to_bot("不存在的顾问", "看看")
    assert "找不到" in text


def test_e17_disabled_mention_stays_plain_text():
    calls = {"n": 0}

    def runner(*_args):
        calls["n"] += 1
        return "不应该被调用"

    plan = plan_mention("@日程秘书 帮我看下周是否冲突", _roster(), enabled=False)
    assert plan.should_call is False
    assert plan.notice
    assert calls["n"] == 0
    assert plan.raw.startswith("@日程秘书")
    runtime = get_runtime()
    runtime.enabled = False
    assert "协作未启用" in delegate_to_bot("日程秘书", "看看")
    assert calls["n"] == 0
    assert runner is not None


def test_e18_suite_does_not_call_openrouter():
    before = orc.NETWORK_CALLS
    run_delegation(
        roster=_roster(),
        bot_id="sec",
        task="只看冲突",
        mode="mock",
    )
    try:
        run_delegation(roster=_roster(), bot_id="sec", task="再派一次", mode="live")
    except DelegateError as exc:
        assert "OpenRouter" in str(exc) or "在线" in str(exc) or "禁止" in str(exc)
    assert orc.NETWORK_CALLS == before
    names = [tool.tool_info["tool_name"] for tool in TOOLS]
    assert "delegate_to_bot" in names


def test_delegate_is_single_level_and_not_tot():
    assert child_delegate_tools_allowed(0) is True
    assert child_delegate_tools_allowed(1) is False
    try:
        run_delegation(roster=_roster(), bot_id="sec", task="再转交", depth=1, mode="mock")
    except DelegateError as exc:
        assert "一层" in str(exc)
    else:
        raise AssertionError("nested delegate should fail")
    quota = DelegateQuota(limit=1, used=1)
    try:
        run_delegation(roster=_roster(), bot_id="sec", task="超额", quota=quota, mode="mock")
    except DelegateError as exc:
        assert "额度" in str(exc)
    else:
        raise AssertionError("quota should fail")


def test_mention_resolves_role_title_when_enabled():
    plan = plan_mention("请 @日程秘书 帮我看下周是否冲突", _roster(), enabled=True)
    assert plan.should_call
    assert plan.target is not None
    assert plan.target.id == "sec"
    assert "冲突" in plan.task
    assert "@" not in plan.task
