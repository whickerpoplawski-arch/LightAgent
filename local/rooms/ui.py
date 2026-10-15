"""Room modals and sidebar rows. The app only opens these and applies the result."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from local.conversations.collaborate import resolve_bot
from local.conversations.models import ConversationMeta

from .types import GroupRoom, RoomMessage


def member_labels(room: GroupRoom, roster: list[ConversationMeta]) -> list[str]:
    labels = []
    for bot_id in room.member_bot_ids:
        meta = resolve_bot(roster, bot_id)
        if meta is None:
            labels.append(bot_id)
        else:
            labels.append(meta.identity.role_title.strip() or meta.title)
    return labels


def room_preview(messages: list[RoomMessage]) -> str:
    for message in reversed(messages or []):
        if message.content and message.kind in ("chat", "host_summary", "system_notice"):
            text = " ".join(message.content.split())[:36]
            return f"{message.speaker_label}：{text}"
    return "还没有人发言"


class RoomRow(Horizontal):
    """Sidebar row for one room. Same shape as a session row."""

    can_focus = True

    def __init__(self, room: GroupRoom, preview: str) -> None:
        super().__init__(classes="session-row room-row")
        self.room_id = room.id
        self.room_title = room.title
        self.preview = preview
        self.unread = room.unread

    def compose(self) -> ComposeResult:
        yield Static("👥", classes="s-avatar")
        with Vertical(classes="s-meta"):
            yield Label(self.room_title, classes="s-title")
            yield Label(self.preview, classes="s-preview")

    def on_mount(self) -> None:
        self.query_one(".s-avatar", Static).styles.border = ("round", "#34d399")
        if self.unread:
            self.add_class("unread")

    def on_click(self) -> None:
        opener = getattr(self.app, "open_room", None)
        if opener:
            opener(self.room_id)

    def on_key(self, event) -> None:
        if event.key in ("colon", "m"):
            menu = getattr(self.app, "open_room_menu", None)
            if menu:
                menu(self.room_id)
                event.stop()
                event.prevent_default()


class CreateRoomScreen(ModalScreen[dict | None]):
    BINDINGS = [Binding("escape", "cancel", "关闭")]

    def __init__(self, bots: list[ConversationMeta]) -> None:
        super().__init__()
        self.bots = list(bots)

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-dialog"):
            yield Label("创建群聊", id="menu-title")
            yield Static("选 2 到 6 个已有 Bot。一句话可以请到多个人。", id="menu-hint")
            yield Input(value="健康日常", id="room-title")
            with VerticalScroll(id="room-members"):
                if not self.bots:
                    yield Static("还没有 Bot。先建两个身份再来。", id="room-empty")
                for meta in self.bots:
                    role = meta.identity.role_title.strip() or meta.title
                    yield Checkbox(f"{role}", id=f"room-member-{meta.id}")
            yield Checkbox("场景提示：健身和饮食", id="room-hint-fitness", value=True)
            yield Static("", id="room-form-error")
            with Horizontal(id="menu-buttons"):
                yield Button("创建", id="room-create", variant="primary")
                yield Button("取消", id="room-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "room-cancel":
            self.dismiss(None)
            return
        if event.button.id != "room-create":
            return
        selected = [
            meta.id
            for meta in self.bots
            if self.query_one(f"#room-member-{meta.id}", Checkbox).value
        ]
        if not 2 <= len(selected) <= 6:
            self.query_one("#room-form-error", Static).update("请选择 2 到 6 个 Bot")
            return
        hints = ["fitness_diet"] if self.query_one("#room-hint-fitness", Checkbox).value else []
        title = self.query_one("#room-title", Input).value.strip() or "健康日常"
        self.dismiss({"title": title, "member_bot_ids": selected, "scenario_hints": hints})

    def action_cancel(self) -> None:
        self.dismiss(None)


class RoomMenuScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "关闭")]

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-dialog"):
            yield Label("群聊", id="menu-title")
            yield OptionList(
                Option("重命名群", id="rename"),
                Option("管理成员", id="members"),
                Option("删除群", id="delete"),
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        self.dismiss(None)


class ManageMembersScreen(ModalScreen[list[str] | None]):
    BINDINGS = [Binding("escape", "cancel", "关闭")]

    def __init__(self, bots: list[ConversationMeta], selected: list[str]) -> None:
        super().__init__()
        self.bots = list(bots)
        self.selected = set(selected)

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-dialog"):
            yield Label("管理成员", id="menu-title")
            yield Static("仍然需要 2 到 6 人。", id="menu-hint")
            with VerticalScroll(id="room-members"):
                for meta in self.bots:
                    role = meta.identity.role_title.strip() or meta.title
                    yield Checkbox(role, id=f"room-member-{meta.id}", value=meta.id in self.selected)
            yield Static("", id="room-form-error")
            with Horizontal(id="menu-buttons"):
                yield Button("保存", id="room-members-save", variant="primary")
                yield Button("取消", id="room-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "room-members-save":
            self.dismiss(None)
            return
        chosen = [
            meta.id
            for meta in self.bots
            if self.query_one(f"#room-member-{meta.id}", Checkbox).value
        ]
        if not 2 <= len(chosen) <= 6:
            self.query_one("#room-form-error", Static).update("请选择 2 到 6 个 Bot")
            return
        self.dismiss(chosen)

    def action_cancel(self) -> None:
        self.dismiss(None)
