"""图片样式控件：气泡和头像走 TGP，否则 Sixel。

默认路径禁止 Halfcell / Unicode 马赛克。xfce 上的半块图不能当验收。
"""
from __future__ import annotations

import os

# textual-image 在 import 时记住 TMUX。从 tmux 里拉起 kitty 时这个变量会漏进来，
# 图形序列被错误包一层，kitty 里就看不到图。真正的 tty 是 kitty 时不要按 tmux 处理。
if os.environ.get("KITTY_WINDOW_ID") or "kitty" in os.environ.get("TERM", ""):
    os.environ.pop("TMUX", None)
    os.environ.pop("TMUX_PANE", None)


def preserve_image_colors() -> None:
    """让气泡前景色保持真彩色。

    Kitty 的 Unicode 占位符把图像 id 编进单元格前景色。
    进程里如果有 NO_COLOR，Textual 会把所有颜色改成灰度，id 对不上，气泡就是空白。
    必须在 App 初始化之前调用。
    """
    os.environ.pop("NO_COLOR", None)

from PIL import Image as PILImage

from textual_image._terminal import get_cell_size
from textual_image.widget import HalfcellImage, SixelImage, TGPImage, UnicodeImage
from textual_image.widget._base import Image as GraphicsWidget

# Kitty 占位符用变音符号编号，超限会在渲染时抛错。留一点余量。
_CELL_CAP = 280

_FORBIDDEN = (HalfcellImage, UnicodeImage)


def _env_flag(name: str) -> str:
    return os.environ.get(name, "").strip().lower()


def terminal_prefers_tgp() -> bool:
    """kitty / 已探测到的 TGP。不把 Sixel 终端误判成半块图。"""
    if os.environ.get("KITTY_WINDOW_ID") or os.environ.get("KITTY_PID"):
        return True
    term = os.environ.get("TERM", "")
    program = os.environ.get("TERM_PROGRAM", "")
    if "kitty" in term or "kitty" in program.lower():
        return True
    try:
        from textual_image._terminal import probe_terminal

        return bool(probe_terminal().tgp)
    except Exception:
        return False


def graphics_widget_class():
    """气泡正文和头像的控件类。只会是 TGPImage 或 SixelImage。"""
    forced = _env_flag("LIGHTAGENT_IMAGE_PROTOCOL")
    if forced in {"halfcell", "unicode", "mosaic"}:
        forced = ""
    if forced == "tgp":
        return TGPImage
    if forced == "sixel":
        return SixelImage
    if terminal_prefers_tgp():
        return TGPImage
    return SixelImage


def fit_graphics_widget(widget) -> None:
    """按像素 / 单元格对齐，避免把 18px 中文拉成整行再缩成马赛克。"""
    image = getattr(widget, "image", None)
    if not isinstance(image, PILImage.Image):
        return
    cell = get_cell_size()
    cw = max(1, int(cell.width))
    ch = max(1, int(cell.height))
    cols = max(1, min(_CELL_CAP, round(image.width / cw)))
    rows = max(1, min(_CELL_CAP, round(image.height / ch)))
    widget.styles.width = cols
    widget.styles.height = rows
    widget.styles.min_width = cols
    widget.styles.max_width = cols
    widget.styles.min_height = rows
    widget.styles.max_height = rows


def GraphicsImage(image: PILImage.Image, *, classes: str | None = None, id: str | None = None):
    """挂一张 PIL 图。优先 TGP，否则 Sixel。"""
    widget = graphics_widget_class()(image, classes=classes, id=id)
    if isinstance(widget, _FORBIDDEN):
        raise RuntimeError("气泡/头像不能走 halfcell 或 unicode")
    fit_graphics_widget(widget)
    return widget


def is_graphics_widget(widget) -> bool:
    return isinstance(widget, (TGPImage, SixelImage, GraphicsWidget)) and not isinstance(widget, _FORBIDDEN)


__all__ = [
    "GraphicsImage",
    "GraphicsWidget",
    "TGPImage",
    "SixelImage",
    "HalfcellImage",
    "UnicodeImage",
    "fit_graphics_widget",
    "graphics_widget_class",
    "is_graphics_widget",
    "terminal_prefers_tgp",
]
