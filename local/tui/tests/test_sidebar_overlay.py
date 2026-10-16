"""Row overlay menu, inline rename, and 15-grapheme preview."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from textual.screen import ModalScreen

from local.conversations.context_menu import menu_entries
from local.rooms.types import GroupRoom, RoomMessage
from local.rooms.ui import RoomRow
from local.tui.app import LightAgentTUI, Session, SessionRow, meta_from_session
from local.tui.backend import MockBackend
from local.tui.chrome import ShellChrome
from local.tui.identity_ui import ConfirmScreen, MoveGroupScreen
from local.tui.preview_text import grapheme_len
from local.tui.row_menu import MenuAction, RowContextMenu, TitleInput


def _plain(widget) -> str:
    rendered = widget.render()
    plain = getattr(rendered, "plain", None)
    if isinstance(plain, str):
        return plain
    return str(rendered)


def _actions(menu: RowContextMenu) -> list[MenuAction]:
    return [item for item in menu.query(MenuAction) if not item._pruning]


def _app(tmp_path, sessions: list[Session] | None = None) -> LightAgentTUI:
    if sessions is None:
        sessions = [
            Session(
                "主对话",
                id="main01",
                events=[("agent", "接下来怎么走？今天先看菜单")],
                avatar="blue_drop",
                accent="#3b82f6",
            ),
            Session(
                "日程",
                id="sec01",
                events=[("user", "明天下午有空吗，想约一下")],
                avatar="pink_cloud",
                accent="#ec4899",
            ),
        ]
    return LightAgentTUI(
        MockBackend(delay=0),
        sessions,
        [],
        workspace_dir=tmp_path,
        persist=False,
    )


async def _open(pilot, app: LightAgentTUI, session_id: str = "main01", key: str = "colon") -> SessionRow:
    row = next(item for item in app.query(SessionRow) if item.session.id == session_id)
    row.focus()
    await pilot.press(key)
    await pilot.pause()
    await pilot.pause()
    return row


def test_overlay_menu_covers_main_and_keeps_the_shell(tmp_path):
    asyncio.run(_overlay_menu(tmp_path))


async def _overlay_menu(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(120, 42)) as pilot:
        assert "menu" in app.screen.layers
        menu = app.query_one(RowContextMenu)
        assert menu.parent is app.screen
        assert not any(isinstance(node, ShellChrome) for node in menu.ancestors)
        assert not menu.display

        row = await _open(pilot, app)
        assert len(app.screen_stack) == 1
        assert not isinstance(app.screen, ModalScreen)
        assert menu.display
        assert menu.region.overlaps(app.query_one("#main").region)
        assert abs(menu.region.y - row.region.y) <= 2
        labels = [item.label_text for item in _actions(menu)]
        expected = [entry.label for entry in menu_entries(meta_from_session(row.session))]
        assert labels == expected
        assert len(menu.query(".menu-sep")) >= 3
        delete = next(item for item in _actions(menu) if item.action_id == "delete")
        assert "danger" in delete.classes
        svg = app.export_screenshot()
        # Rich writes each glyph in its own <text> node.
        assert "置</text>" in svg and "顶</text>" in svg
        assert "LightAgent" in svg
        assert isinstance(app.focused, MenuAction)
        assert app.focused.action_id == "toggle_pin"

        await pilot.press("escape")
        await pilot.pause()
        assert not menu.display

        await _open(pilot, app, key="m")
        assert menu.display
        assert _actions(menu)[0].action_id == "toggle_pin"
        await pilot.press("escape")
        await pilot.pause()

        current = app.current.id
        await pilot.click(row, button=3)
        await pilot.pause()
        assert menu.display
        assert len(app.screen_stack) == 1
        assert app.current.id == current
        other = next(item for item in app.query(SessionRow) if item.session.id != current)
        await pilot.click(other)
        await pilot.pause()
        assert not menu.display
        assert app.current.id == current

        await _open(pilot, app)
        await pilot.press("enter")
        await pilot.pause()
        saved = next(item for item in app.sessions if item.id == "main01")
        assert saved.pinned
        assert saved.id == "main01"
        assert len(app.screen_stack) == 1


def test_move_stays_overlay_and_delete_still_confirms(tmp_path):
    asyncio.run(_move_and_delete(tmp_path))


async def _move_and_delete(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(120, 42)) as pilot:
        await _open(pilot, app)
        await pilot.press("down", "enter")
        await pilot.pause()
        await pilot.pause()
        menu = app.query_one(RowContextMenu)
        labels = [item.label_text for item in _actions(menu)]
        assert any("移至新分组" in label for label in labels)
        assert len(app.screen_stack) == 1
        assert not isinstance(app.screen, MoveGroupScreen)
        await pilot.press("escape")
        await pilot.pause()

        await _open(pilot, app)
        delete = next(item for item in _actions(app.query_one(RowContextMenu)) if item.action_id == "delete")
        delete.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)


def test_inline_rename_commits_cancels_and_locks(tmp_path):
    asyncio.run(_rename(tmp_path))


async def _rename(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(120, 42)) as pilot:
        session = next(item for item in app.sessions if item.id == "main01")
        original = session.title
        await _open(pilot, app)
        rename = next(item for item in _actions(app.query_one(RowContextMenu)) if item.action_id == "rename")
        await pilot.click(rename)
        await pilot.pause()
        await pilot.pause()
        field = app.query_one(TitleInput)
        assert field.value == original
        assert (field.selection.start, field.selection.end) == (0, len(original))
        title = field.parent.query_one(".s-title")
        assert not title.display
        bg = str(field.styles.background).lower()
        assert "2f7cf6" in bg or "47, 124, 246" in bg or "#2f7cf6" in bg

        await pilot.press("x")
        assert field.value == "x"
        other = next(item for item in app.query(SessionRow) if item.session.id == "sec01")
        current = app.current.id
        count = len(app.sessions)
        await pilot.click(other)
        await pilot.pause()
        assert app.current.id == current
        assert app._rename_locked
        assert app.query_one(TitleInput).value == "x"
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert len(app.sessions) == count
        assert app.current.id == current

        await pilot.press("escape")
        await pilot.pause()
        assert session.title == original
        assert session.id == "main01"
        assert not list(app.query(TitleInput))
        assert not app._rename_locked

        await _open(pilot, app)
        rename = next(item for item in _actions(app.query_one(RowContextMenu)) if item.action_id == "rename")
        rename.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        field = app.query_one(TitleInput)
        await pilot.press("backspace", "enter")
        await pilot.pause()
        assert app._rename_locked
        assert session.title == original
        assert app.query_one(TitleInput).value == ""

        await pilot.press("二", "开", "enter")
        await pilot.pause()
        assert session.title == "二开"
        assert session.id == "main01"
        assert not app._rename_locked
        assert not list(app.query(TitleInput))
        shown = next(item for item in app.query(SessionRow) if item.session.id == "main01")
        assert "二开" in _plain(shown.query_one(".s-title"))


def test_preview_is_latest_message_and_search_keeps_the_tail(tmp_path):
    asyncio.run(_preview(tmp_path))


async def _preview(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(120, 42)) as pilot:
        await pilot.pause()
        row = next(item for item in app.query(SessionRow) if item.session.id == "main01")
        assert _plain(row.query_one(".s-preview")) == "接下来怎么走？今天先看菜单"
        assert "blue_drop" not in _plain(row.query_one(".s-preview"))
        long = ("甲" * 20) + "尾部标记"
        app.add_event(row.session, "agent", long)
        await pilot.pause()
        row = next(item for item in app.query(SessionRow) if item.session.id == "main01")
        preview = _plain(row.query_one(".s-preview"))
        assert preview == "甲" * 15
        assert grapheme_len(preview) == 15
        assert row.session.avatar not in preview
        app._nav_filter = "尾部标记"
        app.rebuild_nav()
        await pilot.pause()
        assert any(item.session.id == "main01" for item in app.query(SessionRow))

        room = GroupRoom(id="room1", title="健康日常", member_bot_ids=["main01", "sec01"])
        app.rooms = [room]
        app.room_messages[room.id] = [
            RoomMessage(
                id="m1",
                role="assistant",
                speaker="bot",
                speaker_label="教练",
                content="甲" * 30,
                ts=1,
                kind="chat",
            )
        ]
        app._nav_filter = ""
        app.rebuild_nav()
        await pilot.pause()
        room_row = next(item for item in app.query(RoomRow) if item.room_id == "room1")
        room_preview_text = _plain(room_row.query_one(".s-preview"))
        assert grapheme_len(room_preview_text) == 15
        assert room_preview_text.startswith("教练：")

        room_row.focus()
        await pilot.press("m")
        await pilot.pause()
        await pilot.pause()
        menu = app.query_one(RowContextMenu)
        assert menu.display
        assert [item.action_id for item in _actions(menu)] == ["rename", "members", "delete"]
        assert "danger" in next(item for item in _actions(menu) if item.action_id == "delete").classes
        assert len(app.screen_stack) == 1
        rename = _actions(menu)[0]
        rename.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        field = app.query_one(TitleInput)
        assert field.value == "健康日常"
        await pilot.press("x")
        assert field.value == "x"
        await pilot.press("enter")
        await pilot.pause()
        assert room.title == "x"
        assert room.id == "room1"


def test_open_menu_holds_tgp_uploads(tmp_path):
    asyncio.run(_holds_tgp(tmp_path))


async def _holds_tgp(tmp_path):
    """Blur and shell paint must not swap images while the row menu is up."""
    app = _app(tmp_path)
    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        field = app.query_one("#search-wrap")
        top = field.query_one(".soft-top")
        first = top.render()
        assert top.render() is first
        image = top.image
        await _open(pilot, app)
        assert app._tgp_hold
        field._paint_key = None
        field._repaint()
        assert field._tgp_pending
        assert top.image is image
        assert top.render() is first
        chrome = app.query_one(ShellChrome)
        chrome._key = None
        chrome.paint()
        assert chrome._tgp_pending
        assert chrome._key is None
        await pilot.press("escape")
        await pilot.pause()
        await pilot.pause()
        assert not app._tgp_hold
        assert not field._tgp_pending
        assert not chrome._tgp_pending
