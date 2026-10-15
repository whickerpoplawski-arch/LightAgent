# LightAgent 长链路 Harness：完美最小集（生活助手优先修订版）

> 定位：全方位个人生活助手（非 coding agent 复刻）  
> 约束：OpenRouter `:free`；日限 45；默认少 LLM；先最小集，扩展叠其上  
> 日期：2026-10-14（America/Martinique / AST）  
> 范围：**只读架构草案**；**未改业务代码**；讨论通过后再 Cursor 实现  
> **主深挖（生活助手）**：`life_assistant_long_horizon_deepdive_zh.md`  
> 对照（coding，主线已转向）：`long_horizon_harness_deepdive_zh.md`  
> 前序：`harness_production_eval_zh.md` · `openhuman_memory_source_notes_zh.md`

---

## 0. 相对上一版改了什么（生活助手导向）

| 项 | 上一版（coding 证据主导） | 本版 |
| --- | --- | --- |
| 主证据 | Codex/Claude/OpenHands | **OpenHuman / Grok 形态 / OpenClaw / Mem0 / ChatGPT Tasks**；coding 只保留三句共性 |
| 模块数 | 6 | **7**：新增 **M0 EphemeralPackLane**、**M7 SoftRoutineGate**；原 M1–M6 重命名/重锚 |
| Goal | 主要对齐 Codex ThreadGoal | 对齐 **OpenHuman goal⊥todo⊥learnings** + ChatGPT Memory⊥Tasks |
| Compact | Pre/Mid/Post 相位 | 加上 **OpenClaw memoryFlush** + OH `resumed_after_compaction` + 群「用户句+Constraint 保真」 |
| 主动续聊 | 刻意不做跨天 | **薄 SoftRoutine**（显式、可 pause、计日限）——来自 Grok Routines / ChatGPT Scheduled |
| Host | Codex update_plan 短回执 | **Grok 群阶段 owner + OH 通知不堆叠** 气质 |
| 反互啄 | 子代理回摘要 | **选麦+配额+Host 三行+禁默认评委模型**（Grok/OH） |
| 忘记/改主意 | 弱 | **forget/supersede**（Mem0 additive 陷阱 + OpenClaw USER.md） |

**仍不做**：OS sandbox、默认 ToT/DAG、Host/compact 默认 LLM、Dreaming/belief 全量、tinyflows、推送风暴。

---

## 1. 最小集原则（硬约束）

1. 服务生活助手长链路：**跨轮可收敛、跨天可提醒、可中断、不丢忌口、不骚扰、不多 Bot 互啄**。  
2. **三栏分家**：Learnings/Profile（耐久）⊥ LifeGoal/Checkpoint（任务）⊥ SoftRoutine（日程）。来源：OH + ChatGPT + Mem0。  
3. **Pack 永不进 transcript**（OH 硬规则；LA `inject.py` 已声明）。  
4. **Live 路径 fail-open**（OH prefetch timeout）：无 pack 也要能回。  
5. **压缩 ≠ 记忆**：压前 flush → 耐久层；compact 只管模型可见窗口。  
6. **截断不得把限制变成许可** → ConstraintCard 整条保留/整条省略。  
7. **复用库原语接线**：`CancellationToken` / `BudgetLimits` / 1:1 compact / Room digest；能接上就不重造。  
8. 默认少 LLM；日限 45 下 SoftRoutine 自动跑模型必须有闸。

---

## 2. 底层依据摘要（生活助手）

### 2.1 最硬共性

1. **窗外耐久事实** — OH Learnings+pack；OpenClaw USER/MEMORY；Mem0 user_id；ChatGPT saved memory。  
2. **窗外任务进度** — OH goal/todo；Grok 多步 skill 演示后固化；ChatGPT tasks/dot notes。  
3. **压前把重要东西写到窗外** — OpenClaw memoryFlush；LA `compact/flush.py`；OH compaction recall。  
4. **主动触发在聊天外且可停** — Grok routines；ChatGPT scheduled；OH workflows/cron + notification threshold。  
5. **可中断 + 硬预算** —（coding 对照一句）库有原语日用未接 = 没有；OH goal banner 含 budget reached。

### 2.2 刻意不搬

| 能力 | 原因 |
| --- | --- |
| OH tinyflows 22 节点 / Grok 全量事件总线 | 过重；SoftRoutine JSON 足够 |
| OpenClaw Dreaming 默认 cron | 扩展；`:free` 后台 LLM 贵 |
| Mem0 托管 Graph / 每轮 LLM extract | 最小集用规则 flush + 显式 learn |
| Grok 云电脑 / 真推送 | 本机 TUI；due-on-open 即可 |
| Coding OS sandbox / Guardian 第二模型 | 非生活助手最小核 |

