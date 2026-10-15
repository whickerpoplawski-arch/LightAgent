# 调研：多对话身份编排（完整版）

> 定位：长久日用的全方位个人生活助手  
> 对照：Grok Bot 侧边栏多 Bot + 右键菜单 +「设定身份」诉求  
> 范围：只读本地代码 + 公开概念；**未改**业务代码；**未调** OpenRouter  
> 日期：2026-10-12（America/Martinique）

---

## 0. 结论先行

用户要的「完整版」其实是两层能力叠在一起：

| 层 | 是什么 | 用户截图主要覆盖？ | 难度 |
| --- | --- | --- | --- |
| **A. 多会话壳（产品）** | 侧边栏多个对话/Bot；右键置顶/分组/重命名/隐藏/删除；每对话一份身份 | **是** | 中：主要改 TUI + 持久化元数据 |
| **B. 运行时多 Agent 协作（内核）** | 主对话 `@` 另一身份，或派子任务给另一 Agent 实例并回写 | 部分（「编排合作」） | 中大：要接 LightSwarm/轻量派发，控制额度 |

**不要混成一件事。** A 不做，B 没有挂载点；B 不做，A 只是「多个带 system 前缀的聊天窗口」。完整版最终态两者都要，但交付必须分阶段：先壳与身份，再持久化与菜单齐全，最后跨 Bot 协作。

本地基线：**侧栏 Session + Project 已有雏形，但无右键菜单、无身份字段、无磁盘持久化；Persona 全局一份；上游已有 LightSwarm handoff 与 LightFlow，TUI 尚未接。**

---

## 1. 本地现状（只读扫描）

### 1.1 TUI 壳 — `local/tui/`

| 能力 | 现状 | 路径 |
| --- | --- | --- |
| 侧栏会话列表 | 有：`Session` + `SessionRow`，头像/标题/预览/时间 | `app.py` `Session` |
| 项目分组 | 有：`Project` + `ProjectRow`，可展开、项目内新建会话 | `projects.py`、`app.py` |
| 新建会话/项目 | 有：Ctrl+N / Ctrl+P、侧栏 + | `app.py` Bindings |
| 搜索会话 | 有：Ctrl+K | `app.py` |
| 右键菜单 | **无** | — |
| 置顶 / 隐藏 / 未读 / 复制 ID | **无** | — |
| 重命名 Bot | **无**（标题随会话，无菜单入口） | — |
| 每对话身份/职位 | **无** | — |
| 磁盘持久化 | **无**（进程内内存；重启丢失） | `projects.py` 注释写明 |
| Modal 模式 | 有：Settings 用 `ModalScreen` | `settings.py` |
| Mock 后端 | 有：已走 `prepare_turn` ephemeral pack | `backend.py` |

当前 `Session` 字段大致：`title, messages, events, avatar, accent, trace, id, project_id, updated_at`。  
缺：`pinned, hidden, unread, identity, persona_override, space_id, bot_name, share_profile` 等。

### 1.2 Persona / 用户画像 — `local/memory/` + `local/persona/`

| 项 | 现状 |
| --- | --- |
| 全局 Persona | `local/persona/SOUL.md` + `IDENTITY.md`；`persona.py` 整段注入 `<persona>` |
| 每 Bot Persona 覆盖 | **无**（`load_persona_text()` 无 session/agent 参数） |
| User Profile | P0 SQLite + general/situational；`MemoryHost` 已预留 `session_id` / `agent_id` / `space_id` |
| Pack 注入 | ephemeral 进 system；**不**写回聊天（已验收） |
| 身份 ≠ 用户画像 | 文档与代码均强调；设定身份时应进 Persona/identity 块，**不**写进 Profile learnings |

接入点：`inject.prepare_turn` / `attach_profile_memory` 目前写死全局 `persona_system_block()`——多身份时这里要变成「全局默认 + 本 Bot 覆盖」。

