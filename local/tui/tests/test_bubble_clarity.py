"""气泡正文必须是 Textual 文本；头像才用 TermImage。"""

from __future__ import annotations

import asyncio
import inspect

import pytest

pytest.importorskip("textual")

from textual.widgets import Static
from textual_image.widget import Image as TermImage

from local.tui.app import ChatBubble, LightAgentTUI, SessionRow, format_header, seed_demo_workspace
from local.tui.backend import MockBackend


def _plain(widget) -> str:
    rendered = widget.render()
    plain = getattr(rendered, "plain", None)
    if isinstance(plain, str):
        return plain
    return str(rendered)


def test_compose_does_not_rasterize_bubble_text():
    src = inspect.getsource(ChatBubble.compose)
    assert "render_user_bubble" not in src
    assert "compose_agent_row" not in src
    assert "user-bubble" in src
    assert "agent-bubble" in src
    assert "load_avatar" in src


def test_header_format_includes_avatar_id():
    assert format_header("新建试用", "indigo_hex") == "[b]新建试用[/] · 头像 indigo_hex"
    assert "· 头像 blue_drop" in format_header("健康日常", "", "习惯教练")


def test_bubbles_are_text_and_new_session_stays_ungrouped(tmp_path):
    asyncio.run(_pilot(tmp_path))


async def _pilot(tmp_path):
    sessions, projects = seed_demo_workspace()
    app = LightAgentTUI(
        MockBackend(delay=0),
        sessions,
        projects,
        workspace_dir=tmp_path,
        persist=False,
    )
    async with app.run_test(size=(120, 46)) as pilot:
        await pilot.pause(0.05)
        current = app.current
        header = _plain(app.query_one("#h-title"))
        assert current.title in header
        assert f"· 头像 {current.avatar}" in header

        demo = next(project for project in app.projects if project.name == "LightAgent 二开")
        user_text = "你好，这是新对话"
        agent_text = "你好！这是一条新会话，头像已与其它会话区分。"
        app.current.events = [("user", user_text), ("agent", agent_text)]
        app.load_session(app.current)
        await pilot.pause(0.05)

        user = next(bubble for bubble in app.query(ChatBubble) if bubble.kind == "user")
        agent = next(bubble for bubble in app.query(ChatBubble) if bubble.kind == "agent")
        assert list(user.query(TermImage)) == []
        body = user.query_one(".user-bubble", Static)
        assert user_text in _plain(body)
        assert body.size.width > 4
        assert body.styles.background.hex.lower() == "#2f7cf6"

        images = list(agent.query(TermImage))
        assert len(images) == 1
        assert "msg-avatar" in images[0].classes
        assert images[0].image.size[0] <= 64
        agent_body = agent.query_one(".agent-bubble", Static)
        assert "新会话" in _plain(agent_body)
        assert "soft-bubble" not in agent_body.classes
        assert agent_body.styles.background.hex.lower() == "#e9e9eb"
        assert agent_body.size.width > 4

        nested = next(row for row in app.query(SessionRow) if row.nested)
        preview = nested.query_one(".s-preview")
        assert nested.session.avatar in _plain(preview)
        assert preview.display

        nav_ids = [child.id for child in app.query_one("#nav").children]
        assert nav_ids.index("new-project-btn") < nav_ids.index("project-list")
        assert nav_ids.index("project-list") < nav_ids.index("room-section")
        assert nav_ids.index("room-section") < nav_ids.index("group-chat-btn")
        assert nav_ids.index("group-chat-btn") < nav_ids.index("ungrouped-list")
        assert app.query_one("#room-section").display
        assert "创建群聊" in _plain(app.query_one("#group-chat-btn"))

        await pilot.press("ctrl+n")
        await pilot.pause(0.05)
        created = app.current
        assert created.project_id is None
        assert created.id not in demo.session_ids
        assert created.id not in {item.id for item in app.sessions_in_project(demo)}
        ungrouped_ids = {row.session.id for row in app.query_one("#ungrouped-list").query(SessionRow)}
        assert created.id in ungrouped_ids
        assert f"· 头像 {created.avatar}" in _plain(app.query_one("#h-title"))

        await pilot.click("#new-btn")
        await pilot.pause(0.05)
        assert app.current.project_id is None
        assert app.current.id not in demo.session_ids

        project_row = next(row for row in app.query(".project-row") if row.project.name == "LightAgent 二开")
        await pilot.click(project_row.query_one(".project-add"))
        await pilot.pause(0.05)
        assert app.current.project_id == demo.id
        assert app.current.id in demo.session_ids