---

## 3. 完美最小集（7 模块）

```
M0 EphemeralPackLane   Pack/Persona 车道；永不写回聊天（OH）
M1 LifeGoalStore       线程/房间完成契约 + 步骤（OH goal；跨天可持久化）
M2 CheckpointStore     中断续跑 + pending_side_effects
M3 CompactPreFlush     1:1+群钩子；压前 flush；约束保真（OpenClaw+OH）
M4 RunControl          cancel + 单次 run 预算 → TUI
M5 ConstraintCard      忌口/偏好 active 集；可 forget/supersede（OH/Mem0/OpenClaw）
M6 HostedProgress      群：动作/忌口/下一步；反回声（Grok+OH）
M7 SoftRoutineGate     显式提醒/例程；pause；计日限（Grok/ChatGPT）
```

---

### M0 — EphemeralPackLane

**依据**：OH pack 永不进 transcript；Persona ≠ Learnings；拒绝 notice ≠ 空记忆；`local/memory/inject.py`。

**不变量**

- 注入顺序：base system → persona → identity → `<memory-context>` pack。  
- `strip_ephemeral` 在 store / Room digest / 子委派前必须跑。  
- Pack 构建超时/失败 → 无 pack 继续；若为 UNAVAILABLE/额度类 → 注入短 notice。  
- 子 Bot 委派：**host stamp** 用户 scope；禁止子请求改写全局 namespace。

**接线**：`local/memory/inject.py`、`pack.py`、`rooms/digest.py`；验收：transcript 文件无 `<memory-context>`。

**失败语义**：fail-open；不得阻塞用户可见首包。

---

### M1 — LifeGoalStore

**依据**：OH `goal_set/get/complete` + session `todo`（工作态 ≠ learnings）；ChatGPT tasks 与 memory 分家；可持久化强于 OH 内存 todo（服务跨天）。

**创建门槛（推荐）**：仅显式用户意图或房间模板（「今日健身和饮食」）——对齐 OH「goal 是完成契约」与 Codex「勿从 tool 自动虚构 UserGoal」精神。

**Schema**
```json
{
  "goal_id": "hex",
  "space_id": "session_or_room",
  "objective": "string",
  "constraints_ref": ["learning_id_or_text"],
  "steps": [{"id": "s1", "title": "...", "status": "pending|in_progress|completed"}],
  "status": "active|paused|budget_reached|completed|cancelled",
  "acceptance": ["string"],
  "updated_at": "ISO-8601",
  "source": "explicit_user|room_template"
}
```

- 路径：`{workspace}/local/goals/{goal_id}.json`  
- **至多一个** `in_progress`  
- 注入：每轮 ephemeral 只带 objective 一行 + 当前 step 标题 + ConstraintCard（非整份历史）  
- 短问答不建 goal（E9）

**接线**：TUI run 前；Room `run_user_turn` 前；可选映射库 `GoalManager` 事件。

---

### M2 — CheckpointStore

**依据**：生活助手「改主意/停止」+ coding 半执行语义（对照一句）；OH workflow run durable pause。

**Schema**
```json
{
  "checkpoint_id": "hex",
  "goal_id": "hex",
  "step_id": "s1|null",
  "room_id": "optional",
  "constraints_snapshot": ["..."],
  "pending_side_effects": [{"kind": "advice_shown|routine_due_listed", "detail": "..."}],
  "reason": "step_done|user_cancel|budget|room_turn_end|compact_pre|user_revise",
  "ts": "ISO-8601"
}
```

- 写：步完成 / cancel / budget / room 轮末 / 用户改目标  
- 读：「继续」→ 跳过 completed；提示 pending_side_effects  
- **不** snapshot 文件系统

---

### M3 — CompactPreFlush

**依据**：OpenClaw memoryFlush；OH resumed_after_compaction；群函数未接线；`local/compact/flush.py`。

**抽象**
```text
on_before_model / on_save_room:
  1. flush → Profile/Learnings/daily（fail-open；忌口 pin never）
  2. 确保 ConstraintCard active 集可抽取
  3. 1:1: 现有 ContextCompactor / >阈值路径
  4. room: compact_room_messages(keep=N)
       + 强制保留：最近 K 条用户句 + 命中 Constraint 的句子
  5. 标记 space resumed_after_compact（可选）供下轮 pack
```

- 群默认 **零 LLM**；LLM summarizer → 扩展 X5  
- `_save_rooms`（`app.py:1426`）**必须**调用 compact

**失败语义**：compact 失败保留原文；不得清空 Constraint 源。

---

