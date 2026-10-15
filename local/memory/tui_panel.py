"""Textual panel for listing, editing, forgetting, and pinning learnings."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, ListItem, ListView, Label, Static

from .editor import MemoryEditor
from .host import bind_host, current_host


class MemoryPanel(Vertical):
    """Embedded or standalone editor. Persona files are not edited here."""

    def __init__(self, editor: MemoryEditor | None = None) -> None:
        super().__init__(classes="memory-panel")
        self.editor = editor or MemoryEditor()
        self._selected: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("用户画像 · 与助手人格分开", classes="mem-hint")
        yield ListView(id="mem-list")
        yield Input(placeholder="新的偏好或事实", id="mem-new")
        yield Input(placeholder="车道 general / situational", id="mem-lane", value="general")
        yield Input(placeholder="facet：identity / style / goal / tooling / veto / channel / life", id="mem-facet", value="identity")
        yield Input(placeholder="选中后在这里改原文", id="mem-edit")
        with Horizontal(classes="mem-actions"):
            yield Button("记住", id="mem-learn")
            yield Button("保存", id="mem-save")
            yield Button("忘记", id="mem-forget")
            yield Button("钉住", id="mem-pin")
            yield Button("确认", id="mem-confirm")
        yield Static("", id="mem-status")

    def on_mount(self) -> None:
        self.refresh_rows()

    def refresh_rows(self) -> None:
        self.editor.host = current_host()
        listing = self.query_one("#mem-list", ListView)
        listing.clear()
        for row in self.editor.list_rows():
            item = ListItem(Label(row["label"]))
            item.learning_id = row["id"]
            item.learning_text = row["text"]
            listing.append(item)
        if not self.editor.list_rows():
            self.query_one("#mem-status", Static).update("还没有画像。写下一句偏好，点「记住」。")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        self._selected = getattr(item, "learning_id", None)
        self.query_one("#mem-edit", Input).value = getattr(item, "learning_text", "")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        status = self.query_one("#mem-status", Static)
        try:
            if button == "mem-learn":
                text = self.query_one("#mem-new", Input).value.strip()
                lane = self.query_one("#mem-lane", Input).value.strip() or "general"
                facet = self.query_one("#mem-facet", Input).value.strip() or "identity"
                result = self.editor.learn(text, lane=lane, facet=facet)
                status.update(result.reason or result.status)
            elif button == "mem-save":
                if not self._selected:
                    status.update("先在列表里选一条。")
                    return
                result = self.editor.edit(self._selected, self.query_one("#mem-edit", Input).value)
                status.update(result.reason or result.status)
            elif button == "mem-forget":
                if not self._selected:
                    status.update("先在列表里选一条。")
                    return
                self.editor.forget(self._selected)
                self._selected = None
                status.update("已忘记。")
            elif button == "mem-pin":
                if not self._selected:
                    status.update("先在列表里选一条。")
                    return
                saved = self.editor.pin(self._selected, pinned=True)
                status.update("已钉住。" if saved else "没有找到这条。")
            elif button == "mem-confirm":
                if not self._selected:
                    status.update("先在列表里选一条。")
                    return
                saved = self.editor.confirm(self._selected)
                status.update("已确认，之后会进入记忆包。" if saved else "没有找到这条。")
        except Exception as exc:
            status.update(f"没有写成：{exc}")
            return
        self.refresh_rows()


class MemoryApp(App):
    CSS = """
    Screen { background: #f5f5f7; color: #1c1c1e; }
    .memory-panel { height: 100%; padding: 1 2; }
    .mem-hint { height: 1; color: #8e8e93; margin: 0 0 1 0; }
    #mem-list { height: 1fr; border: round #d4d4d8; background: transparent; }
    .mem-actions { height: 3; margin: 1 0 0 0; }
    .mem-actions Button { margin: 0 1 0 0; }
    #mem-status { height: 2; color: #3f3f46; }
    Input { margin: 0 0 1 0; border: round #d4d4d8; background: transparent; }
    """

    def compose(self) -> ComposeResult:
        yield MemoryPanel()


def main() -> None:
    bind_host(current_host())
    MemoryApp().run()


if __name__ == "__main__":
    main()