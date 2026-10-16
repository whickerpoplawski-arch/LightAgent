"""LightAgent TUI 简易模版（Grok Bot 对齐 UI + 轨迹可视化）。

运行：
    python -m local.tui.app --mock   # 假后端，不调 API
    python -m local.tui.app          # 默认 MX（deepseek-v4.1-flash, effort=low）
"""
from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets import Input, Label, ListItem, ListView, Markdown, Static, TabbedContent, TabPane

from local.conversations.context_menu import (
    Workspace,
    apply_action,
    menu_entries,
    move_targets,
    sidebar_sections,
)
from local.conversations.identity_inject import blocks_for_meta
from local.conversations.models import BotIdentity, ConversationMeta, ProjectGroup
from local.conversations.store import StoredWorkspace, Transcript, load_workspace, save_workspace
from local.memory.host import MemoryHost, bind_host
from local.memory.tui_panel import MemoryPanel
from local.tui.preview_text import latest_message_text, message_preview
from local.tui.projects import Project, touch
from local.tui.row_menu import (
    LightAgentScreen,
    MenuAction,
    RowContextMenu,
    TitleInput,
    begin_title_edit,
    end_title_edit,
    is_right_button,
)
from local.tui.trace import (
    LANE_COLOR,
    LANE_LABEL,
    LANE_ORDER,
    ContextUsage,
    TraceStep,
    TraceStore,
    match_trace_query,
)

DAILY_LIMIT = 45

from local.tui.blobs import accent_for, assign_blob, paint_blob, pick_unused_blob
from local.tui.blobs import BLOB_CATALOG as _BLOB_CATALOG
AVATARS = [(b['id'], b['accent']) for b in _BLOB_CATALOG]
from local.tui.chrome import ShellChrome, SoftButton, SoftField, nav_pill, row_cap_px
from local.tui.graphics import (
    GraphicsImage,
    fit_graphics_widget,
    preserve_image_colors,
    rewrite_character_plane,
    tgp_held,
)
from local.tui.shell_render import (
    FIELD_RGBA,
    HOVER_RGBA,
    MAIN_RGBA,
    PCT_RGBA,
    SELECT_RGBA,
    SIDEBAR_RGBA,
    render_end_caps,
    rgb_hex,
)
from local.tui.soft_render import display_avatar, render_agent_bubble, render_user_bubble

# 兼容旧名
assign_avatar = assign_blob

# 工具/错误行仍按单元格折行。用户/助手正文是 soft_render PNG，不走这条。
BUBBLE_WRAP_CELLS = 42


def _rich_escape(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace("[", "\\[")


def model_caption(name: str) -> str:
    """交稿画面不把 mock-echo 摆在顶栏。真模型名仍显示。"""
    text = (name or "").strip()
    if not text or "mock" in text.lower():
        return ""
    return f"模型 · {text}"


def format_header(title: str, avatar_id: str, suffix: str = "") -> str:
    """顶栏：``{title} · 头像 {avatar_id}``。"""
    avatar = avatar_id or "blue_drop"
    line = f"[b]{_rich_escape(title)}[/] · 头像 {avatar}"
    extra = (suffix or "").strip()
    if extra:
        line += f"  [#3b82f6]{_rich_escape(extra)}[/]"
    return line


def wrap_terminal_text(text: str, width: int = BUBBLE_WRAP_CELLS) -> str:
    """按显示宽度折行，避免气泡被拉成一整行。"""
    from rich.cells import cell_len

    width = max(4, width)
    lines: list[str] = []
    for raw in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw == "":
            lines.append("")
            continue
        buf = ""
        used = 0
        for ch in raw:
            cell = cell_len(ch) or 1
            if buf and used + cell > width:
                lines.append(buf)
                buf = ch
                used = cell
            else:
                buf += ch
                used += cell
        if buf:
            lines.append(buf)
    return "\n".join(lines)


def style_blob(widget, accent: str = "", *, blob_id: str = "") -> None:
    """侧栏/消息/标题共用：半块真 blob（参考图裁切）。"""
    bid = blob_id or getattr(widget, "_blob_id", "") or ""
    if not bid:
        # accent 反查或默认
        from local.tui.blobs import BLOB_CATALOG
        bid = next((b["id"] for b in BLOB_CATALOG if b["accent"] == accent), BLOB_CATALOG[0]["id"])
    paint_blob(widget, bid, cols=7, rows=4)


@dataclass
class Session:
    title: str
    messages: list[dict] = field(default_factory=list)  # OpenAI 格式，直接作为 history 传给 LightAgent
    events: list[tuple[str, str]] = field(default_factory=list)  # 界面渲染用：(kind, text)
    avatar: str = ""
    accent: str = ""
    trace: TraceStore = field(default_factory=TraceStore)
    id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex[:8])
    project_id: str | None = None
    updated_at: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    pinned: bool = False
    hidden: bool = False
    unread: bool = False
    identity: BotIdentity = field(default_factory=BotIdentity)
    share_user_profile: bool = True
    agent_id: str | None = None
    space_id: str | None = None
    compact_banner: str = ""
    pending_skills: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.avatar or not self.accent:
            blob_id, accent = assign_avatar(0)
            if not self.avatar:
                self.avatar = blob_id
            if not self.accent:
                self.accent = accent
        # 旧 emoji 头像 → 映射到 blob id
        from local.tui.blobs import BLOB_CATALOG, blob_path
        if self.avatar and blob_path(self.avatar) is None:
            # 非 blob id：按 accent 或默认轮换稳定映射
            idx = abs(hash(self.avatar)) % len(BLOB_CATALOG)
            if self.accent:
                for i, b in enumerate(BLOB_CATALOG):
                    if b["accent"].lower() == self.accent.lower():
                        idx = i
                        break
            self.avatar = BLOB_CATALOG[idx]["id"]
            self.accent = BLOB_CATALOG[idx]["accent"]
        if not isinstance(self.identity, BotIdentity):
            self.identity = BotIdentity.from_dict(self.identity)
        if not self.agent_id:
            self.agent_id = f"bot-{self.id}"
        if self.space_id is None:
            self.space_id = self.project_id

    @property
    def latest_plain(self) -> str:
        """Untruncated latest user/agent text. Search uses this, not the 15-grapheme line."""
        return latest_message_text(self.events)

    @property
    def preview(self) -> str:
        return message_preview(self.latest_plain)


