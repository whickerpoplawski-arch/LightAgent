"""PIL 圆角气泡和头像。TUI 用 TGP/Sixel 挂这些 PNG，不用半块马赛克，也不用 Static 冒充。

HTML 预览只是附属，不能代替 kitty 里的真图验收。
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from local.tui.blobs import BLOB_DIR, blob_path

# 字号 ≥18、半径 ≥20。色值贴参考：用户蓝 #2f7cf6，助手灰 #e9e9eb。
BUBBLE_FONT_PX = 20
BUBBLE_RADIUS = 28
AVATAR_PX = 64
PAD_X, PAD_Y = 22, 16
MAX_BUBBLE_W = 460
LINE_H = 30
USER_RGBA = (47, 124, 246, 255)  # #2f7cf6
AGENT_RGBA = (233, 233, 235, 255)  # #e9e9eb
USER_TEXT = (255, 255, 255, 255)
AGENT_TEXT = (28, 28, 30, 255)

_FONT_REGULAR = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
)
_FONT_BOLD = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
)


def _first_font(candidates: tuple[str, ...]) -> str | None:
    for path in candidates:
        if Path(path).is_file():
            return path
    return None


@lru_cache(maxsize=8)
def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    path = _first_font(_FONT_BOLD if bold else _FONT_REGULAR)
    if path:
        try:
            return ImageFont.truetype(path, size=size, index=0)
        except Exception:
            pass
    return ImageFont.load_default()


def load_avatar(blob_id: str, size: int = AVATAR_PX) -> Image.Image:
    path = blob_path(blob_id)
    if path is None:
        # 纯色圆 blob + 白眼
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse((2, 2, size - 3, size - 3), fill=(59, 130, 246, 255))
        eye_w, eye_h = max(3, size // 10), max(8, size // 4)
        gap = size // 6
        cx, cy = size // 2, size // 2 - size // 10
        for dx in (-gap, gap):
            x0 = cx + dx - eye_w // 2
            y0 = cy - eye_h // 2
            d.rounded_rectangle((x0, y0, x0 + eye_w, y0 + eye_h), radius=eye_w, fill=(255, 255, 255, 255))
        return im
    im = Image.open(path).convert("RGBA")
    im = im.resize((size, size), Image.Resampling.LANCZOS)
    return im


def _wrap(text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return [""]
    lines: list[str] = []
    # CJK：按字符贪心
    buf = ""
    for ch in text:
        trial = buf + ch
        if font.getlength(trial) <= max_w:
            buf = trial
        else:
            if buf:
                lines.append(buf)
            buf = ch
    if buf:
        lines.append(buf)
    return lines or [""]


def _rounded_rect(size: tuple[int, int], radius: int, fill: tuple[int, int, int, int]) -> Image.Image:
    """超采样再缩小，圆角是光滑的，不是锯齿方块。"""
    w, h = size
    scale = 4
    big = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    draw.rounded_rectangle((0, 0, w * scale - 1, h * scale - 1), radius=radius * scale, fill=fill)
    return big.resize((w, h), Image.Resampling.LANCZOS)


def _paint_lines(image: Image.Image, lines: list[str], font: ImageFont.ImageFont, fill: tuple[int, int, int, int]) -> None:
    draw = ImageDraw.Draw(image)
    y = PAD_Y
    for line in lines:
        draw.text((PAD_X, y), line, font=font, fill=fill)
        y += LINE_H


def render_user_bubble(text: str) -> Image.Image:
    """右对齐蓝胶囊。交给 TGPImage / SixelImage，不要交给 Halfcell。"""
    font = _font(True, BUBBLE_FONT_PX)
    inner_w = MAX_BUBBLE_W - 2 * PAD_X
    lines = _wrap(text, font, inner_w)
    tw = int(max(font.getlength(ln) for ln in lines))
    th = LINE_H * len(lines)
    w = min(MAX_BUBBLE_W, max(tw + 2 * PAD_X, BUBBLE_RADIUS * 2))
    h = th + 2 * PAD_Y
    bg = _rounded_rect((w, h), BUBBLE_RADIUS, USER_RGBA)
    _paint_lines(bg, lines, font, USER_TEXT)
    return bg


def render_agent_bubble(text: str) -> Image.Image:
    """左对齐浅灰胶囊。"""
    font = _font(False, BUBBLE_FONT_PX)
    plain = re.sub(r"[*_`#>+]", "", text)
    inner_w = MAX_BUBBLE_W - 2 * PAD_X
    lines = _wrap(plain, font, inner_w)
    tw = int(max((font.getlength(ln) for ln in lines), default=0))
    th = LINE_H * len(lines)
    w = min(MAX_BUBBLE_W, max(tw + 2 * PAD_X, 80))
    h = th + 2 * PAD_Y
    bg = _rounded_rect((w, h), BUBBLE_RADIUS, AGENT_RGBA)
    _paint_lines(bg, lines, font, AGENT_TEXT)
    return bg


def compose_agent_row(blob_id: str, text: str, *, gap: int = 12) -> Image.Image:
    """头像 + 灰气泡整行。TUI 也可以拆成 blob 小图和气泡 PNG 两张。"""
    av = load_avatar(blob_id)
    bub = render_agent_bubble(text)
    h = max(av.height, bub.height)
    w = av.width + gap + bub.width
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(av, (0, 0), av)
    canvas.paste(bub, (av.width + gap, max(0, (h - bub.height) // 2)), bub)
    return canvas


def save_chat_preview_html(
    out_html: Path,
    *,
    title: str,
    blob_id: str,
    turns: list[tuple[str, str]],
    avatar_dir: Path | None = None,
) -> Path:
    """验收用：CSS border-radius + 真 PNG，Chrome 截即光滑卡通。"""
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    asset = out_html.parent / (out_html.stem + "_assets")
    asset.mkdir(exist_ok=True)
    av = load_avatar(blob_id, 64)
    av_path = asset / "avatar.png"
    av.save(av_path)

    parts = []
    for i, (kind, text) in enumerate(turns):
        if kind == "user":
            img = render_user_bubble(text)
            p = asset / f"u{i}.png"
            img.save(p)
            parts.append(f'<div class="row user"><img class="bub" src="{p.name}" alt=""/></div>')
        elif kind == "agent":
            img = compose_agent_row(blob_id, text)
            p = asset / f"a{i}.png"
            img.save(p)
            parts.append(f'<div class="row agent"><img class="rowimg" src="{p.name}" alt=""/></div>')
        else:
            parts.append(f'<div class="tool">⚙ {text}</div>')

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
body{{margin:0;background:#f5f5f7;font-family:-apple-system,"Noto Sans CJK SC",sans-serif;color:#1c1c1e}}
.shell{{display:flex;width:1100px;height:700px;margin:0 auto;background:#fff;}}
.side{{width:280px;background:#f5f5f7;border-right:1px solid #e5e5ea;padding:16px}}
.side .item{{display:flex;gap:10px;align-items:center;padding:10px;border-radius:14px;margin:6px 0}}
.side .item.on{{background:#e8e8ed}}
.side img.av{{width:40px;height:40px}}
.main{{flex:1;display:flex;flex-direction:column;background:#fafafa}}
.head{{padding:14px 20px;border-bottom:1px solid #ebebef;font-weight:700}}
.chat{{flex:1;padding:20px 28px;overflow:auto}}
.row{{margin:14px 0;display:flex}}
.row.user{{justify-content:flex-end}}
.row.agent{{justify-content:flex-start}}
.row img.bub,.row img.rowimg{{max-width:100%;height:auto;display:block}}
.tool{{color:#8e8e93;font-size:13px;margin:8px 0 8px 56px}}
.composer{{margin:12px 20px;padding:12px 16px;border-radius:22px;border:1px solid #d1d1d6;background:#fff;color:#8e8e93}}
</style></head><body>
<div class="shell">
  <div class="side">
    <div style="font-weight:700;margin-bottom:12px">✨ LightAgent</div>
    <div class="item on"><img class="av" src="{av_path.name}"/><div><b>{title}</b><div style="color:#8e8e93;font-size:12px">当前会话</div></div></div>
  </div>
  <div class="main">
    <div class="head">{title}</div>
    <div class="chat">
      {"".join(parts)}
    </div>
    <div class="composer">给 LightAgent 发消息…</div>
  </div>
</div>
</body></html>"""
    # rewrite asset refs to relative
    html = html.replace(str(av_path.name), "avatar.png")
    out_html.write_text(html, encoding="utf-8")
    # copy avatar into assets already; fix paths in html to assets/
    html2 = html.replace('src="avatar.png"', f'src="{asset.name}/avatar.png"')
    for i, (kind, _) in enumerate(turns):
        if kind == "user":
            html2 = html2.replace(f'src="u{i}.png"', f'src="{asset.name}/u{i}.png"')
        elif kind == "agent":
            html2 = html2.replace(f'src="a{i}.png"', f'src="{asset.name}/a{i}.png"')
    out_html.write_text(html2, encoding="utf-8")
    return out_html
