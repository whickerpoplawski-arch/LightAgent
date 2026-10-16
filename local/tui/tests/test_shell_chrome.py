"""整窗预渲壳：大圆角抗锯齿，搜索/输入/侧栏按钮不再用字符细线框。"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from local.tui.app import LightAgentTUI, SessionRow, seed_demo_workspace
from local.tui.backend import MockBackend
from local.tui.graphics import HalfcellImage, UnicodeImage
from local.tui.shell_render import (
    PAGE_RGBA,
    SIDEBAR_RGBA,
    card_silhouette,
    compute_metrics,
    cover_content_hole,
    diagonal_rgb,
    render_chrome,
    render_pill,
)
from local.tui.soft_render import _bubble_radius, render_user_bubble


def _border_name(widget) -> str:
    edge = widget.styles.border.top
    name = edge[0] if isinstance(edge, tuple) else getattr(edge, "type", "")
    return str(name or "")


def _corner_has_antialiasing(image, radius: int) -> bool:
    """卡片左上角沿对角线应当出现半透明或中间色，而不是一刀切的方格。"""
    pixels = image.load()
    mixed = 0
    for step in range(2, radius):
        px = pixels[step, step]
        alpha = px[3]
        if 25 < alpha < 240:
            mixed += 1
            continue
        # 落在页底和卡片之间的过渡色
        if alpha > 240 and px[:3] != PAGE_RGBA[:3] and px[:3] != (255, 255, 255) and px[:3] != SIDEBAR_RGBA[:3]:
            mixed += 1
    return mixed >= 2


def _soft_diagonal(image, metrics) -> bool:
    """从页底走到侧栏色，中间要有多档过渡，不能一像素硬切。"""
    colors = diagonal_rgb(image, metrics.page_px + metrics.radius_px + 6)
    side = SIDEBAR_RGBA[:3]

    def dist(a, b) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])

    hit = next((i for i, color in enumerate(colors) if dist(color, side) <= 8), None)
    if hit is None or hit < 4:
        return False
    window = colors[hit - 4 : hit + 1]
    return len(set(window)) >= 3


def test_chrome_is_a_rounded_card_not_a_square():
    metrics = compute_metrics(120, 46, 10, 20, sidebar_cols=32)
    assert metrics.radius_px >= 24
    # 洞口必须盖住整条圆角带，子控件的直角底才不会切掉弧。
    assert metrics.inset_x * metrics.cw >= metrics.page_px + metrics.radius_px
    assert metrics.inset_y * metrics.ch >= metrics.page_px + metrics.radius_px
    image = render_chrome(metrics)
    assert image.size == (120 * 10, 46 * 20)
    assert image.getpixel((0, 0))[:3] == PAGE_RGBA[:3]
    # 侧栏洞内对应的底色
    side_x = metrics.split_x // 2
    side_y = image.height // 2
    assert image.getpixel((side_x, side_y))[:3] == SIDEBAR_RGBA[:3]
    main_x = (metrics.split_x + image.width) // 2
    assert image.getpixel((main_x, side_y))[:3] == (255, 255, 255)
    assert _corner_has_antialiasing(image, metrics.radius_px)
    # 卡片角外侧仍是页底，不是直角白块
    assert image.getpixel((2, 2))[:3] == PAGE_RGBA[:3]
    # 洞口涂成控件底色之后，外轮廓仍是圆角，对角线仍有多档过渡。
    visible = cover_content_hole(image, metrics)
    steps = card_silhouette(visible)
    assert len(set(steps)) >= 8
    assert _soft_diagonal(visible, metrics)


def test_short_bubble_is_a_fat_capsule():
    image = render_user_bubble("你好")
    radius = _bubble_radius(image.height, 1)
    assert radius == image.height // 2
    # 左上角透明，垂直中线贴边是实色（胶囊最宽处）
    assert image.getpixel((0, 0))[3] < 40
    mid = image.getpixel((4, image.height // 2))
    assert mid[3] > 200
    assert mid[:3] == (47, 124, 246)
    # 顶边靠近左端仍应是透明的，说明不是小圆角方块
    assert image.getpixel((2, 1))[3] < 80


def test_pill_slice_is_round_and_controls_have_no_hairline(tmp_path):
    pill = render_pill(200, 60, (238, 238, 239, 255))
    assert pill.getpixel((0, 0))[3] < 40
    assert pill.getpixel((100, 30))[:3] == (238, 238, 239)
    asyncio.run(_controls(tmp_path))


async def _controls(tmp_path):
    sessions, projects = seed_demo_workspace()
    app = LightAgentTUI(MockBackend(delay=0), sessions, projects, workspace_dir=tmp_path, persist=False)
    async with app.run_test(size=(120, 46)) as pilot:
        await pilot.pause(0.1)
        shell = app.query_one("#shell")
        assert _border_name(shell) in {"", "none", "hidden", "blank"}
        for selector in ("#search", "#prompt", "#new-project-btn", "#group-chat-btn", "#composer"):
            border = _border_name(app.query_one(selector))
            assert border in {"", "none", "hidden", "blank"}, selector
        assert not list(app.query(HalfcellImage))
        assert not list(app.query(UnicodeImage))
        metrics = app._shell_metrics
        assert metrics.radius_px >= 16
        chrome = app.query_one("#shell-chrome")
        shell = app.query_one("#shell")
        # padding 必须是 0。非 0 时外圈是平涂底色，TGP 圆角进不了画面。
        assert chrome.styles.padding.top == 0
        assert chrome.styles.padding.left == 0
        assert shell.styles.margin.top == metrics.inset_y
        assert shell.styles.margin.left == metrics.inset_x
        assert shell.region.x >= chrome.region.x + metrics.inset_x
        assert shell.region.y >= chrome.region.y + metrics.inset_y
        assert chrome.region.right - shell.region.right >= metrics.inset_x
        assert chrome.region.bottom - shell.region.bottom >= metrics.inset_y
        selected = [row for row in app.query(SessionRow) if "selected" in row.classes]
        assert selected
        left = selected[0].query_one(".row-cap-left")
        assert left.image.getpixel((0, 0))[3] < 80
