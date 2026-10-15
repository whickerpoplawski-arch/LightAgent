# 完整版实现 Plan：多对话身份编排

> 给 Cursor 云端实现用。中文。落 `local/`，少改内核，free-only，离线单测。  
> 依据：`multi_conversation_identity_survey_zh.md` + 已有 P0 记忆 + TUI Projects  
> 日期：2026-10-12 · **实现阶段勿默认调 OpenRouter**

---


> **用户澄清（2026-10-12）**：身份注入以**用户自定义**为主（自由填写职位/职责等）；预设模板仅为可选起点，不可强制选用模板。

## 0. 给用户看的 10 行摘要

1. 目标：侧边栏多 Bot/对话 + 右键菜单 + 每对话「设定身份」，最终能跨身份协作。  
2. 拆两层：先做**多会话壳与身份注入**，再做**跨 Bot 派发协作**（不默认 ToT）。  
3. 身份 = 职位/角色 system 块；**不进** User Profile；Profile 默认跨 Bot 共享。  
4. 右键对齐 Grok：置顶、移至分组、标未读、重命名、复制 ID、隐藏、删除，并加「设定身份」。  
5. 身份预设：生活助理、日程秘书、学习导师、出行顾问、健康习惯教练等。  
6. 阶段：P0.5 壳+身份 → P1 持久化/菜单齐全 → P2 `@`/派发协作。  
7. 代码落 `local/conversations/`（或 `local/bots/`）+ TUI 改动；复用 LightSwarm 做薄协作。  
8. 验收 E1–E18 离线可测；协作单测用 mock，不烧额度。  
9. 群聊多 Bot 同房写最终态，本 plan 首交付不做。  
10. 长久日用：身份/置顶/分组必须落盘，重启仍在。

---

## 1. 最终态（一句话）

用户在侧栏管理多个带身份的生活助手对话（可置顶、分组、隐藏、重命名），每个对话以独立职位/人设注入 system；需要时主对话可派任务给另一身份 Bot 并回写结果；User Profile 仍跨 Bot 共享，Persona/身份 per-Bot，Space 不串味。

---

## 2. 产品范围

### 2.1 侧边栏

- 列表展示：头像、标题（Bot 名）、预览、相对时间  
- 置顶区在上，其余按 `updated_at`  
- 隐藏项默认不显示；设置或「显示已隐藏」可恢复  
- 未读：圆点或粗标题；打开会话清未读（可手动再标未读）  
- 项目/分组：复用并强化现有 `Project`（「移至分组 / 移至新分组 / 移出分组」）  
- 顶栏动作：新建会话（Bot）、新建分组；**群聊入口可灰显或隐藏（后置）**

### 2.2 右键菜单（单会话）— 必须项

| # | 菜单项 | 行为 |
| --- | --- | --- |
| 1 | 置顶 / 取消置顶 | `pinned` 布尔；置顶区排序 |
| 2 | 移至分组… | 选已有 Project 或「新分组」 |
| 3 | 标为未读 / 标为已读 | `unread` |
| 4 | 重命名 Bot | 改 `title`（显示名） |
| 5 | 设定身份… | 打开身份编辑 Modal（见下） |
| 6 | 复制对话 ID | 剪贴板写 `session.id`；无剪贴板则通知栏展示 |
| 7 | 从侧边栏隐藏 / 取消隐藏 | `hidden` |
| 8 | 删除 | 确认后删会话（含消息）；不可恢复或进回收站（P1 简单确认即可） |

键盘等价：焦点在会话行时按 `:` 或 `m` 打开同一菜单；Delete 触发删除确认。

### 2.3 「设定身份」字段（与 User Profile 分离）

```text
Identity:
  display_name   # 可选，默认用 title
  role_title     # 短职位，如「日程秘书」
  job_description# 多行：职责、边界、语气
  template_id    # 可选，来自预设
  persona_mode   # inherit | override
                 # inherit = 全局 SOUL/IDENTITY + 本身份块
                 # override = 仅用本 Bot 的 persona 文本/文件
```

注入（ephemeral，不写进 messages 持久化）：

```xml
<identity bot_id="...">
角色：日程秘书
职责：...
</identity>
```

拼接顺序建议：`base system` → `<persona>`（全局或覆盖）→ `<identity>` → memory pack。  
**禁止**把 job_description 当作 `memory_learn` 写入 Profile。

