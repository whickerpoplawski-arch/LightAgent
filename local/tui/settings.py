"""Cursor-like Settings overlay — 「插件」页接 local/plugins_system。"""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static, Switch

from local.plugins_system import (
    disable,
    enable,
    install_from_spec,
    list_plugins,
    load_enabled_plugins,
)


class PluginRow(Horizontal):
    """单行：标题 + 描述 + 右侧开关。"""

    def __init__(self, info: dict) -> None:
        super().__init__(classes="plugin-row")
        self.info = info
        self.plugin_name = str(info["name"])

    def compose(self) -> ComposeResult:
        yield Static("🔌", classes="plugin-icon")
        with Vertical(classes="plugin-meta"):
            title = self.info.get("name") or "?"
            ver = self.info.get("version") or ""
            yield Label(f"{title}  ·  v{ver}" if ver else title, classes="plugin-title")
            desc = (self.info.get("description") or "").strip() or "（无描述）"
            bits = []
            if self.info.get("has_tools"):
                bits.append("tools")
            if self.info.get("has_skills"):
                bits.append("skills")
            if self.info.get("has_mcp"):
                bits.append("mcp")
            if bits:
                desc = f"{desc}  ·  {', '.join(bits)}"
            yield Label(desc[:72], classes="plugin-desc")
        yield Switch(value=bool(self.info.get("enabled")), id=f"sw-{self.plugin_name}", classes="plugin-switch")

    @on(Switch.Changed)
    def on_switch(self, event: Switch.Changed) -> None:
        event.stop()
        screen = self.app.screen
        if not isinstance(screen, SettingsScreen):
            return
        try:
            if event.value:
                enable(self.plugin_name)
            else:
                disable(self.plugin_name)
            screen.set_status(f"{'已启用' if event.value else '已禁用'}：{self.plugin_name}")
            screen.notify_plugins_changed()
        except Exception as exc:
            # revert visual
            event.switch.value = not event.value
            screen.set_status(f"开关失败：{exc}")


class SettingsScreen(ModalScreen[None]):
    """全屏设置：左侧导航（插件为首），右侧插件列表 + 安装框。"""

    BINDINGS = [
        Binding("escape", "close", "关闭", priority=True),
        Binding("ctrl+comma", "close", "关闭", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._nav = "plugins"
        self._filter = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="settings-shell"):
            with Vertical(id="settings-nav"):
                with Horizontal(id="settings-nav-top"):
                    yield Static("←", id="settings-back")
                    yield Input(placeholder="🔍  搜索设置", id="settings-filter")
                yield Static("🔌  插件", classes="settings-nav-item selected", id="nav-plugins")
                yield Static("⚙  通用", classes="settings-nav-item", id="nav-general")
                yield Static("🎨  外观", classes="settings-nav-item", id="nav-appearance")
                yield Static("🤖  Agents", classes="settings-nav-item", id="nav-agents")
                yield Static("📦  Models", classes="settings-nav-item", id="nav-models")
                with Horizontal(id="settings-nav-foot"):
                    yield Static("P", id="settings-profile-dot")
                    yield Label("asqwe", id="settings-profile-label")
                    yield Static("⚙", id="settings-nav-gear")
            with Vertical(id="settings-main"):
                yield Label("插件", id="settings-title")
                yield Label(
                    "从 GitHub 或本地目录安装；开关即时写入 enabled.json，下次对话热加载工具。",
                    id="settings-subtitle",
                )
                yield Input(
                    placeholder="🔍  GitHub URL / owner/repo / 本地路径，Enter 安装",
                    id="plugin-install",
                )
                yield Static("", id="plugin-status")
                yield VerticalScroll(id="plugin-list")

    def on_mount(self) -> None:
        self.refresh_plugin_list()
        self.query_one("#plugin-install", Input).focus()

    def set_status(self, text: str) -> None:
        self.query_one("#plugin-status", Static).update(text)

    def notify_plugins_changed(self) -> None:
        app = self.app
        if hasattr(app, "on_plugins_changed"):
            app.on_plugins_changed()  # type: ignore[attr-defined]

    def refresh_plugin_list(self) -> None:
        box = self.query_one("#plugin-list", VerticalScroll)
        box.remove_children()
        rows = list_plugins()
        q = self._filter.strip().lower()
        if q:
            rows = [
                r
                for r in rows
                if q in r["name"].lower()
                or q in (r.get("description") or "").lower()
            ]
        if not rows:
            box.mount(Static("暂无已安装插件。在上方粘贴本地路径或 GitHub 地址安装。", classes="plugin-empty"))
            return
        for info in rows:
            box.mount(PluginRow(info))

    def action_close(self) -> None:
        self.dismiss(None)

    def on_click(self, event) -> None:
        wid = getattr(event.widget, "id", None)
        if wid == "settings-back":
            self.action_close()
            return
        if wid and wid.startswith("nav-"):
            for item in self.query(".settings-nav-item"):
                item.remove_class("selected")
            event.widget.add_class("selected")
            self._nav = wid.removeprefix("nav-")
            title = self.query_one("#settings-title", Label)
            if self._nav == "plugins":
                title.update("插件")
                self.query_one("#plugin-install").display = True
                self.query_one("#plugin-list").display = True
                self.query_one("#settings-subtitle").display = True
                self.refresh_plugin_list()
            else:
                title.update(event.widget.renderable if hasattr(event.widget, "renderable") else self._nav)
                # keep plugins widgets but show placeholder
                self.query_one("#plugin-install").display = False
                self.query_one("#plugin-list").display = True
                self.query_one("#settings-subtitle").display = False
                box = self.query_one("#plugin-list", VerticalScroll)
                box.remove_children()
                box.mount(Static("（占位）此分类尚未实现，当前仅「插件」可用。", classes="plugin-empty"))

    @on(Input.Changed, "#settings-filter")
    def on_settings_filter(self, event: Input.Changed) -> None:
        # filter nav labels lightly; for plugins also filter list when on plugins
        self._filter = event.value
        if self._nav == "plugins":
            self.refresh_plugin_list()

    @on(Input.Submitted, "#plugin-install")
    def on_install(self, event: Input.Submitted) -> None:
        source = event.value.strip()
        if not source:
            return
        self.set_status(f"正在安装：{source} …")
        try:
            # local paths: prefer symlink for examples so edits hot-apply
            symlink = False
            from pathlib import Path

            p = Path(source).expanduser()
            if p.exists() and p.is_dir():
                symlink = "examples" in p.parts or source.endswith("hello_plugin")
            m = install_from_spec(source, enable_after=True, symlink=symlink)
            event.input.value = ""
            self.set_status(f"已安装并启用：{m.name}@{m.version}")
            self.refresh_plugin_list()
            self.notify_plugins_changed()
            # show loaded tool count
            loaded = load_enabled_plugins()
            tools = [
                (t.tool_info.get("tool_name") if getattr(t, "tool_info", None) else getattr(t, "__name__", "?"))
                for t in loaded.tools
            ]
            self.set_status(
                f"已安装并启用：{m.name}@{m.version}  ·  已加载工具 {len(tools)}：{', '.join(tools) or '-'}"
            )
        except Exception as exc:
            self.set_status(f"安装失败：{exc}")
