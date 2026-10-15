# 实现 Plan：主持式同房群聊（Hosted Room）

> 给 Cursor 云端：**边实现边验证**，每阶段 pytest 过关再进下一阶段；代码精简。  
> 依据：`multi_agent_group_chat_survey_zh.md`（首选 Hosted Room）、`multi_conversation_identity_plan_zh.md` + acceptance、`local/conversations/collaborate.py`  
> 风格对齐：`compact_impl_plan_zh.md` / `p0_memory_impl_plan_zh.md`  
> 日期：2026-10-12 · 落点：`local/rooms/` 为主，TUI 薄接线；**不改** LightSwarm.run 默认行为  
> **实现与单测默认不调 OpenRouter**；child 发言用现有 `run_delegation(..., mode="mock")`；真 `:free` 仅 opt-in。

---

## 0. 给用户 / Cursor 的 10 行摘要

1. **做什么**：侧栏真正「创建群聊」→ 共享消息流 → 用户一句话，Host 按规则请 1–N 个身份各说一轮（气泡带角色名），可 `@` 定向；支撑「今日健身、饮食规划」。  
2. **怎么跑**：每个群内发言 = 一次现有 **单层** `run_delegation`；**禁止** AG2 式 LLM 选麦互啄、禁止子再派发、禁止 ToT。  
3. **选谁说话**：代码编排 `TurnPlan`（`@` 优先 → 场景模板 → 沉默）；默认 `max_speakers≈3`，单回合气泡上限约 4（含 Host 短综合）。  
4. **身份 / 记忆**：成员仍是已有 `ConversationMeta`；Profile 可共享；`<identity>`/`<persona>` per utterance；群闲聊默认不写 Profile。  
5. **目录**：新逻辑进 `local/rooms/`；`collaborate.py` 只复用、不重写辩论内核。  
6. **TUI**：启用现灰显的「创建群聊」；群会话行 + 多 speaker 气泡；主对话 `@` delegate **保留**。  
7. **阶段**：R0 模型+TurnPlan+mock → R1 持久化+房间跑通 → R2 TUI → R3 边界（compact/memory/敏感）+回归。  
8. **每阶段必有可 pytest 的 E 项**；失败不进下一阶段。  
9. **非目标**：Crew/ChatDev 冒充群聊、群内审批/外发、默认 LLM auto 选麦、外部 IM 多 Bot。  
10. **验收锚点**：健身教练 + 饮食顾问同房，无 `@` 也能按模板各说一轮 + Host 综合。

---

## 1. 目标 / 非目标

### 1.1 目标（MVP 做完应有）

1. **GroupRoom** 一等实体：标题、成员（2–6 个已有 Bot）、Host、限额、持久化；重启仍在。  
2. **共享 transcript**：每条消息带 `speaker`（`user` | `host` | `bot:<id>` | `system`）；用户看见多身份气泡，不是折叠进 tool result。  
3. **TurnPlan（代码优先）**：解析 `@` / 场景模板（至少 `fitness_diet`）→ 有序 speaker 列表 → 顺序 `run_room_utterance` ≈ `run_delegation` → 可选 Host 短综合。  
4. **沉默一等公民**：未被选中的成员本回合不发言。  
5. **TUI**：创建群聊 Modal、侧栏群行、群内聊天、状态提示（「正在请习惯教练…」）。  
6. **边界**：群内禁敏感审批/外发伪成功；与 compact/memory/1:1 collab 边界清晰；E15–E18 类 1:1 delegate 回归仍过。  
7. **离线单测全绿**；可选真 `:free` 冒烟默认可跳过。

### 1.2 非目标（MVP 明确不做）

