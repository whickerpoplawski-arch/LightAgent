"""ContextCompactor user-turn window, pins, and spill."""

from __future__ import annotations

from LightAgent.session import ContextCompactor


def test_recent_tool_stays_inline_and_older_tool_spills():
    marker = "UNIQUE_SPILL_MARKER"
    big = marker + ("x" * 15000)
    messages = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "查一下"},
        {"role": "tool", "content": big},
        {"role": "user", "content": "再查"},
        {"role": "tool", "content": "small recent result"},
    ]
    compactor = ContextCompactor(max_inline_tool_chars=100, min_keep_tool_steps=1)
    result = compactor.compact(messages, keep_user_turns=6)

    assert result.spilled
    assert result.spilled[0]["content"].startswith(marker)
    assert any(message.get("content") == "small recent result" for message in result.messages)
    assert any("Tool result stored outside context" in str(message.get("content")) for message in result.messages)


def test_error_tool_results_can_be_deferred():
    messages = [
        {"role": "user", "content": "go"},
        {"role": "tool", "content": "e" * 500, "metadata": {"is_error": True}},
        {"role": "tool", "content": "ok"},
    ]
    compactor = ContextCompactor(max_inline_tool_chars=40, min_keep_tool_steps=0, defer_error_tool_results=True)
    result = compactor.compact(messages, keep_user_turns=6)
    assert result.spilled == []
    assert any(message.get("content") == "e" * 500 for message in result.messages)


def test_never_compact_survives_aggressive_max_messages():
    pinned = {"role": "user", "content": "我对花生过敏", "metadata": {"compact": "never"}}
    messages = [{"role": "system", "content": "policy"}, pinned]
    messages.extend({"role": "user", "content": f"later-{index}"} for index in range(8))
    result = ContextCompactor().compact(messages, max_messages=2)

    assert any("花生" in str(message.get("content")) for message in result.messages)
    assert result.removed_count > 0


def test_user_turn_window_keeps_six_user_utterances():
    users = [f"user-utterance-{index}" for index in range(8)]
    messages = [{"role": "system", "content": "policy"}]
    for text in users:
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": f"ack {text}"})
    result = ContextCompactor().compact(messages, keep_user_turns=6)
    kept = [message["content"] for message in result.messages if message.get("role") == "user"]
    assert kept == users[-6:]
    assert "user-utterance-0" not in kept
    assert "user-utterance-1" not in kept
