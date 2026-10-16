"""Headless TUI checks: keyboard menu and a user-written identity."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from textual.screen import ModalScreen

from local.conversations.models import BotIdentity
from local.tui.app import LightAgentTUI, Session, SessionRow
from local.tui.backend import MockBackend
from local.tui.identity_ui import IdentityEditorScreen
from local.tui.row_menu import MenuAction, RowContextMenu


def test_colon_opens_the_session_menu_and_identity_save_is_custom(tmp_path):
    asyncio.run(_pilot(tmp_path))


async def _pilot(tmp_path):
    session = Session("主对话", id="main01")
    other = Session(
        "日程",
        id="sec01",
        identity=BotIdentity(role_title="日程秘书", job_description="只看冲突。"),
    )
    app = LightAgentTUI(
        MockBackend(delay=0),
        [session, other],
        [],
        workspace_dir=tmp_path,
        persist=False,
    )
    async with app.run_test(size=(120, 42)) as pilot:
        row = next(item for item in app.query(SessionRow) if item.session.id == "main01")
        row.focus()
        await pilot.press("colon")
        await pilot.pause()
        assert len(app.screen_stack) == 1
        assert not isinstance(app.screen, ModalScreen)
        menu = app.query_one(RowContextMenu)
        assert menu.display
        labels = [item.label_text for item in menu.query(MenuAction) if not item._pruning]
        assert any("设定身份" in label for label in labels)
        assert any("置顶" in label for label in labels)
        await pilot.press("escape")
        await pilot.pause()
        assert not menu.display

        app.open_identity_editor(next(item for item in app.sessions if item.id == "main01"))
        await pilot.pause(0.05)
        editor = app.screen
        assert isinstance(editor, IdentityEditorScreen)
        editor.query_one("#identity-role").value = "家庭账本官"
        editor.query_one("#identity-job").load_text("只记猫粮，这是我自己写的，不是模板。")
        await pilot.click("#identity-save")
        await pilot.pause(0.1)

    saved = next(item for item in app.sessions if item.id == "main01")
    assert saved.identity.role_title == "家庭账本官"
    assert "猫粮" in saved.identity.job_description
    assert saved.identity.template_id is None
    assert saved.id == "main01"