| 不做 | 原因 |
| --- | --- |
| AG2 / Letta `auto` LLM 选麦互啄 | `:free` 每轮多一次；失败模式见 failure map |
| CrewAI / ChatDev / MetaGPT 流水线冒充群聊 UI | 无同房气泡语义 |
| 默认开启 LightSwarm.run / handoff 链 | 与 `collaborate.py` 设计冲突 |
| 群内 Bot 自由异步互 @、无预算 | 刷屏烧额度 |
| 群内审批卡、密钥、邮箱/Slack 草稿「已发送」 | 对标 Grok：敏感回 1:1 |
| 把全量群 transcript 塞进每个 child | 只传 task + 短 digest + 必要 pack |
| 外部 Slack/WhatsApp 多 Bot 同房 | 后置 |
| 替换主对话 `@` / `delegate_to_bot` | 群聊是平行入口 |

### 1.3 用户硬约束（不可违背）

| 项 | 决定 |
| --- | --- |
| 运行时 | 复用单层 `run_delegation`；子无 `delegate_to_bot`、无 ToT |
| 选麦 | **默认规则 Host**，不默认 LLM 选麦 |
| 成本 | `:free`；`max_speakers` 默认 3；复用/延伸 `DelegateQuota` |
| 代码 | 精简；逻辑在 `local/rooms/`；内核尽量零改 |
| 验证 | **每功能/每阶段**有 pytest；达预期再合并下一阶段 |
| MVP 场景 | 「今日健身、饮食规划」同房协调可演示 |

---

## 2. 数据模型

### 2.1 核心类型（建议 `local/rooms/types.py`）

```python
@dataclass
class GroupRoom:
    id: str
    title: str
    member_bot_ids: list[str]      # ConversationMeta.id，2–6，去重保序
    host_bot_id: str | None        # None = 内置「生活助手 Host」虚拟主持（不占成员席）
    max_speakers: int = 3
    max_bubbles_per_turn: int = 4  # 含 Host 综合
    scenario_hints: list[str] = field(default_factory=list)  # 如 ["fitness_diet"]
    created_at: float
    updated_at: float
    pinned: bool = False
    hidden: bool = False
    unread: bool = False
    space_id: str | None = None    # 可选；默认可与 project 对齐

@dataclass
class RoomMessage:
    id: str
    role: str                      # "user" | "assistant" | "system"
    speaker: str                   # "user" | "host" | f"bot:{meta.id}" | "system"
    speaker_label: str             # 展示名：用户 / 生活助手 / 习惯教练
    content: str
    ts: float
    turn_id: str | None = None     # 同一用户回合共用
    kind: str = "chat"             # chat | host_summary | system_notice | error
    meta: dict = field(default_factory=dict)  # bot_id, template_id, error, etc.

@dataclass
class TurnPlan:
    turn_id: str
    speakers: list[str]            # 有序 bot id；不含 host（host 综合另一步）
    reason: str                    # "mention" | "template:fitness_diet" | "fallback_host_only"
    include_host_summary: bool = True
    silent_member_ids: list[str] = field(default_factory=list)

@dataclass
class TurnResult:
    turn_id: str
    plan: TurnPlan
    bubbles: list[RoomMessage]     # 已写入 transcript 的本回合气泡
    errors: list[str] = field(default_factory=list)
```

### 2.2 与 `ConversationMeta` 的关系

| 概念 | 关系 |
| --- | --- |
| 成员 | **引用**已有 `ConversationMeta.id`；不复制 Identity；改设定身份立即对下次 utterance 生效 |
| Host | 优先：指定某 Bot 为 Host；默认：虚拟 Host（代码模板综合，可不烧 LLM） |
| 1:1 会话 | 成员 Bot 自己的侧栏会话**继续存在**；群聊不吞掉 1:1 transcript |
| 侧栏行 | Room 是**另一类行**（`kind=room`），不是把 ConversationMeta 改成群 |

持久化建议（对齐现有 `local/conversations/store.py` 风格）：

```text
local/data/workspace/
  workspace.json          # + "rooms": [ GroupRoom.to_dict(), ... ]
  rooms/<room_id>.json    # { "messages": [ RoomMessage, ... ], "trace": {...} }
```

