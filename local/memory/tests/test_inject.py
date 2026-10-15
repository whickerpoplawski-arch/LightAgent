from types import SimpleNamespace

from LightAgent import LightAgent

from local.memory.host import MemoryHost
from local.memory.inject import prepare_turn, turn_index, user_text_contains_pack
from local.memory.persona import load_persona_text
from local.openrouter_config import _assert_free


class StaticCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **params):
        self.calls.append(params)
        message = SimpleNamespace(content="好的，小Q。", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_prepare_turn_puts_pack_on_system_and_leaves_user_text(env):
    env.learn("以后简称我小Q", user_id="alice", namespace="profile", lane="general", facet="identity")
    host = MemoryHost(user_id="alice", namespace="profile", session_id="s1")
    history = [{"role": "user", "content": "上一句"}, {"role": "assistant", "content": "上一答"}]
    prepared = prepare_turn(
        system="你是助手。",
        history=history,
        user_text="今天晚饭吃什么",
        host=host,
        store=env,
    )
    assert prepared.user_text == "今天晚饭吃什么"
    assert prepared.messages[-1] == {"role": "user", "content": "今天晚饭吃什么"}
    assert user_text_contains_pack(prepared.messages) is False
    system = prepared.messages[0]["content"]
    assert "<memory-context>" in system
    assert "小Q" in system
    assert "<persona>" in system
    assert "小Q" not in load_persona_text()
    assert all("<memory-context>" not in str(item.get("content")) for item in prepared.messages if item["role"] != "system")


def test_turn_index_is_stable():
    assert turn_index(0) == (0, 1)
    assert turn_index(3) == (6, 7)


def test_agent_turn_injects_pack_without_storing_it_as_user(env):
    env.learn("以后简称我小Q", user_id="alice", namespace="profile", lane="general", facet="identity")
    agent = LightAgent(
        name="life",
        model="gpt-4o-mini",
        api_key="test-key",
        base_url="http://127.0.0.1:9/v1",
        auto_discover_skills=False,
        log_level="ERROR",
    )
    completions = StaticCompletions()
    agent.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    from local.memory.inject import attach_profile_memory

    attach_profile_memory(agent, user_id="alice", namespace="profile", session_id="s9", store=env)

    query = "今天晚饭吃什么"
    result = agent.run(query, user_id="mallory", result_format="object", trace=True)
    assert result.content == "好的，小Q。"

    sent = completions.calls[0]["messages"]
    system = sent[0]["content"]
    user = sent[-1]
    assert user["role"] == "user"
    assert user["content"] == query
    assert "<memory-context>" in system
    assert "小Q" in system
    assert "<memory-context>" not in user["content"]
    assert "小Q" not in user["content"]

    exported = agent.export_session()
    user_blobs = []
    for event in exported["events"]:
        data = event["data"]
        if event["type"] == "message.received":
            user_blobs.append(data.get("content", ""))
            assert data.get("content") == query
        if event["type"] == "model.requested":
            for message in data.get("messages") or []:
                content = str(message.get("content") or "")
                assert "<memory-context>" not in content
                if message.get("role") == "user":
                    user_blobs.append(content)
                    assert "小Q" not in content
    assert query in user_blobs
    assert env.list_learnings(user_id="alice", namespace="profile")[0].text == "以后简称我小Q"


def test_kernel_memory_is_ephemeral_and_stores_the_raw_query():
    class RecordingMemory:
        def __init__(self):
            self.store_calls = []
            self.results = [{"memory": "用户喜欢安静", "metadata": {"user_id": "alice"}}]

        def retrieve(self, query, user_id):
            return {"results": self.results}

        def store(self, data, user_id, metadata=None):
            self.store_calls.append({"data": data, "user_id": user_id, "metadata": metadata})
            return {"memory_id": "1"}

    memory = RecordingMemory()
    agent = LightAgent(
        name="life",
        model="gpt-4o-mini",
        api_key="test-key",
        base_url="http://127.0.0.1:9/v1",
        memory=memory,
        auto_discover_skills=False,
        log_level="ERROR",
    )
    completions = StaticCompletions()
    agent.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    query = "今天晚饭吃什么"
    agent.run(query, user_id="alice", result_format="object", trace=True)

    sent = completions.calls[0]["messages"]
    assert "用户喜欢安静" in sent[0]["content"]
    assert "<memory-context>" in sent[0]["content"]
    assert sent[-1]["content"] == query
    assert "用户喜欢安静" not in sent[-1]["content"]
    assert memory.store_calls[0]["data"] == query
    assert "<memory-context>" not in memory.store_calls[0]["data"]

    exported = agent.export_session()
    for event in exported["events"]:
        if event["type"] != "model.requested":
            continue
        blob = "\n".join(str(item.get("content") or "") for item in event["data"].get("messages") or [])
        assert "用户喜欢安静" not in blob
        assert "<memory-context>" not in blob


def test_self_learning_does_not_fill_the_profile(env):
    class RecordingMemory:
        def retrieve(self, query, user_id):
            return {"results": []}

        def store(self, data, user_id, metadata=None):
            return {"memory_id": "1"}

    agent = LightAgent(
        name="life",
        model="gpt-4o-mini",
        api_key="test-key",
        base_url="http://127.0.0.1:9/v1",
        memory=RecordingMemory(),
        self_learning=True,
        auto_discover_skills=False,
        log_level="ERROR",
    )
    agent.client = SimpleNamespace(chat=SimpleNamespace(completions=StaticCompletions()))
    from local.memory.inject import attach_profile_memory

    attach_profile_memory(agent, user_id="alice", store=env)
    agent.run("记住我喜欢安静", user_id="alice")
    assert env.list_learnings(user_id="alice", namespace="profile") == []
    assert agent.list_memory_candidates()[0]["source"] == "reflection"


def test_memory_tools_are_registered_with_local_tools():
    from local.tui.tools import TOOLS

    names = [tool.tool_info["tool_name"] for tool in TOOLS]
    for name in ("memory_learn", "memory_forget", "memory_recall", "memory_pin", "web_search"):
        assert name in names


def test_paid_models_stay_rejected():
    from local import openrouter_config as orc

    if orc.REQUIRE_FREE_SUFFIX:
        _assert_free("google/gemma-4-31b-it:free")
        try:
            _assert_free("openai/gpt-4o")
        except ValueError as exc:
            assert "非免费" in str(exc)
        else:
            raise AssertionError("paid model was accepted")
    else:
        # MX 路径不强制 :free；默认模型应可过断言
        _assert_free(orc.DEFAULT_MODEL)
        _assert_free("openai/gpt-4o")  # 后缀策略关闭时不因「非免费」拒绝
