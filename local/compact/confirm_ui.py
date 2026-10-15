"""Modal that asks whether a procedural compact hit should become a skill."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class SkillConfirmScreen(ModalScreen[bool]):
    """Yes stores the listed procedures as LightAgent skills. No leaves them queued."""

    BINDINGS = [Binding("escape", "cancel", "取消")]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-dialog"):
            yield Label("存为 skill？", id="menu-title")
            yield Static(self.message, id="menu-hint")
            with Horizontal(id="menu-buttons"):
                yield Button("保存", id="confirm-yes", variant="primary")
                yield Button("先不存", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def action_cancel(self) -> None:
        self.dismiss(False)