- `version`  bump 或兼容读：无 `rooms` 键 = 空列表。  
- 删成员 Bot：Room 保存时校验；缺失成员 → 系统气泡提示 + TurnPlan 跳过。  
- 测试一律 `tmp_path`。

### 2.3 Transcript 消息形状（写入约定）

```json
{
  "id": "m1",
  "role": "assistant",
  "speaker": "bot:abc123",
  "speaker_label": "习惯教练",
  "content": "今晚做 20 分钟徒手，避开深蹲…",
  "ts": 1728...,
  "turn_id": "t9",
  "kind": "chat",
  "meta": {"bot_id": "abc123", "via": "run_delegation"}
}
```

用户消息：`speaker="user"`。Host 综合：`speaker="host"`, `kind="host_summary"`。

**不要**把 child 的 `<identity>` / pack 写入房间 messages（与 E3/E15 一致）。

---

## 3. 回合编排

### 3.1 流水线（实现必须一致）

```text
[用户在 Room 发一条消息]
  1. append RoomMessage(user)
  2. plan = build_turn_plan(text, room, roster)   # 纯函数，可单测
  3. digest = build_room_digest(recent_messages) # 短；禁 ephemeral 标签
  4. for bot_id in plan.speakers:                 # 已截断至 max_speakers
       outcome = run_room_utterance(...)          # 包装 run_delegation
       append bubble(speaker=bot:…)
       if bubbles >= max_bubbles_per_turn: break
  5. if plan.include_host_summary and 还有气泡额度:
       append host_summary（规则模板优先；可选 mock/LLM）
  6. 失败：系统 error 气泡 + Host 用已有片段尽力综合；不抛崩 TUI
  7. 更新 room.updated_at / unread
```

### 3.2 `build_turn_plan` 规则（MVP，零选麦 LLM）

1. **多 `@`**：用现有 mention 正则（可抽 `collaborate._MENTION` 或 rooms 内复用同一模式）；按出现顺序 `resolve_bot(roster, token)`；只保留 **本房成员**；去重保序；截断 `max_speakers`。`reason="mention"`。  
2. **无 `@`**：匹配场景模板（见下）；命中则按模板 speaker 角色解析到成员（按 `role_title` / `template_id` / 标题模糊匹配）。  
3. **模板未命中**：`speakers=[]`，`include_host_summary=True`，`reason="fallback_host_only"`——Host 用一句话引导用户 `@` 某人或说明「可以说：今日健身和饮食」。  
4. **沉默**：`silent_member_ids = members - speakers`。  
5. **焦点不盖安全**：若用户句含忌口/否决，digest 与 task 保留原话片段；模板不能删掉「禁止事项」。

### 3.3 场景模板表（MVP 至少 1 个）

| template_id | 触发关键词（中文，小写/包含） | speakers 顺序 | Host 综合 |
| --- | --- | --- | --- |
| `fitness_diet` | 健身、锻炼、运动、饮食、配餐、今日练、吃什么（需同时沾「动/练」类 **或** 用户显式「健身和饮食/运动和饮食」） | 1) 习惯教练/`habit_coach` 2) 饮食顾问/`nutrition_advisor`（若无则跳过并 system 提示缺成员） | 是：≤5 行，点名引用两人要点 |
| `schedule_conflict`（可选 R2） | 冲突、档期、日程撞 | 日程秘书 | 是 |

**成员准备**：MVP 文档要求用户先建好两个身份 Bot（可用模板）。若仓库尚无 `nutrition_advisor` 模板，**允许**在 `templates.py` **加一条精简模板**（饮食顾问：配餐建议、尊重忌口、不诊疗）——这是为场景服务的最小增量，不算「新协作内核」。

触发检测必须是 **纯函数 + 单测**，避免误伤闲聊；宁可 fallback_host_only，也不要乱拉全员。

