"""Grok 风格彩色 blob 头像：参考图裁切 + 程序生成变体（>=50）。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from rich.text import Text

BLOB_DIR = Path(__file__).resolve().parent / "assets" / "blobs"

BLOB_CATALOG: list[dict[str, str]] = [{'id': 'blue_drop', 'file': 'blue_drop.png', 'accent': '#3b82f6'}, {'id': 'pink_cloud', 'file': 'pink_cloud.png', 'accent': '#ec4899'}, {'id': 'orange_cloud', 'file': 'orange_cloud.png', 'accent': '#f97316'}, {'id': 'black_star', 'file': 'black_star.png', 'accent': '#1c1c1e'}, {'id': 'brown_hex', 'file': 'brown_hex.png', 'accent': '#a16207'}, {'id': 'blue_tri', 'file': 'blue_tri.png', 'accent': '#2563eb'}, {'id': 'blue_circle', 'file': 'blue_circle.png', 'accent': '#3b82f6'}, {'id': 'pink_squircle', 'file': 'pink_squircle.png', 'accent': '#ec4899'}, {'id': 'orange_pill', 'file': 'orange_pill.png', 'accent': '#f97316'}, {'id': 'ink_cloud', 'file': 'ink_cloud.png', 'accent': '#1c1c1e'}, {'id': 'brown_hex2', 'file': 'brown_hex2.png', 'accent': '#a16207'}, {'id': 'navy_tri', 'file': 'navy_tri.png', 'accent': '#2563eb'}, {'id': 'lime_diamond', 'file': 'lime_diamond.png', 'accent': '#84cc16'}, {'id': 'purple_blob', 'file': 'purple_blob.png', 'accent': '#a855f7'}, {'id': 'teal_star', 'file': 'teal_star.png', 'accent': '#14b8a6'}, {'id': 'coral_bean', 'file': 'coral_bean.png', 'accent': '#f43f5e'}, {'id': 'indigo_circle', 'file': 'indigo_circle.png', 'accent': '#6366f1'}, {'id': 'mint_squircle', 'file': 'mint_squircle.png', 'accent': '#2dd4bf'}, {'id': 'amber_pill', 'file': 'amber_pill.png', 'accent': '#f59e0b'}, {'id': 'sky_cloud', 'file': 'sky_cloud.png', 'accent': '#0ea5e9'}, {'id': 'red_hex', 'file': 'red_hex.png', 'accent': '#ef4444'}, {'id': 'green_tri', 'file': 'green_tri.png', 'accent': '#22c55e'}, {'id': 'gold_diamond', 'file': 'gold_diamond.png', 'accent': '#eab308'}, {'id': 'violet_blob', 'file': 'violet_blob.png', 'accent': '#8b5cf6'}, {'id': 'cyan_star', 'file': 'cyan_star.png', 'accent': '#06b6d4'}, {'id': 'fuchsia_bean', 'file': 'fuchsia_bean.png', 'accent': '#d946ef'}, {'id': 'slate_circle', 'file': 'slate_circle.png', 'accent': '#64748b'}, {'id': 'rose_squircle', 'file': 'rose_squircle.png', 'accent': '#f472b6'}, {'id': 'spring_pill', 'file': 'spring_pill.png', 'accent': '#4ade80'}, {'id': 'peach_cloud', 'file': 'peach_cloud.png', 'accent': '#fb923c'}, {'id': 'ice_hex', 'file': 'ice_hex.png', 'accent': '#38bdf8'}, {'id': 'lilac_tri', 'file': 'lilac_tri.png', 'accent': '#c084fc'}, {'id': 'sunny_diamond', 'file': 'sunny_diamond.png', 'accent': '#facc15'}, {'id': 'jade_blob', 'file': 'jade_blob.png', 'accent': '#34d399'}, {'id': 'blush_star', 'file': 'blush_star.png', 'accent': '#fb7185'}, {'id': 'periwinkle_bean', 'file': 'periwinkle_bean.png', 'accent': '#818cf8'}, {'id': 'chartreuse_circle', 'file': 'chartreuse_circle.png', 'accent': '#a3e635'}, {'id': 'honey_squircle', 'file': 'honey_squircle.png', 'accent': '#fbbf24'}, {'id': 'aqua_pill', 'file': 'aqua_pill.png', 'accent': '#2dd4bf'}, {'id': 'orchid_cloud', 'file': 'orchid_cloud.png', 'accent': '#e879f9'}, {'id': 'cornflower_hex', 'file': 'cornflower_hex.png', 'accent': '#60a5fa'}, {'id': 'blue_tri2', 'file': 'blue_tri2.png', 'accent': '#3b82f6'}, {'id': 'pink_diamond', 'file': 'pink_diamond.png', 'accent': '#ec4899'}, {'id': 'orange_blob', 'file': 'orange_blob.png', 'accent': '#f97316'}, {'id': 'ink_star', 'file': 'ink_star.png', 'accent': '#1c1c1e'}, {'id': 'brown_bean', 'file': 'brown_bean.png', 'accent': '#a16207'}, {'id': 'navy_circle', 'file': 'navy_circle.png', 'accent': '#2563eb'}, {'id': 'lime_squircle', 'file': 'lime_squircle.png', 'accent': '#84cc16'}, {'id': 'purple_pill', 'file': 'purple_pill.png', 'accent': '#a855f7'}, {'id': 'teal_cloud', 'file': 'teal_cloud.png', 'accent': '#14b8a6'}, {'id': 'coral_hex', 'file': 'coral_hex.png', 'accent': '#f43f5e'}, {'id': 'indigo_tri', 'file': 'indigo_tri.png', 'accent': '#6366f1'}]


def _accent_for_name(blob_id: str) -> str:
    keys = (
        ("indigo", "#6366f1"),
        ("blue", "#3b82f6"),
        ("navy", "#2563eb"),
        ("pink", "#ec4899"),
        ("rose", "#f472b6"),
        ("orange", "#f97316"),
        ("amber", "#f59e0b"),
        ("gold", "#eab308"),
        ("lime", "#84cc16"),
        ("mint", "#2dd4bf"),
        ("teal", "#14b8a6"),
        ("green", "#22c55e"),
        ("purple", "#a855f7"),
        ("violet", "#8b5cf6"),
        ("brown", "#a16207"),
        ("coral", "#f43f5e"),
        ("red", "#ef4444"),
    )
    for key, color in keys:
        if key in blob_id:
            return color
    return "#6366f1"


def _merge_disk_blobs() -> None:
    """目录里多出来的 PNG（例如 indigo_hex）也进头像池，已有 id 的顺序不变。"""
    known = {item["id"] for item in BLOB_CATALOG}
    if not BLOB_DIR.is_dir():
        return
    for path in sorted(BLOB_DIR.glob("*.png")):
        blob_id = path.stem
        if blob_id in known:
            continue
        BLOB_CATALOG.append({"id": blob_id, "file": path.name, "accent": _accent_for_name(blob_id)})
        known.add(blob_id)


_merge_disk_blobs()

_CACHE: dict[tuple[str, int, int], Text] = {}


def assign_blob(index: int) -> tuple[str, str]:
    """按序号轮换（兼容旧调用）。"""
    item = BLOB_CATALOG[index % len(BLOB_CATALOG)]
    return item["id"], item["accent"]


def pick_unused_blob(used: set[str] | None = None, *, prefer_index: int | None = None) -> tuple[str, str]:
    """新建会话：优先选未占用的 blob；都占用则按 prefer_index 轮换。"""
    used = used or set()
    free = [b for b in BLOB_CATALOG if b["id"] not in used]
    if free:
        i = 0 if prefer_index is None else prefer_index % len(free)
        item = free[i]
        return item["id"], item["accent"]
    return assign_blob(prefer_index or 0)


def blob_path(blob_id: str) -> Path | None:
    for item in BLOB_CATALOG:
        if item["id"] == blob_id:
            p = BLOB_DIR / item["file"]
            return p if p.is_file() else None
    p = BLOB_DIR / f"{blob_id}.png"
    return p if p.is_file() else None


def accent_for(blob_id: str, fallback: str = "#3b82f6") -> str:
    for item in BLOB_CATALOG:
        if item["id"] == blob_id:
            return item["accent"]
    return fallback or "#3b82f6"


def render_blob(blob_id: str, *, cols: int = 5, rows: int = 3) -> Text:
    key = (blob_id, cols, rows)
    if key in _CACHE:
        return _CACHE[key].copy()
    path = blob_path(blob_id)
    if path is None:
        t = Text()
        for r in range(rows):
            t.append(("॥" if r == rows // 2 else " ").center(cols), style="bold white")
            if r < rows - 1:
                t.append("\n")
        _CACHE[key] = t
        return t.copy()
    im = Image.open(path).convert("RGBA")
    tw, th = cols, rows * 2
    im = im.resize((tw, th), Image.Resampling.LANCZOS)
    px = im.load()
    out = Text()

    def sty(c):
        if c[3] < 40:
            return None
        return f"rgb({c[0]},{c[1]},{c[2]})"

    for y in range(0, th, 2):
        for x in range(tw):
            top = px[x, y]
            bot = px[x, y + 1] if y + 1 < th else (0, 0, 0, 0)
            ts, bs = sty(top), sty(bot)
            if ts and bs:
                out.append("▀", style=f"{ts} on {bs}")
            elif ts:
                out.append("▀", style=ts)
            elif bs:
                out.append("▄", style=bs)
            else:
                out.append(" ")
        if y + 2 < th:
            out.append("\n")
    _CACHE[key] = out
    return out.copy()


def paint_blob(widget, blob_id: str, *, cols: int = 5, rows: int = 3) -> None:
    widget.update(render_blob(blob_id, cols=cols, rows=rows))
    widget.styles.background = "transparent"
    widget.styles.border = ("none", "transparent")
    widget.styles.padding = (0, 0)
