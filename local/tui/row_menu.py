"""Row-anchored menu and inline title editor. Not drawn into the shell bitmap."""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, Static

from local.conversations.context_menu import MenuEntry

# Visual groups from the reference card. Business labels stay as menu_entries wrote them.
_BREAK_BEFORE = frozenset({"rename", "copy_id", "toggle_hidden"})


def is_right_button(event) -> bool:
    button = getattr(event, "button", 1)
    value = getattr(button, "value", button)
    try:
        if int(value) == 3:
            return True
    except (TypeError, ValueError):
        pass
    return str(button).lower().endswith("right")


def group_entries(entries: list[MenuEntry]) -> list[MenuEntry | None]:
    """Insert a separator before rename / copy id / hide. No leading rule."""
    rows: list[MenuEntry | None] = []
    for entry in entries:
        if entry.action in _BREAK_BEFORE and rows:
            rows.append(None)
        rows.append(entry)
    return rows


class LightAgentScreen(Screen):
    """Default screen. Pointer lock for the row menu lives here so pilot and kitty share it."""

    def _forward_event(self, event) -> None:
        app = self.app
        consume = getattr(app, "consume_blocked_pointer", None)
        if consume is not None and consume(event):
            return
        super()._forward_event(event)

    async def _on_idle(self, event) -> None:
        await super()._on_idle(event)
        # Shell margin lands after the first frames. Re-anchor only when the offset moved.
        sync = getattr(self.app, "_sync_open_menu", None)
        if sync is not None:
            sync()


class MenuSeparator(Static):
    def __init__(self) -> None:
        super().__init__("──────────────────────", classes="menu-sep")


class MenuAction(Static):
    can_focus = True
    BINDINGS = [
        Binding("enter", "pick", "选择"),
        Binding("up", "prev", "上一项", priority=True),
        Binding("down", "next", "下一项", priority=True),
        Binding("escape", "dismiss", "关闭", priority=True),
    ]

    def __init__(self, entry: MenuEntry) -> None:
        classes = "menu-item danger" if entry.action == "delete" else "menu-item"
        super().__init__(entry.label, classes=classes)
        self.action_id = entry.action
        self.label_text = entry.label

    def _items(self) -> list[MenuAction]:
        parent = self.parent
        if parent is None:
            return [self]
        return [item for item in parent.query(MenuAction) if not item._pruning]

    def _move(self, step: int) -> None:
        items = self._items()
        if not items or self not in items:
            return
        items[(items.index(self) + step) % len(items)].focus(False)

    def action_prev(self) -> None:
        self._move(-1)

    def action_next(self) -> None:
        self._move(1)

    def action_pick(self) -> None:
        if self._pruning:
            return
        pick = getattr(self.app, "pick_row_menu", None)
        if pick is not None:
            pick(self.action_id)

    def action_dismiss(self) -> None:
        dismiss = getattr(self.app, "dismiss_row_menu", None)
        if dismiss is not None:
            dismiss()

    def on_click(self, event) -> None:
        event.stop()
        self.action_pick()


class RowContextMenu(Vertical):
    """Small card anchored to a row. ``overlay: screen`` so it covers the chat, not the shell PNG."""

    can_focus = False
    DEFAULT_CSS = """
    RowContextMenu {
        overlay: screen;
        layer: menu;
        width: 24;
        height: auto;
        display: none;
        background: #ffffff;
        color: #1c1c1e;
        border: round #d4d4d8;
        padding: 0;
        margin: 0;
        constrain: inside inside;
    }
    RowContextMenu .menu-item {
        height: 1;
        width: 1fr;
        padding: 0 1;
        background: #ffffff;
        color: #1c1c1e;
        content-align: left middle;
    }
    RowContextMenu .menu-item:hover {
        background: #f2f2f7;
    }
    RowContextMenu .menu-item:focus {
        background: #f2f2f7;
        text-style: bold;
    }
    RowContextMenu .menu-item.danger {
        color: #dc2626;
    }
    RowContextMenu .menu-item.danger:hover, RowContextMenu .menu-item.danger:focus {
        background: #fef2f2;
        color: #dc2626;
    }
    RowContextMenu .menu-sep {
        height: 1;
        color: #e5e5ea;
        padding: 0 1;
        background: #ffffff;
    }
    """

    def show_entries(self, entries: list[MenuEntry]) -> None:
        self.remove_children()
        widgets = []
        for item in group_entries(entries):
            widgets.append(MenuSeparator() if item is None else MenuAction(item))
        if widgets:
            self.mount(*widgets)
        self.display = True

    def hide(self) -> None:
        self.display = False
        if list(self.children):
            self.remove_children()


class TitleInput(Input):
    """One-line rename field. Select-all once; later focus must not reset the caret."""

    BINDINGS = [Binding("escape", "cancel_rename", "取消", priority=True)]

    def __init__(self, value: str) -> None:
        super().__init__(
            value=value,
            compact=True,
            select_on_focus=False,
            classes="s-rename",
            id="title-edit",
        )
        # Not MessagePump._closing — that flag drops the Prune that remove() posts.
        self._edit_closing = False

    def on_mount(self) -> None:
        def focus_and_select() -> None:
            if self._edit_closing:
                return
            self.focus(False)
            self.select_all()
            self.call_later(self.select_all)

        self.call_after_refresh(focus_and_select)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        commit = getattr(self.app, "commit_title_edit", None)
        if commit is not None:
            commit(event.value)

    def on_blur(self, event) -> None:
        del event
        if self._edit_closing:
            return
        if getattr(self.app, "_rename_locked", False):
            self.call_later(self.focus, False)

    def action_cancel_rename(self) -> None:
        cancel = getattr(self.app, "cancel_title_edit", None)
        if cancel is not None:
            cancel()


def begin_title_edit(row, title: str) -> TitleInput:
    """Hide the title label and mount an input in its place, above the preview."""
    row._renaming = True
    row.query_one(".s-title", Label).display = False
    field = TitleInput(title)
    row.query_one(".s-meta").mount(field, before=row.query_one(".s-preview"))
    return field


def end_title_edit(row) -> None:
    row._renaming = False
    try:
        field = row.query_one(TitleInput)
    except Exception:
        field = None
    if field is not None:
        field._edit_closing = True
        field.remove()
    try:
        row.query_one(".s-title", Label).display = True
    except Exception:
        pass