### 2.4 身份预设模板（`templates.py`）

至少内置（中文）：

| template_id | role_title | 用途摘要 |
| --- | --- | --- |
| `life_assistant` | 个人生活助手 | 默认全能（与现 SOUL 对齐） |
| `schedule_secretary` | 日程秘书 | 日程冲突、提醒、今日三事 |
| `study_tutor` | 学习导师 | 讲解、计划、打卡，不代写应试作弊 |
| `travel_advisor` | 出行顾问 | 行程偏好、行李清单 |
| `habit_coach` | 习惯教练 | 运动/睡眠习惯，不诊疗 |
| `home_manager` | 家务管家 | 采购、家务清单 |
| `work_scribe` | 工作纪要 | 会议纪要、待办提炼（Space=work） |

选模板 → 填充 `role_title` + `job_description`，用户仍可改。

### 2.5 编排合作（最终态，P2 交付）

**最小可用协作语义（Delegate，非 ToT）：**

1. 用户在主对话输入含 `@日程秘书 帮我看下周是否冲突`，或点「请另一身份帮忙」。  
2. Host 解析目标 Bot（按 title / role_title / id）；目标必须已存在且未删除。  
3. 主 Agent 调用本地工具 `delegate_to_bot(bot_id, task, context_summary)`（或等价）。  
4. 运行时：用目标 Identity 构造**一次性**子 Agent（或注册进 LightSwarm），`run(task)`；**共享**同一 User Profile host；**不**把主会话全量历史塞给子 Agent（只传 task + 短 context + 必要 pack）。  
5. 子结果作为 tool result 回主 Agent；主 Agent 对用户总结；轨迹页记 `delegate` 步骤。  
6. 额度：子调用走同一 `openrouter_config` 日限；mock 后端可假回执。  
7. **不做**：多 Agent 自由互啄、默认 Flow DAG、默认 ToT、自动创建群聊。

可选增强（仍属 P2，可后移）：显式 Handoff「转交并把用户切到目标会话」。

---

## 3. 数据模型

```python
@dataclass
class BotIdentity:
    role_title: str = ""
    job_description: str = ""
    template_id: str | None = None
    persona_mode: str = "inherit"  # inherit | override
    persona_text: str = ""         # override 时使用；或指向文件

@dataclass
class ConversationMeta:
    id: str
    title: str
    avatar: str
    accent: str
    project_id: str | None
    space_id: str | None          # 生活域；可默认映射 project
    pinned: bool = False
    hidden: bool = False
    unread: bool = False
    updated_at: float
    created_at: float
    identity: BotIdentity = field(default_factory=BotIdentity)
    share_user_profile: bool = True   # 默认共享
    agent_id: str | None = None       # 稳定逻辑名，供 Swarm 注册
    # 消息体可分文件存：messages.json / 同库表
```

持久化建议（P1，P0.5 可先用同一 JSON 以免返工）：

```
local/data/workspace/
  workspace.json          # projects + conversation metas
  conversations/<id>.json # messages + events 摘要
```

或单 SQLite `local/data/workspace.sqlite`。选一种写清迁移；测试用 tmp_path。

**与 P0 记忆关系：**

| 数据 | 范围 | 说明 |
| --- | --- | --- |
| User Profile learnings | 跨 Bot 默认共享 | `share_user_profile=True` 时同一 `user_id` |
| situational | 可按 `space_id` 过滤 | host.space_id 盖章 |
| Persona 全局 | 默认 inherit | `local/persona/*` |
| Identity per-Bot | 每会话 | `<identity>` 块 |
| Persona override | 每 Bot 可选 | `local/persona/bots/<id>/` 或 inline |

---

## 4. TUI 交互与快捷键

| 操作 | 鼠标 | 键盘 |
| --- | --- | --- |
| 打开会话菜单 | 右键 SessionRow | `:` 或 `m`（焦点在行上） |
| 新会话 | 侧栏 + / 按钮 | Ctrl+N |
| 新分组 | | Ctrl+P（已有） |
| 设定身份 | 菜单 | 菜单内；或 Ctrl+Shift+I |
| 置顶 | 菜单 | 菜单内 |
| 删除 | 菜单 | Delete → 确认 Modal |
| 切对话/轨迹/记忆 | | Ctrl+1/2/3（已有） |

UI 组件：

