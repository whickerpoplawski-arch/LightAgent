"""图片样式气泡：soft_render PNG + TGP/Sixel。侧栏副标题是 avatar_id。"""

from __future__ import annotations

import asyncio
import inspect
import os

import pytest

pytest.importorskip("textual")

from local.tui.app import ChatBubble, LightAgentTUI, SessionRow, format_header, seed_demo_workspace
from local.tui.backend import MockBackend
from local.tui.blobs import BLOB_CATALOG
from local.tui.graphics import (
    HalfcellImage,
    SixelImage,
    TGPImage,
    UnicodeImage,
    graphics_widget_class,
    preserve_image_colors,
)
from local.tui.soft_render import (
    AGENT_RGBA,
    BUBBLE_FONT_PX,
    BUBBLE_RADIUS,
    USER_RGBA,
    _font,
    render_agent_bubble,
    render_user_bubble,
)


def _plain(widget) -> str:
    rendered = widget.render()
    plain = getattr(rendered, "plain", None)
    if isinstance(plain, str):
        return plain
    return str(rendered)


def test_header_format_includes_avatar_id():
    assert format_header("新建试用", "indigo_hex") == "[b]新建试用[/] · 头像 indigo_hex"
    assert "· 头像 blue_drop" in format_header("健康日常", "", "习惯教练")


def test_avatar_pool_includes_reference_ids():
    assert len(BLOB_CATALOG) >= 50
    ids = {item["id"] for item in BLOB_CATALOG}
    assert "indigo_hex" in ids
    assert "blue_drop" in ids


