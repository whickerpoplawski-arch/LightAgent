# LightAgent TUI 简易模版

基于 [Textual](https://textual.textualize.io/) 的终端聊天界面，视觉参考 Grok Bot 桌面端：
左侧会话列表（彩色卡通头像）、右侧「对话 / 轨迹」双页、圆角气泡、底部胶囊输入框 + 实时 token 统计条。

```
local/tui/
├── app.py        # 界面与交互（会话、标签页、轨迹、统计、快捷键、设置入口）
├── app.tcss      # 软 UI 样式（浅灰白、圆角、彩色头像底、Settings）
├── settings.py   # Cursor 风格设置层：「插件」安装/开关
├── backend.py    # 后端：OpenRouterBackend（默认 MX，可切 OpenRouter）/ MockBackend
├── projects.py   # 项目数据结构
├── trace.py      # TraceStep / TraceStore / 时间线投影
├── tools.py      # Agent 工具：get_weather + web_search/web_fetch（来自 local/tools）
├── shot.py       # 无头测试 + 导出 SVG（对话页 + 轨迹页，mock，0 API）
├── ux_probe.py   # 交互探测（轨迹 / 项目 / 插件设置）
└── svg2png.sh    # SVG -> PNG（headless Chrome）
```

## 运行

日常默认走 **MX**（`deepseek-v4.1-flash`，`reasoning_effort=low`）。

```bash
cd /workspace/LightAgent
export MX_API_KEY=...   # 或 OPENAI_API_KEY

# 推荐：一键脚本
./local/run_tui.sh

# 等价：模块启动（未 --mock 时自动设 PROVIDER=mx / ALLOW / effort=low）
env -u NO_COLOR PYTHONPATH=. /workspace/la-venv/bin/python -m local.tui.app

# mock：不调 API（截图 / 调 UI）
./local/run_tui.sh --mock
# 或
env -u NO_COLOR PYTHONPATH=. /workspace/la-venv/bin/python -m local.tui.app --mock

# 可选：切回 OpenRouter :free
LIGHTAGENT_PROVIDER=openrouter OPENROUTER_API_KEY=... ./local/run_tui.sh
```

> 若终端是黑白的，检查是否设置了 `NO_COLOR`，用 `env -u NO_COLOR ...` 启动。

## 快捷键

| 按键 | 作用 |
|---|---|
| Enter | 发送 |
| Ctrl+1 | 切到「对话」页 |
| Ctrl+2 | 切到「轨迹」页 |
| Ctrl+U | 打开/关闭上下文占用弹出层 |
| Ctrl+N | 新会话（自动换下一个卡通头像） |
| Ctrl+K | 搜索会话 |
| Ctrl+L | 清空当前会话（含轨迹） |
| Ctrl+, | 打开设置（插件） |
| Ctrl+Shift+I | 设定当前 Bot 的身份（职位和职责，模板只是可选起稿） |
| `:` 或 `m` | 焦点在侧栏会话行上时，打开同一套会话菜单 |
| Delete | 焦点在会话行上时，确认删除 |
| Ctrl+Q | 退出 |

侧栏「+」按钮也可新建会话。

## UI 要点

- **设置 / 插件**：左下角 ⚙（或 Ctrl+,）打开设置层；左侧导航「插件」为首项；上方搜索/安装框支持本地路径、`owner/repo`、GitHub URL（git clone）；列表行标题 + 开关，写入 `local/plugins/enabled.json`，下次对话热加载工具（0 marketplace）
- **侧栏**：「项目」（可展开文件夹 +「+ 新项目」/ 行内 + 新建会话）与「会话」（未分组，按最后活动时间降序）；Ctrl+P 新项目，Ctrl+N 在当前项目或未分组新建会话
- **对话页**：用户蓝圆角气泡右对齐；Agent 灰圆角气泡左对齐；工具调用灰色斜体小胶囊
- **轨迹页**：
  - 顶栏：时长 / 轮次 / 调用数 + 轨迹搜索
  - 多泳道时间线：输入（青）/ 模型（紫）/ 工具（橙）/ 其他（绿）
  - 彩色标签 feed：用户 / 助手 / 工具 / 上下文（工具失败显示红色 ✕）
  - **可交互**：点击时间线条块跳到该步骤；点泳道名筛泳道；点步骤高亮；点「调用」只看工具；搜索支持 `tool:`/`model:`/`user:`/`助手:` 前缀（默认不误伤 detail 里提到的工具名）；Enter 跳回对话并高亮对应气泡/工具芯片；Esc 清筛选
- **底部统计条**（composer 下方）：`轮数 · 步数 · tok/s · 累计 tokens · 缓存命中% · 今日免费 x/45` + 可点的上下文 `%` 胶囊（Ctrl+U / 点击打开右侧紧凑「上下文已用」卡片：分段条 + 系统提示词/工具定义/对话消息）
- 注意：Textual「有底色 + round 边框」四角会露方块，气泡/输入框用「透明底 + 圆角描边」

## 统计字段：哪些是真的？

| 字段 | mock | 真实 OpenRouter |
|---|---|---|
| 轮数 / 步数 | 真（本会话计数） | 真 |
| tok/s | 假估算（按 tokens/耗时） | 假估算（启发式 tokens + 墙钟） |
| 累计 tokens | mock 假数 | 启发式估算（无 usage 回传） |
| 缓存命中% | mock 假数 | 固定 0（未知） |
| 今日免费 x/45 | mock 本地假计数 | 真（`openrouter_config`） |

## 额度保护

真实模式全部经过 `local/openrouter_config.py`：只允许 `:free` 模型，本地每日上限 45 次，
遇到限额/下线自动换下一个免费模型。带工具调用的一轮会记 2 次。

## 二开入口

- 换模型 / 接别的服务：实现 `chat(history, prompt) -> Reply` 和 `usage()`，替换 `backend.py`
- 加工具：在 `tools.py` / `local/tools/` 写函数 + `tool_info`，放进 `TOOLS`（联网工具已内置）
- 装插件：设置页或 `python -m local.plugins_system install <path|owner/repo>`；见 `local/plugins_system/README.md`
- 多轮记忆：每个 `Session.messages` 是 OpenAI 格式历史，作为 `history=` 传给 `LightAgent.run`
- 轨迹可视化：在 `Reply.steps` 填 `TraceStep`；会话级汇总在 `Session.trace`
- 改样子 / 换头像池：改 `app.tcss` 与 `app.py` 里的 `AVATARS`

## 测试 / 截图

```bash
env -u NO_COLOR PYTHONPATH=. uv tool run --from poetry==2.4.1 poetry run python -m local.tui.shot
sh local/tui/svg2png.sh /workspace/lightagent_tui.svg /workspace/lightagent_tui.png
sh local/tui/svg2png.sh /workspace/lightagent_tui_trace.svg /workspace/lightagent_tui_trace.png
sh local/tui/svg2png.sh /workspace/lightagent_tui_context.svg /workspace/lightagent_tui_context.png
# 交互探测（mock）：含设置·插件开关/本地安装，并写出 lightagent_tui_plugins.svg
env -u NO_COLOR PYTHONPATH=. uv tool run --from poetry==2.4.1 poetry run python -m local.tui.ux_probe
sh local/tui/svg2png.sh /workspace/lightagent_tui_plugins.svg /workspace/lightagent_tui_plugins.png
```

打开插件 UI：mock 启动后点左下角 **⚙**，或按 **Ctrl+,**。安装示例：

```text
local/plugins_system/examples/hello_plugin
```

## 联网工具（一等 Tools，非插件）

- `web_search` / `web_fetch`：实现在 `local/tools/web.py`，已加入 `TOOLS`
- 默认搜索：**ddgs**（零 key）；若设置 `TAVILY_API_KEY` 或 `BRAVE_API_KEY` 则优先
- 抓取：httpx + 正文抽取 + 截断 + SSRF（禁 localhost/私网）
- 冒烟（不走 OpenRouter）：`PYTHONPATH=. poetry run python -m local.smoke_web_tools`
- JS/交互站：用 Skill `browser-use`（[browser-use/browser-use](https://github.com/browser-use/browser-use)，见 `skills/browser-use/` 与 `example/08.browser_use.py`），不要把 search/fetch 做成 Skill
