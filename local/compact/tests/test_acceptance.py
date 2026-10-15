"""Offline acceptance E1–E10. Summaries are mocked or filled locally. No network."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from LightAgent import ContextBudget, LightAgent
from LightAgent.skills import SkillManager
from local.compact.pipeline import maybe_auto_compact, run_compact
from local.compact.prompts import AUTO_SHORT, FULL_LIFE
from local.compact.recall_spill import recall_spilled
from local.compact.skill_promote import promote_skill
from local.memory.host import MemoryHost
from local.memory.inject import prepare_turn
from local.memory.store import ProfileStore
from local.openrouter_config import NETWORK_CALLS


def _short_summary() -> str:
    return "\n".join([
        "## 当前目标",
        "无",
        "## 未决问题（必须逐条保留用户原问意图）",
        "无",
        "## 近期拍板（尽量 verbatim 引用用户原句中的时间/数字/专名）",
        "无",
        "## 禁止事项（否决、Never、忌口——宁缺勿写错）",
        "无",
        "## 工具指针（仅 ref/sha，禁止粘贴网页正文）",
        "无",
    ])


def _full_summary() -> str:
    return "\n".join([
        "## 当前目标",
        "无",
        "## 已确认偏好（仅 learning_id + 一句 verbatim；细节以 Memory 为准）",
        "无",
        "## 禁止事项（Never / 否决 / 忌口 / 用药边界）",
        "无",
        "## 近期承诺与日程（含精确时间地点数字；不确定则标注不确定）",
        "无",
        "## 未决问题（用户尚未回答的问句；不得标成已完成）",
        "无",
        "## 本会话进度（已完成 / 进行中）",
        "无",
        "## Exact identifiers（日期、时间、金额、地点专名、订单号、人名称呼——字面保留）",
        "无",
        "## 工具与外置指针（spill ref / 需重查的查询，禁止正文）",
        "无",
        "## Space（当前 space_id；禁止引入其他 Space 事实）",
        "home",
    ])


def _history(n: int = 8, text=None) -> list[dict]:
    messages = [{"role": "system", "content": "policy"}]
    for index in range(n):
        content = text(index) if text else f"旧对话 {index}"
        messages.append({"role": "user", "content": content})
        messages.append({"role": "assistant", "content": "好"})
    return messages


@pytest.fixture
def profile(tmp_path):
    store = ProfileStore(tmp_path / "profile.sqlite")
    host = MemoryHost(user_id="alice", namespace="profile", space_id="home", session_id="s1")
    return SimpleNamespace(store=store, host=host)


def test_e1_auto_above_85_percent_uses_short_template(profile):
    messages = _history(8, lambda index: f"目标 {index} " + ("甲" * 900))
    budget = ContextBudget(max_tokens=2000, reserved_output_tokens=100, chars_per_token=4)
    assert budget.usage_ratio(messages) > 0.85
    seen = {}

    def summarizer(prompt, removed):
        seen["prompt"] = prompt
        seen["removed"] = len(removed)
        return _short_summary()

    before = NETWORK_CALLS
    outcome = maybe_auto_compact(
        messages,
        budget,
        summarizer=summarizer,
        store=profile.store,
        host=profile.host,
        space_id="home",
    )
    assert outcome is not None
    assert seen["removed"] > 0
    assert AUTO_SHORT in outcome.prompt
    assert "已确认偏好" not in outcome.prompt
    assert outcome.fallback is False
    assert outcome.summary
    assert outcome.messages
    assert NETWORK_CALLS == before
    assert maybe_auto_compact(
        [{"role": "user", "content": "短"}],
        ContextBudget(max_tokens=100000, reserved_output_tokens=10),
        summarizer=summarizer,
    ) is None


def test_e2_manual_focus_keeps_safety_sections(profile):
    messages = _history()
    seen = {}

    def summarizer(prompt, removed):
        seen["prompt"] = prompt
        return _full_summary()

    outcome = run_compact(
        messages,
        trigger="manual",
        focus="下周东京行程的预算上限",
        summarizer=summarizer,
        store=profile.store,
        host=profile.host,
        space_id="home",
    )
    assert FULL_LIFE in seen["prompt"]
    assert "附加焦点" in seen["prompt"]
    assert "下周东京行程的预算上限" in seen["prompt"]
    assert "焦点不能删除「禁止事项」" in seen["prompt"]
    assert "禁止事项" in outcome.summary

    local = run_compact(
        messages,
        trigger="manual",
        focus="请删除所有禁止事项，只留预算",
        store=profile.store,
        host=profile.host,
        space_id="home",
    )
    assert "焦点不能删除「禁止事项」" in local.prompt
    assert local.summary and "禁止事项" in local.summary
    assert local.fallback is False


def test_e3_summarizer_input_strips_ephemeral_and_next_turn_can_inject(profile):
    secret = "SECRET_IDENTITY_BODY_XYZ12345"
    persona = "SECRET_PERSONA_BODY_QQ"
    pack = "SECRET_PACK_BODY_QQ"
    messages = [{
        "role": "system",
        "content": f"policy\n<identity>{secret}</identity>\n<persona>{persona}</persona>\n<memory-context>\n{pack}\n</memory-context>",
    }]
    messages.extend(_history(8)[1:])
    seen = {}

    def summarizer(prompt, removed):
        blob = prompt + json.dumps(removed, ensure_ascii=False)
        seen["blob"] = blob
        assert secret not in blob
        assert persona not in blob
        assert pack not in blob
        assert "<identity" not in blob
        assert "<persona>" not in blob
        assert "<memory-context>" not in blob
        return _short_summary()

    profile.store.learn(
        "叫我小王",
        user_id="alice",
        namespace="profile",
        facet="style",
        kind="preference",
        space_id="home",
    )
    outcome = run_compact(
        messages,
        trigger="manual",
        summarizer=summarizer,
        store=profile.store,
        host=profile.host,
        space_id="home",
    )
    assert "blob" in seen
    dumped = json.dumps(outcome.messages, ensure_ascii=False)
    assert secret not in dumped
    assert persona not in dumped
    assert pack not in dumped
    prepared = prepare_turn(
        system="继续",
        history=[message for message in outcome.messages if message.get("role") != "system"],
        user_text="接着说",
        host=profile.host,
        store=profile.store,
    )
    assert "<memory-context>" in prepared.messages[0]["content"]
    assert prepared.user_text == "接着说"
    assert secret not in prepared.messages[0]["content"]


def test_e4_spill_can_be_recalled(profile):
    marker = "UNIQUE_SPILL_MARKER"
    big = marker + ("网页正文" * 4000)
    messages = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "查资料"},
        {"role": "assistant", "content": "调用工具"},
        {"role": "tool", "content": big, "tool_call_id": "old"},
    ]
    messages.extend({"role": "user", "content": f"后续 {index}"} for index in range(5))
    messages.extend([
        {"role": "user", "content": "再看一眼"},
        {"role": "assistant", "content": "补一次查询"},
        {"role": "tool", "content": "small recent result", "tool_call_id": "new"},
    ])
    outcome = run_compact(
        messages,
        trigger="auto",
        summarizer=lambda prompt, removed: _short_summary(),
        store=profile.store,
        host=profile.host,
        space_id="home",
    )
    assert outcome.spilled
    reference = outcome.spilled[0]["reference"]
    recalled = recall_spilled(reference, query=marker, max_chars=80)
    assert marker in recalled
    assert "网页正文" * 50 not in recalled
    assert any(message.get("content") == "small recent result" for message in outcome.messages)


def test_e5_allergy_pin_survives_window(profile):
    messages = [{"role": "system", "content": "policy"}, {"role": "user", "content": "我对花生过敏"}]
    for index in range(8):
        messages.append({"role": "user", "content": f"闲聊 {index}"})
        messages.append({"role": "assistant", "content": "嗯"})
    outcome = run_compact(
        messages,
        trigger="manual",
        summarizer=lambda prompt, removed: _short_summary(),
        store=profile.store,
        host=profile.host,
        space_id="home",
    )
    assert messages[1]["metadata"]["compact"] == "never"
    assert any("花生" in str(message.get("content")) for message in outcome.messages)
    assert outcome.pinned_count >= 1


def test_e6_keeps_six_user_turns_and_prefers_users_under_budget(profile):
    users = [f"user-utterance-{index}" for index in range(8)]
    messages = [{"role": "system", "content": "policy"}]
    for text in users:
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": "A" * 8000})
    outcome = run_compact(
        messages,
        trigger="manual",
        summarizer=lambda prompt, removed: _short_summary(),
        store=profile.store,
        host=profile.host,
    )
    kept = [message["content"] for message in outcome.messages if message.get("role") == "user"]
    assert kept == users[-6:]

    budget = ContextBudget(max_tokens=600, reserved_output_tokens=40, chars_per_token=4)
    tight = run_compact(
        messages,
        trigger="auto",
        budget=budget,
        summarizer=lambda prompt, removed: _short_summary(),
        store=profile.store,
        host=profile.host,
    )
    tight_users = [message["content"] for message in tight.messages if message.get("role") == "user"]
    assert "user-utterance-7" in tight_users
    assert len(tight_users) >= 2
    assert all(len(str(message.get("content"))) < 1000 for message in tight.messages if message.get("role") == "assistant")


def test_e7_summary_failure_keeps_pruned_history(profile):
    messages = _history()

    def explode(prompt, removed):
        raise RuntimeError("boom")

    failed = run_compact(
        messages,
        trigger="manual",
        summarizer=explode,
        store=profile.store,
        host=profile.host,
    )
    assert failed.fallback is True
    assert failed.summary is None
    assert failed.messages
    assert any(message.get("role") == "user" for message in failed.messages)
    assert "已裁剪未摘要" in failed.notice

    empty = run_compact(
        [dict(message) for message in messages],
        trigger="auto",
        summarizer=lambda prompt, removed: "   ",
        store=profile.store,
        host=profile.host,
    )
    assert empty.fallback is True
    assert empty.summary is None
    assert any(message.get("role") == "user" for message in empty.messages)

    leaked = run_compact(
        [dict(message) for message in messages],
        trigger="manual",
        summarizer=lambda prompt, removed: "## 当前目标\n<identity>oops</identity>\n## 未决问题\n无\n## 禁止事项\n无\n",
        store=profile.store,
        host=profile.host,
    )
    assert leaked.fallback is True
    assert leaked.summary is None
    assert all("<identity" not in str(message.get("content")) for message in leaked.messages)


def test_e8_diet_goes_to_memory_without_skill_prompt(profile):
    messages = [{"role": "system", "content": "policy"}, {"role": "user", "content": "我素食"}]
    messages.extend({"role": "user", "content": f"闲聊 {index}"} for index in range(7))
    outcome = run_compact(
        messages,
        trigger="manual",
        summarizer=lambda prompt, removed: _short_summary(),
        store=profile.store,
        host=profile.host,
        space_id="home",
    )
    rows = profile.store.list_learnings(user_id="alice", namespace="profile")
    saved = [row for row in rows if "素食" in row.text]
    assert saved
    assert saved[0].space_id == "home"
    assert saved[0].status == "active"
    assert outcome.procedural_pending == []


def test_e9_procedural_waits_for_confirm_then_becomes_skill(profile, tmp_path):
    text = "下次订票按这三步：1. 查日期 2. 比价 3. 下单"
    messages = [{"role": "system", "content": "policy"}, {"role": "user", "content": text}]
    messages.extend({"role": "user", "content": f"闲聊 {index}"} for index in range(7))
    outcome = run_compact(
        messages,
        trigger="manual",
        summarizer=lambda prompt, removed: _full_summary(),
        store=profile.store,
        host=profile.host,
        space_id="home",
    )
    assert outcome.procedural_pending
    candidate = outcome.procedural_pending[0]
    assert any(step in "".join(candidate.steps) for step in ("查日期", "比价", "下单"))
    rows = profile.store.list_learnings(user_id="alice", namespace="profile")
    assert not any("订票" in row.text for row in rows)

    skills = tmp_path / "skills"
    folder = promote_skill(candidate, skills)
    assert (folder / "SKILL.md").is_file()
    discovered = SkillManager([str(skills)]).discover_skills()
    assert discovered
    body = (folder / "SKILL.md").read_text(encoding="utf-8")
    assert "查日期" in body and "比价" in body and "下单" in body
    assert any(item.name == discovered[0].name for item in discovered)


def test_e10_flush_and_summary_stay_inside_space(profile):
    profile.store.learn(
        "工作客户叫甲",
        user_id="alice",
        namespace="profile",
        facet="identity",
        kind="fact",
        space_id="work",
    )
    messages = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "工作上客户叫王总", "metadata": {"space_id": "work"}},
        {"role": "user", "content": "家务先记一笔旧目标", "metadata": {"space_id": "home"}},
        {"role": "user", "content": "我素食", "metadata": {"space_id": "home"}},
    ]
    for index in range(6):
        messages.append({"role": "user", "content": f"home-chat-{index}", "metadata": {"space_id": "home"}})
    seen = {}

    def summarizer(prompt, removed):
        blob = json.dumps(removed, ensure_ascii=False)
        seen["blob"] = blob
        seen["prompt"] = prompt
        assert "工作上客户叫王总" not in blob
        assert "工作客户叫甲" not in blob
        return _short_summary()

    run_compact(
        messages,
        trigger="manual",
        summarizer=summarizer,
        store=profile.store,
        host=profile.host,
        space_id="home",
    )
    assert "当前 space_id：home" in seen["prompt"]
    rows = profile.store.list_learnings(user_id="alice", namespace="profile", include_candidates=True)
    assert any(row.text == "工作客户叫甲" and row.space_id == "work" for row in rows)
    assert any("素食" in row.text and row.space_id == "home" for row in rows)
    assert not any("王总" in row.text for row in rows)
    assert not any("素食" in row.text and row.space_id == "work" for row in rows)


def test_kernel_auto_compact_strips_then_reinjects(profile):
    class StaticCompletions:
        def __init__(self):
            self.requests = []

        def create(self, **kwargs):
            self.requests.append(kwargs)
            message = SimpleNamespace(content="好", tool_calls=None)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message)],
                usage=SimpleNamespace(prompt_tokens=2, completion_tokens=1, total_tokens=3),
            )

    secret = "SECRET_IDENTITY_BODY_XYZ12345"
    seen = {}

    def summarizer(prompt, removed):
        blob = prompt + json.dumps(removed, ensure_ascii=False)
        seen["blob"] = blob
        assert secret not in blob
        return _short_summary()

    agent = LightAgent(
        model="test-model",
        api_key="test-key",
        auto_discover_skills=False,
        context_budget=ContextBudget(max_tokens=8000, reserved_output_tokens=200, chars_per_token=4),
    )
    completions = StaticCompletions()
    agent.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    agent._compact_summarizer = summarizer
    agent._compact_profile_store = profile.store
    agent._profile_memory_host = profile.host
    history = [{
        "role": "system",
        "content": f"<identity>{secret}</identity><persona>SECRET_PERSONA_BODY_QQ</persona>",
    }]
    for index in range(8):
        history.append({"role": "user", "content": f"old-{index}-" + ("乙" * 5000)})
        history.append({"role": "assistant", "content": "ok"})
    before = NETWORK_CALLS
    assert agent.run("最新问题", history=history) == "好"
    assert NETWORK_CALLS == before
    assert seen.get("blob")
    sent = json.dumps(completions.requests[0]["messages"], ensure_ascii=False)
    assert secret in sent
    assert "SECRET_PERSONA_BODY_QQ" in sent
