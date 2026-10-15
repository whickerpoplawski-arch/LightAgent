"""M5: active constraints are the only injectable diet facts."""

from __future__ import annotations

from local.constraints.card import (
    ConstraintStore,
    active_texts,
    forget,
    remember,
    render_constraints_markdown,
    supersede,
)
from local.constraints.extract import apply_utterance, classify_utterance
from local.harness.ephemeral import sanitize_transcript
from local.memory.host import MemoryHost
from local.memory.inject import prepare_turn


def test_remember_supersede_and_forget(tmp_path):
    from local.constraints.card import ConstraintCard

    card = ConstraintCard()
    card = remember(card, "忌口：海鲜")
    assert active_texts(card) == ["忌口：海鲜"]

    card = supersede(card, old_id_or_text="忌口：海鲜", new_text="其实可以吃虾")
    assert active_texts(card) == ["其实可以吃虾"]
    assert "忌口：海鲜" not in active_texts(card)
    old = [item for item in card.items if item.text == "忌口：海鲜"]
    assert old and old[0].status == "superseded"
    assert any(item.supersedes == old[0].id for item in card.items if item.status == "active")

    card = forget(card, "其实可以吃虾")
    assert active_texts(card) == []

    store = ConstraintStore(tmp_path)
    store.remember("忌口：海鲜")
    store.supersede(old_id_or_text="忌口：海鲜", new_text="其实可以吃虾")
    reloaded = ConstraintStore(tmp_path).load()
    assert active_texts(reloaded) == ["其实可以吃虾"]
    assert (tmp_path / "constraints" / "card.json").exists()


def test_lift_utterance_supersedes_the_same_theme():
    from local.constraints.card import ConstraintCard

    card = remember(ConstraintCard(), "忌口：海鲜")
    assert classify_utterance("今天吃什么") is None
    assert classify_utterance("其实可以吃虾") == "supersede"
    updated = apply_utterance(card, "其实可以吃虾")
    assert updated is not None
    assert active_texts(updated) == ["其实可以吃虾"]
    assert all(item.status == "superseded" for item in updated.items if "海鲜" in item.text and item.status != "active")
    markdown = render_constraints_markdown(updated)
    assert "其实可以吃虾" in markdown
    assert "忌口：海鲜" not in markdown


def test_ephemeral_pack_contains_only_the_active_row(env, tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_WORKSPACE", str(tmp_path))
    store = ConstraintStore(tmp_path)
    store.remember("忌口：海鲜")
    store.supersede(old_id_or_text="忌口：海鲜", new_text="其实可以吃虾")

    prepared = prepare_turn(
        system="你是助手。",
        history=[],
        user_text="今天晚饭吃什么",
        host=MemoryHost(user_id="alice", namespace="profile", session_id="s1"),
        store=env,
        persona_text="",
        identity_block="",
    )
    assert "其实可以吃虾" in prepared.ephemeral
    assert "忌口：海鲜" not in prepared.ephemeral
    assert prepared.messages[-1]["content"] == "今天晚饭吃什么"
    persisted = sanitize_transcript(prepared.messages)
    blob = "\n".join(str(item.get("content") or "") for item in persisted)
    assert "<memory-context>" not in blob
    assert "其实可以吃虾" not in blob


def test_corrupt_card_does_not_block_the_turn(env, tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_WORKSPACE", str(tmp_path))
    path = tmp_path / "constraints"
    path.mkdir()
    (path / "card.json").write_text("{not json", encoding="utf-8")
    prepared = prepare_turn(
        system="你是助手。",
        history=[],
        user_text="今天晚饭吃什么",
        host=MemoryHost(user_id="alice", namespace="profile"),
        store=env,
        persona_text="",
        identity_block="",
    )
    assert prepared.messages[-1]["content"] == "今天晚饭吃什么"
    assert "忌口" not in (prepared.ephemeral or "")