class SessionRow(Horizontal):
    """侧栏会话行。焦点在行上时 ``:`` 或 ``m`` 打开菜单，右键同样打开。"""

    can_focus = True

    def __init__(self, session: Session, *, nested: bool = False) -> None:
        classes = "session-row nested" if nested else "session-row"
        super().__init__(classes=classes)
        self.session = session
        self.nested = nested

    def _title(self) -> str:
        bits = []
        if self.session.pinned:
            bits.append("📌")
        if self.session.unread:
            bits.append("●")
        prefix = (" ".join(bits) + " ") if bits else ""
        return f"{prefix}{self.session.title}"

    def _subtitle(self) -> str:
        """名称下是最新消息，约 15 字素。头像 id 只出现在顶栏。"""
        return self.session.preview

    def compose(self) -> ComposeResult:
        yield GraphicsImage(self._cap_image(SIDEBAR_RGBA, right=False), classes="row-cap row-cap-left")
        yield GraphicsImage(self._avatar_image(SIDEBAR_RGBA), classes="s-avatar")
        with Vertical(classes="s-meta"):
            yield Label(self._title(), classes="s-title")
            yield Label(self._subtitle(), classes="s-preview")
        yield GraphicsImage(self._cap_image(SIDEBAR_RGBA, right=True), classes="row-cap row-cap-right")

    def _avatar_image(self, backdrop: tuple[int, int, int, int]):
        return display_avatar(self.session.avatar or "blue_drop", backdrop)

    def _cap_image(self, fill: tuple[int, int, int, int], *, right: bool):
        height, cap = row_cap_px()
        left, right_img = render_end_caps(height, cap, fill, radius=min(18, height // 3))
        return right_img if right else left

    def on_mount(self) -> None:
        app = self.app
        if isinstance(app, LightAgentTUI) and app.current is self.session:
            self.add_class("selected")
        self._sync_flags()
        self._sync_plate(force=True)

    def on_enter(self, _event=None) -> None:
        self._hot = True
        self._sync_plate(force=True)

    def on_leave(self, _event=None) -> None:
        self._hot = False
        self._sync_plate(force=True)

    def _plate_fill(self) -> tuple[int, int, int, int]:
        if "selected" in self.classes:
            return SELECT_RGBA
        if getattr(self, "_hot", False):
            return HOVER_RGBA
        return SIDEBAR_RGBA

    def _sync_plate(self, force: bool = False) -> None:
        if tgp_held(self.app):
            self._tgp_pending = True
            return
        self._tgp_pending = False
        fill = self._plate_fill()
        if not force and getattr(self, "_plate_fill_key", None) == fill:
            return
        self._plate_fill_key = fill
        self.styles.background = rgb_hex(fill)
        try:
            left = self.query_one(".row-cap-left")
            right = self.query_one(".row-cap-right")
            avatar = self.query_one(".s-avatar")
        except Exception:
            return
        left.image = self._cap_image(fill, right=False)
        right.image = self._cap_image(fill, right=True)
        avatar.image = self._avatar_image(fill)
        for widget in (left, right, avatar):
            fit_graphics_widget(widget)
        rewrite_character_plane(self.app)

    def _sync_flags(self) -> None:
        if self.session.unread:
            self.add_class("unread")
        else:
            self.remove_class("unread")
        if self.session.hidden:
            self.add_class("is-hidden")
        else:
            self.remove_class("is-hidden")

    def refresh_text(self) -> None:
        self.query_one(".s-title", Label).update(self._title())
        self.query_one(".s-preview", Label).update(self._subtitle())
        self._sync_flags()
        self._sync_plate(force=True)

    def on_click(self, event=None) -> None:
        if event is not None and is_right_button(event):
            event.stop()
            return
        app = self.app
        if not isinstance(app, LightAgentTUI):
            return
        if app._rename_locked or getattr(self, "_renaming", False):
            if event is not None:
                event.stop()
            return
        app.select_session(self.session)

    def on_key(self, event) -> None:
        app = self.app
        if not isinstance(app, LightAgentTUI):
            return
        if app._rename_locked or getattr(self, "_renaming", False):
            return
        if event.key in ("colon", "m", ":"):
            app.open_session_menu(self.session)
            event.stop()
            event.prevent_default()
        elif event.key == "delete":
            app.confirm_delete_session(self.session)
            event.stop()
            event.prevent_default()

    def on_mouse_down(self, event) -> None:
        if not is_right_button(event):
            return
        app = self.app
        if not isinstance(app, LightAgentTUI):
            return
        if app._rename_locked or getattr(self, "_renaming", False):
            event.stop()
            return
        app.open_session_menu(self.session, from_mouse=True)
        event.stop()


class ProjectRow(Vertical):
    """项目里的会话平铺成 blob 行，不画「名称 ▼」文件夹头。"""

    def __init__(self, project: Project, sessions: list[Session]) -> None:
        super().__init__(classes="project-row")
        self.project = project
        self._sessions = list(sessions)

    def compose(self) -> ComposeResult:
        for s in sorted(self._sessions, key=lambda x: x.updated_at, reverse=True):
            yield SessionRow(s, nested=False)


SessionItem = SessionRow  # 旧测试兼容



class ChatBubble(Horizontal):
    """对话区一条气泡/工具芯片；agent 行左侧挂会话 blob 头像。"""

    def __init__(
        self,
        kind: str,
        text: str,
        event_idx: int,
        speaker_label: str = "",
        speaker_class: str = "",
        *,
        avatar: str = "",
        accent: str = "",
    ) -> None:
        row_class = {
            "user": "user-row",
            "tool": "tool-row",
            "error": "error-row",
            "agent": "agent-row",
            "notice": "agent-row",
        }.get(kind, "agent-row")
        super().__init__(classes=f"{row_class} chat-bubble")
        self.kind = kind
        self.event_idx = event_idx
        self._text = text
        self.speaker_label = speaker_label
        self.speaker_class = speaker_class
        self.avatar = avatar
        self.accent = accent

    def compose(self):
        if self.speaker_label:
            classes = "speaker-label"
            if self.speaker_class:
                classes += f" {self.speaker_class}"
            yield Static(self.speaker_label, classes=classes)
        if self.kind == "user":
            yield GraphicsImage(render_user_bubble(self._text), classes="soft-bubble user-soft")
        elif self.kind == "tool":
            yield Static(f"⚙  工具调用 · {wrap_terminal_text(self._text)}", classes="tool-line", markup=False)
        elif self.kind == "error":
            yield Static(f"✖  {wrap_terminal_text(self._text)}", classes="error-line", markup=False)
        elif self.kind == "notice":
            yield Static(f"✳  {wrap_terminal_text(self._text)}", classes="notice-line", markup=False)
        else:
            bid = self.avatar or "blue_drop"
            yield GraphicsImage(display_avatar(bid, MAIN_RGBA), classes="msg-avatar")
            yield GraphicsImage(render_agent_bubble(self._text), classes="soft-bubble agent-soft")

    def on_mount(self) -> None:
        for widget in self.query(".soft-bubble, .msg-avatar"):
            fit_graphics_widget(widget)


class TraceRow(Static):
    """可点击的轨迹步骤行：选中高亮；Enter 跳回对话（用户/助手步）。"""

    can_focus = True

    def __init__(self, step: TraceStep, index: int) -> None:
        text = _format_trace_step(step)
        classes = "trace-row"
        if step.status == "error":
            classes += " err"
        super().__init__(text, classes=classes)
        self.step = step
        self.step_index = index

    def on_click(self) -> None:
        app = self.app
        if isinstance(app, LightAgentTUI):
            app.select_trace_step(self.step_index)

    def on_key(self, event) -> None:
        if event.key == "enter":
            app = self.app
            if isinstance(app, LightAgentTUI):
                app.action_jump_trace_to_chat()
                event.prevent_default()
                event.stop()


class TimelineBlock(Static):
    """时间线上的一段色块：点击跳到对应步骤并高亮。"""

    def __init__(self, step_index: int, cells: int, color: str, error: bool = False) -> None:
        ch = "▒" if error else "█"
        n = max(1, cells)
        super().__init__(f"[{color}]{ch * n}[/{color}]", classes="tl-block")
        self.step_index = step_index
        self.styles.width = n

    def on_click(self) -> None:
        app = self.app
        if isinstance(app, LightAgentTUI):
            # 点色块：选中该步（清掉泳道过滤以免行被藏住）
            app._lane_filter = None
            app._kind_filter = None
            app.select_trace_step(self.step_index)


class TimelineLaneLabel(Static):
    """泳道名：点击按 lane 过滤。"""

    def __init__(self, lane: str) -> None:
        color = LANE_COLOR[lane]
        label = LANE_LABEL[lane]
        super().__init__(f"[bold {color}]{label:<4}[/]", classes="tl-label")
        self.lane = lane
        self.styles.width = 5

    def on_click(self) -> None:
        app = self.app
        if isinstance(app, LightAgentTUI):
            app.toggle_lane_filter(self.lane)


class TimelineLane(Horizontal):
    """一行泳道：标签（筛泳道）+ 可点色块（跳步骤）+ 间隙点。"""

    def __init__(self, lane: str, segments: list[tuple[int, int, int, str]], width: int = 48) -> None:
        classes = "tl-lane"
        super().__init__(classes=classes)
        self.lane = lane
        self._segments = segments
        self._bar_width = width

    def compose(self):
        yield TimelineLaneLabel(self.lane)
        color = LANE_COLOR[self.lane]
        pos = 0
        for step_idx, start, end, status in self._segments:
            if start > pos:
                gap = Static("[#d4d4d8]" + ("·" * (start - pos)) + "[/#d4d4d8]", classes="tl-gap")
                gap.styles.width = start - pos
                yield gap
            yield TimelineBlock(step_idx, end - start, color, error=(status == "error"))
            pos = end
        if pos < self._bar_width:
            gap = Static("[#d4d4d8]" + ("·" * (self._bar_width - pos)) + "[/#d4d4d8]", classes="tl-gap")
            gap.styles.width = self._bar_width - pos
            yield gap


def _format_trace_step(step: TraceStep) -> str:
    tag = f"[{step.color} bold] {step.label} [/{step.color} bold]"
    body = step.summary
    extras = []
    if step.tool_name and step.tool_args:
        extras.append(f"[#8e8e93]args[/] {step.tool_args}")
    if step.tool_result:
        if step.status == "error":
            extras.append(f"[#c45c5c]✕ {step.tool_result}[/#c45c5c]")
        else:
            extras.append(f"[#5a9e6f]→ {step.tool_result[:80]}[/#5a9e6f]")
    if step.detail and step.kind in ("context", "model") and not extras:
        extras.append(f"[#8e8e93]{step.detail[:90]}[/#8e8e93]")
    bits = []
    if step.duration_ms:
        bits.append(f"{step.duration_ms}ms")
    if step.tokens:
        bits.append(f"{step.tokens} tok")
    meta = f"  [#8e8e93]{' · '.join(bits)}[/#8e8e93]" if bits else ""
    text = f"{tag}  {body}{meta}"
    if extras:
        text += "\n     " + "  ·  ".join(extras)
    return text



def seed_demo_workspace() -> tuple[list[Session], list[Project]]:
    """演示用：2 个项目（含会话）+ 若干未分组会话。"""
    now = time.time()
    a = assign_avatar

    def S(title, events, avatar, ago_s, project_id=None):
        if isinstance(avatar, int):
            em, ac = a(avatar)
        else:
            em, ac = str(avatar), accent_for(str(avatar))
        s = Session(title, events=list(events), avatar=em, accent=ac, project_id=project_id)
        s.updated_at = now - ago_s
        return s

    p1 = Project("LightAgent 二开", expanded=True)
    p2 = Project("评测 Harness", expanded=True)
    s1 = S("TUI 气泡样式", [("user", "对话框软化"), ("agent", "已改成圆角气泡")], "blue_drop", 600, p1.id)
    s2 = S("轨迹可视化", [("user", "加轨迹页"), ("agent", "泳道+feed 好了")], "pink_cloud", 3600, p1.id)
    s3 = S("免费额度护栏", [("user", "别超额度"), ("agent", "本地 45 次上限")], "orange_cloud", 7200, p1.id)
    s4 = S("任务集设计", [("user", "怎么做评测？"), ("agent", "mock 工具+轨迹断言")], "black_star", 86400, p2.id)
    s5 = S("抽检脚本", [("user", "写个 runner"), ("agent", "pytest + fixtures")], "brown_hex", 90000, p2.id)
    p1.session_ids = [s1.id, s2.id, s3.id]
    p2.session_ids = [s4.id, s5.id]

    u1 = S("随便问问", [("user", "今天天气？"), ("agent", "（未分组）晴")], "blue_tri", 300)
    u2 = S("灵感备忘", [("user", "记一下想法"), ("agent", "已记下")], "lime_squircle", 1800)
    u3 = S("临时代码", [("user", "一段 scrap"), ("agent", "ok")], "purple_blob", 100000)

    sessions = [s1, s2, s3, s4, s5, u1, u2, u3]
    return sessions, [p1, p2]


def meta_from_session(session: Session) -> ConversationMeta:
    identity = session.identity
    return ConversationMeta(
        id=session.id,
        title=session.title,
        avatar=session.avatar,
        accent=session.accent,
        project_id=session.project_id,
        space_id=session.space_id,
        pinned=session.pinned,
        hidden=session.hidden,
        unread=session.unread,
        updated_at=session.updated_at,
        created_at=session.created_at,
        identity=BotIdentity(
            display_name=identity.display_name,
            role_title=identity.role_title,
            job_description=identity.job_description,
            template_id=identity.template_id,
            persona_mode=identity.persona_mode,
            persona_text=identity.persona_text,
        ),
        share_user_profile=session.share_user_profile,
        agent_id=session.agent_id,
    )


def apply_meta_to_session(session: Session, meta: ConversationMeta) -> None:
    session.title = meta.title
    session.avatar = meta.avatar
    session.accent = meta.accent
    session.project_id = meta.project_id
    session.space_id = meta.space_id
    session.pinned = meta.pinned
    session.hidden = meta.hidden
    session.unread = meta.unread
    session.updated_at = meta.updated_at
    session.created_at = meta.created_at
    session.identity = BotIdentity.from_dict(meta.identity.to_dict())
    session.share_user_profile = meta.share_user_profile
    session.agent_id = meta.agent_id


def trace_to_dict(session: Session) -> dict:
    return {
        "steps": [
            {
                "kind": step.kind,
                "summary": step.summary,
                "detail": step.detail,
                "status": step.status,
                "tokens": step.tokens,
                "duration_ms": step.duration_ms,
                "lane": step.lane,
                "tool_name": step.tool_name,
                "tool_args": step.tool_args,
                "tool_result": step.tool_result,
            }
            for step in session.trace.steps
        ],
        "stats": {
            "rounds": session.trace.stats.rounds,
            "steps": session.trace.stats.steps,
            "tokens": session.trace.stats.tokens,
            "tok_per_s": session.trace.stats.tok_per_s,
            "cache_hit_pct": session.trace.stats.cache_hit_pct,
        },
    }


def sessions_from_stored(stored: StoredWorkspace) -> tuple[list[Session], list[Project]]:
    sessions: list[Session] = []
    for meta in stored.conversations:
        transcript = stored.transcripts.get(meta.id, Transcript())
        session = Session(
            title=meta.title,
            messages=list(transcript.messages),
            events=[(str(kind), str(text)) for kind, text in transcript.events],
            avatar=meta.avatar,
            accent=meta.accent,
            id=meta.id,
            project_id=meta.project_id,
            updated_at=meta.updated_at,
            created_at=meta.created_at,
            pinned=meta.pinned,
            hidden=meta.hidden,
            unread=meta.unread,
            identity=BotIdentity.from_dict(meta.identity.to_dict()),
            share_user_profile=meta.share_user_profile,
            agent_id=meta.agent_id,
            space_id=meta.space_id,
        )
        blob = transcript.trace or {}
        for item in blob.get("steps") or []:
            session.trace.steps.append(
                TraceStep(
                    kind=str(item.get("kind") or "context"),
                    summary=str(item.get("summary") or ""),
                    detail=str(item.get("detail") or ""),
                    status=str(item.get("status") or "ok"),
                    tokens=int(item.get("tokens") or 0),
                    duration_ms=int(item.get("duration_ms") or 0),
                    lane=str(item.get("lane") or ""),
                    tool_name=str(item.get("tool_name") or ""),
                    tool_args=str(item.get("tool_args") or ""),
                    tool_result=str(item.get("tool_result") or ""),
                )
            )
        stats = blob.get("stats") or {}
        session.trace.stats.rounds = int(stats.get("rounds") or 0)
        session.trace.stats.steps = len(session.trace.steps)
        session.trace.stats.tokens = int(stats.get("tokens") or 0)
        session.trace.stats.tok_per_s = float(stats.get("tok_per_s") or 0)
        session.trace.stats.cache_hit_pct = float(stats.get("cache_hit_pct") or 0)
        sessions.append(session)
    projects = [
        Project(group.name, id=group.id, expanded=group.expanded, session_ids=list(group.session_ids))
        for group in stored.projects
    ]
    return sessions, projects


class LightAgentTUI(App):
    CSS_PATH = "app.tcss"
    TITLE = "LightAgent"
    BINDINGS = [
        Binding("ctrl+n", "new_session", "新会话", priority=True),
        Binding("ctrl+p", "new_project", "新项目", priority=True),
        Binding("ctrl+k", "focus_search", "搜索"),
        Binding("ctrl+l", "clear", "清空"),
        Binding("ctrl+1", "tab_chat", "对话"),
        Binding("ctrl+2", "tab_trace", "轨迹"),
        Binding("ctrl+3", "tab_memory", "记忆"),
        Binding("ctrl+u", "toggle_context", "上下文", priority=True),
        Binding("ctrl+f", "focus_trace_search", "搜轨迹"),
        Binding("escape", "clear_trace_filters", "清除筛选"),
        Binding("enter", "jump_trace_to_chat", "跳对话", show=False),
        Binding("ctrl+comma", "open_settings", "设置", priority=True),
        Binding("ctrl+shift+i", "edit_identity", "设定身份", priority=True),
        Binding("ctrl+x", "stop_run", "停止", priority=True),
        Binding("ctrl+q", "quit", "退出"),
    ]

    def __init__(
        self,
        backend,
        sessions: list[Session] | None = None,
        projects: list[Project] | None = None,
        *,
        workspace_dir: str | Path | None = None,
        persist: bool | None = None,
    ) -> None:
        preserve_image_colors()
        super().__init__()
        self.backend = backend
        self._workspace_dir = Path(workspace_dir) if workspace_dir else (
            Path(__file__).resolve().parents[1] / "data" / "workspace"
        )
        import os
        os.environ["LIGHTAGENT_WORKSPACE"] = str(self._workspace_dir)
        self._show_hidden = False
        self.collaboration_enabled = True
        auto = sessions is None and projects is None
        self._persist = auto if persist is None else persist
        if auto:
            loaded = load_workspace(self._workspace_dir) if self._persist else None
            if loaded is None:
                sessions, projects = seed_demo_workspace()
            else:
                sessions, projects = sessions_from_stored(loaded)
                if not sessions:
                    blob_id, accent = assign_avatar(0)
                    sessions = [Session("新会话", avatar=blob_id, accent=accent)]
        elif sessions is None:
            blob_id, accent = assign_avatar(0)
            sessions = [Session("新会话", avatar=blob_id, accent=accent)]
        self.sessions = list(sessions)  # 全部会话（含项目内）
        self.projects = list(projects or [])
        self.current = self.sessions[0]
        self.active_project: Project | None = self.projects[0] if self.projects else None
        self.busy = False
        self._avatar_seq = len(self.sessions)
        self._live_tok_s = 0.0
        self._trace_filter = ""
        self._lane_filter: str | None = None
        self._kind_filter: str | None = None  # e.g. "tool"
        self._selected_step: int | None = None
        self._context_open = False
        self._nav_filter = ""
        self._plugins_revision = 0
        self.rooms = []
        self.room_messages: dict[str, list] = {}
        self.room_traces: dict[str, dict] = {}
        self.current_room_id: str | None = None
        self._rename_locked = False
        self._rename_row = None
        self._rename_kind: str | None = None
        self._rename_target_id: str | None = None
        self._menu_callback = None
        self._menu_anchor = None
        self._menu_swallow_click = False
        self._suppress_menu_click = False
        # 行菜单打开期间冻结会换图的 TGP。关掉或落稳后再整屏重写字符层。
        self._tgp_hold = False
        if self._persist:
            self._load_rooms()

    _LOCKED_WHILE_RENAMING = frozenset(
        {
            "new_session",
            "new_project",
            "focus_search",
            "clear",
            "tab_chat",
            "tab_trace",
            "tab_memory",
            "toggle_context",
            "focus_trace_search",
            "jump_trace_to_chat",
            "open_settings",
            "edit_identity",
            "stop_run",
            "quit",
            "help_quit",
        }
    )

    def get_default_screen(self) -> Screen:
        return LightAgentScreen(id="_default")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self._rename_locked and action in self._LOCKED_WHILE_RENAMING:
            return False
        return True

    # ---------- 布局 ----------
    def compose(self) -> ComposeResult:
        with ShellChrome(id="shell-chrome"):
            with Horizontal(id="shell"):
                with Vertical(id="sidebar"):
                    with Horizontal(id="side-top"):
                        yield Label("✨ LightAgent", id="brand")
                        yield SoftButton(id="new-btn")
                    yield SoftField(
                        Input(placeholder="🔍  搜索项目/会话", id="search"),
                        id="search-wrap",
                    )
                    with VerticalScroll(id="nav"):
                        yield Label("置顶", id="pinned-section", classes="nav-section")
                        yield Vertical(id="pinned-list")
                        yield Label("项目", classes="nav-section")
                        yield nav_pill("+ 新项目", "new-project-btn")
                        yield Vertical(id="project-list")
                        yield Label("群聊", id="room-section", classes="nav-section")
                        yield nav_pill("创建群聊", "group-chat-btn")
                        yield Vertical(id="room-list")
                        yield Label("会话", classes="nav-section")
                        yield Vertical(id="ungrouped-list")
                        yield nav_pill("显示已隐藏", "show-hidden-btn")
                    with Horizontal(id="side-foot"):
                        yield Static("P", id="profile-dot")
                        yield Label("本地 · MX" if __import__("os").environ.get("LIGHTAGENT_PROVIDER", "mx") != "openrouter" else "本地 · 免费额度", id="profile-label")
                        yield Static("⚙", id="settings-gear")
                with Vertical(id="main"):
                    with Horizontal(id="header"):
                        yield GraphicsImage(display_avatar("blue_drop", MAIN_RGBA), id="h-avatar", classes="h-avatar")
                        yield Label("", id="h-title")
                        yield Label("", id="h-model")
                    with TabbedContent(id="tabs"):
                        with TabPane("对话", id="tab-chat"):
                            yield VerticalScroll(id="chat")
                        with TabPane("记忆", id="tab-memory"):
                            yield MemoryPanel()
                        with TabPane("轨迹", id="tab-trace"):
                            with Vertical(id="trace-pane"):
                                with Horizontal(id="trace-meta"):
                                    yield Label("⏱ 时长", id="tm-dur")
                                    yield Label("🔁 轮次", id="tm-rounds")
                                    yield Label("⚙ 调用", id="tm-calls")
                                    yield Label("", id="tm-filter")
                                    yield Input(placeholder="🔍  tool:名 / user: / 关键词", id="trace-search")
                                yield Vertical(id="timeline")
                                yield VerticalScroll(id="trace-feed")
                    yield Static("", id="thinking")
                    yield SoftField(
                        Input(placeholder="+ 给 LightAgent 发消息…", id="prompt"),
                        fill=FIELD_RGBA,
                        id="composer",
                    )
                    with Horizontal(id="context-dock"):
                        yield Static("", id="ctx-spacer")
                        with Vertical(id="context-popover"):
                            with Horizontal(id="ctx-head"):
                                yield Static("", id="ctx-title")
                                yield Static("", id="ctx-used")
                            yield Static("", id="ctx-bar")
                            yield Static("", id="ctx-rows")
                    with Horizontal(id="stats-bar"):
                        yield Static("", id="stats")
                        yield SoftField(
                            Static("", id="ctx-pct"),
                            fill=PCT_RGBA,
                            focus_fill=None,
                            id="pct-wrap",
                            click_target_id="ctx-pct",
                        )
        yield RowContextMenu(id="row-menu")

    def on_mount(self) -> None:
        self.theme = "textual-light"
        self.query_one("#context-dock").display = False
        self._sync_memory_host()
        self._bind_collaboration()
        self.rebuild_nav()
        self.load_session(self.current)
        self.update_stats()
        if os.environ.get("LIGHTAGENT_TUI_SHOT") == "1":
            # 截图时不要把焦点停在搜索或输入上，避免焦点底色抢画面。
            rows = [row for row in self.query(SessionRow) if row.session is self.current]
            if rows:
                rows[0].focus()
        else:
            self.query_one("#prompt").focus()
        try:
            self.query_one(ShellChrome).paint()
        except Exception:
            pass
        if self._persist:
            self.persist_workspace()
        self._announce_due()

    def _sync_memory_host(self) -> None:
        session = self.current
        bind_host(MemoryHost(
            user_id="local-user",
            namespace="profile",
            session_id=session.id,
            agent_id=session.agent_id,
            space_id=session.space_id or session.project_id,
        ))

    def _bind_collaboration(self) -> None:
        from local.conversations.collaborate import get_runtime

        runtime = get_runtime()
        runtime.enabled = self.collaboration_enabled
        runtime.roster = [meta_from_session(item) for item in self.sessions]
        runtime.mode = "mock" if self.backend.__class__.__name__ == "MockBackend" else "live"
        runtime.depth = 0


    # ---------- 侧栏：项目 / 会话 ----------
    def sessions_in_project(self, project: Project) -> list[Session]:
        ids = set(project.session_ids)
        return [s for s in self.sessions if s.id in ids or s.project_id == project.id]

    def ungrouped_sessions(self) -> list[Session]:
        in_proj = set()
        for project in self.projects:
            in_proj.update(project.session_ids)
            for session in self.sessions:
                if session.project_id == project.id:
                    in_proj.add(session.id)
        return sorted(
            [
                session
                for session in self.sessions
                if session.id not in in_proj and session.project_id is None and not session.hidden
            ],
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def workspace_state(self) -> Workspace:
        return Workspace(
            conversations=[meta_from_session(session) for session in self.sessions],
            projects=[
                ProjectGroup(
                    name=project.name,
                    id=project.id,
                    expanded=project.expanded,
                    session_ids=list(project.session_ids),
                )
                for project in self.projects
            ],
            show_hidden=self._show_hidden,
            collaboration_enabled=self.collaboration_enabled,
        )

    def write_workspace(self, ws: Workspace) -> None:
        by_id = {session.id: session for session in self.sessions}
        kept: list[Session] = []
        for meta in ws.conversations:
            session = by_id.get(meta.id)
            if session is None:
                session = Session(meta.title, id=meta.id, avatar=meta.avatar, accent=meta.accent)
            apply_meta_to_session(session, meta)
            kept.append(session)
        self.sessions = kept
        if self.current.id not in {session.id for session in kept}:
            self.current = kept[0] if kept else self.current
        else:
            self.current = next(session for session in kept if session.id == self.current.id)
        old = {project.id: project for project in self.projects}
        projects: list[Project] = []
        for group in ws.projects:
            project = old.get(group.id) or Project(group.name, id=group.id)
            project.name = group.name
            project.expanded = group.expanded
            project.session_ids = list(group.session_ids)
            projects.append(project)
        self.projects = projects
        self._bind_collaboration()

    def persist_workspace(self) -> None:
        if not self._persist:
            return
        from local.harness.ephemeral import sanitize_transcript

        for session in self.sessions:
            session.messages = sanitize_transcript(session.messages)
        ws = self.workspace_state()
        stored = StoredWorkspace(
            projects=ws.projects,
            conversations=ws.conversations,
            transcripts={
                session.id: Transcript(
                    messages=list(session.messages),
                    events=[[kind, text] for kind, text in session.events],
                    trace=trace_to_dict(session),
                )
                for session in self.sessions
            },
        )
        save_workspace(self._workspace_dir, stored)
        self._save_rooms()

    def _mutate(self, session: Session, action: str, **payload):
        ws = self.workspace_state()
        result = apply_action(ws, session.id, action, **payload)
        if result.ok and not result.needs_confirm:
            self.write_workspace(ws)
            self.persist_workspace()
        return result, ws

    def rebuild_nav(self) -> None:
        from local.rooms.ui import RoomRow, room_preview

        if self._rename_locked:
            self._clear_rename_lock()
        if self._menu_is_open():
            self._hide_menu()

        pinned_box = self.query_one("#pinned-list", Vertical)
        project_box = self.query_one("#project-list", Vertical)
        ungrouped_box = self.query_one("#ungrouped-list", Vertical)
        room_box = self.query_one("#room-list", Vertical)
        pinned_box.remove_children()
        project_box.remove_children()
        ungrouped_box.remove_children()
        room_box.remove_children()
        self.query_one("#room-section", Label).display = True
        for room in self.rooms:
            if room.hidden and not self._show_hidden:
                continue
            room_box.mount(RoomRow(room, room_preview(self.room_messages.get(room.id, []))))
        query = self._nav_filter.strip().lower()
        sections = sidebar_sections(self.workspace_state())
        by_id = {session.id: session for session in self.sessions}

        def matches(session: Session) -> bool:
            if not query:
                return True
            blob = (session.avatar or "").lower()
            haystack = f"{session.title}\n{session.latest_plain}\n{blob}".lower()
            return query in haystack

        pinned = [by_id[meta.id] for meta in sections["pinned"] if meta.id in by_id and matches(by_id[meta.id])]
        self.query_one("#pinned-section", Label).display = bool(pinned)
        self.query_one("#pinned-list", Vertical).display = bool(pinned)
        for session in pinned:
            pinned_box.mount(SessionRow(session, nested=False))
        for group in sections["projects"]:
            project = next((item for item in self.projects if item.id == group["project"].id), None)
            if project is None:
                continue
            members = [by_id[meta.id] for meta in group["sessions"] if meta.id in by_id]
            if query:
                name_hit = query in project.name.lower()
                members = [session for session in members if name_hit or matches(session)]
                if not name_hit and not members:
                    continue
            project_box.mount(ProjectRow(project, members))
        for meta in sections["ungrouped"]:
            session = by_id.get(meta.id)
            if session is None or not matches(session):
                continue
            ungrouped_box.mount(SessionRow(session, nested=False))
        for row in self.query(SessionRow):
            if self.current_room_id is None and row.session is self.current:
                row.add_class("selected")
            else:
                row.remove_class("selected")
        for row in self.query(RoomRow):
            if row.room_id == self.current_room_id:
                row.add_class("selected")
            else:
                row.remove_class("selected")
        hidden_btn = self.query_one("#show-hidden-btn")
        hidden_label = hidden_btn.query_one(".pill-label", Static)
        hidden_label.update("隐藏已隐藏项" if self._show_hidden else "显示已隐藏")
        for row in self.query(SessionRow):
            row._sync_plate(force=True)

    def select_session(self, session: Session) -> None:
        if self._rename_locked:
            return
        self.current = session
        if session.unread:
            self._mutate(session, "mark_read")
            session = self.current
        self._sync_memory_host()
        if session.project_id:
            self.active_project = next((project for project in self.projects if project.id == session.project_id), self.active_project)
        self.load_session(session)
        self.rebuild_nav()
        self.query_one("#prompt").focus()
        self._announce_due()

    def toggle_project(self, project: Project) -> None:
        project.expanded = not project.expanded
        self.active_project = project
        self.rebuild_nav()

    def create_project(self, name: str = "新项目") -> Project:
        # 避免重名
        base = name.strip() or "新项目"
        names = {p.name for p in self.projects}
        n = base
        i = 2
        while n in names:
            n = f"{base} {i}"
            i += 1
        proj = Project(n, expanded=True)
        self.projects.insert(0, proj)
        self.active_project = proj
        self.rebuild_nav()
        self.persist_workspace()
        return proj

    def new_session_in_project(self, project: Project | None = None) -> Session:
        """新建会话。``project is None`` 进未分组「会话」，不回退到当前/演示项目。"""
        used = {x.avatar for x in self.sessions}
        blob_id, accent = pick_unused_blob(used, prefer_index=self._avatar_seq)
        self._avatar_seq += 1
        s = Session("新会话", avatar=blob_id, accent=accent)
        touch(s)
        if project is not None:
            s.project_id = project.id
            s.space_id = project.id
            project.session_ids.insert(0, s.id)
            project.expanded = True
            self.active_project = project
        self.sessions.insert(0, s)
        self.current = s
        self._sync_memory_host()
        self._bind_collaboration()
        self.rebuild_nav()
        self.load_session(s)
        self.persist_workspace()
        self.query_one("#prompt").focus()
        return s

    def action_new_project(self) -> None:
        self.create_project("新项目")

    # ---------- 渲染：对话 ----------
    def empty_state(self) -> Static:
        art = (
            "\n"
            "          ╭──────────╮\n"
            "          │   🤖✨   │\n"
            "          ╰──────────╯\n"
            "\n"
            "     开始一段新对话吧\n"
            "  试试：「帮我查一下上海的天气」\n"
        )
        return Static(art, classes="empty")

    def bubble(self, kind: str, text: str, event_idx: int = -1):
        avatar, accent = "", ""
        if kind == "agent":
            avatar = self.current.avatar
            accent = self.current.accent
        return ChatBubble(
            kind,
            text,
            event_idx if event_idx >= 0 else 0,
            avatar=avatar,
            accent=accent,
        )

    def _map_step_to_event(self, step_index: int) -> int | None:
        """轨迹步骤 → 对话 events 下标（用户/助手/工具芯片）。"""
        s = self.current
        if not (0 <= step_index < len(s.trace.steps)):
            return None
        step = s.trace.steps[step_index]
        if step.kind == "user":
            target = (step.detail or step.summary or "").strip()
            for i, (k, text) in enumerate(s.events):
                if k == "user" and (text == target or text.startswith(step.summary[:16])):
                    return i
        elif step.kind == "assistant":
            detail = (step.detail or step.summary or "").strip()
            for i, (k, text) in enumerate(s.events):
                if k == "agent" and detail and (
                    text == detail or text[:40] == detail[:40] or detail[:40] in text
                ):
                    return i
        elif step.kind == "tool":
            name = step.tool_name or step.summary
            # 第 n 个同名工具事件
            seen = 0
            want = sum(
                1
                for j in range(step_index + 1)
                if s.trace.steps[j].kind == "tool"
                and (s.trace.steps[j].tool_name or s.trace.steps[j].summary) == name
            )
            for i, (k, text) in enumerate(s.events):
                if k == "tool" and name in text:
                    seen += 1
                    if seen == want:
                        return i
        return None

    def focus_chat_event(self, event_idx: int | None) -> bool:
        """在对话区高亮并滚到指定 event；返回是否找到。"""
        chat = self.query_one("#chat", VerticalScroll)
        found = False
        for w in chat.query(ChatBubble):
            if event_idx is not None and w.event_idx == event_idx:
                w.add_class("chat-focused")
                w.scroll_visible(animate=False)
                found = True
            else:
                w.remove_class("chat-focused")
        return found

    # ---------- 渲染：轨迹 ----------
    def select_trace_step(self, index: int) -> None:
        self._selected_step = index
        self.refresh_trace(self.current)
        # 滚到选中行
        for row in self.query(TraceRow):
            if row.step_index == index:
                row.focus()
                row.scroll_visible(animate=False)
                break
        # 同步对话区高亮（切页后仍在）
        ev = self._map_step_to_event(index)
        try:
            self.focus_chat_event(ev)
        except Exception:
            pass

    def toggle_lane_filter(self, lane: str) -> None:
        self._lane_filter = None if self._lane_filter == lane else lane
        self._kind_filter = None
        self._selected_step = None
        self.refresh_trace(self.current)

    def toggle_kind_filter(self, kind: str) -> None:
        self._kind_filter = None if self._kind_filter == kind else kind
        self._lane_filter = None
        self._selected_step = None
        self.refresh_trace(self.current)

    def refresh_trace(self, s: Session | None = None) -> None:
        s = s or self.current
        if s is not self.current:
            return
        st = s.trace.stats
        tool_n = sum(1 for x in s.trace.steps if x.kind == "tool")
        dur_ms = sum(x.duration_ms for x in s.trace.steps)
        self.query_one("#tm-dur", Label).update(f"⏱  {dur_ms/1000:.1f}s")
        self.query_one("#tm-rounds", Label).update(f"🔁  {st.rounds} 轮")
        calls = self.query_one("#tm-calls", Label)
        if self._kind_filter == "tool":
            calls.update(f"⚙  {tool_n} 次调用 ✕")
        else:
            calls.update(f"⚙  {tool_n} 次调用")
        # 筛选提示
        bits = []
        if self._lane_filter:
            bits.append(f"泳道={LANE_LABEL.get(self._lane_filter, self._lane_filter)}")
        if self._kind_filter:
            bits.append(f"类型={self._kind_filter}")
        if self._trace_filter.strip():
            bits.append(f"搜索={self._trace_filter.strip()[:12]}")
        tip = ("筛选: " + " · ".join(bits) + "  Esc清除") if bits else "点色块跳步骤 · 点泳道名筛选 · tool:/user: 搜索 · Enter跳对话"
        self.query_one("#tm-filter", Label).update(f"[#8e8e93]{tip}[/#8e8e93]")

        # 可点击时间线（标签筛泳道；色块跳步骤）
        tl = self.query_one("#timeline", Vertical)
        tl.remove_children()
        segs = s.trace.timeline_segments(width=48)
        for lane in LANE_ORDER:
            lane_w = TimelineLane(lane, segs.get(lane, []), width=48)
            if self._lane_filter == lane:
                lane_w.add_class("active")
            tl.mount(lane_w)

        # feed
        feed = self.query_one("#trace-feed", VerticalScroll)
        feed.remove_children()
        q = self._trace_filter.strip()
        shown = 0
        for i, step in enumerate(s.trace.steps):
            if self._lane_filter and step.lane != self._lane_filter:
                continue
            if self._kind_filter and step.kind != self._kind_filter:
                continue
            if q and not match_trace_query(step, q):
                continue
            row = TraceRow(step, i)
            if self._selected_step == i:
                row.add_class("selected")
            feed.mount(row)
            shown += 1
        if shown == 0:
            if s.trace.steps:
                feed.mount(Static("没有匹配的步骤 · Esc 清除筛选", classes="trace-empty"))
            else:
                feed.mount(Static("暂无轨迹 · 发一条消息后会出现模型 / 工具步骤", classes="trace-empty"))
        else:
            # 有选中则滚到选中，否则滚到底
            if self._selected_step is None:
                feed.scroll_end(animate=False)

    def load_session(self, s: Session) -> None:
        self.current_room_id = None
        self.current = s
        chat = self.query_one("#chat", VerticalScroll)
        chat.remove_children()
        if not s.events:
            chat.mount(self.empty_state())
        for i, (kind, text) in enumerate(s.events):
            chat.mount(self.bubble(kind, text, i))
        chat.scroll_end(animate=False)
        role = (s.identity.role_title or "").strip()
        self.paint_header(s.title, s.avatar, role)
        self.query_one("#h-model", Label).update(model_caption(self.backend.name))
        self.refresh_trace(s)
        self.update_stats()

    def add_event(self, s: Session, kind: str, text: str) -> None:
        s.events.append((kind, text))
        if s is self.current:
            chat = self.query_one("#chat", VerticalScroll)
            for w in chat.query(".empty"):
                w.remove()
            chat.mount(self.bubble(kind, text, len(s.events) - 1))
            chat.scroll_end(animate=False)
        for item in self.query(SessionRow):
            if item.session is s:
                item.refresh_text()

    def _fmt_tokens(self, n: int) -> str:
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}k"
        return str(n)

    def refresh_context_usage(self, s: Session | None = None) -> ContextUsage:
        """按会话内容估算上下文占用（mock）；系统/工具用固定底数，对话随消息增长。"""
        s = s or self.current
        ctx = s.trace.context
        # 对话消息：字符粗估 + 轨迹里已累计的 step tokens 的一部分
        msg_chars = sum(len(str(m.get("content", ""))) for m in s.messages)
        for kind, text in s.events:
            if kind in ("user", "agent", "tool"):
                msg_chars += len(text)
        estimated = max(msg_chars // 3, s.trace.stats.tokens)
        # 有对话时给一个可读底数；不覆盖已手动抬高的演示值（如截图用的 ~88.8K）
        floor = 12_000 if (s.messages or s.events) else 0
        ctx.messages = max(ctx.messages, estimated, floor)
        return ctx

    def _segment_bar(self, ctx: ContextUsage, width: int = 42) -> str:
        """按各类 token 占 limit 的比例画分段条（剩余为空心）。"""
        parts = [
            ("#a1a1aa", ctx.system),
            ("#818cf8", ctx.tools),
            ("#60a5fa", ctx.messages),
        ]
        # 先按 limit 映射到宽度；过小的非零段至少 1 格
        widths = []
        for _, n in parts:
            if n <= 0:
                widths.append(0)
            else:
                widths.append(max(1, int(round(n / ctx.limit * width))))
        # 若合计超出 used 对应宽度，等比压缩
        used_w = max(1, int(round(ctx.used / ctx.limit * width)))
        total = sum(widths)
        if total > used_w and total > 0:
            widths = [max(1 if w else 0, int(round(w * used_w / total))) for w in widths]
            # 微调到 used_w
            while sum(widths) > used_w:
                for i in range(len(widths) - 1, -1, -1):
                    if widths[i] > 1:
                        widths[i] -= 1
                        break
                else:
                    break
        cells = [f"[{c}]{'█' * w}[/{c}]" for (c, _), w in zip(parts, widths) if w]
        empty = max(0, width - sum(widths))
        if empty:
            cells.append(f"[#e4e4e7]{'░' * empty}[/#e4e4e7]")
        return "".join(cells)

    def refresh_context_popover(self, s: Session | None = None) -> None:
        s = s or self.current
        ctx = self.refresh_context_usage(s)
        self.query_one("#ctx-title", Static).update(
            f"上下文已用 [bold #3b82f6]{ctx.pct}%[/bold #3b82f6]"
        )
        self.query_one("#ctx-used", Static).update(
            f"[#8e8e93]{ctx.fmt(ctx.used)} / {ctx.fmt(ctx.limit).lstrip('~')}[/#8e8e93]"
        )
        self.query_one("#ctx-bar", Static).update(self._segment_bar(ctx, width=28))
        sq = "■"
        rows = "\n".join(
            [
                f"[#a1a1aa]{sq}[/#a1a1aa]  系统提示词          [#8e8e93]{ctx.fmt(ctx.system)}[/#8e8e93]",
                f"[#818cf8]{sq}[/#818cf8]  工具定义            [#8e8e93]{ctx.fmt(ctx.tools)}[/#8e8e93]",
                f"[#60a5fa]{sq}[/#60a5fa]  对话消息            [#8e8e93]{ctx.fmt(ctx.messages)}[/#8e8e93]",
            ]
        )
        self.query_one("#ctx-rows", Static).update(rows)
        dock = self.query_one("#context-dock")
        dock.display = self._context_open
        ring = "◉" if self._context_open else "○"
        self.query_one("#ctx-pct", Static).update(f"{ring} {ctx.pct}%")

    def update_stats(self, live_tok_s: float | None = None) -> None:
        s = self.current
        st = s.trace.stats
        used = self.backend.usage()
        tok_s = live_tok_s if live_tok_s is not None else st.tok_per_s
        self._live_tok_s = tok_s
        from local import openrouter_config as orc

        quota = "今日用量" if orc.PROVIDER == "mx" else "今日免费"
        line = f"⚡  {st.rounds}轮 · {st.steps}步 · {quota} {used}/{DAILY_LIMIT}"
        if tok_s:
            line += f"  ·  {tok_s:.0f} tok/s"
        if s.compact_banner:
            line += f"   ·   {s.compact_banner}"
        self.query_one("#stats", Static).update(line)
        self.refresh_context_popover(s)

    def action_toggle_context(self) -> None:
        self._context_open = not self._context_open
        self.refresh_context_popover(self.current)

    # ---------- 交互 ----------
    def _live_context_ratio(self, session: Session) -> float:
        """Ratio that can fall after compaction. The popover keeps its high-water mark."""
        ctx = session.trace.context
        limit = ctx.limit or 1
        msg_chars = sum(len(str(message.get("content", ""))) for message in session.messages)
        for kind, text in session.events:
            if kind in ("user", "agent", "tool"):
                msg_chars += len(text)
        estimated = max(msg_chars // 3, session.trace.stats.tokens)
        floor = 12_000 if (session.messages or session.events) else 0
        used = ctx.system + ctx.tools + max(estimated, floor)
        return used / limit

    def _compact_store_and_host(self, session: Session):
        from local.memory.host import MemoryHost
        from local.memory.store import get_store

        host = MemoryHost(
            user_id="local-user",
            session_id=session.id,
            agent_id=session.agent_id,
            space_id=session.space_id or session.project_id,
        )
        return get_store(), host

    def _apply_compact(self, session: Session, *, trigger: str, focus: str | None) -> None:
        from local.compact.pipeline import run_compact
        from local.compact.types import CompactTrigger

        store, host = self._compact_store_and_host(session)
        try:
            outcome = run_compact(
                session.messages,
                trigger=CompactTrigger(trigger),
                focus=focus,
                store=store,
                host=host,
                space_id=session.space_id or session.project_id,
            )
        except Exception as exc:
            self.add_event(session, "error", f"压缩失败，对话已保留：{exc}")
            return
        session.messages = outcome.messages
        session.pending_skills = list(outcome.procedural_pending)
        session.compact_banner = "上下文已压缩" if trigger == "auto" else outcome.notice
        self.add_event(session, "notice", outcome.notice)
        self.update_stats()
        self.persist_workspace()
        if outcome.procedural_pending:
            self._confirm_skills(session, outcome.procedural_pending)

    def _confirm_skills(self, session: Session, pending) -> None:
        from local.compact.confirm_ui import SkillConfirmScreen
        from local.compact.skill_promote import default_skills_dir, promote_skill

        lines = []
        for item in pending:
            steps = " → ".join(item.steps[:4])
            lines.append(f"· {item.title}：{steps}")
        message = "这些流程可以存成 LightAgent skill，下次直接用。\n\n" + "\n".join(lines)

        def done(accepted: bool | None) -> None:
            if not accepted:
                self.notify("先不存 skill")
                session.pending_skills = []
                return
            root = default_skills_dir()
            written = []
            for item in pending:
                written.append(promote_skill(item, root))
            session.pending_skills = []
            self.notify(f"已保存 {len(written)} 个 skill")
            self.add_event(session, "notice", f"已保存 skill：{', '.join(path.name for path in written)}")

        self.push_screen(SkillConfirmScreen(message), done)

    def _maybe_resume(self, session: Session, text: str) -> None:
        try:
            from local.checkpoints.store import is_resume_request, resume

            if not is_resume_request(text):
                return
            space_id = session.space_id or session.project_id or session.id
            plan = resume(self._workspace_dir, space_id)
        except Exception:
            return
        if plan is not None and plan.notice:
            self.add_event(session, "notice", plan.notice)
            self.notify(plan.notice.split("\n", 1)[0][:80])

    def _absorb_user_constraints(self, text: str) -> None:
        """Write a 1:1 diet sentence onto the constraint card before a goal snapshot."""
        try:
            from local.constraints.extract import absorb_user_text

            absorb_user_text(self._workspace_dir, text)
        except Exception:
            return

    def _maybe_open_goal(self, session: Session, text: str) -> None:
        try:
            from local.goals.store import maybe_open_goal

            space_id = session.space_id or session.project_id or session.id
            maybe_open_goal(self._workspace_dir, space_id, text)
        except Exception:
            return

    def _maybe_advance_step(self, session: Session, text: str) -> None:
        try:
            from local.goals.advance import maybe_advance_goal

            space_id = session.space_id or session.project_id or session.id
            goal = maybe_advance_goal(self._workspace_dir, space_id, text)
        except Exception:
            return
        if goal is None:
            return
        done = ""
        nxt = ""
        for step in goal.steps:
            if step.status == "completed":
                done = step.title
            elif step.status == "in_progress":
                nxt = step.title
                break
        if done and nxt:
            notice = f"已完成：{done} → 下一步：{nxt}"
        elif done and goal.status == "completed":
            notice = f"已完成：{done} → 这项目标的步骤都完成了"
        else:
            return
        self.add_event(session, "notice", notice)
        self.notify(notice[:80])

    def _maybe_auto_compact(self, session: Session) -> None:
        from local.compact.policy import should_auto_compact

        try:
            if should_auto_compact(self._live_context_ratio(session)):
                self._apply_compact(session, trigger="auto", focus=None)
        except Exception:
            return

    def _active_space_id(self) -> str:
        if self.current_room_id:
            room = next((item for item in self.rooms if item.id == self.current_room_id), None)
            if room is not None:
                return room.space_id or room.id
        session = self.current
        return session.space_id or session.project_id or session.id

    def _announce_due(self) -> None:
        """List due reminders when the app or a session opens. No model call.

        Quiet hours and a repeated due set stay silent. Confirm still runs the routine.
        """
        try:
            from local.routines.due import take_due_notices

            payload = take_due_notices(self._workspace_dir, space_id=self._active_space_id())
        except Exception:
            return
        for notice in payload.get("notices") or []:
            self.notify(notice)

    def _show_routine_note(self, user_text: str, notice: str) -> None:
        if self.current_room_id:
            self._append_room_note(user_text, notice)
            return
        session = self.current
        touch(session)
        self.add_event(session, "user", user_text)
        self.add_event(session, "notice", notice)
        self.persist_workspace()
        self.notify(notice.split("\n", 1)[0][:80])

    def _append_room_note(self, user_text: str, notice: str) -> None:
        import time

        from local.rooms.types import RoomMessage, new_id

        room = next((item for item in self.rooms if item.id == self.current_room_id), None)
        if room is None:
            return
        messages = self.room_messages.setdefault(room.id, [])
        messages.append(RoomMessage(
            id=new_id(),
            role="user",
            speaker="user",
            speaker_label="用户",
            content=user_text,
            ts=time.time(),
            kind="chat",
        ))
        messages.append(RoomMessage(
            id=new_id(),
            role="assistant",
            speaker="host",
            speaker_label="生活助手",
            content=notice,
            ts=time.time(),
            kind="system_notice",
        ))
        self.load_room(room)
        self._save_rooms()
        self.notify(notice.split("\n", 1)[0][:80])

    def _routine_runner(self, instruction: str, *, budget_limits, cancellation_token):
        """Confirm path. Mock and the forbid gate never call a model."""
        import os

        if os.environ.get("LIGHTAGENT_FORBID_OPENROUTER") == "1" or self.backend.__class__.__name__ == "MockBackend":
            return f"已确认提醒，这次不调用模型：{instruction}"
        from local.checkpoints.store import record_run_event
        from local.harness.run_control import execute_controlled
        from local.openrouter_config import _check_and_count, make_agent

        _check_and_count()
        agent = make_agent(budget_limits=budget_limits)
        space = self._active_space_id()

        def on_event(name, payload):
            record_run_event(space, name, detail=str((payload or {}).get("notice") or ""))

        outcome = execute_controlled(
            agent,
            instruction,
            cancellation_token=cancellation_token,
            on_event=on_event,
        )
        return outcome.content

    def _confirm_due_routine(self, text: str) -> bool:
        from local.routines.due import confirm_first_due

        try:
            result = confirm_first_due(
                self._workspace_dir,
                space_id=self._active_space_id(),
                runner=self._routine_runner,
            )
        except Exception as exc:
            self._show_routine_note(text, f"这次没能执行提醒：{exc}")
            return True
        if not result.get("ok"):
            self._show_routine_note(text, "现在没有到点的提醒。")
            return True
        routine = result["routine"]
        content = result.get("content") or f"已确认「{routine.title}」。"
        self._show_routine_note(text, str(content))
        return True

    def _pause_or_delete_routine(self, text: str, verb: str, needle: str) -> bool:
        from local.routines.store import RoutineStore

        if not needle:
            self._show_routine_note(text, "说「暂停提醒」或「删除提醒」，后面加上名字。")
            return True
        store = RoutineStore(self._workspace_dir)
        space = self._active_space_id()
        rows = [
            item
            for item in store.list_routines()
            if (not item.owner_space or item.owner_space == space)
            and (needle in item.title or needle in item.instruction)
        ]
        if not rows:
            self._show_routine_note(text, "没有找到这个提醒。")
            return True
        target = rows[0]
        if verb == "delete":
            store.delete(target.id)
            self._show_routine_note(text, f"已删除提醒：{target.title}。")
        else:
            store.pause(target.id)
            self._show_routine_note(text, f"已暂停提醒：{target.title}。")
        return True

    def _consume_routine(self, text: str) -> bool:
        """Explicit routine turns stay off the model path."""
        try:
            from local.routines.detect import parse_routine, routine_action
        except Exception:
            return False
        action = routine_action(text)
        if action is not None:
            verb, needle = action
            if verb == "confirm":
                return self._confirm_due_routine(text)
            return self._pause_or_delete_routine(text, verb, needle)
        parsed = parse_routine(text)
        if parsed is None:
            return False
        from local.routines.due import create_explicit

        try:
            created = create_explicit(
                self._workspace_dir,
                text,
                owner_space=self._active_space_id(),
            )
        except Exception as exc:
            self._show_routine_note(text, f"没能记下提醒：{exc}")
            return True
        routine = created.get("routine")
        if not created.get("created"):
            title = routine.title if routine is not None else parsed["title"]
            self._show_routine_note(text, f"已经有这条提醒：{title}。不会再记一条。")
            return True
        self._show_routine_note(
            text,
            f"已记下提醒：{routine.title}。到点打开时会列出来，确认后才跑。",
        )
        return True

    @on(Input.Submitted, "#prompt")
    def send(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self.busy:
            return
        event.input.value = ""
        if self._consume_routine(text):
            return
        if self.current_room_id:
            self._send_room_turn(text)
            return
        s = self.current
        from local.compact.chat_commands import parse_compact_command

        command = parse_compact_command(text)
        if command is not None:
            self.add_event(s, "user", text)
            self._apply_compact(s, trigger="manual", focus=command.focus)
            return
        if s.title == "新会话" and not s.messages:
            s.title = text[:12]
            self.paint_header(s.title, s.avatar, (s.identity.role_title or "").strip())
            for item in self.query(SessionRow):
                if item.session is s:
                    item.refresh_text()
        touch(s)
        self._maybe_resume(s, text)
        self._absorb_user_constraints(text)
        self._maybe_open_goal(s, text)
        self._maybe_advance_step(s, text)
        self._maybe_auto_compact(s)
        history = list(s.messages)
        # 用户步写入轨迹
        s.trace.add(
            TraceStep(
                kind="user",
                summary=text[:80],
                detail=text,
                tokens=max(8, len(text) // 2),
                duration_ms=0,
                lane="input",
            )
        )
        self.add_event(s, "user", text)
        self.refresh_trace(s)
        self.busy = True
        begin = getattr(self.backend, "begin_run", None)
        if begin is not None:
            begin()
        self.query_one("#thinking", Static).update("⠋  LightAgent 思考中…")
        self.update_stats(live_tok_s=12.0)
        self.ask(s, history, text)

    @work(thread=True, exclusive=True)
    def ask(self, s: Session, history: list[dict], text: str) -> None:
        # 模拟流式期间刷新 tok/s（仅 UI；mock 不耗额度）
        import time as _t

        for i, rate in enumerate((18.0, 34.0, 52.0, 61.0)):
            _t.sleep(0.12)
            self.call_from_thread(self.update_stats, rate)
            self.call_from_thread(
                self.query_one("#thinking", Static).update,
                f"{'⠋⠙⠹⠸⠼⠴⠦⠧'[i % 8]}  LightAgent 思考中…  {rate:.0f} tok/s",
            )
        try:
            reply = self.backend.chat(history, text, turn=self.turn_context(s))
        except Exception as e:  # 包括本地额度保护抛出的错误
            self.call_from_thread(self.finish, s, text, None, str(e))
            return
        self.call_from_thread(self.finish, s, text, reply, None)

    def finish(self, s: Session, text: str, reply, error: str | None) -> None:
        self.busy = False
        self.query_one("#thinking", Static).update("")
        if error:
            s.trace.add(
                TraceStep(
                    kind="error",
                    summary=error[:100],
                    detail=error,
                    status="error",
                    lane="other",
                )
            )
            self.add_event(s, "error", error)
        else:
            for step in reply.steps:
                s.trace.add(step)
            for call in reply.tool_calls:
                self.add_event(s, "tool", call)
            from local.harness.ephemeral import clean_persisted_text

            self.add_event(s, "agent", reply.content)
            s.messages += [
                {"role": "user", "content": clean_persisted_text(text)},
                {"role": "assistant", "content": clean_persisted_text(reply.content)},
            ]
            # 统计（tokens 已在 TraceStore.add 里按 step 累加，这里不再重复加）
            st = s.trace.stats
            st.rounds += 1
            turn_tok = reply.tokens_in + reply.tokens_out
            if reply.duration_ms > 0 and turn_tok > 0:
                st.tok_per_s = round(turn_tok / (reply.duration_ms / 1000), 1)
            # 滚动平均缓存命中
            if st.rounds == 1:
                st.cache_hit_pct = reply.cache_hit_pct
            else:
                st.cache_hit_pct = round(
                    (st.cache_hit_pct * (st.rounds - 1) + reply.cache_hit_pct) / st.rounds, 1
                )
            self.query_one("#h-model", Label).update(model_caption(getattr(reply, "model", "") or self.backend.name))
        touch(s)
        self._maybe_auto_compact(s)
        self.refresh_trace(s)
        self.update_stats()
        self.rebuild_nav()
        self.persist_workspace()

    @on(Input.Changed, "#search")
    def filter_sessions(self, event: Input.Changed) -> None:
        self._nav_filter = event.value
        self.rebuild_nav()

    @on(Input.Changed, "#trace-search")
    def filter_trace(self, event: Input.Changed) -> None:
        self._trace_filter = event.value
        self.refresh_trace(self.current)

    def _clicked_id(self, widget) -> str | None:
        """点在预渲端盖上时，id 在父胶囊上，不在那张图上。"""
        known = {
            "new-btn",
            "new-project-btn",
            "settings-gear",
            "ctx-pct",
            "tm-calls",
            "show-hidden-btn",
            "group-chat-btn",
        }
        while widget is not None and widget is not self:
            wid = getattr(widget, "id", None)
            if wid in known:
                return wid
            alias = getattr(widget, "click_target_id", None)
            if alias in known:
                return alias
            widget = getattr(widget, "parent", None)
        return None

    def on_click(self, event) -> None:
        if self._rename_locked:
            return
        wid = self._clicked_id(event.widget)
        if wid == "new-btn":
            self.new_session_in_project(None)
        elif wid == "new-project-btn":
            self.create_project("新项目")
        elif wid == "settings-gear":
            self.action_open_settings()
        elif wid == "ctx-pct":
            self.action_toggle_context()
        elif wid == "tm-calls":
            self.toggle_kind_filter("tool")
        elif wid == "show-hidden-btn":
            self._show_hidden = not self._show_hidden
            self.rebuild_nav()
        elif wid == "group-chat-btn":
            self.open_create_room()

    def _load_rooms(self) -> None:
        from local.rooms.store import load_rooms, load_transcript

        self.rooms = load_rooms(self._workspace_dir)
        self.room_messages = {}
        self.room_traces = {}
        for room in self.rooms:
            messages, trace = load_transcript(self._workspace_dir, room.id)
            self.room_messages[room.id] = messages
            self.room_traces[room.id] = trace or {"steps": []}

    def _save_rooms(self) -> None:
        if not self._persist:
            return
        from local.rooms.digest import prepare_room_transcript
        from local.rooms.store import save_rooms, save_transcript

        save_rooms(self._workspace_dir, self.rooms)
        for room in self.rooms:
            original = list(self.room_messages.get(room.id, []))
            try:
                messages = prepare_room_transcript(
                    original,
                    workspace=self._workspace_dir,
                    room_id=room.id,
                )
            except Exception:
                messages = original
            self.room_messages[room.id] = messages
            save_transcript(
                self._workspace_dir,
                room.id,
                messages,
                self.room_traces.get(room.id) or {"steps": []},
            )

    def open_create_room(self) -> None:
        from local.rooms.ui import CreateRoomScreen

        bots = [meta_from_session(session) for session in self.sessions]
        self.push_screen(CreateRoomScreen(bots), self._on_room_created)

    def _on_room_created(self, payload: dict | None) -> None:
        if not payload:
            return
        from local.rooms.actions import RoomError, create_room, welcome_message

        try:
            room = create_room(
                payload.get("title") or "健康日常",
                list(payload.get("member_bot_ids") or []),
                scenario_hints=list(payload.get("scenario_hints") or []),
            )
        except RoomError as exc:
            self.notify(str(exc))
            return
        roster = [meta_from_session(session) for session in self.sessions]
        self.rooms.insert(0, room)
        self.room_messages[room.id] = [welcome_message(room, roster)]
        self.room_traces[room.id] = {"steps": []}
        self._save_rooms()
        self.open_room(room.id)

    def open_room(self, room_id: str) -> None:
        if self._rename_locked:
            return
        room = next((item for item in self.rooms if item.id == room_id), None)
        if room is None:
            return
        room.unread = False
        self.current_room_id = room.id
        self.load_room(room)
        self.rebuild_nav()
        self._save_rooms()
        self.query_one("#prompt", Input).focus()
        self._announce_due()

    def load_room(self, room) -> None:
        from local.rooms.ui import member_labels

        self.current_room_id = room.id
        chat = self.query_one("#chat", VerticalScroll)
        chat.remove_children()
        messages = self.room_messages.get(room.id, [])
        if not messages:
            chat.mount(Static("群里还没有消息。", classes="empty"))
        for index, message in enumerate(messages):
            chat.mount(self._room_bubble(message, index))
        chat.scroll_end(animate=False)
        roster = [meta_from_session(session) for session in self.sessions]
        names = " · ".join(member_labels(room, roster))
        self.paint_header(room.title, "blue_drop", names)
        self.query_one("#h-model", Label).update("群聊 · 规则主持")
        self.query_one("#thinking", Static).update("")

    def _room_bubble(self, message, index: int) -> ChatBubble:
        if message.speaker == "user":
            kind, speaker_class = "user", "user"
        elif message.kind == "error":
            kind, speaker_class = "error", "system"
        elif message.kind == "system_notice":
            kind, speaker_class = "notice", "system"
        elif message.kind == "host_summary" or message.speaker == "host":
            kind, speaker_class = "agent", "host"
        else:
            kind, speaker_class = "agent", "bot"
        avatar, accent = "", ""
        if kind == "agent":
            avatar, accent = self._avatar_for_speaker(message.speaker)
        return ChatBubble(
            kind,
            message.content,
            index,
            message.speaker_label,
            speaker_class,
            avatar=avatar,
            accent=accent,
        )

    def _avatar_for_speaker(self, speaker: str) -> tuple[str, str]:
        """群聊发言人 → 成员会话的 blob；host 用蓝滴。"""
        if speaker == "host" or speaker.startswith("host"):
            return "blue_drop", "#3b82f6"
        bot_id = speaker.split(":", 1)[-1] if ":" in speaker else speaker
        for session in self.sessions:
            if session.id == bot_id or session.agent_id == bot_id:
                return session.avatar, session.accent
        return "blue_tri", "#2563eb"

    def _send_room_turn(self, text: str) -> None:
        import os

        from local.conversations.collaborate import get_runtime
        from local.memory.host import MemoryHost
        from local.memory.inject import prepare_turn
        from local.rooms.runtime import run_user_turn

        room = next((item for item in self.rooms if item.id == self.current_room_id), None)
        if room is None:
            return
        messages = self.room_messages.setdefault(room.id, [])
        trace = self.room_traces.setdefault(room.id, {"steps": []})
        thinking = self.query_one("#thinking", Static)
        roster = [meta_from_session(session) for session in self.sessions]
        runtime = get_runtime()
        runtime.roster = roster
        mode = "mock"
        if self.backend.__class__.__name__ != "MockBackend" and os.environ.get("LIGHTAGENT_ALLOW_OPENROUTER") == "1":
            mode = "live"
        profile_block = ""
        try:
            prepared = prepare_turn(
                system="",
                history=[],
                user_text=text,
                host=MemoryHost(
                    user_id="local-user",
                    session_id=room.id,
                    agent_id="room-host",
                    space_id=room.space_id,
                ),
                persona_text="",
                identity_block="",
                share_user_profile=True,
            )
            profile_block = prepared.ephemeral or ""
        except Exception:
            profile_block = ""

        def status(line: str) -> None:
            thinking.update(line)

        run_user_turn(
            room,
            text,
            roster,
            messages,
            quota=runtime.quota,
            mode=mode,
            profile_block=profile_block,
            status=status,
            trace=trace,
        )
        thinking.update("")
        self.load_room(room)
        self.rebuild_nav()
        self._save_rooms()

    def consume_blocked_pointer(self, event) -> bool:
        """Swallow pointer events that would dismiss a just-opened menu or switch sessions mid-rename.

        Pilot and the real driver both enter through ``Screen._forward_event``.
        A right-click is MouseDown plus a later MouseUp/Click on the row; that
        trailing click must not close the menu it just opened. An outside press
        closes the menu and eats the rest of that gesture so the row underneath
        is not selected. Rename only accepts Enter and Esc.
        """
        from textual.events import Click, MouseDown, MouseUp

        if not isinstance(event, (MouseDown, MouseUp, Click)):
            return False
        if self._rename_locked:
            return not self._pointer_on_rename_field(event)

        if isinstance(event, MouseDown):
            self._suppress_menu_click = False
            self._menu_swallow_click = False
            if self._menu_is_open() and not self._pointer_on_menu(event):
                if is_right_button(event):
                    self._hide_menu()
                    return False
                self.dismiss_row_menu()
                self._menu_swallow_click = True
                return True
            return False

        if self._suppress_menu_click or self._menu_swallow_click:
            if isinstance(event, Click):
                self._suppress_menu_click = False
                self._menu_swallow_click = False
            return True
        if self._menu_is_open() and isinstance(event, Click) and not self._pointer_on_menu(event):
            self.dismiss_row_menu()
            return True
        return False

    def _event_xy(self, event) -> tuple[int, int] | None:
        try:
            return int(event.x), int(event.y)
        except Exception:
            return None

    def _pointer_widget(self, event):
        xy = self._event_xy(event)
        if xy is None:
            return None
        try:
            widget, _region = self.screen.get_widget_at(*xy)
        except Exception:
            return None
        return widget

    def _pointer_inside(self, widget, event) -> bool:
        if widget is None:
            return False
        target = self._pointer_widget(event)
        if target is None:
            return False
        if target is widget:
            return True
        return widget in getattr(target, "ancestors", ())

    def _row_menu(self) -> RowContextMenu | None:
        try:
            return self.query_one("#row-menu", RowContextMenu)
        except Exception:
            return None

    def _menu_is_open(self) -> bool:
        menu = self._row_menu()
        return bool(menu is not None and menu.display)

    def _pointer_on_menu(self, event) -> bool:
        menu = self._row_menu()
        if menu is None or not menu.display:
            return False
        return self._pointer_inside(menu, event)

    def _rename_field(self) -> TitleInput | None:
        row = self._rename_row
        if row is None:
            return None
        try:
            return row.query_one(TitleInput)
        except Exception:
            return None

    def _pointer_on_rename_field(self, event) -> bool:
        return self._pointer_inside(self._rename_field(), event)

    def _session_row(self, session: Session):
        for row in self.query(SessionRow):
            if row.session.id == session.id and not row._pruning:
                return row
        return None

    def _focus_session_row(self, session: Session) -> None:
        row = self._session_row(session)
        if row is not None:
            row.focus()

    def _focus_room_row(self, room_id: str) -> None:
        from local.rooms.ui import RoomRow

        row = next((item for item in self.query(RoomRow) if item.room_id == room_id and not item._pruning), None)
        if row is not None:
            row.focus()

    def open_row_menu(self, anchor, entries, callback, *, from_mouse: bool = False) -> None:
        if self._rename_locked or anchor is None:
            return
        menu = self._row_menu()
        if menu is None:
            return
        self._tgp_hold = True
        self._menu_callback = callback
        self._menu_anchor = anchor
        self._suppress_menu_click = bool(from_mouse)
        menu.show_entries(entries)
        self._place_menu(menu, anchor)
        self.call_after_refresh(self._settle_menu)

    def _menu_offset(self, anchor) -> Offset:
        try:
            main = self.query_one("#main")
            x = max(0, main.region.x - 4)
        except Exception:
            x = max(0, anchor.region.x)
        return Offset(x, max(0, anchor.region.y))

    def _clamp_offset(self, offset: Offset, menu: RowContextMenu) -> Offset:
        width = menu.region.width
        height = menu.region.height
        if width <= 0 or height <= 0:
            return offset
        size = self.screen.size
        x, y = offset.x, offset.y
        if x + width > size.width:
            x = max(0, size.width - width)
        if y + height > size.height:
            y = max(0, size.height - height)
        return Offset(x, y)

    def _place_menu(self, menu: RowContextMenu, anchor) -> None:
        menu.absolute_offset = self._clamp_offset(self._menu_offset(anchor), menu)
        menu.refresh(layout=True)

    def _sync_open_menu(self) -> None:
        menu = self._row_menu()
        anchor = self._menu_anchor
        if menu is None or not menu.display or anchor is None:
            return
        try:
            if not anchor.is_attached or anchor._pruning:
                return
        except Exception:
            return
        desired = self._clamp_offset(self._menu_offset(anchor), menu)
        if menu.absolute_offset == desired:
            return
        menu.absolute_offset = desired
        menu.refresh(layout=True)
        rewrite_character_plane(self)

    def _settle_menu(self, *, retry: bool = True) -> None:
        menu = self._row_menu()
        anchor = self._menu_anchor
        if menu is None or not menu.display or anchor is None:
            return
        try:
            if not anchor.is_attached or anchor._pruning:
                return
        except Exception:
            return
        # Shell margin lands a frame after mount. Place again once layout has caught up.
        self._place_menu(menu, anchor)
        actions = [item for item in menu.query(MenuAction) if not item._pruning]
        if retry:
            self.call_after_refresh(lambda: self._settle_menu(retry=False))
            return
        self._clamp_menu(menu)
        if actions and not any(item.has_focus for item in actions):
            actions[0].focus(False)
        rewrite_character_plane(self)

    def _clamp_menu(self, menu: RowContextMenu) -> None:
        anchor = self._menu_anchor
        if anchor is None:
            return
        self._place_menu(menu, anchor)

    def _hide_menu(self) -> None:
        self._menu_callback = None
        self._menu_anchor = None
        menu = self._row_menu()
        if menu is not None:
            menu.hide()
        self._tgp_hold = False
        self._apply_pending_tgp()
        self.call_after_refresh(self.rewrite_character_plane)

    def rewrite_character_plane(self) -> None:
        rewrite_character_plane(self)

    def _apply_pending_tgp(self) -> None:
        """菜单关掉之后补做被冻住的壳图、胶囊和行端盖。"""
        if self._tgp_hold:
            return
        pending_chrome = [widget for widget in self.query(ShellChrome) if getattr(widget, "_tgp_pending", False)]
        pending_fields = [widget for widget in self.query(SoftField) if getattr(widget, "_tgp_pending", False)]
        pending_buttons = [widget for widget in self.query(SoftButton) if getattr(widget, "_tgp_pending", False)]
        pending_rows = [widget for widget in self.query(SessionRow) if getattr(widget, "_tgp_pending", False)]
        for widget in pending_chrome:
            widget._tgp_pending = False
            widget.paint()
        for widget in pending_fields:
            widget._tgp_pending = False
            widget._repaint()
        for widget in pending_buttons:
            widget._tgp_pending = False
            widget._repaint()
        for widget in pending_rows:
            widget._tgp_pending = False
            widget._sync_plate(force=True)

    def dismiss_row_menu(self) -> None:
        anchor = self._menu_anchor
        self._hide_menu()
        if anchor is not None:
            try:
                if anchor.is_attached and not anchor._pruning:
                    anchor.focus()
            except Exception:
                pass

    def pick_row_menu(self, action_id: str) -> None:
        callback = self._menu_callback
        self._hide_menu()
        if callback is not None:
            callback(action_id)

    def _start_rename(self, row, kind: str, target_id: str, title: str) -> None:
        if self._rename_locked or row is None:
            return
        self._rename_locked = True
        self._rename_kind = kind
        self._rename_target_id = target_id
        self._rename_row = row
        try:
            begin_title_edit(row, title)
        except Exception:
            self._clear_rename_lock()
            raise

    def _clear_rename_lock(self) -> None:
        row = self._rename_row
        self._rename_locked = False
        self._rename_row = None
        self._rename_kind = None
        self._rename_target_id = None
        if row is not None:
            end_title_edit(row)

    def cancel_title_edit(self) -> None:
        row = self._rename_row
        self._clear_rename_lock()
        if row is not None:
            try:
                if row.is_attached and not row._pruning:
                    row.focus(False)
            except Exception:
                pass

    def commit_title_edit(self, raw: str) -> None:
        title = (raw or "").strip()
        if not title:
            self.notify("名称不能为空")
            field = self._rename_field()
            if field is not None:
                field.focus()
                field.select_all()
            return
        kind = self._rename_kind
        target_id = self._rename_target_id
        self._clear_rename_lock()
        if kind == "session":
            session = next((item for item in self.sessions if item.id == target_id), None)
            if session is None:
                return
            previous = session.id
            result, _ws = self._mutate(session, "rename", title=title)
            if not result.ok:
                self.notify(result.message)
                return
            if session.id != previous:
                self.notify("重命名不应改变 id")
            self.rebuild_nav()
            if self.current.id == session.id:
                self.load_session(self.current)
            self._focus_session_row(session)
            return
        if kind == "room":
            from local.rooms.actions import RoomError, rename_room

            room = next((item for item in self.rooms if item.id == target_id), None)
            if room is None:
                return
            try:
                rename_room(room, title)
            except RoomError as exc:
                self.notify(str(exc))
                return
            self.rebuild_nav()
            if self.current_room_id == room.id:
                self.load_room(room)
            self._save_rooms()
            self._focus_room_row(room.id)

    def open_room_menu(self, room_id: str, *, from_mouse: bool = False) -> None:
        from local.conversations.context_menu import MenuEntry
        from local.rooms.ui import RoomRow

        if self._rename_locked:
            return
        row = next((item for item in self.query(RoomRow) if item.room_id == room_id), None)
        if row is None:
            return
        entries = [
            MenuEntry("rename", "重命名群"),
            MenuEntry("members", "管理成员"),
            MenuEntry("delete", "删除群"),
        ]
        self.open_row_menu(
            row,
            entries,
            lambda action: self._on_room_menu(room_id, action),
            from_mouse=from_mouse,
        )

    def _on_room_menu(self, room_id: str, action: str | None) -> None:
        if not action:
            return
        room = next((item for item in self.rooms if item.id == room_id), None)
        if room is None:
            return
        if action == "rename":
            self._rename_room(room)
        elif action == "members":
            self._manage_room_members(room)
        elif action == "delete":
            self._confirm_delete_room(room)

    def _rename_room(self, room) -> None:
        from local.rooms.ui import RoomRow

        row = next((item for item in self.query(RoomRow) if item.room_id == room.id), None)
        if row is None:
            return
        self._start_rename(row, "room", room.id, room.title)

    def _manage_room_members(self, room) -> None:
        from local.rooms.actions import RoomError, set_members
        from local.rooms.ui import ManageMembersScreen

        bots = [meta_from_session(session) for session in self.sessions]

        def done(chosen: list[str] | None) -> None:
            if not chosen:
                return
            try:
                set_members(room, chosen)
            except RoomError as exc:
                self.notify(str(exc))
                return
            self.rebuild_nav()
            if self.current_room_id == room.id:
                self.load_room(room)
            self._save_rooms()

        self.push_screen(ManageMembersScreen(bots, list(room.member_bot_ids)), done)

    def _confirm_delete_room(self, room) -> None:
        from local.rooms.actions import delete_room
        from local.rooms.store import delete_transcript
        from local.tui.identity_ui import ConfirmScreen

        def done(confirmed: bool | None) -> None:
            if not confirmed:
                return
            self.rooms = delete_room(self.rooms, room.id)
            self.room_messages.pop(room.id, None)
            self.room_traces.pop(room.id, None)
            if self._persist:
                delete_transcript(self._workspace_dir, room.id)
                self._save_rooms()
            if self.current_room_id == room.id:
                self.current_room_id = None
                self.load_session(self.current)
            else:
                self.rebuild_nav()

        self.push_screen(ConfirmScreen(f"删除群聊「{room.title}」？成员自己的对话会留着。", title="删除群聊"), done)

    def turn_context(self, session: Session):
        from local.tui.backend import TurnContext

        self._bind_collaboration()
        meta = meta_from_session(session)
        persona_text, identity_block = blocks_for_meta(meta)
        from local.conversations.collaborate import get_runtime

        runtime = get_runtime()
        return TurnContext(
            identity_block=identity_block,
            persona_text=persona_text,
            share_user_profile=session.share_user_profile,
            session_id=session.id,
            agent_id=session.agent_id,
            space_id=session.space_id or session.project_id,
            collaboration_enabled=self.collaboration_enabled,
            roster=list(runtime.roster),
            quota=runtime.quota,
        )

    def open_session_menu(self, session: Session, *, from_mouse: bool = False) -> None:
        if self._rename_locked:
            return
        row = self._session_row(session)
        if row is None:
            return
        entries = menu_entries(meta_from_session(session))
        self.open_row_menu(
            row,
            entries,
            lambda action: self._on_menu(session, action),
            from_mouse=from_mouse,
        )

    def _on_menu(self, session: Session, action: str | None) -> None:
        if not action:
            return
        if action == "rename":
            self._rename_session(session)
            return
        if action == "move":
            self._move_session(session)
            return
        if action == "set_identity":
            self.open_identity_editor(session)
            return
        if action == "delete":
            self.confirm_delete_session(session)
            return
        if action == "copy_id":
            result, _ws = self._mutate(session, "copy_id")
            copied = result.copied_id or session.id
            try:
                self.copy_to_clipboard(copied)
            except Exception:
                pass
            self.notify(f"对话 ID：{copied}")
            self._focus_session_row(session)
            return
        result, _ws = self._mutate(session, action)
        if not result.ok:
            self.notify(result.message)
            return
        self.rebuild_nav()
        if session.id == self.current.id:
            self.load_session(self.current)
        self._focus_session_row(session)

    def _rename_session(self, session: Session) -> None:
        row = self._session_row(session)
        if row is None:
            return
        self._start_rename(row, "session", session.id, session.title)

    def _move_session(self, session: Session) -> None:
        from local.tui.identity_ui import NewGroupScreen

        row = self._session_row(session)
        if row is None:
            return
        entries = move_targets(self.workspace_state(), meta_from_session(session))

        def done(choice: str | None) -> None:
            if not choice:
                return
            if choice == "new_project":
                self.push_screen(NewGroupScreen(), lambda name: self._finish_new_group(session, name))
                return
            if choice == "ungroup":
                self._mutate(session, "ungroup")
            elif choice.startswith("project:"):
                self._mutate(session, "move", project_id=choice.split(":", 1)[1])
            self.rebuild_nav()
            self.load_session(self.current)
            self._focus_session_row(session)

        self.open_row_menu(row, entries, done)

    def _finish_new_group(self, session: Session, name: str | None) -> None:
        if not name:
            return
        self._mutate(session, "move", new_project_name=name)
        self.rebuild_nav()
        self.load_session(self.current)

    def open_identity_editor(self, session: Session | None = None) -> None:
        from local.tui.identity_ui import IdentityEditorScreen

        session = session or self.current

        def done(payload: dict | None) -> None:
            if not payload:
                return
            self._mutate(
                session,
                "set_identity",
                identity=payload["identity"],
                share_user_profile=payload["share_user_profile"],
            )
            self.rebuild_nav()
            self.load_session(self.current)
            role = payload["identity"].role_title or "（未填职位）"
            self.notify(f"已保存身份：{role}")

        self.push_screen(
            IdentityEditorScreen(session.identity, share_user_profile=session.share_user_profile),
            done,
        )

    def confirm_delete_session(self, session: Session) -> None:
        from local.tui.identity_ui import ConfirmScreen

        probe, _ws = self._mutate(session, "delete", confirm=False)
        if not probe.needs_confirm:
            return

        def done(confirmed: bool | None) -> None:
            if not confirmed:
                self._mutate(session, "delete_cancel")
                return
            deleted = session.id
            self._mutate(session, "delete", confirm=True)
            if not self.sessions:
                blob_id, accent = pick_unused_blob(set(), prefer_index=self._avatar_seq)
                self._avatar_seq += 1
                blank = Session("新会话", avatar=blob_id, accent=accent)
                self.sessions = [blank]
            if self.current.id == deleted or self.current not in self.sessions:
                self.current = self.sessions[0]
            self._sync_memory_host()
            self.rebuild_nav()
            self.load_session(self.current)
            self.persist_workspace()

        self.push_screen(ConfirmScreen(probe.message), done)

    def action_edit_identity(self) -> None:
        self.open_identity_editor(self.current)

    def paint_header(self, title: str, avatar_id: str, suffix: str = "") -> None:
        avatar_id = avatar_id or "blue_drop"
        avatar = self.query_one("#h-avatar")
        avatar.image = display_avatar(avatar_id, MAIN_RGBA)
        fit_graphics_widget(avatar)
        self.query_one("#h-title", Label).update(format_header(title, avatar_id, suffix))

    async def action_new_session(self) -> None:
        # Ctrl+N / 顶栏 + ：未分组「会话」，不钻进项目。
        if self._rename_locked:
            return
        self.new_session_in_project(None)


    def action_focus_search(self) -> None:
        self.query_one("#search").focus()

    def action_stop_run(self) -> None:
        """协作边界停止。不杀线程；进行中的 run 在模型/工具边界停下。"""
        from local.harness.run_control import USER_CANCEL_NOTICE

        if not self.busy:
            return
        cancel = getattr(self.backend, "cancel_active", None)
        if cancel is None:
            return
        cancel(reason="user_cancel")
        self.notify(USER_CANCEL_NOTICE)

    def action_clear(self) -> None:
        self.current.messages.clear()
        self.current.events.clear()
        self.current.trace.clear()
        self._lane_filter = None
        self._kind_filter = None
        self._selected_step = None
        self._trace_filter = ""
        self.load_session(self.current)

    def action_tab_chat(self) -> None:
        self.query_one("#tabs", TabbedContent).active = "tab-chat"

    def action_tab_trace(self) -> None:
        self.query_one("#tabs", TabbedContent).active = "tab-trace"
        self.refresh_trace(self.current)

    def action_tab_memory(self) -> None:
        self.query_one("#tabs", TabbedContent).active = "tab-memory"
        try:
            self.query_one(MemoryPanel).refresh_rows()
        except Exception:
            pass

    def action_focus_trace_search(self) -> None:
        self.action_tab_trace()
        self.query_one("#trace-search").focus()

    def action_clear_trace_filters(self) -> None:
        if self._rename_locked:
            self.cancel_title_edit()
            return
        if self._menu_is_open():
            self.dismiss_row_menu()
            return
        had_filter = bool(
            self._trace_filter.strip()
            or self._lane_filter
            or self._kind_filter
            or self._selected_step is not None
        )
        if had_filter:
            self._trace_filter = ""
            self._lane_filter = None
            self._kind_filter = None
            self._selected_step = None
            try:
                self.query_one("#trace-search", Input).value = ""
            except Exception:
                pass
            self.refresh_trace(self.current)
            return
        if self._context_open:
            self.action_toggle_context()

    def action_jump_trace_to_chat(self) -> None:
        """选中步骤时切回对话页，并滚到对应气泡/工具芯片。"""
        tabs = self.query_one("#tabs", TabbedContent)
        if tabs.active != "tab-trace":
            return
        if self._selected_step is None:
            return
        steps = self.current.trace.steps
        if not (0 <= self._selected_step < len(steps)):
            return
        step = steps[self._selected_step]
        if step.kind not in ("user", "assistant", "tool"):
            return
        ev = self._map_step_to_event(self._selected_step)
        self.action_tab_chat()
        self.focus_chat_event(ev)
        self.query_one("#prompt").focus()


    def action_open_settings(self) -> None:
        """打开 Cursor 风格设置（默认停在「插件」）。"""
        from local.tui.settings import SettingsScreen

        self.push_screen(SettingsScreen())

    def on_plugins_changed(self) -> None:
        """设置页开关 / 安装后回调：热加载标记 + 刷新底部提示。"""
        self._plugins_revision += 1
        if hasattr(self.backend, "reload_plugins"):
            try:
                self.backend.reload_plugins()
            except Exception:
                pass
        # 轻量提示到 thinking 行（不挡对话）
        try:
            from local.plugins_system import list_plugins, load_enabled_plugins

            on = [r["name"] for r in list_plugins() if r.get("enabled")]
            loaded = load_enabled_plugins()
            n_tools = len(loaded.tools)
            self.query_one("#thinking", Static).update(
                f"插件已更新 · 启用 {len(on)} · 工具 {n_tools}（下次对话生效）"
            )
        except Exception:
            pass


def make_backend(mock: bool):
    from local.tui.backend import MockBackend, OpenRouterBackend

    return MockBackend() if mock else OpenRouterBackend()


def seed_shot_workspace() -> tuple[list[Session], list[Project]]:
    """截图用短对话。文案里不出现 mock，头像用侧栏同一套 blob。"""
    sessions, projects = seed_demo_workspace()
    project = projects[0]
    blob = "indigo_hex"
    session = Session(
        "新建试用",
        events=[
            ("user", "你好，这是新建对话"),
            ("agent", "你好！这是一条新会话，头像已与其它会话区分。"),
        ],
        avatar=blob,
        accent=accent_for(blob),
        project_id=project.id,
    )
    session.trace.stats.rounds = 1
    session.trace.stats.steps = 2
    project.session_ids.insert(0, session.id)
    sessions.insert(0, session)
    return sessions, projects


def main() -> None:
    p = argparse.ArgumentParser(description="LightAgent TUI")
    p.add_argument("--mock", action="store_true", help="使用假后端，不调用任何 API")
    p.add_argument("--shot", action="store_true", help="预置一条短对话供 kitty 截图，画面不写 mock 文案")
    args = p.parse_args()
    if args.shot:
        os.environ["LIGHTAGENT_TUI_SHOT"] = "1"
        backend = make_backend(True)
        backend._mock_used = 2
        LightAgentTUI(backend, *seed_shot_workspace(), persist=False).run()
        return
    if not args.mock:
        # 日常默认：MX deepseek-v4.1-flash + effort=low（可用环境变量覆盖）
        os.environ.setdefault("LIGHTAGENT_PROVIDER", "mx")
        os.environ.setdefault("LIGHTAGENT_REASONING_EFFORT", "low")
        os.environ.setdefault("LIGHTAGENT_ALLOW_OPENROUTER", "1")
    LightAgentTUI(make_backend(args.mock)).run()


if __name__ == "__main__":
    main()