### 3.4 `run_room_utterance`（复用契约）

```text
run_room_utterance(room, bot_id, user_text, digest, roster, quota, mode) -> RoomMessage
  → 调用 run_delegation(
        roster=成员对应 ConversationMeta 列表（可含全 roster 以便 resolve）,
        bot_id=bot_id,
        task=面向该角色的短任务（可加「你在群「{title}」中发言；只代表自己；2–5 句」）,
        context_summary=digest,   # 禁止夹带 <memory-context>/<persona>/<identity>
        depth=0,                  # 对 run_delegation 而言仍是「父层发起」
        quota=共享 DelegateQuota 或 RoomQuota,
        profile_block=…,         # 仅当 meta.share_user_profile
        mode=mock|live,
     )
  → 将 outcome.result 映成 RoomMessage；step 写入 room trace
```

硬约束（测试锁死）：

- child tools **无** `delegate_to_bot`（沿用 collaborate 断言）。  
- 子 `tree_of_thought=False`。  
- pack/identity **不**出现在房间 bubble content。  
- 同一 `turn_id` 内 speaker 次数计入 `max_speakers` / quota。

### 3.5 Host 综合（默认零 LLM）

MVP 默认 **规则拼接**：

```text
【综合】
- 习惯教练：{截断摘要}
- 饮食顾问：{截断摘要}
下一步：{若有未决则列出；否则「按上面执行即可」}
```

可选：`LIGHTAGENT_ROOM_HOST_LLM=1` 时用 `:free` 极短综合；单测默认关。

### 3.6 成本闸

| 闸 | 默认 |
| --- | --- |
| `max_speakers` | 3 |
| `max_bubbles_per_turn` | 4 |
| 成员数 | 创建时校验 2–6 |
| `DelegateQuota` | 复用；群发言每次 utterance `charge` 一次 |
| 可选 `RoomQuota` | 每日群气泡上限（可与 DelegateQuota 共用一个计数，MVP 不必两套） |
| 选麦 LLM | **默认关** |

---

## 4. TUI

### 4.1 入口

- 侧栏 `group-chat-btn`：去掉「稍后」灰态，改为可点「创建群聊」。  
- Modal：选 2–6 个已有 Bot（多选列表）+ 群标题（可默认「健康日常」）+ 可选勾选场景提示 `fitness_diet`。  
- 创建成功 → 侧栏出现 **Room 行**（头像可用 👥）→ 打开群 transcript。

### 4.2 群内 UI

| 元素 | 行为 |
| --- | --- |
| 气泡 | 显示 `speaker_label` + 内容；Host / 不同 Bot 可不同 accent |
| 输入 | 普通发送走 Turn 流水线；支持 `@显示名` / `@role_title` |
| 状态 | 轮到某 Bot 时 status「正在请{label}…」；结束清除 |
| 顶栏 | 群标题 + 成员缩略名 |
| 菜单 | 重命名群、管理成员（增删，仍限 2–6）、删除群（确认）——逻辑放 `local/rooms/actions.py`，便于无头测 |

### 4.3 与 1:1 的区分

- 打开 Room **不**走 `_maybe_delegate` 主对话路径；走 `rooms.runtime.run_user_turn`。  
- 主对话 `@` 行为 **不变**（回归 E15–E18）。

### 4.4 精简原则（UI）

- 不重做整套侧栏；RoomRow 尽量复用 SessionRow 样式或薄包装。  
- 逻辑不进 `app.py` 长函数：app 只调 `rooms.actions` / `rooms.runtime`。

---

## 5. 与 memory / compact / collab 边界

