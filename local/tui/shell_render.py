"""整窗预渲壳：侧栏 + 主区外框、大圆角、轻阴影。

同一套超采样圆角也用来画搜索、侧栏按钮、输入条和选中行两端。
洞口按单元格对齐，文字控件只占圆角内侧的格子，不和 TGP 占位符抢同一格。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter

# 和 app.tcss 里的洞内底色保持同一套色值，接缝才看不见。
PAGE_RGBA = (232, 232, 237, 255)  # #e8e8ed
SIDEBAR_RGBA = (245, 245, 247, 255)  # #f5f5f7
MAIN_RGBA = (255, 255, 255, 255)
SELECT_RGBA = (228, 228, 233, 255)  # #e4e4e9
HOVER_RGBA = (236, 236, 240, 255)  # #ececf0
SEARCH_RGBA = (238, 238, 239, 255)  # #eeeeef
FIELD_RGBA = (243, 243, 245, 255)  # #f3f3f5 白底上的输入胶囊
ACTION_RGBA = (255, 255, 255, 255)
FOCUS_RGBA = (231, 240, 254, 255)  # #e7f0fe
BLUE_RGBA = (47, 124, 246, 255)  # #2f7cf6
WHITE_RGBA = (255, 255, 255, 255)
PCT_RGBA = (242, 242, 244, 255)  # #f2f2f4


def rgb_hex(color: tuple[int, int, int, int]) -> str:
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def cell_size() -> tuple[int, int]:
    """终端单元格像素。探测失败时用 VT340 的 10×20，和 textual-image 一致。"""
    try:
        from textual_image._terminal import get_cell_size

        size = get_cell_size()
        width, height = int(size.width), int(size.height)
        if width > 0 and height > 0:
            return width, height
    except Exception:
        pass
    return 10, 20


@dataclass(frozen=True)
class ShellMetrics:
    """洞口按格对齐。内容从 inset 开始，圆角和阴影留在外侧格子里。"""

    cols: int
    rows: int
    cw: int
    ch: int
    inset_x: int
    inset_y: int
    sidebar_cols: int
    page_px: int
    radius_px: int
    split_x: int

    @property
    def pixel_size(self) -> tuple[int, int]:
        return self.cols * self.cw, self.rows * self.ch


def compute_metrics(cols: int, rows: int, cw: int, ch: int, *, sidebar_cols: int = 32) -> ShellMetrics:
    """大圆角必须落在内容区外侧。终端变矮时缩小半径，而不是盖住洞口。"""
    cols = max(1, cols)
    rows = max(1, rows)
    cw = max(1, cw)
    ch = max(1, ch)
    radius = 36
    page = 14
    while radius > 16:
        inset_x = max(2, math.ceil((page + radius) / cw))
        inset_y = max(1, math.ceil((page + radius) / ch))
        if inset_x * 2 <= cols - 40 and inset_y * 2 <= rows - 16:
            break
        radius -= 2
        if page > 8 and radius < 28:
            page -= 1
    else:
        inset_x = max(1, min(4, cols // 8))
        inset_y = max(1, min(2, rows // 10))
        radius = max(8, min(radius, inset_y * ch - 4, inset_x * cw - 4))
        page = max(4, min(page, inset_x * cw - radius))
    inset_x = max(2, math.ceil((page + radius) / cw))
    inset_y = max(1, math.ceil((page + radius) / ch))
    inset_x = min(inset_x, max(1, cols // 5))
    inset_y = min(inset_y, max(1, rows // 6))
    room = cols - inset_x * 2 - 28
    sidebar_cols = max(20, min(sidebar_cols, max(20, room)))
    if inset_x + sidebar_cols >= cols - 8:
        sidebar_cols = max(16, cols - inset_x - 12)
    return ShellMetrics(
        cols=cols,
        rows=rows,
        cw=cw,
        ch=ch,
        inset_x=inset_x,
        inset_y=inset_y,
        sidebar_cols=sidebar_cols,
        page_px=page,
        radius_px=radius,
        split_x=(inset_x + sidebar_cols) * cw,
    )


def _aa_round_rect(
    size: tuple[int, int],
    radius: int,
    fill: tuple[int, int, int, int],
    *,
    scale: int = 3,
) -> Image.Image:
    """超采样圆角。返回的图四角透明，弧上有中间色。"""
    width, height = size
    width = max(2, width)
    height = max(2, height)
    radius = max(1, min(int(radius), width // 2, height // 2))
    big = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    draw.rounded_rectangle(
        (0, 0, width * scale - 1, height * scale - 1),
        radius=radius * scale,
        fill=fill,
    )
    return big.resize((width, height), Image.Resampling.LANCZOS)


def render_chrome(metrics: ShellMetrics) -> Image.Image:
    """整窗一张：页底、轻阴影、圆角卡片、侧栏/主区两块底色。"""
    width, height = metrics.pixel_size
    page = metrics.page_px
    radius = metrics.radius_px
    card_left = page
    card_top = page
    card_w = max(8, width - 2 * page)
    card_h = max(8, height - 2 * page)
    radius = max(4, min(radius, card_w // 2 - 1, card_h // 2 - 1))

    canvas = Image.new("RGBA", (width, height), PAGE_RGBA)
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    blob = _aa_round_rect((card_w, card_h), radius, (0, 0, 0, 88), scale=2)
    shadow.paste(blob, (card_left, card_top + max(2, metrics.ch // 8)), blob)
    blur = max(2, min(10, page // 2 + 2))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur))
    canvas = Image.alpha_composite(canvas, shadow)

    card = Image.new("RGBA", (card_w, card_h), MAIN_RGBA)
    side_w = metrics.split_x - card_left
    if side_w > 0:
        ImageDraw.Draw(card).rectangle((0, 0, min(card_w, side_w), card_h), fill=SIDEBAR_RGBA)
    mask = _aa_round_rect((card_w, card_h), radius, (255, 255, 255, 255), scale=2).getchannel("A")
    card.putalpha(mask)
    canvas.paste(card, (card_left, card_top), card)
    return canvas


def render_pill(
    width: int,
    height: int,
    fill: tuple[int, int, int, int],
    *,
    radius: int | None = None,
) -> Image.Image:
    """短控件用胶囊：半径默认半高。"""
    width = max(4, int(width))
    height = max(4, int(height))
    if radius is None:
        radius = height // 2
    return _aa_round_rect((width, height), radius, fill, scale=3)


def slice_pill(image: Image.Image, row_px: int, cap_px: int) -> dict[str, Image.Image]:
    """切成上沿、下沿、左右端盖。中间一横条留给真正的输入/文字控件。"""
    row_px = max(1, min(row_px, image.height // 3))
    cap_px = max(1, min(cap_px, image.width // 2 - 1))
    top = image.crop((0, 0, image.width, row_px))
    bottom = image.crop((0, image.height - row_px, image.width, image.height))
    mid = image.crop((0, row_px, image.width, image.height - row_px))
    left = mid.crop((0, 0, cap_px, mid.height))
    right = mid.crop((mid.width - cap_px, 0, mid.width, mid.height))
    return {"top": top, "bottom": bottom, "left": left, "right": right}


def cap_columns(height_px: int, cw: int) -> int:
    """端盖要盖住半高半径，否则胶囊两端会被中间的方块裁掉。"""
    cw = max(1, cw)
    radius = max(1, height_px // 2)
    return max(2, math.ceil(radius / cw))


def render_end_caps(
    height_px: int,
    cap_px: int,
    fill: tuple[int, int, int, int],
    *,
    radius: int = 16,
) -> tuple[Image.Image, Image.Image]:
    """选中行左右两端。中间用同色平涂，四角弧留在端盖里。"""
    height_px = max(4, height_px)
    cap_px = max(2, cap_px)
    radius = max(2, min(radius, height_px // 2, cap_px))
    width = cap_px * 2 + 8
    plate = _aa_round_rect((width, height_px), radius, fill, scale=3)
    left = plate.crop((0, 0, cap_px, height_px))
    right = plate.crop((width - cap_px, 0, width, height_px))
    return left, right


def render_plus_button(width: int, height: int, *, radius: int | None = None) -> Image.Image:
    """蓝色圆角方钮，加号画进图里，不靠字符边框。"""
    width = max(8, width)
    height = max(8, height)
    if radius is None:
        radius = int(min(width, height) * 0.36)
    scale = 3
    big_w, big_h = width * scale, height * scale
    big_r = max(1, min(radius * scale, big_w // 2, big_h // 2))
    image = Image.new("RGBA", (big_w, big_h), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((0, 0, big_w - 1, big_h - 1), radius=big_r, fill=BLUE_RGBA)
    cx, cy = big_w // 2, big_h // 2
    arm = int(min(big_w, big_h) * 0.22)
    thick = max(scale * 2, int(min(big_w, big_h) * 0.08))
    pen.rounded_rectangle(
        (cx - thick // 2, cy - arm, cx + thick // 2, cy + arm),
        radius=thick // 2,
        fill=WHITE_RGBA,
    )
    pen.rounded_rectangle(
        (cx - arm, cy - thick // 2, cx + arm, cy + thick // 2),
        radius=thick // 2,
        fill=WHITE_RGBA,
    )
    return image.resize((width, height), Image.Resampling.LANCZOS)
