"""E11–E14: create a room in the sidebar, speak, and leave 1:1 @ alone."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from local.conversations.models import BotIdentity
from local.rooms.ui import RoomRow
from local.tui.app import ChatBubble, LightAgentTUI, Session
from local.tui.backend import MockBackend


def _sessions() -> list[Session]:
    return [
        Session("主对话", id="main01"),
        Session(
            "习惯教练",
            id="c1",
            identity=BotIdentity(role_title="习惯教练", job_description="运动。", template_id="habit_coach"),
        ),
        Session(
            "饮食顾问",
            id="d1",
            identity=BotIdentity(role_title="饮食顾问", job_description="配餐。", template_id="nutrition_advisor"),
        ),
    ]


def _app(tmp_path, *, persist: bool = False) -> LightAgentTUI:
    return LightAgentTUI(MockBackend(delay=0), _sessions(), [], workspace_dir=tmp_path, persist=persist)


async def _create_room(pilot, app: LightAgentTUI) -> None:
    await pilot.click("#group-chat-btn")
    await pilot.pause(0.05)
    await pilot.click("#room-member-c1")
    await pilot.click("#room-member-d1")
    await pilot.click("#room-create")
    await pilot.pause(0.1)
    assert app.current_room_id
    assert app.rooms


def test_e11_create_room_shows_a_sidebar_row_and_welcome(tmp_path):
    asyncio.run(_e11(tmp_path))


async def _e11(tmp_path):
    app = _app(tmp_path, persist=True)
    async with app.run_test(size=(120, 42)) as pilot:
        button = str(app.query_one("#group-chat-btn").content)
        assert "稍后" not in button
        assert "创建群聊" in button
        await _create_room(pilot, app)
        row = next(item for item in app.query(RoomRow))
        assert row.room_title == "健康日常"
        labels = [bubble.speaker_label for bubble in app.query(ChatBubble)]
        assert "系统" in labels
        blob = " ".join(bubble._text for bubble in app.query(ChatBubble))
        assert "已创建群聊" in blob
        assert "习惯教练" in blob and "饮食顾问" in blob

    reloaded = LightAgentTUI(MockBackend(delay=0), _sessions(), [], workspace_dir=tmp_path, persist=True)
    async with reloaded.run_test(size=(120, 42)) as pilot:
        await pilot.pause(0.05)
        assert any(room.title == "健康日常" for room in reloaded.rooms)
        assert any(row.room_title == "健康日常" for row in reloaded.query(RoomRow))


def test_e12_fitness_turn_shows_two_speakers_and_host(tmp_path):
    asyncio.run(_e12(tmp_path))


async def _e12(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(120, 42)) as pilot:
        await _create_room(pilot, app)
        prompt = app.query_one("#prompt")
        prompt.focus()
        prompt.value = "帮我安排今日健身和饮食（忌深蹲，晚饭少油）"
        await pilot.press("enter")
        await pilot.pause(0.2)
        labels = [bubble.speaker_label for bubble in app.query(ChatBubble)]
        assert "习惯教练" in labels
        assert "饮食顾问" in labels
        assert "生活助手" in labels
        host = next(bubble for bubble in app.query(ChatBubble) if bubble.speaker_label == "生活助手")
        assert "动作：" in host._text
        assert "忌口：" in host._text
        assert "下一步：" in host._text
        diet = next(bubble for bubble in app.query(ChatBubble) if bubble.speaker_label == "饮食顾问")
        assert "忌深蹲" in diet._text
        assert str(app.query_one("#thinking").content) == ""


def test_e13_mention_keeps_the_other_member_silent(tmp_path):
    asyncio.run(_e13(tmp_path))


async def _e13(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(120, 42)) as pilot:
        await _create_room(pilot, app)
        prompt = app.query_one("#prompt")
        prompt.focus()
        prompt.value = "@饮食顾问 只改午餐"
        await pilot.press("enter")
        await pilot.pause(0.2)
        labels = [bubble.speaker_label for bubble in app.query(ChatBubble)]
        assert "饮食顾问" in labels
        assert "习惯教练" not in labels
        assert "生活助手" not in labels


def test_e14_main_chat_mention_still_delegates(tmp_path):
    asyncio.run(_e14(tmp_path))


async def _e14(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(120, 42)) as pilot:
        assert app.current_room_id is None
        assert app.current.id == "main01"
        prompt = app.query_one("#prompt")
        prompt.focus()
        prompt.value = "@习惯教练 只改今晚训练"
        await pilot.press("enter")
        await pilot.pause(1.4)
        assert app.current_room_id is None
        kinds = [kind for kind, _text in app.current.events]
        blob = "\n".join(text for _kind, text in app.current.events)
        assert "user" in kinds
        assert "习惯教练" in blob
        assert "已看过" in blob
        assert app.rooms == []