- `ConversationMenuScreen(ModalScreen)` — OptionList  
- `IdentityEditorScreen(ModalScreen)` — 模板下拉 + role + job 文本区 + 保存/取消  
- 侧栏：`pinned` 区、隐藏过滤、未读样式  
- 顶栏展示当前 `role_title`（如有）

尽量把**纯逻辑**放 `local/conversations/context_menu.py`（apply_action），TUI 只负责展示——便于无头测试。

---

## 5. 分阶段交付

### P0.5 — UI 壳 + 身份（先可用）

**做：**

- `ConversationMeta` + `BotIdentity` 挂到现有 `Session`（可 composition 或扩字段）  
- 身份编辑 Modal + 预设模板  
- `inject`：`persona_system_block(session)` + `identity_system_block(session)`  
- backend `prepare_turn` / `attach_profile_memory` 传入当前 session 的 identity / agent_id / space_id  
- 最小菜单：重命名、设定身份、删除（确认）、移至分组（可复用已有 project API）  
- 右键或 `:` 打开菜单  
- 离线单测：身份块出现在 system、不出现在 stored user message；选模板填充字段  
- 中文 README：`local/conversations/README.md`

**不做：** 未读/隐藏/置顶精致交互可延后但模型字段可先加上；跨 Bot 协作；群聊。

**持久化：** 允许先内存 + 可选 JSON 快照；若半天内能做 `workspace.json` 读写则直接做，避免 P1 大改。

### P1 — 持久化 / 分组 / 菜单齐全

**做：**

- workspace 落盘；启动加载；每次菜单动作后保存  
- 菜单项齐全：置顶、移至新分组、未读、复制 ID、隐藏、删除  
- 侧栏渲染置顶区 / 隐藏过滤 / 未读标记  
- `share_user_profile` 开关（默认 True）；False 时该 Bot 不注入 Profile pack（仍可有 identity）  
- ux_probe / shot 覆盖菜单与身份顶栏  
- 迁移：无文件则 seed 演示工作区

### P2 — 跨 Bot 协作

**做：**

- `delegate_to_bot` 工具 + mock/真后端分支  
- 解析 `@角色名` 或命令面板选目标  
- LightSwarm 薄封装：按当前非隐藏会话的 `agent_id`/`title` 注册  
- 轨迹步骤 `kind=delegate`  
- 额度计入；失败可见错误（目标不存在、限额）  
- 单测：mock delegate 回写；禁止 ToT；子调用不把 pack 写入主 transcript

**后置（写最终态但不阻塞验收）：** 群聊 UI、Handoff 切会话、Flow 例程编排。

---

## 6. 目录与接入点

```
local/conversations/
  __init__.py
  models.py
  store.py
  templates.py
  identity_inject.py    # identity_system_block / resolve_persona
  context_menu.py       # actions: pin, hide, rename, ...
  collaborate.py        # P2 delegate
  README.md             # 中文
  tests/
    test_identity_inject.py
    test_context_menu.py
    test_store.py
    test_delegate.py      # P2
local/tui/app.py          # Session 扩字段、菜单、侧栏
local/tui/identity_ui.py  # Modal（可新建）
local/memory/inject.py    # 接受 persona_text / identity 参数（小改）
local/tui/backend.py      # chat 时带上当前 identity
```

**内核改动约束：**

- 优先不改 `LightAgent/core.py`  
- 若必须：仅文档化调用 `LightSwarm.register_agent` / `run(..., light_swarm=)` 从 `local/` 包装  
- **不要**默认打开 `tree_of_thought`  
- 保持 ephemeral：身份与 pack 只进当轮 system

`inject.py` 建议签名扩展（兼容旧调用）：

```python
def prepare_turn(..., persona_text: str | None = None, identity_block: str | None = None)
def persona_system_block(text: str | None = None)  # None → 读全局文件
```

---

## 7. 验收标准（可测）

### 壳与身份（P0.5+）

- **E1** 新建会话可打开「设定身份」，保存后 `meta.identity.role_title` 非空  
- **E2** 选模板 `schedule_secretary` 后 job_description 含日程相关文案  
- **E3** `prepare_turn` / mock chat：system（或 ephemeral provider 返回值）含 `<identity>`，且 **user 消息原文不变**  
- **E4** 身份文本**不**出现在 Profile store learnings  
- **E5** `persona_mode=inherit`：全局 SOUL 与 identity 同时存在；`override`：全局 SOUL 可不注入，仅 override 文本 + identity  
- **E6** 重命名只改 title，不改 id  
- **E7** 删除后列表不再出现该 id；确认取消则保留  

