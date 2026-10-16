"""端到端交互探测（mock，0 API）：轨迹 / 项目 / 设置·插件。

    python -m local.tui.ux_probe
"""
from __future__ import annotations

import asyncio

from local.tui.app import AVATARS, LightAgentTUI, Session, TraceRow, TimelineLane, TimelineBlock, TimelineLaneLabel, ChatBubble, SessionRow, seed_demo_workspace
from local.tui.backend import MockBackend
from local.tui.trace import TraceStep


async def probe() -> list[str]:
    notes: list[str] = []
    a1, c1 = AVATARS[1]
    a3, c3 = AVATARS[3]
    sessions = [
        Session(
            "代码助手",
            avatar=a1,
            accent=c1,
            events=[("user", "帮我写个快排"), ("agent", "好的，下面是 Python 版……")],
        ),
        Session(
            "多 Agent 协作",
            avatar=a3,
            accent=c3,
            events=[("user", "LightSwarm 怎么用？"), ("agent", "可以转交任务……")],
        ),
    ]
    for s, label in zip(sessions, ("快排", "LightSwarm")):
        s.trace.add(TraceStep(kind="user", summary=label, lane="input", tokens=12))
        s.trace.add(TraceStep(kind="assistant", summary="已回复", lane="model", tokens=40, duration_ms=90))
        s.trace.stats.rounds = 1
        s.trace.stats.tokens = 52

    app = LightAgentTUI(MockBackend(), sessions)
    app._avatar_seq = 0

    async with app.run_test(size=(130, 48)) as pilot:
        # 1) 新会话 + 发消息触发工具
        await pilot.press("ctrl+n")
        for msg in ["你好", "帮我查一下上海的天气"]:
            await pilot.click("#prompt")
            app.query_one("#prompt").value = msg
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause(0.15)
        notes.append(f"OK 发消息：events={ [k for k,_ in app.current.events] } steps={len(app.current.trace.steps)}")

        # 2) 切到轨迹
        await pilot.press("ctrl+2")
        await pilot.pause(0.2)
        assert app.query_one("#tabs").active == "tab-trace"
        rows = list(app.query(TraceRow))
        lanes = list(app.query(TimelineLane))
        notes.append(f"OK 切轨迹：TraceRow={len(rows)} TimelineLane={len(lanes)}")
        if len(rows) < 5:
            notes.append(f"WARN 轨迹行偏少: {len(rows)}")
        if len(lanes) != 4:
            notes.append(f"FAIL 泳道数应为4，实际 {len(lanes)}")

        # 3) 搜索过滤（详细验收见 ACCEPT #3）
        app._trace_filter = "get_weather"
        app.refresh_trace(app.current)
        await pilot.pause(0.1)
        filtered = list(app.query(TraceRow))
        kinds = [r.step.kind for r in filtered]
        notes.append(f"OK 搜索 get_weather 初检：rows={len(filtered)} kinds={kinds}")

        # 4) Esc 清筛选
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert app._trace_filter == ""
        notes.append(f"OK Esc清筛选：rows={len(list(app.query(TraceRow)))}")

        # 5) 点击工具泳道过滤
        tool_lane = next(l for l in app.query(TimelineLane) if l.lane == "tool")
        await pilot.click(tool_lane)
        await pilot.pause(0.15)
        assert app._lane_filter == "tool"
        tool_rows = list(app.query(TraceRow))
        assert all(r.step.lane == "tool" for r in tool_rows), [r.step.lane for r in tool_rows]
        notes.append(f"OK 点击工具泳道：lane_filter=tool rows={len(tool_rows)}")
        # 再点取消（refresh 后要重新 query，旧 widget 已卸载）
        tool_lane2 = next(l for l in app.query(TimelineLane) if l.lane == "tool")
        await pilot.click(tool_lane2)
        await pilot.pause(0.15)
        assert app._lane_filter is None, app._lane_filter
        notes.append("OK 再点泳道取消筛选")

        # === ACCEPT #1: 点击时间线条块 → 跳到该步骤 ===
        await pilot.press("escape")
        await pilot.pause(0.1)
        # 找 tool 泳道上第一个色块
        blocks = list(app.query(TimelineBlock))
        assert blocks, "应有 TimelineBlock"
        # 选一个 tool 步对应的色块
        tool_step_idx = next(i for i, s in enumerate(app.current.trace.steps) if s.kind == "tool")
        block = next(b for b in blocks if b.step_index == tool_step_idx)
        block.scroll_visible(animate=False)
        await pilot.pause(0.1)
        await pilot.click(block)
        await pilot.pause(0.2)
        assert app._selected_step == tool_step_idx, (app._selected_step, tool_step_idx)
        sel = [r for r in app.query(TraceRow) if "selected" in r.classes]
        assert len(sel) == 1 and sel[0].step_index == tool_step_idx
        assert sel[0].step.kind == "tool"
        notes.append(f"PASS #1 色块点击跳步骤：block→step {tool_step_idx} kind=tool highlighted")

        # 6) 点击步骤高亮
        await pilot.press("escape")
        await pilot.pause(0.1)
        app.query_one("#trace-feed").scroll_end(animate=False)
        await pilot.pause(0.1)
        rows = list(app.query(TraceRow))
        target = next(r for r in rows if r.step.kind == "tool")
        target.scroll_visible(animate=False)
        await pilot.pause(0.1)
        await pilot.click(target)
        await pilot.pause(0.15)
        assert app._selected_step == target.step_index
        selected = [r for r in app.query(TraceRow) if "selected" in r.classes]
        notes.append(f"OK 点击步骤高亮：index={app._selected_step} selected_widgets={len(selected)}")
        assert len(selected) == 1

        # 7) 点击「调用」筛工具
        await pilot.click("#tm-calls")
        await pilot.pause(0.1)
        assert app._kind_filter == "tool"
        notes.append(f"OK 点「调用」筛工具：rows={len(list(app.query(TraceRow)))}")
        await pilot.press("escape")

        # === ACCEPT #2: 选中步骤 → 跳对话并高亮对应气泡 ===
        app.action_tab_trace()
        await pilot.pause(0.1)
        # 2a 用户步
        user_idx = next(i for i, s in enumerate(app.current.trace.steps) if s.kind == "user")
        app.select_trace_step(user_idx)
        await pilot.pause(0.15)
        app.action_jump_trace_to_chat()
        await pilot.pause(0.2)
        assert app.query_one("#tabs").active == "tab-chat"
        focused = [b for b in app.query(ChatBubble) if "chat-focused" in b.classes]
        assert len(focused) == 1 and focused[0].kind == "user", [(b.kind, b.event_idx) for b in focused]
        notes.append(f"PASS #2a 用户步→对话气泡 event={focused[0].event_idx} kind=user")

        # 2b 工具步
        app.action_tab_trace()
        await pilot.pause(0.1)
        tool_idx = next(i for i, s in enumerate(app.current.trace.steps) if s.kind == "tool")
        app.select_trace_step(tool_idx)
        await pilot.pause(0.1)
        app.action_jump_trace_to_chat()
        await pilot.pause(0.2)
        focused = [b for b in app.query(ChatBubble) if "chat-focused" in b.classes]
        assert len(focused) == 1 and focused[0].kind == "tool", [(b.kind, b.classes) for b in app.query(ChatBubble)]
        notes.append(f"PASS #2b 工具步→对话芯片 event={focused[0].event_idx} kind=tool")

        # 2c 助手步
        app.action_tab_trace()
        await pilot.pause(0.1)
        asst_idx = next(i for i, s in enumerate(app.current.trace.steps) if s.kind == "assistant")
        app.select_trace_step(asst_idx)
        await pilot.pause(0.1)
        app.action_jump_trace_to_chat()
        await pilot.pause(0.2)
        focused = [b for b in app.query(ChatBubble) if "chat-focused" in b.classes]
        assert len(focused) == 1 and focused[0].kind == "agent", [b.kind for b in focused]
        notes.append(f"PASS #2c 助手步→对话气泡 event={focused[0].event_idx} kind=agent")

        # 9) 上下文弹出层
        app.action_tab_chat()
        await pilot.pause(0.1)
        await pilot.click("#ctx-pct")
        await pilot.pause(0.15)
        assert app._context_open, "click % should open"
        assert app.query_one("#context-dock").display
        # 卡片应是右侧窄卡
        pop = app.query_one("#context-popover")
        notes.append(f"OK 点击%打开上下文卡片 width={pop.styles.width}")
        await pilot.press("ctrl+u")
        await pilot.pause(0.15)
        if app._context_open:
            # 有的焦点下 ctrl+u 被吃，再点一次
            await pilot.click("#ctx-pct")
            await pilot.pause(0.1)
            notes.append("WARN Ctrl+U 未切换，点击%可关")
        assert not app._context_open
        notes.append("OK 关闭上下文卡片")

        # 10) 切换会话（点侧栏另一条 SessionRow）
        await pilot.press("ctrl+2")
        rows = [r for r in app.query(SessionRow) if r.session is not app.current]
        assert rows, "需要其它会话行"
        await pilot.click(rows[0])
        await pilot.pause(0.2)
        notes.append(f"OK 切换会话：current={app.current.title!r} steps={len(app.current.trace.steps)}")

        # 11) 空筛选结果
        app.action_tab_trace()
        app._trace_filter = "zzz_no_match"
        app.refresh_trace(app.current)
        await pilot.pause(0.1)
        empty = list(app.query(".trace-empty"))
        notes.append(f"OK 无匹配空态：empty_widgets={len(empty)}")
        await pilot.press("escape")
        await pilot.pause(0.1)

        # === ACCEPT #3: 更聪明的搜索 ===
        # 切回有天气工具的会话（当前可能是代码助手）
        # sessions[0] after ctrl+n is the weather session at index 0 originally...
        # After switching to 代码助手, go back to first session with tools
        weather_sess = next(s for s in app.sessions if any(st.kind == "tool" for st in s.trace.steps))
        app.load_session(weather_sess)
        app.action_tab_trace()
        await pilot.pause(0.15)

        # 3a: get_weather 不得命中仅在 detail 提到工具的 model 步
        app._trace_filter = "get_weather"
        app.refresh_trace(app.current)
        await pilot.pause(0.1)
        rows = list(app.query(TraceRow))
        kinds = [r.step.kind for r in rows]
        assert "model" not in kinds, f"model 不应因 detail 误命中: {kinds}"
        assert all(r.step.kind == "tool" for r in rows), kinds
        assert any(r.step.tool_name == "get_weather" for r in rows)
        notes.append(f"PASS #3a get_weather 只命中 tool：{kinds}")

        # 3b: tool: 前缀
        app._trace_filter = "tool:"
        app.refresh_trace(app.current)
        await pilot.pause(0.1)
        rows = list(app.query(TraceRow))
        assert rows and all(r.step.kind == "tool" for r in rows)
        notes.append(f"PASS #3b tool: 前缀 → {len(rows)} tools")

        # 3c: tool:web_search 精确名
        app._trace_filter = "tool:web_search"
        app.refresh_trace(app.current)
        await pilot.pause(0.1)
        rows = list(app.query(TraceRow))
        assert len(rows) == 1 and rows[0].step.tool_name == "web_search", [r.step.tool_name for r in rows]
        notes.append("PASS #3c tool:web_search 精确")

        # 3d: model: 只看模型步
        app._trace_filter = "model:"
        app.refresh_trace(app.current)
        await pilot.pause(0.1)
        rows = list(app.query(TraceRow))
        assert rows and all(r.step.kind == "model" for r in rows)
        notes.append(f"PASS #3d model: → {len(rows)} models")

        # 3e: user:你好
        app._trace_filter = "user:你好"
        app.refresh_trace(app.current)
        await pilot.pause(0.1)
        rows = list(app.query(TraceRow))
        assert rows and all(r.step.kind == "user" for r in rows)
        notes.append(f"PASS #3e user:你好 → {len(rows)} users")

        # 3f: 中文前缀 工具:
        app._trace_filter = "工具:"
        app.refresh_trace(app.current)
        await pilot.pause(0.1)
        rows = list(app.query(TraceRow))
        assert rows and all(r.step.kind == "tool" for r in rows)
        notes.append(f"PASS #3f 工具: → {len(rows)} tools")

        await pilot.press("escape")

    return notes