def test_soft_render_is_a_rounded_cjk_image():
    assert BUBBLE_FONT_PX >= 18
    assert BUBBLE_RADIUS >= 20
    box = _font(False, BUBBLE_FONT_PX).getbbox("你")
    assert box[2] - box[0] >= 16

    user = render_user_bubble("你好，这是新对话")
    agent = render_agent_bubble("你好！这是一条新会话，头像已与其它会话区分。")
    assert user.getpixel((0, 0))[3] < 40
    assert agent.getpixel((0, 0))[3] < 40
    assert user.getpixel((12, user.height // 2))[:3] == USER_RGBA[:3]
    assert agent.getpixel((12, agent.height // 2))[:3] == AGENT_RGBA[:3]
    assert user.height >= BUBBLE_FONT_PX
    assert agent.height >= BUBBLE_FONT_PX
    def _count(image, pred) -> int:
        pixels = image.load()
        found = 0
        for y in range(image.height):
            for x in range(image.width):
                if pred(pixels[x, y]):
                    found += 1
        return found

    whites = _count(user, lambda px: px[0] > 240 and px[1] > 240 and px[2] > 240 and px[3] > 200)
    darks = _count(agent, lambda px: px[0] < 50 and px[1] < 50 and px[2] < 50 and px[3] > 200)
    assert whites > 40
    assert darks > 40


def test_bubble_widgets_are_tgp_or_sixel(monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_IMAGE_PROTOCOL", "tgp")
    assert graphics_widget_class() is TGPImage
    monkeypatch.setenv("LIGHTAGENT_IMAGE_PROTOCOL", "sixel")
    assert graphics_widget_class() is SixelImage
    monkeypatch.setenv("LIGHTAGENT_IMAGE_PROTOCOL", "halfcell")
    monkeypatch.delenv("KITTY_WINDOW_ID", raising=False)
    monkeypatch.delenv("KITTY_PID", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    chosen = graphics_widget_class()
    assert chosen in (TGPImage, SixelImage)
    assert chosen not in (HalfcellImage, UnicodeImage)

    src = inspect.getsource(ChatBubble.compose)
    assert "render_user_bubble" in src
    assert "render_agent_bubble" in src
    assert "GraphicsImage" in src
    assert "HalfcellImage" not in src
    assert "UnicodeImage" not in src
    assert "user-bubble" not in src
    assert "agent-bubble" not in src


def test_launcher_prefers_kitty_and_does_not_pass_halfcell():
    script = (os.path.dirname(__file__) + "/../../run_tui.sh")
    text = open(os.path.normpath(script), encoding="utf-8").read()
    assert "kitty" in text
    assert "图片气泡需 TGP/Sixel 终端" in text
    assert "halfcell/unicode 马赛克" in text
    assert "LIGHTAGENT_IMAGE_PROTOCOL" in text
    assert "unset NO_COLOR" in text


def test_startup_clears_no_color_before_textual(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    preserve_image_colors()
    assert "NO_COLOR" not in os.environ
    src = inspect.getsource(LightAgentTUI.__init__)
    assert src.find("preserve_image_colors") < src.find("super().__init__")


def test_flat_sidebar_and_image_bubbles(tmp_path):
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
        user_images = list(user.query(TGPImage)) + list(user.query(SixelImage))
        assert len(user_images) == 1
        assert "soft-bubble" in user_images[0].classes
        assert user_images[0].image.size[0] >= 40
        assert not list(user.query(HalfcellImage))
        assert not list(user.query(UnicodeImage))
        assert user_images[0].size.width < 70

        agent_images = list(agent.query(TGPImage)) + list(agent.query(SixelImage))
        assert len(agent_images) == 2
        assert any("msg-avatar" in image.classes for image in agent_images)
        assert any("soft-bubble" in image.classes for image in agent_images)
        bubble = next(image for image in agent_images if "soft-bubble" in image.classes)
        assert bubble.image.size[1] >= BUBBLE_FONT_PX
        assert not list(agent.query(HalfcellImage))

        project_rows = list(app.query_one("#project-list").query(SessionRow))
        assert project_rows
        assert all(not row.nested for row in project_rows)
        assert "TUI 气泡样式" in {row.session.title for row in project_rows}
        assert "随便问问" not in {row.session.title for row in project_rows}
        preview = project_rows[0].query_one(".s-preview")
        assert project_rows[0].session.avatar in _plain(preview)
        assert not list(app.query(".project-title"))
        assert "二开" not in _plain(app.query_one("#nav"))

        nav_ids = [child.id for child in app.query_one("#nav").children]
        assert nav_ids.index("new-project-btn") < nav_ids.index("project-list")
        assert nav_ids.index("project-list") < nav_ids.index("room-section")
        assert nav_ids.index("room-section") < nav_ids.index("group-chat-btn")
        assert nav_ids.index("group-chat-btn") < nav_ids.index("ungrouped-list")
        assert app.query_one("#room-section").display
        assert "创建群聊" in _plain(app.query_one("#group-chat-btn"))
        assert "+ 给 LightAgent 发消息" in app.query_one("#prompt").placeholder
        stats = _plain(app.query_one("#stats"))
        assert "⚡" in stats
        assert "今日用量" in stats or "今日免费" in stats

        await pilot.press("ctrl+n")
        await pilot.pause(0.05)
        created = app.current
        assert created.project_id is None
        assert created.id not in demo.session_ids
        assert created.id not in {item.id for item in app.sessions_in_project(demo)}
        ungrouped_ids = {row.session.id for row in app.query_one("#ungrouped-list").query(SessionRow)}
        assert created.id in ungrouped_ids
        assert f"· 头像 {created.avatar}" in _plain(app.query_one("#h-title"))
        created_row = next(row for row in app.query(SessionRow) if row.session.id == created.id)
        assert created.avatar in _plain(created_row.query_one(".s-preview"))

        await pilot.click("#new-btn")
        await pilot.pause(0.05)
        assert app.current.project_id is None
        assert app.current.id not in demo.session_ids

        before = set(demo.session_ids)
        placed = app.new_session_in_project(demo)
        await pilot.pause(0.05)
        assert placed.project_id == demo.id
        assert placed.id in demo.session_ids
        assert placed.id not in before
        in_project = {row.session.id for row in app.query_one("#project-list").query(SessionRow)}
        assert placed.id in in_project