### 1.3 上游多 Agent 运行时

| 模块 | 路径 | 作用 | 与完整版关系 |
| --- | --- | --- | --- |
| **LightSwarm** | `LightAgent/core.py` `LightSwarm` | 注册多 Agent；`run(..., light_swarm=)` 时解析 `transfer to X` handoff | **P2 协作首选**：按身份名注册 Bot，主对话可转交 |
| 示例 | `example/04.multi_agent.py` | 前台/预订/技术/HR 四角色 | 产品壳应对齐「身份 = role + instructions」 |
| **LightFlow** | `LightAgent/flow.py` | DAG 步骤、依赖、审批、超时 | 偏工作流引擎；生活助手「随便 @ 一下」过重，**P2 不用默认开** |
| **ToT** | `core.py` `tree_of_thought` | 额外推理模型调用 | **烧额度**；完整版明确禁用默认 ToT |
| SessionStore | `LightAgent/session.py` | 事件溯源/fork/replay | 内核会话模型；TUI 自己的 `Session` 未对接 |

结论：协作不必自研编排内核——**复用 LightSwarm handoff**，在 `local/` 做「Bot 注册表 + 派发工具 + 结果回写气泡」即可。Flow/ToT 不进默认路径。

### 1.4 与生活助手愿景的衔接

`personal_life_assistant_memory_zh.md` 已规划 Space（家/工作/学习/出行）与 Persona 分栏。多对话身份应：

- **User Profile**：默认跨 Bot **共享**（「越用越懂」是懂你这个人）
- **Persona / 身份**：per-Bot（日程秘书 ≠ 学习导师）
- **situational / Space**：可按 `space_id` 或 project 过滤，避免工作客户名串进「家」闲聊
- **Project**：现有 TUI 项目 ≈ 分组；完整版「移至分组」应统一到同一模型，不必再发明第二套文件夹

---

## 2. 业界拆法（轻量对照）

### 2.1 多会话壳（产品）

ChatGPT Projects、Claude Projects、Cursor Agents 列表、Grok Bot 侧栏：共同点是 **UI 元数据 + 每会话 system/自定义指令**，记忆策略各异。

用户截图菜单（右键单对话）：

1. 置顶  
2. 移至新分组  
3. 标为未读  
4. 重命名 Bot  
5. 复制对话 ID  
6. 从侧边栏隐藏  
7. 删除  

另：侧栏顶「创建新 Bot / 创建群聊」；列表多项独立 Bot。  
用户额外要求：**「设定身份」**（职位/身份描述）——截图菜单里没有，但产品必须加。

**群聊**（多 Bot 同房）完整版可规划，但实现成本高（@ 路由、发言权、共享 transcript）。建议最终态写入，**首交付不做群聊 UI**，用「主对话派发子 Agent」替代协作体验。

### 2.2 运行时协作（内核）

常见模式：

| 模式 | 语义 | 适合本产品？ |
| --- | --- | --- |
| Handoff / transfer | A 把整轮转给 B | 适合「这件事该日程秘书管」 |
| Delegate / sub-call | A 调 B 拿结果，A 继续对用户说 | **最适合**个人助手（用户仍跟主 Bot 聊） |
| Swarm 自由互调 | 多 Agent 来回 | 易失控、烧额度；需白名单 |
| Flow DAG | 固定流水线 | 适合例程，不适合随意对话 |
| ToT | 多路径搜索 | 默认关 |

OpenHuman/Letta 类产品强调 **Persona 块常驻、记忆按 scope**——与我们 P0 一致：身份是「助手是谁」，不是「用户是谁」。

### 2.3 对本仓库的启示