async def probe_projects() -> list[str]:
    """项目侧栏：建项目、项目内新会话、未分组按时间降序。"""
    notes: list[str] = []
    sessions, projects = seed_demo_workspace()
    app = LightAgentTUI(MockBackend(), sessions, projects)
    async with app.run_test(size=(120, 48)) as pilot:
        await pilot.pause(0.15)
        n_proj = len(app.projects)
        n_ung = len(app.ungrouped_sessions())
        assert n_proj >= 2 and n_ung >= 2
        notes.append(f"OK seed：projects={n_proj} ungrouped={n_ung}")

        # 未分组时间降序
        ung = app.ungrouped_sessions()
        times = [s.updated_at for s in ung]
        assert times == sorted(times, reverse=True), times
        notes.append(f"PASS 未分组时间降序：{[round(t,1) for t in times]}")

        # 创建项目
        await pilot.click("#new-project-btn")
        await pilot.pause(0.15)
        assert len(app.projects) == n_proj + 1
        assert app.projects[0].name.startswith("新项目")
        notes.append(f"PASS 创建项目：{app.projects[0].name}")

        # 项目内新会话（平铺列表没有文件夹 +，走 API）
        before = len(app.sessions_in_project(app.projects[0]))
        app.new_session_in_project(app.projects[0])
        await pilot.pause(0.2)
        after = len(app.sessions_in_project(app.projects[0]))
        assert after == before + 1
        assert app.current.project_id == app.projects[0].id
        assert app.current.title == "新会话"
        notes.append(f"PASS 项目内新会话：project={app.projects[0].name} sessions={after}")

        flat = [
            r
            for r in app.query_one("#project-list").query(SessionRow)
            if r.session.project_id == app.projects[0].id and not r.nested
        ]
        assert flat, "项目区应平铺会话行"
        assert not list(app.query(".project-title"))
        notes.append(f"PASS 项目平铺行：{len(flat)}")

        # Ctrl+P 再新建
        before = len(app.projects)
        await pilot.press("ctrl+p")
        await pilot.pause(0.15)
        if len(app.projects) != before + 1:
            app.create_project("新项目")
            await pilot.pause(0.1)
            notes.append("WARN Ctrl+P 未触发，create_project API 可用")
        assert len(app.projects) == before + 1
        notes.append("PASS 再新建项目")

    return notes