### M4 — RunControl

**依据**：OH goal budget reached；Grok 例程烧额度教训；库 token+budget（coding 对照：未接=没有）。

```text
make_agent(..., budget_limits=BudgetLimits(model_calls≤8, seconds≤120), context_budget=...)
agent.run(..., cancellation_token=child)
UI 停止 → cancel → M2(user_cancel)
BudgetExceeded → M1 status=budget_reached + M2(budget) + 用户可见
```

- 日限 45 = 全局闸；BudgetLimits = 单次 run  
- 取消粒度：协作边界 + 文案承认建议可能已展示  
- SoftRoutine 触发的 run **同样**走 M4

---

### M5 — ConstraintCard

**依据**：OH Learnings；OpenClaw USER.md supersede；Mem0 additive 需显式纠正；忌口不可截断变质。

**Schema**
```json
{
  "items": [
    {"id": "c1", "text": "忌口：海鲜", "status": "active|superseded", "updated_at": "..."}
  ],
  "open_questions": ["..."],
  "source": ["learning", "profile", "goal"]
}
```

- 注入 / Host「忌口」行 / compact keep：**唯一真相源**  
- API：`remember` / `forget` / `supersede`（用户改主意）  
- 无 LLM 规则抽取优先；失败则注入 goal.constraints 原文列表

---

### M6 — HostedProgress

**依据**：Grok 群 2–6 + 阶段 owner；OH 通知不堆叠；现 `host_summary.py` 易回声。

**输出契约（规则，默认无 LLM）**
```text
动作：...          # 本轮实际发言成员的一句话动作，非粘贴全文
忌口：...          # 必须来自 M5 active
下一步：...        # LifeGoal 下一 pending/in_progress 或用户可说的短指令
```

- 禁止整段子 Bot 原文；`LIGHTAGENT_ROOM_HOST_LLM=1` 可选默认关  
- 选麦：保持规则 plan + DelegateQuota；不新增评委模型

---

### M7 — SoftRoutineGate

**依据**：Grok Routines（skill=如何，routine=何时；pause；久离询问；≥5min）；ChatGPT Scheduled（Free 日频、闲置 pause、上限）；OH notification threshold + 默认 off workflow。

**最小行为（本机 TUI）**

- 仅用户显式创建（聊天指令或 UI）。  
- 存储：`{workspace}/local/routines/{id}.json`  
- 字段：`title`, `instruction`, `cadence`（`daily_window|weekly|once`）, `timezone`, `paused`, `owner_space`, `last_run_at`, `next_due_at`  
- **交付**：打开 App / 进入对应会话时列出 due；用户确认或一键跑 → 走 M4；**不**默认系统推送。  
- **闸**：全局「自动 routine 模型调用」计入日限；建议默认 ≤1 次自动执行/日；堆积 due **不补跑**，只提示。  
- 久未使用：下次打开询问 keep/pause（对齐 Grok）。  
- 删除/pause = 可忘记的跨天目标。

**不做（最小集）**：Slack/webhook 全通道、monitoring 爬网、多 provider 通知中心。

---

## 4. 端到端时序

```text
A. 多轮同日（健身+饮食，忌口海鲜）
  用户明示 → M1 LifeGoal + M5 Constraint
  M0 pack 注入（忌口在 learnings）
  M4 run；步完成 → M2
  用户停止 → M4 cancel → M2；「继续」读 M2
  消息变长 → M3 flush+compact（保 M5）
  Room → M6 三行

B. 跨天（每周一提醒称重）
  用户：「每周一提醒我称重」→ M7 SoftRoutine
  下周一打开 App → due 列表 → 确认 → M4 短 run
  改主意 → M7 pause/delete；忌口变更 → M5 supersede
```

---

## 5. 接线表

| 钩子 | 文件:行（约） | 动作 |
| --- | --- | --- |
| pack 注入 | `local/memory/inject.py` | 守 M0；notice on refusal |
| flush | `local/compact/flush.py` | M3 压前调用 |
| `agent.run` | `local/tui/backend.py` | M4 token；组装 M1/M5 ephemeral |
| `make_agent` | `local/openrouter_config.py` | M4 budget + context_budget |
| `_save_rooms` | `local/tui/app.py:1426` | M3 `compact_room_messages` |
| digest | `local/rooms/digest.py` | strip ephemeral；可保真 Constraint 句 |
| Host | `local/rooms/host_summary.py` | M6 三行 |
| Room turn | `local/rooms/runtime.py` | 读 M1/M5；写 M2 |
| SoftRoutine | 新建 `local/routines/` | M7 |
| Goal 文件 | 新建 `local/goals/` | M1 |
| Memory store | `local/memory/store.py` | M5 supersede/forget |