1. **先做壳**：没有稳定的 Bot 元数据与身份注入，协作无处可挂。  
2. **身份 = 注入 system 的 role 块**，与 Profile pack 分栏拼接。  
3. **协作最小语义用 Delegate**（子调用回写），Handoff 作为可选；不要一上来 ToT/Flow。  
4. **持久化必须尽早**：否则置顶/身份/分组重启即丢，违背「长久日用」。  
5. Textual 无原生桌面右键菜单惯例时，可用：**右键 / 菜单键 / `:` 快捷菜单** 打开 `ModalScreen` 或弹出 `OptionList`（已有 Settings Modal 模式可复用）。

---

## 3. 差距矩阵（现状 → 完整版）

| 能力 | 现状 | 完整版目标 | 建议阶段 |
| --- | --- | --- | --- |
| 多会话列表 | 有 | 有 + Bot 感命名 | 已有 |
| 项目分组 | 有（内存） | 持久化 + 移至分组菜单 | P0.5→P1 |
| 右键菜单 | 无 | 截图 7 项 +「设定身份」 | P0.5 部分 / P1 齐全 |
| 设定身份 | 无 | title/role/job → system | P0.5 |
| 身份预设模板 | 无 | 生活助理/日程秘书/学习导师等 | P0.5 |
| 置顶/隐藏/未读 | 无 | 有 | P1 |
| 复制 ID / 删除确认 | 无 | 有 | P1 |
| Persona per-Bot | 无（全局） | 覆盖文件或 inline identity | P0.5 |
| Profile 共享 | 全局一份 | 默认共享，可标隔离 | P0.5 默认 / P1 开关 |
| 磁盘持久化 | 无 | JSON/SQLite workspace | P1（P0.5 可先 JSON） |
| @ / 派发协作 | 无（内核有 Swarm） | Delegate 最小可用 | P2 |
| 群聊多 Bot | 无 | 最终态可选 | 后置 |
| ToT / Flow 默认 | 有模块 | 默认关 | 全程 |

---

## 4. 风险与设计原则

### 4.1 风险 Top

1. **把身份写进 User Profile**：污染「越用越懂」；必须 Persona/identity 通道。  
2. **协作默认全量 Swarm**：额度与失控；应用白名单 + 单次子调用预算。  
3. **只做内存 UI**：重启丢身份/置顶，违背长久日用；P1 前必须落盘。  
4. **Textual 右键体验弱**：需键盘等价操作与可测 API，不能只依赖鼠标。  
5. **改内核过深**：应落 `local/bots/` 或 `local/conversations/`，Swarm 只做薄封装。

### 4.2 硬原则（承接记忆 P0）

1. Pack / 身份块 **永不写回** transcript。  
2. Persona/身份 ≠ User Profile。  
3. Host stamp：`agent_id` / `session_id` / `space_id` 由壳盖章。  
4. free-only；协作子调用计入同一日限额。  
5. 离线单测可验收菜单与注入，不调 OpenRouter。

---

## 5. 推荐落点（给 Plan 用）

```
local/conversations/     # 或 local/bots/
  models.py              # Conversation/Bot 元数据、Identity
  store.py               # JSON/SQLite 持久化
  templates.py           # 身份预设
  inject_identity.py     # 拼 <identity> / 覆盖 persona
  collaborate.py         # P2：delegate / register swarm
  context_menu.py        # 菜单动作纯函数（便于单测）
  tests/
local/tui/               # 接菜单、Modal、侧栏置顶/隐藏渲染
local/persona/bots/<id>/ # 可选：每 Bot SOUL 覆盖
```

复用：`local/memory/inject.py`、`MemoryHost`、`Project`、上游 `LightSwarm`。

---

## 6. 给用户的直觉说明

- 现在：多个聊天窗口 + 项目文件夹，但**不能**给某个窗口设「你是日程秘书」，也**不能**右键管理，重启还丢。  
- 完整版：每个对话像一个带职位的小助手；侧栏像 Grok Bot；需要时主助手可以请另一个身份帮一把，再把结果说给你听。  
- 用户画像仍然一份、跨助手共享——变的是**助手角色**，不是把你记成好几个人。

