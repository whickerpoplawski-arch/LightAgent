"""整窗壳控件，以及同一套预渲胶囊。

壳图是 ShellChrome 自己的 render()。圆角带必须落在子控件的 margin 外，
不能落在本控件的 padding 上：Textual 画 padding 时只用背景色填一条空白，
不会把 render() 里的 TGP 图画进去。洞口一旦盖住弧，源 PNG 仍是圆角，
真机外轮廓却是直角硬切。

搜索、侧栏动作、输入条是胶囊切片：上下沿和左右端盖是 PNG，
中间那一格才是真正能打字、能点的控件。
"""
from __future__ import annotations

import math

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

from local.tui.graphics import GraphicsImage, fit_graphics_widget, graphics_widget_class
from local.tui.shell_render import (
    ACTION_RGBA,
    FOCUS_RGBA,
    SEARCH_RGBA,
    cell_size,
    cap_columns,
    compute_metrics,
    render_chrome,
    render_pill,
    render_plus_button,
    rgb_hex,
    slice_pill,
)

_PLACEHOLDER = None


def _pixel() -> "object":
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        from PIL import Image

        _PLACEHOLDER = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    return _PLACEHOLDER


class ShellChrome(Vertical):
    """全屏预渲壳。子树用 margin 让出圆角带。resize 节流重画。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._timer = None
        self._key: tuple | None = None
        self._image = None
        self._renderable = None

    def on_resize(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_timer(0.1, self.paint)

    def paint(self) -> None:
        self._timer = None
        cols, rows = self.size.width, self.size.height
        if cols < 24 or rows < 12:
            return
        cw, ch = cell_size()
        key = (cols, rows, cw, ch)
        if key == self._key and self._image is not None:
            return
        metrics = compute_metrics(cols, rows, cw, ch)
        self._image = render_chrome(metrics)
        if self._renderable is not None:
            cleanup = getattr(self._renderable, "cleanup", None)
            if cleanup:
                cleanup()
        self._renderable = None
        self._key = key
        # padding 会被 Textual 画成平涂底色，圆角弧进不了那一圈。
        # 洞口用子控件 margin 让出来，外侧格子才留得住整张壳图。
        self.styles.padding = (0, 0)
        try:
            shell = self.query_one("#shell")
            shell.styles.margin = (metrics.inset_y, metrics.inset_x)
            self.query_one("#sidebar").styles.width = metrics.sidebar_cols
        except Exception:
            pass
        setattr(self.app, "_shell_metrics", metrics)
        self.refresh(layout=True)

    def render(self):
        if self._image is None:
            return ""
        if self._renderable is None:
            # 按整窗格数铺，不让 Rich 把图缩进内容盒后再被子控件盖住。
            cols = max(1, int(self.size.width))
            rows = max(1, int(self.size.height))
            self._renderable = graphics_widget_class()._Renderable(self._image, cols, rows)
        return self._renderable


class SoftField(Vertical):
    """一条预渲胶囊。中间控件保持原来的 id，端盖不参与打字。"""

    def __init__(
        self,
        center: Widget,
        *,
        fill: tuple[int, int, int, int] = SEARCH_RGBA,
        focus_fill: tuple[int, int, int, int] | None = FOCUS_RGBA,
        id: str | None = None,
        classes: str | None = None,
        click_target_id: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._center = center
        self._fill = fill
        self._focus_fill = focus_fill
        self.click_target_id = click_target_id
        self._focused = False
        self._paint_key: tuple | None = None
        self.add_class("soft-field")

    @property
    def content(self):
        label = self.query(".pill-label")
        if label:
            return label.first().content
        return ""

    def compose(self) -> ComposeResult:
        yield GraphicsImage(_pixel(), classes="soft-top")
        with Horizontal(classes="soft-mid"):
            yield GraphicsImage(_pixel(), classes="soft-left")
            yield self._center
            yield GraphicsImage(_pixel(), classes="soft-right")
        yield GraphicsImage(_pixel(), classes="soft-bot")

    def on_mount(self) -> None:
        self.call_after_refresh(self._repaint)

    def on_resize(self) -> None:
        self._repaint()

    def on_descendant_focus(self) -> None:
        self._focused = True
        self._paint_key = None
        self._repaint()

    def on_descendant_blur(self) -> None:
        self._focused = False
        self._paint_key = None
        self._repaint()

    def _repaint(self) -> None:
        width = self.size.width
        height = self.size.height
        if width < 8 or height < 3:
            return
        fill = self._focus_fill if self._focused and self._focus_fill else self._fill
        key = (width, height, fill)
        if key == self._paint_key:
            return
        cw, ch = cell_size()
        cap_cols = min(width // 3, cap_columns(height * ch, cw))
        cap_cols = max(2, cap_cols)
        if cap_cols * 2 >= width:
            cap_cols = max(1, width // 4)
        image = render_pill(width * cw, height * ch, fill)
        parts = slice_pill(image, ch, cap_cols * cw)
        top = self.query_one(".soft-top")
        bottom = self.query_one(".soft-bot")
        left = self.query_one(".soft-left")
        right = self.query_one(".soft-right")
        top.image = parts["top"]
        bottom.image = parts["bottom"]
        left.image = parts["left"]
        right.image = parts["right"]
        for piece in (top, bottom, left, right):
            fit_graphics_widget(piece)
        color = rgb_hex(fill)
        mid = self.query_one(".soft-mid")
        mid.styles.background = color
        self._center.styles.background = color
        self._center.styles.border = ("none", color)
        self._center.styles.height = 1
        self._center.styles.min_height = 1
        self._center.styles.padding = (0, 1)
        self._paint_key = key


class SoftButton(Widget):
    """整颗预渲按钮（加号）。点击落在子图上时，id 仍在这颗按钮上。"""

    def compose(self) -> ComposeResult:
        yield GraphicsImage(_pixel(), classes="soft-button-img")

    def on_mount(self) -> None:
        self.call_after_refresh(self._repaint)

    def on_resize(self) -> None:
        self._repaint()

    def _repaint(self) -> None:
        width, height = self.size.width, self.size.height
        if width < 2 or height < 2:
            return
        cw, ch = cell_size()
        image = render_plus_button(width * cw, height * ch)
        widget = self.query_one(".soft-button-img")
        widget.image = image
        fit_graphics_widget(widget)


def nav_pill(label: str, pill_id: str) -> SoftField:
    center = Static(label, classes="pill-label")
    return SoftField(
        center,
        fill=ACTION_RGBA,
        focus_fill=None,
        id=pill_id,
        classes="nav-action",
        click_target_id=pill_id,
    )


def row_cap_px() -> tuple[int, int]:
    """选中行端盖：高跟头像行，宽盖住圆角。"""
    cw, ch = cell_size()
    height = ch * 3
    radius = max(12, min(18, ch))
    cols = max(2, math.ceil((radius + 2) / cw))
    return height, cols * cw