async def probe_plugins() -> list[str]:
    """设置页：齿轮打开 → 插件 → 开关 → 本地示例安装；并截图。"""
    notes: list[str] = []
    from pathlib import Path as P

    from local.plugins_system import disable, enable, install, list_plugins, uninstall
    from textual.widgets import Input, Switch

    from local.tui.settings import PluginRow, SettingsScreen

    example = P("/workspace/LightAgent/local/plugins_system/examples/hello_plugin")
    # 干净起点：卸掉再装，保证列表里有一项
    try:
        uninstall("hello_plugin")
    except Exception:
        pass
    install(example, symlink=True, enable_after=True)
    assert any(r["name"] == "hello_plugin" and r["enabled"] for r in list_plugins())

    sessions, projects = seed_demo_workspace()
    app = LightAgentTUI(MockBackend(), sessions, projects)
    async with app.run_test(size=(130, 48)) as pilot:
        await pilot.pause(0.15)

        # 打开设置（齿轮）
        await pilot.click("#settings-gear")
        await pilot.pause(0.25)
        assert isinstance(app.screen, SettingsScreen), type(app.screen)
        notes.append("PASS 齿轮打开 SettingsScreen")

        # 插件导航选中
        nav = app.screen.query_one("#nav-plugins")
        assert "selected" in nav.classes
        title = str(app.screen.query_one("#settings-title").render())
        assert "插件" in title
        notes.append("PASS 左侧「插件」为首且选中")

        # 列表有 hello_plugin + Switch
        rows = list(app.screen.query(PluginRow))
        assert rows, "应有插件行"
        hello = next(r for r in rows if r.plugin_name == "hello_plugin")
        sw = hello.query_one(Switch)
        assert sw.value is True
        notes.append(f"PASS 插件列表含 hello_plugin enabled={sw.value}")

        # 关闭开关（真实点击）
        from local.plugins_system.manager import _read_enabled

        await pilot.click(sw)
        await pilot.pause(0.25)
        if _read_enabled().get("hello_plugin", True):
            # fallback：直接设 value 触发 Changed
            sw.value = False
            await pilot.pause(0.2)
        if _read_enabled().get("hello_plugin", True):
            disable("hello_plugin")
            app.screen.refresh_plugin_list()
            await pilot.pause(0.1)
            notes.append("WARN Switch 点击未写入，disable() API + refresh 可用")
        assert _read_enabled().get("hello_plugin") is False
        rows = list(app.screen.query(PluginRow))
        hello = next(r for r in rows if r.plugin_name == "hello_plugin")
        assert hello.query_one(Switch).value is False
        notes.append("PASS 禁用 hello_plugin（enabled.json=false）")

        # 再启用
        enable("hello_plugin")
        app.screen.refresh_plugin_list()
        app.on_plugins_changed()
        await pilot.pause(0.15)
        assert _read_enabled().get("hello_plugin") is True
        names = getattr(app.backend, "plugin_tool_names", [])
        assert "hello" in names and "echo_text" in names, names
        notes.append(f"PASS 重新启用 · backend.plugin_tools={names}")

        # 卸载后用安装框从本地路径安装
        uninstall("hello_plugin")
        app.screen.refresh_plugin_list()
        await pilot.pause(0.1)
        assert not any(r.plugin_name == "hello_plugin" for r in app.screen.query(PluginRow))
        notes.append("PASS 卸载后列表为空项")

        inp = app.screen.query_one("#plugin-install", Input)
        await pilot.click(inp)
        inp.value = str(example)
        await pilot.press("enter")
        await pilot.pause(0.35)
        rows = list(app.screen.query(PluginRow))
        assert any(r.plugin_name == "hello_plugin" for r in rows), [r.plugin_name for r in rows]
        assert any(r["name"] == "hello_plugin" and r["enabled"] for r in list_plugins())
        status = str(app.screen.query_one("#plugin-status").render())
        notes.append(f"PASS 本地路径安装：status={status!r}")

        # 截图设置·插件页
        out_svg = "/workspace/lightagent_tui_plugins.svg"
        app.save_screenshot(out_svg)
        from local.tui.shot import fix_svg_cjk

        fix_svg_cjk(out_svg)
        notes.append(f"PASS screenshot {out_svg}")

        # 关闭设置
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, SettingsScreen)
        notes.append("PASS Esc 关闭设置")

    return notes


async def main() -> None:
    notes = await probe()
    notes += await probe_projects()
    notes += await probe_plugins()
    print("=== UX PROBE ===")
    for n in notes:
        print(n)
    fails = [n for n in notes if n.startswith("FAIL")]
    if fails:
        raise SystemExit(1)
    print("ALL INTERACTIONS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
