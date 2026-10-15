from types import SimpleNamespace

from LightAgent import LightAgent

from local.conversations.context_menu import Workspace, apply_action, create_conversation
from local.conversations.identity_inject import identity_system_block
from local.conversations.models import BotIdentity, ConversationMeta
from local.conversations.templates import apply_template, commit_identity, get_template
from local.memory.inject import attach_profile_memory, prepare_turn
from local.memory.persona import load_persona_text


def _meta(**kwargs) -> ConversationMeta:
    base = dict(id="bot1", title="主对话")
    base.update(kwargs)
    return ConversationMeta(**base)


def test_e1_custom_identity_saves_role_without_a_template():
    ws = Workspace()
    meta = create_conversation(ws, title="新会话")
    assert meta.identity.role_title == ""
    assert meta.identity.template_id is None
    identity, share = commit_identity(
        role_title="家庭账本官",
        job_description="只记这个家里的猫粮和日用品，不要套用任何预设人设。",
        template_id=None,
    )
    result = apply_action(ws, meta.id, "set_identity", identity=identity, share_user_profile=share)
    assert result.ok
    assert meta.identity.role_title == "家庭账本官"
    assert meta.identity.template_id is None
    block = identity_system_block(meta.identity, bot_id=meta.id)
    assert "家庭账本官" in block
    assert "猫粮" in block
    assert "<identity" in block


def test_e2_template_is_an_optional_starter_and_edits_win():
    template = get_template("schedule_secretary")
    assert template is not None
    assert "日程" in template.job_description
    drafted = apply_template(BotIdentity(), "schedule_secretary")
    assert "日程" in drafted.job_description
    assert "今日三事" in drafted.job_description
    custom, _share = commit_identity(
        role_title="日程秘书",
        job_description="只帮我看下周三下午能不能打羽毛球，别用模板里的今日三事。",
        template_id="schedule_secretary",
    )
    assert custom.template_id is None
    block = identity_system_block(custom, bot_id="s1")
    assert "羽毛球" in block
    assert "不展开无关闲聊" not in block


def test_e3_identity_is_on_system_and_user_text_is_unchanged(env):
    identity, _share = commit_identity(
        role_title="家庭账本官",
        job_description="只记猫粮开支。",
    )
    block = identity_system_block(identity, bot_id="bot1")
    prompt = "今天晚饭吃什么"
    prepared = prepare_turn(
        system="你是助手。",
        history=[{"role": "user", "content": "上一句"}],
        user_text=prompt,
        store=env,
        identity_block=block,
    )
    assert prepared.user_text == prompt
    assert prepared.messages[-1] == {"role": "user", "content": prompt}
    system = prepared.messages[0]["content"]
    assert "<identity" in system
    assert "家庭账本官" in system
    assert "猫粮" in system
    assert all("<identity" not in str(item.get("content")) for item in prepared.messages if item["role"] != "system")

    from local.tui.backend import MockBackend, TurnContext

    reply = MockBackend(delay=0).chat(
        [],
        prompt,
        turn=TurnContext(identity_block=block, collaboration_enabled=False),
    )
    assert prompt in reply.content
    assert "<identity" not in reply.content
    assert "<memory-context>" not in reply.content


def test_e3_agent_provider_keeps_identity_out_of_the_transcript(env):
    identity, _share = commit_identity(role_title="家庭账本官", job_description="只记猫粮开支。")
    block = identity_system_block(identity, bot_id="bot9")
    agent = LightAgent(
        name="life",
        model="gpt-4o-mini",
        api_key="test-key",
        base_url="http://127.0.0.1:9/v1",
        auto_discover_skills=False,
        log_level="ERROR",
        tree_of_thought=False,
    )
    calls = []

    class Completions:
        def create(self, **params):
            calls.append(params)
            message = SimpleNamespace(content="记下了。", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    agent.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    attach_profile_memory(agent, user_id="alice", store=env, identity_block=block, session_id="bot9")
    query = "今天晚饭吃什么"
    agent.run(query, user_id="mallory", result_format="object", trace=True)
    sent = calls[0]["messages"]
    assert "<identity" in sent[0]["content"]
    assert "猫粮" in sent[0]["content"]
    assert sent[-1]["content"] == query
    assert "<identity" not in sent[-1]["content"]
    for event in agent.export_session()["events"]:
        if event["type"] != "model.requested":
            continue
        blob = "\n".join(str(item.get("content") or "") for item in event["data"].get("messages") or [])
        assert "<identity" not in blob
        assert "猫粮" not in blob


def test_e4_identity_is_not_stored_as_a_profile_learning(env):
    before = [item.text for item in env.list_learnings(user_id="alice", namespace="profile")]
    job = "只记这个家里的猫粮开支，这不是用户偏好。"
    identity, _share = commit_identity(role_title="家庭账本官", job_description=job)
    prepare_turn(
        system="你是助手。",
        history=[],
        user_text="记一下",
        store=env,
        identity_block=identity_system_block(identity, bot_id="b"),
    )
    after = [item.text for item in env.list_learnings(user_id="alice", namespace="profile")]
    assert after == before
    assert job not in "\n".join(after)


def test_e5_inherit_keeps_soul_and_override_replaces_it():
    soul = load_persona_text()
    assert "长久陪伴" in soul
    identity = BotIdentity(role_title="日程秘书", job_description="只看冲突。", persona_mode="inherit")
    block = identity_system_block(identity, bot_id="b")
    inherited = prepare_turn(
        system="base",
        history=[],
        user_text="hi",
        persona_text=None,
        identity_block=block,
        share_user_profile=False,
    ).messages[0]["content"]
    assert "<persona>" in inherited
    assert "长久陪伴" in inherited
    assert "<identity" in inherited

    override = BotIdentity(
        role_title="日程秘书",
        job_description="只看冲突。",
        persona_mode="override",
        persona_text="只做日程薄记，不谈灵魂。",
    )
    from local.conversations.identity_inject import resolve_persona_text

    replaced = prepare_turn(
        system="base",
        history=[],
        user_text="hi",
        persona_text=resolve_persona_text(override),
        identity_block=identity_system_block(override, bot_id="b"),
        share_user_profile=False,
    ).messages[0]["content"]
    assert "只做日程薄记" in replaced
    assert "长久陪伴" not in replaced
    assert "<identity" in replaced


def test_e14_private_bot_skips_profile_pack_but_keeps_identity(env):
    env.learn("以后简称我小Q", user_id="alice", namespace="profile", lane="general", facet="identity")
    block = identity_system_block(
        BotIdentity(role_title="家庭账本官", job_description="只记猫粮。"),
        bot_id="priv",
    )
    hidden = prepare_turn(
        system="base",
        history=[],
        user_text="你好",
        store=env,
        identity_block=block,
        share_user_profile=False,
    )
    system = hidden.messages[0]["content"]
    assert "<identity" in system
    assert "猫粮" in system
    assert "小Q" not in system
    assert "<memory-context>" not in system
    shared = prepare_turn(
        system="base",
        history=[],
        user_text="你好",
        store=env,
        identity_block=block,
        share_user_profile=True,
    )
    assert "小Q" in shared.messages[0]["content"]
    assert shared.messages[-1]["content"] == "你好"
