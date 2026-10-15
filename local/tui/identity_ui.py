"""Modals for the session menu and the free-form identity editor."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, Select, Static, TextArea
from textual.widgets.option_list import Option

from local.conversations.context_menu import MenuEntry
from local.conversations.models import BotIdentity
from local.conversations.templates import TEMPLATES, apply_template, commit_identity


class ConversationMenuScreen(ModalScreen[str | None]):
    """Same actions as the ``:`` / ``m`` menu. Dismisses with an action id."""

    BINDINGS = [Binding("escape", "cancel", "关闭")]

    def __init__(self, title: str, entries: list[MenuEntry]) -> None:
        super().__init__()
        self.bot_title = title
        self.entries = entries

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-dialog"):
            yield Label(self.bot_title, id="menu-title")
            yield Static("置顶、分组、身份。Esc 关闭。", id="menu-hint")
            yield OptionList(
                *[Option(entry.label, id=entry.action) for entry in self.entries],
                id="menu-options",
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        self.dismiss(None)


class MoveGroupScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "关闭")]

    def __init__(self, entries: list[MenuEntry]) -> None:
        super().__init__()
        self.entries = entries

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-dialog"):
            yield Label("移至分组", id="menu-title")
            yield OptionList(*[Option(entry.label, id=entry.action) for entry in self.entries])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        self.dismiss(None)


class RenameScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "关闭")]

    def __init__(self, current: str, *, heading: str = "重命名 Bot") -> None:
        super().__init__()
        self.current = current
        self.heading = heading

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-dialog"):
            yield Label(self.heading, id="menu-title")
            yield Static("只改显示名，对话 ID 不变。", id="menu-hint")
            yield Input(value=self.current, id="rename-input")
            with Horizontal(id="menu-buttons"):
                yield Button("保存", id="rename-save", variant="primary")
                yield Button("取消", id="rename-cancel")

    def on_mount(self) -> None:
        self.query_one("#rename-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rename-save":
            self.dismiss(self.query_one("#rename-input", Input).value.strip())
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_cancel(self) -> None:
        self.dismiss(None)


class NewGroupScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "关闭")]

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-dialog"):
            yield Label("新分组", id="menu-title")
            yield Input(placeholder="分组名称", id="group-input")
            with Horizontal(id="menu-buttons"):
                yield Button("创建并移入", id="group-save", variant="primary")
                yield Button("取消", id="group-cancel")

    def on_mount(self) -> None:
        self.query_one("#group-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "group-save":
            self.dismiss(self.query_one("#group-input", Input).value.strip())
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", "取消")]

    def __init__(self, message: str, *, title: str = "删除对话") -> None:
        super().__init__()
        self.message = message
        self.menu_title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-dialog"):
            yield Label(self.menu_title, id="menu-title")
            yield Static(self.message, id="menu-hint")
            with Horizontal(id="menu-buttons"):
                yield Button("删除", id="confirm-yes", variant="error")
                yield Button("取消", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def action_cancel(self) -> None:
        self.dismiss(False)


class IdentityEditorScreen(ModalScreen[dict | None]):
    """Free-form role and job. Templates only fill the draft."""

    BINDINGS = [Binding("escape", "cancel", "取消")]

    def __init__(self, identity: BotIdentity, *, share_user_profile: bool) -> None:
        super().__init__()
        self.identity = identity
        self.share_user_profile = share_user_profile

    def compose(self) -> ComposeResult:
        template_value = self.identity.template_id or "__none__"
        options = [("不使用模板，自己写", "__none__")]
        options.extend((item.role_title, item.template_id) for item in TEMPLATES)
        with Vertical(id="identity-dialog"):
            yield Label("设定身份", id="menu-title")
            yield Static(
                "身份是这个 Bot 的职位，由你来写。模板只是起稿，保存的是你留下的文字，不会写入用户画像。",
                id="menu-hint",
            )
            with VerticalScroll(id="identity-form"):
                yield Label("可选模板")
                yield Select(options, value=template_value, id="identity-template", allow_blank=False)
                yield Label("职位 role_title")
                yield Input(value=self.identity.role_title, placeholder="例如：家庭账本官", id="identity-role")
                yield Label("职责 job_description")
                yield TextArea(self.identity.job_description, id="identity-job")
                yield Label("显示名（可选，不改对话 ID）")
                yield Input(value=self.identity.display_name, id="identity-display")
                yield Label("人格")
                yield Select(
                    [("沿用全局 SOUL / IDENTITY", "inherit"), ("只用下面这段，不用全局人格", "override")],
                    value=self.identity.persona_mode if self.identity.persona_mode in ("inherit", "override") else "inherit",
                    id="identity-persona-mode",
                    allow_blank=False,
                )
                yield Label("覆盖人格（persona_mode=override 时使用）")
                yield TextArea(self.identity.persona_text, id="identity-persona")
                yield Checkbox("与其他 Bot 共享用户画像", value=self.share_user_profile, id="identity-share")
            with Horizontal(id="menu-buttons"):
                yield Button("保存", id="identity-save", variant="primary")
                yield Button("取消", id="identity-cancel")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "identity-template":
            return
        value = event.value
        if not value or value == "__none__":
            return
        draft = apply_template(self.identity, str(value))
        self.query_one("#identity-role", Input).value = draft.role_title
        self.query_one("#identity-job", TextArea).load_text(draft.job_description)
        self.identity = draft

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "identity-cancel":
            self.dismiss(None)
            return
        if event.button.id != "identity-save":
            return
        template_value = self.query_one("#identity-template", Select).value
        template_id = None if template_value in (None, "__none__", Select.NULL) else str(template_value)
        persona_mode = str(self.query_one("#identity-persona-mode", Select).value or "inherit")
        identity, share = commit_identity(
            role_title=self.query_one("#identity-role", Input).value,
            job_description=self.query_one("#identity-job", TextArea).text,
            display_name=self.query_one("#identity-display", Input).value,
            template_id=template_id,
            persona_mode=persona_mode,
            persona_text=self.query_one("#identity-persona", TextArea).text,
            share_user_profile=self.query_one("#identity-share", Checkbox).value,
        )
        self.dismiss({"identity": identity, "share_user_profile": share})

    def action_cancel(self) -> None:
        self.dismiss(None)