| 层 | 群聊行为 |
| --- | --- |
| **collab** | `run_delegation` 为唯一 child 原子；不调用 `LightSwarm.run`；不新增「群内再 delegate」 |
| **identity** | 每次 utterance `blocks_for_meta`；禁止写入 Profile learnings |
| **User Profile** | `share_user_profile=True` 的成员可注入同一 pack；忌口对饮食顾问可见 |
| **群发言 → Memory** | **默认不** admission；用户明确「记住…」仍走既有 learn 路径（若在 Host 综合里出现，可后置；MVP 不做自动从群气泡 learn） |
| **compact** | 房间 transcript 独立文件；若消息变长，R3 可复用 compact 的 prune/尾部策略 **仅作用于 room messages**；**不要**把 room 全量与 1:1 会话混压 |
| **space_id** | Room 可有 `space_id`；situational 召回按 Host stamp，不串其它 space（有测则测） |
| **敏感动作** | 检测用户要「发邮件/下单/交密钥」→ Host/system 气泡：「请回主对话或该 Bot 的 1:1 处理」；**不**调用外发工具 |

---

## 6. 分阶段交付 + 每阶段验证清单

> Cursor：**完成一阶段 → 跑该阶段 E 表 → 全绿再下一阶段**。禁止一次性堆完再测。

### R0 — 纯逻辑（无 TUI）

**做：** `local/rooms/`：`types`、`plan.py`（TurnPlan）、`digest.py`、`utterance.py`（包 `run_delegation`）、`templates_scenario.py`（fitness_diet）、`tests/`。

| ID | 场景 | 期望 |
| --- | --- | --- |
| E1 | `@习惯教练 …` 且教练在成员内 | speakers 仅教练；饮食顾问在 silent |
| E2 | 无 @，文案「安排今日健身和饮食」+ 两成员匹配 | speakers=[教练, 饮食顾问]；reason 含 fitness_diet |
| E3 | 无 @，无关闲聊 | fallback_host_only；speakers=[] |
| E4 | speakers 截断 max_speakers=1 | 只跑 1 个 child |
| E5 | `run_room_utterance` mock | bubble.speaker=`bot:…`；content 无 `<identity>`/`<memory-context>` |
| E6 | child 路径 | 调用栈等价单层；模拟 depth 禁再派发（复用/断言 collaborate 行为） |

**闸门：** `pytest local/rooms/tests` 本阶段相关全绿；0 网络。

### R1 — 持久化 + runtime 一回合

**做：** `store.py` 读写 rooms；`runtime.run_user_turn` 端到端写 transcript；缺成员/配额错误气泡。

| ID | 场景 | 期望 |
| --- | --- | --- |
| E7 | create room → save → load | 成员与标题仍在 |
| E8 | run_user_turn 健身+饮食 | transcript 顺序：user → 教练 → 饮食 → host_summary |
| E9 | 配额用尽 | error/system 中文气泡；不抛未捕获异常 |
| E10 | 删除成员 Bot 后再 turn | 跳过缺失 + 提示；不崩 |

**闸门：** R0+R1 测试全绿。

### R2 — TUI 接线

**做：** 启用创建群聊；Room 侧栏；气泡渲染 speaker_label；输入走 runtime；状态文案。

| ID | 场景 | 期望 |
| --- | --- | --- |
| E11 | 点击创建群聊并选 2 Bot | 侧栏出现群；点开可见空或欢迎 system |
| E12 | 群内发「今日健身和饮食」 | 可见至少 2 个不同 speaker_label 气泡 + Host 综合（mock） |
| E13 | 群内 `@饮食顾问 只改午餐` | 仅饮食顾问气泡；教练沉默 |
| E14 | 主对话原 `@` delegate | 行为不变（跑 conversations 既有 E15–E18 或子集） |

可用 Textual 探针或无头 `apply_action` 风格（对齐 identity 菜单测法）。**闸门：** E11–E14 + 回归 conversations/memory 冒烟。

### R3 — 边界打磨 + 文档

**做：** 敏感意图拦截；room digest 长度上限；README；可选 room compact hook（可只留接口）；`nutrition_advisor` 模板若未加则补上。