### 菜单与持久化（P1）

- **E8** 置顶后会话出现在置顶区；取消恢复  
- **E9** 移至分组 / 新分组后 `project_id` 正确；侧栏嵌套显示  
- **E10** 标未读 → UI 有未读态；打开会话后未读清除（或按产品约定）  
- **E11** 隐藏后默认列表不可见；取消隐藏恢复  
- **E12** 复制 ID：动作返回的 id 与 `session.id` 一致  
- **E13** 重启（或 `store.load`）后：身份、置顶、分组、隐藏仍在  
- **E14** `share_user_profile=False` 时 pack 不含 Profile learnings，仍可有 identity  

### 协作（P2）

- **E15** `delegate_to_bot` mock：主轨迹含 delegate 步骤，子结果回写，主 transcript **无** pack 污染  
- **E16** 目标 Bot 不存在 → 明确错误，不崩溃  
- **E17** 未开启协作时 `@` 仅当普通文本（或提示未启用），不误调用  
- **E18** 测试套件默认 **0** OpenRouter 请求（可用 env 哨兵或 mock）

### 回归

- 现有 `local/memory/tests` 全绿  
- `local/tui` mock shot / ux_probe 不挂（按改动更新断言）

**通过标准：** P0.5 交付 E1–E7；P1 再加 E8–E14；P2 再加 E15–E18。全绿才称「完整版达标」。

---

## 8. Cursor 实现约束

1. 代码只落 `local/`（conversations + tui + 对 inject 的小改）；少动 `LightAgent/` 包内文件。  
2. free-only：不新增默认付费模型；协作走现有限额。  
3. 离线单测：`pytest local/conversations/tests local/memory/tests`；实现与 CI 默认不调网。  
4. 中文 README（模块说明 + 快捷键 + 非目标）。  
5. 不照搬外部仓库代码；可对齐本调研的机制。  
6. 不做群聊、不做默认 ToT/Flow。  
7. 菜单逻辑可单测；TUI 可用 Textual pilot / 现有 ux_probe 风格。  
8. 文档更新：本 plan 勾选或另写 `multi_conversation_identity_acceptance_zh.md`。  
9. 若开 Cloud Agent：先 P0.5 PR，再 P1、P2；每阶段跑验收表。  
10. 用户机器路径：以 `/workspace/LightAgent` 为准。

---

## 9. 实现顺序（建议 Cursor 任务拆分）

1. `models.py` + `templates.py` + 单测模板  
2. `identity_inject.py` + 改 `inject.prepare_turn` + E3/E4/E5 单测  
3. `context_menu.py` 纯函数（rename/delete/move/pin…）  
4. TUI：Identity Modal + 菜单 Screen + Session 字段  
5. backend 传 identity / host.agent_id  
6. `store.py` 落盘 + E13  
7. 侧栏置顶/隐藏/未读渲染  
8. P2 `collaborate.py` + 工具注册 + E15–E18  
9. README + acceptance 报告  

---

## 10. 实现风险 Top3

1. **身份误写入 Profile / transcript** → 验收 E3/E4 一票否决；code review 盯 inject。  
2. **Textual 右键/焦点菜单 fragile** → 菜单动作必须纯函数可测；键盘 `:` 为一级入口。  
3. **P2 协作烧额度或递归互调** → 单层 delegate、白名单目标、计入日限、禁止 ToT；子 Agent 不携带「再 delegate」工具（或深度硬限制=1）。

次要风险：持久化格式来回改、Project 与 Space 双模型混淆（建议 `space_id` 默认等于 `project_id` 或显式映射表，文档写死一种）。

---

## 11. 非目标（全程）

- 复制 Grok 群聊完整产品  
- 企业级权限/多租户  
- 默认 Tree-of-Thought / 重型 LightFlow  
- 替换 P0 记忆栈  
- 付费模型依赖  

---

## 12. 验收报告模板（实现方填写）

```markdown
# 多对话身份编排验收
阶段：P0.5 | P1 | P2
E1..E18：PASS/FAIL/NA + 证据（测试名）
OpenRouter 调用次数：0
风险：...
结论：达标 / 未达标
```