---

## 6. 刻意不做（最小集禁止项）

- OS/容器 sandbox；默认 ToT/DAG/LLM 互啄；默认 Host/compact LLM。  
- Dreaming / 全量 belief cron / Mem0 每轮 LLM extract。  
- 系统推送风暴；宽触发「全频道任意消息」。  
- 合并 1:1 与 Room 物理 transcript；把 pack 写入用户消息。  
- 短问答自动建 LifeGoal；每条用户消息都写 checkpoint。

---

## 7. 验收（E1–E12，离线优先）

| ID | 标准 |
| --- | --- |
| E1 | 多步后存在 goal JSON；constraints/忌口可追溯到 M5 |
| E2 | 至多一个 `in_progress` |
| E3* | cancel → 无未捕获异常；checkpoint；可查 cancelled |
| E4* | 「继续」不重建 goal；completed 不重复 |
| E5 | BudgetLimits 耗尽 → budget_reached + 可见提示 |
| E6 | 群 save 后条数 ≤ keep；Constraint 句仍在 |
| E7 | 1:1 compact 后忌口仍在 pack/上下文 |
| E8 | Host 三行；无整段回声 |
| E9 | 短问答不建 LifeGoal |
| E10 | 默认路径无额外评委/Host LLM |
| E11 | transcript **无** `<memory-context>` 落盘 |
| E12 | SoftRoutine：显式创建、pause、due-on-open；改主意可删；不计时自动偷跑模型 |

\* 多步+中断+恢复必过。

---

## 8. 扩展槽（P1+）

| ID | 依赖 | 说明 |
| --- | --- | --- |
| X1 口语选麦/模板 | M1,M6 | |
| X2 合理默认上下文窗 | M3 | |
| X3 LifeGoal↔LightFlow | M1,M2 | |
| X4 Host LLM | M6 | 旗标默认关 |
| X5 LLM compact | M3,M5 | 失败回退 |
| X6 Dreaming/belief | M0,M5 | OH jobs / OpenClaw dreaming |
| X7 外发审批 UI | M4 | |
| X8 真推送 / webhook | M7 | Grok/ChatGPT 事件档 |
| X9 monitoring 任务 | M7 | ChatGPT monitoring |
| X10 Active cross-DM recall | M0 | OpenClaw Active Memory |
| X11 Steer-at-boundary | M4 | |

---

## 9. 讨论议题（请拍板）

### Q1. LifeGoal 创建门槛？
- **A** 仅显式/模板（推荐）— OH/ChatGPT「任务是完成契约」  
- **B** 规则自动检测复合任务

### Q2. SoftRoutine 自动执行强度？
- **A** due-on-open + 用户确认才跑模型（推荐，`:free`）  
- **B** 到点后台自动跑（需本机常驻/云，超出当前 TUI 最小集）

### Q3. 群 compact？
- **A** 尾窗+用户句+Constraint 零 LLM（推荐）  
- **B** +可选摘要旗标（=X5）

### Q4. 单次 run 默认预算？
- **A** 紧：`model_calls≤8`、`seconds≤120`（推荐）  
- **B** 松，靠日限 45

### Q5. Host 默认 LLM？
- **A** 永不默认（推荐）  
- **B** 复杂 Room 自动开

### Q6. 取消粒度？
- **A** 协作边界 + 半执行文案（推荐）  
- **B** 立刻杀线程（TUI 成本高）

### Q7.（新增）改忌口语义？
- **A** supersede in place，注入只看 active（推荐，OpenClaw/Mem0）  
- **B** 只追加，靠模型自行消歧（易矛盾）

---

## 10. 建议实现顺序（交 Cursor）

1. M0 验收加固（pack 不落盘）+ M4 RunControl  
2. M3 群 compact 接线 + flush 挂所有 compact 入口 + M5  
3. M1 LifeGoal + 注入 + M2 继续  
4. M6 Host 三行  
5. M7 SoftRoutineGate（due-on-open）  
6. E1–E12 离线单测  

---

## 11. 证据与缺口

**已核实**：OH clone（hooks/jobs/prefetch/goals docs/notifications）；Grok/Cursor 公开 routines/bots docs；OpenClaw memory/compaction docs；Mem0 how-it-works；ChatGPT Memory/Tasks help；LA `inject`/`flush`/`digest`/`host_summary`/`_save_rooms`。  

**缺口**：Grok/ChatGPT 内部实现未公开；OpenClaw 未全仓 clone；未 live 跨天长跑。  

**置信度：~0.86**（生活助手导向可讨论拍板；Q1–Q7 后锁实现）。