| ID | 场景 | 期望 |
| --- | --- | --- |
| E15 | 「帮我发邮件订餐」 | 无外发；系统/Host 提示回 1:1 |
| E16 | digest/task 不含 ephemeral 标签 | 断言 |
| E17 | `LIGHTAGENT_FORBID_OPENROUTER=1` 全套 rooms 测试 | 0 外网；live 路径拒绝 |
| E18 | 回归 | `pytest local/rooms local/conversations local/memory`（及 compact 若存在）全绿 |

**人工验收场景（协调方 / 用户明日）：** 见文末「建议验收场景」。

---

## 7. 目录建议

```text
local/rooms/
  __init__.py          # 导出 run_user_turn, create_room, …
  types.py             # GroupRoom, RoomMessage, TurnPlan, TurnResult
  plan.py              # build_turn_plan
  scenarios.py         # fitness_diet 等模板与匹配
  digest.py            # 短 room digest
  utterance.py         # run_room_utterance → run_delegation
  host_summary.py      # 规则综合（默认）
  runtime.py           # run_user_turn 编排
  store.py             # rooms 持久化（或扩展 conversations/store，二选一写清）
  actions.py           # 创建/改名/成员变更（供 TUI）
  sensitive.py         # 敏感意图检测（规则）
  README.md
  tests/
    test_plan.py
    test_runtime.py
    test_store.py
    test_acceptance.py   # E1–E18 索引
```

薄改：

- `local/conversations/templates.py`：可选新增 `nutrition_advisor`  
- `local/conversations/store.py`：**仅当**选择把 rooms 嵌进 workspace.json 时扩展；否则 rooms 独立 store，workspace 只存 room id 列表——**优先独立 `rooms/store.py` + workspace.json 增加 `rooms` 数组**，避免弄脏 ConversationMeta  
- `local/tui/app.py`：启用群聊按钮、RoomRow、接线；逻辑外置  
- **禁止**改 `LightAgent/core.py` 为群聊开后门；**禁止**默认打开 LightSwarm.run

复用：

- `collaborate.resolve_bot` / `plan_mention` 模式 / `run_delegation` / `DelegateQuota` / `blocks_for_meta`  
- memory pack 注入方式与 1:1 child 相同（通过 `profile_block` 参数）

---

## 8. 实现顺序（写给 Cursor）

1. R0：types + scenarios + plan + utterance(mock) + 单测 E1–E6  
2. R1：store + runtime + E7–E10  
3. 补 `nutrition_advisor` 模板（若缺）  
4. R2：TUI 最小可用 + E11–E14 + 1:1 回归  
5. R3：sensitive + README + E15–E18 + 全量回归  
6. 每步保持模块短小：一个文件一个职责；无「万能 RoomManager 上帝类」

环境变量：

| 变量 | 含义 |
| --- | --- |
| `LIGHTAGENT_COLLAB` | 既有；=0 时群聊也应拒绝 child 或整特征关闭（与产品一致：建议群聊依赖 collab=1） |
| `LIGHTAGENT_ROOM_HOST_LLM` | 默认 0；Host 综合走规则 |
| `LIGHTAGENT_ALLOW_OPENROUTER` | child live；测试默认无 |
| `LIGHTAGENT_FORBID_OPENROUTER` | 测试哨兵 |

---

## 9. 复审节（写完自审）

### 9.1 相对调研删减了什么（故意不做）

