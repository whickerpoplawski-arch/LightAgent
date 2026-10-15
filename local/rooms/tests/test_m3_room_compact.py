"""M3: zero-LLM room compact keeps constraint sentences and flushes first."""

from __future__ import annotations

from types import SimpleNamespace

from local.compact.flush import memory_flush
from local.compact.pipeline import run_compact
from local.constraints.card import ConstraintStore
from local.rooms.digest import compact_room_messages, prepare_room_transcript
from local.rooms.store import load_transcript
from local.rooms.types import GroupRoom, RoomMessage


def _user(index: int, content: str) -> RoomMessage:
    return RoomMessage(
        id=f"u{index}",
        role="user",
        speaker="user",
        speaker_label="用户",
        content=content,
        ts=index,
    )


def _bot(index: int, content: str) -> RoomMessage:
    return RoomMessage(
        id=f"b{index}",
        role="assistant",
        speaker="bot:c1",
        speaker_label="教练",
        content=content,
        ts=index,
    )


def test_e6_constraint_sentence_survives_the_tail_window():
    messages = [_user(0, "忌口：海鲜，不要排进菜单")]
    messages.extend(_bot(index + 1, f"闲聊 {index}") for index in range(50))
    compacted = compact_room_messages(
        messages,
        keep=40,
        constraint_texts=["忌口：海鲜"],
        keep_user=10,
    )
    assert any("忌口：海鲜" in item.content for item in compacted)
    assert compacted[-1].content == "闲聊 49"
    assert len(compacted) <= 40 + 10 + 8
    assert len(compacted) < len(messages)
    # No summarizer: bodies are original strings, not a generated digest.
    assert all(item.content.startswith("闲聊") or "忌口：海鲜" in item.content for item in compacted)


def test_plain_tail_stays_exactly_keep_messages():
    messages = [_user(index, f"第{index}条") for index in range(50)]
    compacted = compact_room_messages(messages, keep=40)
    assert len(compacted) == 40
    assert compacted[0].content == "第10条"
    assert compacted[-1].content == "第49条"


def test_prepare_save_absorbs_and_compacts_without_dropping_the_card(tmp_path):
    messages = [_user(0, "忌口：海鲜")]
    messages.extend(_bot(index + 1, f"闲聊 {index}") for index in range(45))
    saved = prepare_room_transcript(messages, workspace=tmp_path, room_id="r1", keep=40)
    assert any("忌口：海鲜" in item.content for item in saved)
    assert len(saved) < len(messages)
    assert ConstraintStore(tmp_path).active_texts() == ["忌口：海鲜"]
    assert (tmp_path / "rooms" / "r1.resumed_after_compact").is_file()
    assert saved[0].meta.get("compact") == "never"


def test_compact_failure_does_not_erase_the_constraint_file(tmp_path, monkeypatch):
    ConstraintStore(tmp_path).remember("忌口：海鲜")

    def boom(*_args, **_kwargs):
        raise RuntimeError("compact down")

    monkeypatch.setattr("local.rooms.digest.compact_room_messages", boom)
    messages = [_user(0, "忌口：花生")]
    kept = prepare_room_transcript(messages, workspace=tmp_path, room_id="r2", keep=1)
    assert [item.content for item in kept] == ["忌口：花生"]
    assert "忌口：海鲜" in ConstraintStore(tmp_path).active_texts()
    assert (tmp_path / "constraints" / "card.json").is_file()


def test_save_rooms_calls_compact(tmp_path):
    from local.tui.app import LightAgentTUI

    room = GroupRoom(id="r1", title="健康日常", member_bot_ids=["c1", "d1"])
    messages = [_user(0, "忌口：海鲜")]
    messages.extend(_bot(index + 1, f"闲聊 {index}") for index in range(45))
    app = SimpleNamespace(
        _persist=True,
        _workspace_dir=tmp_path,
        rooms=[room],
        room_messages={room.id: messages},
        room_traces={room.id: {"steps": []}},
    )
    LightAgentTUI._save_rooms(app)
    loaded, _trace = load_transcript(tmp_path, room.id)
    assert any("忌口：海鲜" in item.content for item in loaded)
    assert len(loaded) < 46
    assert len(app.room_messages[room.id]) == len(loaded)


def test_e7_flush_pins_diet_and_compact_keeps_it():
    messages = [{"role": "user", "content": "忌口：海鲜", "metadata": {}}]
    messages.extend({"role": "user", "content": f"闲聊{index}"} for index in range(12))
    report = memory_flush(messages, store=None)
    assert report["pinned_count"] >= 1
    assert messages[0]["metadata"]["compact"] == "never"
    outcome = run_compact(messages, trigger="manual", store=None, keep_user_turns=2)
    assert any("忌口：海鲜" in str(item.get("content")) for item in outcome.messages)
    assert "海鲜" in "\n".join(str(item.get("content")) for item in outcome.messages)
