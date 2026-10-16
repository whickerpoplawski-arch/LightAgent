"""无头测试 + 截图（mock 后端，0 API 调用）。"""
from __future__ import annotations

import asyncio
import os
import sys

# Textual Monochrome filter when NO_COLOR is set — drop it so screenshots keep hue
os.environ.pop("NO_COLOR", None)

from local.tui.app import LightAgentTUI, seed_demo_workspace
from local.tui.backend import MockBackend


def fix_svg_cjk(path: str) -> None:
    import html
    import re

    from rich.cells import cell_len

    svg = open(path, encoding="utf-8").read()
    w = 12.2

    def repl(m):
        text = html.unescape(m.group(3))
        return f'{m.group(1)}textLength="{cell_len(text) * w:g}"{m.group(2)}>{m.group(3)}<'

    svg = re.sub(r'(<text[^>]*?)textLength="[\d.]+"([^>]*)>([^<]*)<', repl, svg)
    svg = svg.replace(
        "font-family: Fira Code, monospace;",
        'font-family: "Fira Code", "Noto Sans Mono CJK SC", "Noto Color Emoji", "Apple Color Emoji", monospace;',
    )
    open(path, "w", encoding="utf-8").write(svg)


async def main(
    out_chat: str = "/workspace/lightagent_tui.svg",
    out_trace: str = "/workspace/lightagent_tui_trace.svg",
    out_context: str = "/workspace/lightagent_tui_context.svg",
) -> None:
    sessions, projects = seed_demo_workspace()
    # 保证项目展开
    for p in projects:
        p.expanded = True
    app = LightAgentTUI(MockBackend(), sessions, projects)
    async with app.run_test(size=(130, 52)) as pilot:
        await pilot.pause(0.2)
        assert len(app.projects) >= 2
        assert app.ungrouped_sessions()
        # 选中项目里第一个会话，发两条消息丰富主区
        first = app.sessions_in_project(app.projects[0])[0]
        app.select_session(first)
        await pilot.pause(0.15)
        for msg in ["继续完善 TUI", "帮我查一下上海的天气"]:
            await pilot.click("#prompt")
            app.query_one("#prompt").value = msg
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause(0.2)

        # 对话页：侧栏应有项目+未分组
        app.action_tab_chat()
        if app._context_open:
            app.action_toggle_context()
        app.rebuild_nav()
        app.query_one("#nav").scroll_home(animate=False)
        app.query_one("#chat").scroll_home(animate=False)
        await pilot.pause(0.3)
        # 项目区是平铺会话行，不出现文件夹标题
        from local.tui.app import SessionRow
        rows = list(app.query_one("#project-list").query(SessionRow))
        assert rows
        titles = [row.session.title for row in rows]
        assert any("气泡" in title or "轨迹" in title for title in titles), titles
        assert not list(app.query(".project-title"))
        app.save_screenshot(out_chat)
        fix_svg_cjk(out_chat)

        # 轨迹
        app.action_tab_trace()
        await pilot.pause(0.2)
        tool_i = next((i for i, s in enumerate(app.current.trace.steps) if s.kind == "tool"), None)
        if tool_i is not None:
            app.select_trace_step(tool_i)
        await pilot.pause(0.2)
        app.save_screenshot(out_trace)
        fix_svg_cjk(out_trace)

        # 上下文卡
        ctx = app.current.trace.context
        ctx.system, ctx.tools, ctx.messages, ctx.limit = 2200, 8300, 88800, 1_000_000
        app.action_tab_chat()
        if not app._context_open:
            app.action_toggle_context()
        await pilot.pause(0.2)
        app.save_screenshot(out_context)
        fix_svg_cjk(out_context)

    print("OK projects", [p.name for p in app.projects], "ungrouped", len(app.ungrouped_sessions()), "->", out_chat)


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:]))