| 调研提及 | 本 plan MVP | 理由 |
| --- | --- | --- |
| AG2 Selector / Letta dynamic 选麦 | 不做（仅留「深度模式」一句话后置） | `:free` + 用户要求不默认 LLM 选麦 |
| Bot↔Bot 异步 handoff、群内互 @ | 不做 | 成本与串味；澄清靠下一用户回合 |
| 并行 `asyncio.gather` 双专家 | 不做为默认 | 顺序更易让饮食引用运动负荷；并行可后置 |
| 无 UI 的并行 delegate 冒充群聊 | 明确非目标 | 用户要同房 |
| OpenClaw 式 IM 群绑一脑 | 不做 | 产品不对口 |
| 完整 Grok 私信分流 / 群内表单 | 不做 | 范围膨胀 |
| Room situational 独立 memory space | 仅保留 space_id 字段；不做新 admission 路径 | 精简；忌口走 Profile |
| 群气泡自动压后分流 skill | 不做 | 属 compact 域；避免两套抽取 |

### 9.2 相对调研保留的硬核

- Hosted Room = P5 壳 + P2 运行时  
- 共享 transcript + speaker 标签  
- `@` + 沉默 + max_speakers≈3  
- 单层 utterance = `run_delegation`  
- 群内禁敏感审批  
- 健身+饮食场景模板  
- 失败回退与配额中文错误  

### 9.3 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 模板误触发拉人 | 保守匹配 + E3；fallback Host 引导 |
| 饮食顾问模板缺失 | plan 允许加一条 templates 条目 |
| TUI 一次性改爆 app.py | actions/runtime 外置；RoomRow 薄 |
| 与 1:1 delegate 分叉 | 共用 run_delegation；E14/E18 回归 |
| 串味 / pack 泄漏 | E5/E16；复用 collaborate 断言 |
| 额度烧尽 | max_speakers + quota + mock 默认 |
| 「开会」空转 | Host 综合必须点名；TurnPlan.reason 可进 trace |

### 9.4 精简原则（实现时自检）

1. 能复用 `run_delegation` 就不新写 child runner。  
2. 能规则选人就不加选麦 LLM。  
3. 能独立 `local/rooms/` 就不改 core。  
4. 一个阶段一闸门；测不过不堆功能。  
5. 文件保持可扫：单个模块 ideally &lt; ~200–300 行；超出则拆。  
6. 不引入 AutoGen/Crew 依赖。

### 9.5 复审结论

- Plan 与调研「唯一首选 Hosted Room」对齐；MVP 范围可演示「今日健身、饮食规划」。  
- 刻意砍掉 LLM 选麦与互啄，满足用户与 `:free`。  
- 验收 E 表可 pytest；TUI 与持久化分阶段，降低一次性翻车概率。  
- **诚实缺口**：Host 综合默认是规则拼接（不像真人开会）；饮食是否「引用」教练负荷在 mock 下只能测到「顺序与 digest 传入」，语义质量靠 live/`：free` 或改进 task 提示——不在离线 E 表夸大。

---

## 10. 建议验收场景（人工 / 明日试用）

1. **建群**：侧栏创建群聊，选「习惯教练」+「饮食顾问」，标题「健康日常」→ 重启后仍在。  
2. **同房协调**：群内发「帮我安排今日健身和饮食（忌深蹲，晚饭少油）」→ 两条身份气泡 + Host 综合；忌口出现在饮食侧任务/回复中；教练未提深蹲方案。  
3. **@ 与沉默**：`@习惯教练 只改今晚训练` → 仅教练说话；饮食顾问沉默；主对话里单独 `@` 另一 Bot 仍可用。

---

## 11. 成功标准（本文件）

- [x] 文档落盘本路径  
- [x] 含复审节（删减 / 风险 / 精简）  
- [x] E1–E18 可测  
- [x] 复用 `run_delegation` 写死  
- [x] 非目标含：不做 AG2 auto、不做 Crew 冒充群聊、群内禁敏感审批  

**复审后 MVP 一句话：**  
侧栏建 2–6 人 Room，共享带 speaker 的 transcript；用户一句由规则 TurnPlan（`@` 或健身+饮食模板）顺序触发最多约 3 次单层 `run_delegation`，Host 规则综合收尾——即可演示同房「今日健身、饮食规划」，且不引入 LLM 选麦互啄。
