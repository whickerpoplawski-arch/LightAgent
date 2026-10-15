"""E7: a room survives save and load, and conversation saves keep the room index."""

from __future__ import annotations

from local.conversations.models import ConversationMeta, ProjectGroup
from local.conversations.store import StoredWorkspace, save_workspace
from local.rooms.actions import create_room
from local.rooms.store import load_rooms, load_transcript, save_rooms, save_transcript
from local.rooms.types import RoomMessage


def test_e7_create_save_load_keeps_members_and_title(tmp_path):
    room = create_room("健康日常", ["c1", "d1"], scenario_hints=["fitness_diet"], space_id="life")
    save_rooms(tmp_path, [room])
    message = RoomMessage(
        id="m1",
        role="user",
        speaker="user",
        speaker_label="用户",
        content="安排今日健身和饮食",
        ts=1,
        turn_id="t1",
    )
    save_transcript(tmp_path, room.id, [message], {"steps": []})

    loaded = load_rooms(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].id == room.id
    assert loaded[0].title == "健康日常"
    assert loaded[0].member_bot_ids == ["c1", "d1"]
    assert loaded[0].scenario_hints == ["fitness_diet"]
    assert loaded[0].space_id == "life"
    messages, trace = load_transcript(tmp_path, room.id)
    assert messages[0].content == "安排今日健身和饮食"
    assert messages[0].speaker == "user"
    assert trace == {"steps": []}

    save_workspace(
        tmp_path,
        StoredWorkspace(
            projects=[ProjectGroup(name="生活", id="p1")],
            conversations=[ConversationMeta(id="c1", title="习惯教练")],
        ),
    )
    again = load_rooms(tmp_path)
    assert [item.id for item in again] == [room.id]
    assert again[0].member_bot_ids == ["c1", "d1"]


def test_missing_rooms_key_is_an_empty_list(tmp_path):
    save_workspace(tmp_path, StoredWorkspace())
    assert load_rooms(tmp_path) == []


def test_create_room_rejects_the_wrong_member_count():
    from local.rooms.actions import RoomError

    try:
        create_room("健康日常", ["only-one"])
    except RoomError as exc:
        assert "2" in str(exc)
    else:
        raise AssertionError("one member should fail")
    try:
        create_room("太大", [f"b{i}" for i in range(7)])
    except RoomError as exc:
        assert "6" in str(exc)
    else:
        raise AssertionError("seven members should fail")
