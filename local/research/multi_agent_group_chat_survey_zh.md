# 调研：多智能体 / 多身份「同房群聊」实现与 LightAgent 方案建议

> 定位：全方位个人生活助手二开（wanxingai/LightAgent）  
> 范围：**只调研 + 写文档**，未改业务代码；未默认调 OpenRouter  
> 日期：2026-10-12（America/Martinique，AST）  
> 约束：`:free`、中文、X 搜索 ≤25 次/分钟  
> 依据：本地 `multi_conversation_identity_*`、`collaborate.py`、TUI delegate；公开文档/源码；Grok Bot 公开产品文档 + 可读 skill

---

## 0. 结论先行（读完这节即可拍板）

**唯一首选：主持式同房群聊（Hosted Room）= Grok 式「共享 transcript + @ 定向」产品壳 × OpenAI Agents SDK「agents-as-tools / 主助手保留终稿权」运行时 × 复用并增强现有单层 `delegate_to_bot`。**

不要用 AutoGen/AG2 默认的 LLM `auto` 自由互啄当 MVP；不要用 CrewAI/ChatDev/MetaGPT 那种任务流水线冒充「群聊 UI」。生活助手要的是：**用户看见多个身份在同一条消息流里按角色发言、互相接话，但仍由一个主助手控成本与终稿。**

| 备选 | 何时再考虑 |
| --- | --- |
| **A. AG2 式 Selector GroupChat（LLM 选下一个）** | 用户明确要「多轮辩论/评审」，且接受额外选麦 LLM 成本 |
| **B. 无群聊 UI 的并行 Delegate 增强** | 只想要结果、不要同房气泡（现状小改即可，**不满足**「同房」诉求） |

---

## 1. 目标与约束

### 1.1 产品目标

用户场景例：「今日健身、饮食规划」——希望 **健身教练** 与 **饮食顾问** 等身份在 **同一群聊房间** 里按身份协调，而不是只在主对话里 `@` 派一次活、结果折叠进 tool result。

已有基线（见 `multi_conversation_identity_plan_zh.md` / 验收）：

| 能力 | 状态 |
| --- | --- |
| 侧栏多 Bot、设定身份、Profile 共享 / Persona 隔离 | ✅ |
| 单层 `@` / `delegate_to_bot`（子不可再派发） | ✅ |
| **同房群聊**（共享 transcript、多发言方气泡） | ❌ 首交付明确后置 |

### 1.2 硬约束

- OpenRouter **`:free`**：每用户回合 LLM 次数必须可预算；禁止默认 ToT / 无界互调。
- 身份 ≠ 用户画像：`<identity>` / `<persona>` 不进 Profile learnings（已验收 E3/E4）。
- `collaborate.py` 刻意 **不调用** `LightSwarm.run`（避免模型链上 `transfer to`）；只当 roster 注册表。
- 与 compact / memory 一致：压前 flush、忌口双保险；群聊 transcript 要可裁剪。

### 1.3 分析维度（全文贯穿）

1. 房间模型：共享 transcript vs 分线程汇总  
2. 发言权：轮询 / 主持人选下一个 / @ 定向 / 并行再合并  
3. 身份与记忆：persona 隔离、共享 user profile、防串味  
4. 对用户可见性：群消息流 vs 主助手只出终稿  
5. 成本：几轮 LLM、`:free` 可行性  
6. 与现有 delegate：增强 vs 另建子系统  

---

## 2. 业内实现地图

### 2.1 范式总表

| 范式 | 房间 | 发言权 | 用户可见 | 成本特征 | 代表 |
| --- | --- | --- | --- | --- | --- |
| **P1 共享线程 + Manager 选麦** | 全体共享一份 messages | LLM auto / round_robin / 图约束 | 全量中间话可见（或可 summary） | 每轮 +1 选麦 LLM；易长聊 | AG2 GroupChat、MS AutoGen SelectorGroupChat、Letta dynamic/supervisor |
| **P2 Manager 呼叫专家（agents-as-tools）** | 可有可无共享 UI | 主机决定谁被 call | 默认可只出终稿；可把子回复投影成气泡 | 可控：每专家 1 次 | OpenAI Agents SDK、现有 LightAgent delegate、OpenClaw team coordinator |
| **P3 Handoff 转交所有权** | 会话所有权切换 | 转交后专家直接对用户说 | 用户跟「当前 winner」聊 | 中等；易丢主助手语境 | OpenAI Swarm→Agents handoff、LightSwarm `transfer to`、LangGraph swarm |
| **P4 顺序/层级任务流水线** | 通常无「聊天室」 | 任务图 / 经理派工 | 终稿或阶段产物 | 可预测 | CrewAI sequential/hierarchical、ChatDev ChatChain、MetaGPT SOP+消息池 |
| **P5 产品级 Bot 群聊房** | 真·共享 transcript | @ / 自然路由 / Bot 间异步 handoff；**沉默一等公民** | 群内气泡 + 可选私信 DM | 每 Bot 回复计费 → 必须限人数与轮次 | **Grok Bot 群聊**（公开文档 + skill） |
| **P6 频道绑定单 Agent** | 外部 IM 群 | mention gate；一群一脑 | 群内一人设回复 | 低 | OpenClaw groups（多数是「一群绑一个 agent」） |

**生活助手「同房协调」同时需要 P5 的产品语义 + P2 的成本可控运行时。** P1 作可选升级；P3/P4 不作为默认日用路径。

### 2.2 代表项目证据

#### AG2 / AutoGen GroupChat（P1）

- 文档：[GroupChat - AG2](https://docs.ag2.ai/latest/docs/user-guide/advanced-concepts/groupchat/groupchat/)  
- 机制：`GroupChatManager` 选下一个 → agent 发言 → **广播到所有成员共享线程**；`max_round`；`speaker_selection_method`：`auto`（LLM）/ `round_robin` / `random` / `manual` / Callable。  
- 约束图：`allowed_or_disallowed_speaker_transitions` 限制谁能接谁。  
- `description` 专供选麦，与 `system_message` 分离；可 `send_introductions`。  
- Microsoft AutoGen 的 `SelectorGroupChat` 同类：模型选麦 + 可选 `selector_func` / `candidate_func` 覆盖。  
- **启示**：共享 transcript + 选麦是业界标准「群聊内核」；但 **`auto` 每轮多一次 LLM，对 `:free` 不友好**。MVP 应用 **Callable / 规则 / Host** 代替 auto。

#### CrewAI（P4）

- 文档：[Processes](https://docs.crewai.com/edge/en/concepts/processes)、[Sequential](https://docs.crewai.com/edge/en/learn/sequential-process)、[Custom Manager](https://docs.crewai.com/edge/en/learn/custom-manager-agent)  
- `Process.sequential`：任务按序；`hierarchical`：经理派工+校验。  
- **不是聊天室 UX**，是「项目组跑任务」。适合「例程：每周膳食计划流水线」，不适合「几个身份在群里聊」。

#### ChatDev（P4 + 成对对话）

- 论文/仓库：ChatChain 分阶段；instructor/assistant 多轮；communicative dehallucination（缺上下文先反问）。  
- **强角色扮演 + 阶段门控**，面向软件交付；对生活助手过重，但「澄清后再答、限制反转深度」可借鉴到群内专家互问。

#### MetaGPT（P4 结构化消息池）

- 共享 message pool + **订阅（watch）**，角色发结构化文档而非闲聊；每角色私有 memory。  
- 论文强调：对话式一对一易失真（telephone），结构化发布更稳。  
- **启示**：群聊里专家之间尽量传 **短结构化字段**（训练动作表、热量目标），少传长散文；Host 再渲染成人话气泡。

#### OpenAI Swarm → Agents SDK（P2/P3）

- Swarm 已迁移到 Agents SDK；文档明确两模式：  
  - **Agents as tools**：经理保留对话所有权，专家作有界能力（`as_tool`）。  
  - **Handoffs**：专家接管本轮对用户回复。  
- 官方建议：能单 agent 就别拆；专家为隔离指令/工具/策略而存在。  
- **与 LightAgent 现状对齐度最高**：现有 `delegate_to_bot` ≈ agents-as-tools；`LightSwarm.transfer` ≈ handoff（产品层刻意未默认开链）。

#### LangGraph（P2/P3 图编排）

- Supervisor vs Swarm：中枢委派 vs 对等 handoff 并记住 last active。  
- 社区强调设 recursion limit、数 handoff，防环。  
- **启示**：群聊运行时应是 **有界状态机**，不是「无限聊天」。

#### CAMEL-AI（角色扮演社会）

- RolePlaying 双角色回合；Workforce 可挂 RolePlayingWorker。  
- 偏研究/仿真，日用生活助手可只借「回合上限」概念。

#### OpenHands（委派子代理）

- 父 agent 经 TaskToolSet 启子 agent，同步拿结果；可并行。  
- 是 **编码委派**，不是多身份社交群聊。

#### LightAgent 自带 LightSwarm

- `example/04.multi_agent.py`：多角色 register + `light_swarm.run` 解析 transfer。  
- `docs/multi_agent_failure_map.md`：角色串味、共享记忆污染、互踢死循环、日志难读（ProblemMap No.7/13）。  
- `docs/memory_trace_swarm_boundaries.md`：user / reflection / swarm 作用域分离；委托输出默认不晋升用户记忆。  
- **本地二开已选**：LightSwarm **只作 roster**，`run_delegation` 单层 mock/live，禁止子再 delegate、禁止 ToT。

#### OpenClaw（个人助手多 agent，偏隔离 + 协调员）

- [Multi-agent routing](https://docs.openclaw.ai/concepts/multi-agent/)：每 agent 独立 workspace / SOUL / session SQLite；bindings 路由频道。  
- **Team preset**：coordinator + researcher/writer/reviewer；coordinator 对人；专员 `allowAgents: []` 不可再派发——与我们单层 delegate 同构。  
- [Groups](https://docs.openclaw.ai/channels/groups.md)：多数是 **外部 IM 群绑定一个 agent** + mention gating + 可选沉默；不是「多 Bot 同房 UI」。  
- **启示**：生活助手「防串味」学 OpenClaw 的隔离；「同房多身份」学 Grok，不学 OpenClaw groups 的单脑绑定。

#### Letta Managed Groups（P1 产品化）

- `ManagerType`：`round_robin` | `supervisor` | `dynamic` | `sleeptime` | …（源码 `letta/schemas/group.py`）  
- `max_turns`、`termination_token`（如 `DONE!`）、共享 block（legacy）→ 现推 shared memory repo。  
- **启示**：群对象 + manager 类型枚举 + 硬回合上限，值得直接抄进数据模型。

---

## 3. 「Grok / 自身类」群聊要点（仅公开可读机制）

> 以下来自 **xAI 公开文档**、**Cursor Help**、以及本机可读 skill `group-chat-turns`。  
> **不臆造**未公开的调度算法、选麦模型名或内部队列实现。

### 3.1 产品行为（公开文档）

来源：[Message and collaborate](https://docs.x.ai/grok-bot/chat-and-collaboration)、[Group chats and Bot-to-Bot](https://cursor.com/help/grok-bot/group-chats)

| 点 | 内容 |
| --- | --- |
| 建房 | New → 选 **2–6** 个 Bot → 生成群名可改；成员可后改 |
| 共享 outcome | 开场说明共同目标与「谁拥有下一步」 |
| 定向 | 普通写 → 参与 Bot **自行判断**谁回；`@Bot` 指定；Reply 钉某 Bot；多 @；`@everyone` 少用 |
| 群内能力 | Bot 可在群内发文件/提问/表单；**审批、密钥、邮箱/Slack 草稿不在群内出现** |
| Bot↔Bot | 异步 handoff；接收方醒来处理；**群内 handoff 目前 text-only**（图直接发给对方 Bot） |
| 计费 | **每条 Bot 回复都计入用量**（含群内与 Bot 间）→ 少 Bot = 少回复 |
| 私信分流 | Bot 可给用户私信或给另一 Bot 私信；那些消息在 **各自 1:1**，不在群 transcript |
| 无开关禁互聊 | 靠自然语言约束 + 记忆；无「禁止 Bot 互发」总开关 |

### 3.2 回合语义（可读 skill：`group-chat-turns`）

| 点 | 内容 |
| --- | --- |
| 入站标记 | 用户消息带 `[Group chat: "..."]`（或 `[room "…"]`）= **房间回合**，非私聊 |
| 投递 | 房间回合里默认 `SendToUser` → **房间全员可见**；`to:"dm"` → 仅用户 1:1 |
| 沉默一等公民 | **无 SendToUser = 本回合保持沉默**（不是失败）；避免永远转圈 |
| 短消息 | 通常 1–3 句；**单回合最多约 3 条**群消息；禁止长独白/复述他人 |
| @ | `@Name` 拉人；被 @ 应回应；`@everyone` 全房 |
| 工具 | 房间内工具与私聊同等；工具过程是 **私有草稿**，只有 SendToUser 进房 |
| 身份边界 | 只以自己发言；不伪造其他参与者或用户；不窥探队友私聊/记忆/文件 |

### 3.3 对 LightAgent 的可迁移清单（产品层）

1. **房间是一等会话类型**（侧栏「创建群聊」），成员 = 已有身份 Bot（2–6）。  
2. **共享 transcript + 发言者标签**（用户要看见「健身教练：…」「饮食顾问：…」）。  
3. **@ 定向 + 未点名时可沉默**（防全员刷屏烧 `:free`）。  
4. **群内不出现审批/密钥类卡片**（敏感动作回主助手或 1:1）。  
5. **单回合消息条数与参与人数上限**。  
6. **Bot 间 handoff 可见但可预算**（MVP 可只允许 Host 发起的定向发言，暂禁自由互啄）。

---

## 4. 对照 LightAgent 现状缺口

### 4.1 已有（可复用）

| 构件 | 路径 / 行为 |
| --- | --- |
| `ConversationMeta` + `BotIdentity` | 每 Bot 身份；Profile 共享开关 |
| `plan_mention` / `resolve_bot` / `run_delegation` | `@` 解析、单层派发、配额、禁 pack 泄漏 |
| TUI `backend._maybe_delegate` | 主对话触发 delegate，结果进主气泡/步骤 |
| LightSwarm 注册表 | `register_bots` 只登记不 `run` |
| Memory 边界文档 | swarm/reflection 不默写进 user memory |

### 4.2 缺口（群聊相对现状）

| 缺口 | 说明 |
| --- | --- |
| **Room 实体** | 无 `GroupRoom` / 成员列表 / 群专用 session |
| **共享 transcript** | 无多 `speaker_id` 消息流；delegate 结果是 tool/折叠，不是「他人气泡」 |
| **选麦 / 回合编排** | 仅单次 @ → 单子；无「一用户句 → 多身份依次发言」 |
| **沉默策略** | 无私聊/群聊分流；无「未被选中则不发言」 |
| **群 UI** | plan 写明群聊入口可灰显；菜单无「拉进群」 |
| **成本闸** | 有日协作额度雏形；无「每用户消息 max speakers / max bubbles」群规 |
| **群记忆** | 无 room-scoped situational；专家发言是否可 flush 进 Profile 未定义 |

### 4.3 与 delegate 的关系判定

| 选项 | 评价 |
| --- | --- |
| **另起一套 Swarm 辩论内核** | 与 `collaborate.py` 设计原则冲突；易触发 failure map No.13 |
| **仅增强 delegate、不做群 UI** | 实现快，**不满足**「同房」用户诉求 |
| **首选：Room 编排层包住 delegate** | 每个「群内发言」= 一次有界 child run（同单层规则）；Host 写房间气泡；**delegate 仍是原子** |

---

## 5. 推荐方案

### 5.1 唯一首选：主持式同房群聊（Hosted Room）

**一句话：**  
侧栏建群 → 共享消息流 → 用户一句话由 **Host（主生活助手或指定主持）** 按规则选出 1–N 个身份各说一轮（可 `@` 强制）→ 每人发言复用单层 delegate 语义 → Host 可选做短综合 → **默认禁止群内自由多轮互啄**。

这是 **P5 产品壳 + P2 运行时**，不是 P1 自由 GroupChat。

#### 架构草图

```text
                    ┌─────────────────────────────┐
  用户 ───────────► │  GroupRoom (shared transcript) │
                    │  messages[{speaker, text, ts}] │
                    └──────────────┬──────────────┘
                                   │ 每条用户消息触发一回合
                                   ▼
                    ┌─────────────────────────────┐
                    │  RoomHost (编排，代码优先)     │
                    │  1. 解析 @ / 意图槽位           │
                    │  2. TurnPlan: 有序 speaker 列表 │
                    │  3. 限额: max_speakers, max_bubbles │
                    │  4. 结束: Host 短综合 or 沉默   │
                    └──────────────┬──────────────┘
                                   │ for speaker in plan:
                                   ▼
                    ┌─────────────────────────────┐
                    │  run_room_utterance ≈         │
                    │  run_delegation(单层)           │
                    │  + 写入房间气泡(speaker=身份)   │
                    │  子无 delegate_to_bot / 无 ToT  │
                    └─────────────────────────────┘

记忆：
  User Profile ──共享──► Host + 成员（share_user_profile）
  Identity/Persona ──每 Bot──► 仅该次 utterance 的 system
  Room situational ──可选──► space_id=room:<id>（忌口仍走 Profile）
```

#### TurnPlan 规则（MVP，代码编排，不烧选麦 LLM）

1. 若消息含一个或多个有效 `@Bot` → **按出现顺序**请这些 Bot 各发言 1 次（去重）。  
2. 若无 `@`：Host 用 **轻量规则或一次极短分类**（可选）映射场景模板，例如：  
   - 「健身+饮食」→ `[habit_coach, nutrition_advisor, host_summary]`  
   - 「日程冲突」→ `[schedule_secretary, host_summary]`  
3. 未被选中的成员本回合 **沉默**（对标 Grok skill）。  
4. `max_speakers` 默认 **3**；`max_bubbles_per_turn` 默认 **4**（含 Host 综合）。  
5. 成员之间 **MVP 不互 @**；若需澄清，由 Host 再开下一用户回合或 Host 代问。  
6. 失败回退：任一 child 失败 → 房间系统气泡说明 + Host 用已得片段尽力综合。

可选升级（非 MVP）：`speaker_selection_method="auto"` 仅在用户打开「深度协作」且配额允许时启用（AG2/Letta dynamic 路径）。

#### 与现有 delegate 的关系

| 层 | 职责 |
| --- | --- |
| `collaborate.run_delegation` | **保持**为原子：单层、配额、禁 pack、mock/live |
| 新增 `local/conversations/room.py`（名可议） | Room 模型、TurnPlan、把多次 utterance 投影为群消息 |
| TUI | 群会话行、多 speaker 气泡、建群 Modal；**不**改内核 LightSwarm.run 默认行为 |
| 主对话 `@` | **保留**；群聊是平行入口，不是替换 |

#### MVP 范围（建议 1 个里程碑可演示「健身+饮食」）

1. 数据：`GroupRoom{id, title, member_bot_ids[], host_bot_id, max_speakers, created_at}` 持久化。  
2. UI：侧栏「创建群聊」选 2–4 个已有 Bot；群内消息列表显示头像/角色名。  
3. 运行：用户消息 → TurnPlan → 顺序 utterance → 写入 transcript；Host 末尾 ≤5 行综合。  
4. 记忆：成员 `share_user_profile=True` 时注入同一 Profile pack；identity 块 per utterance；**不**把群闲聊自动写成 Profile（沿用 admission）。  
5. 成本：复用 `DelegateQuota`；群回合额外 `RoomQuota`（例如每日群发言气泡上限）。  
6. 测试：离线 mock；E 场景「今日健身+饮食」见 §6。

#### 非目标（MVP）

- AG2 式无界 `auto` 互啄 / 默认 ToT / LightFlow DAG  
- Bot 在群内自由异步互发且无预算  
- 群内弹出审批、密钥、外发邮件草稿（对标 Grok：回 1:1）  
- 把群 transcript 全量塞进每个 child（只传 task + 短 room digest + 必要 pack）  
- 外部 Slack/WhatsApp 多 Bot 同房（可后置，OpenClaw 路线）

### 5.2 备选 A：Selector GroupChat（LLM 选麦）

- 实现：Room + `max_round` + Host LLM 选下一个（AG2/Letta dynamic）。  
- 优点：更「像真人开会」、少写场景模板。  
- 缺点：每轮 +1 `:free` 调用；易角色串味与死循环（需 termination_token、禁止连麦、白名单转移图）。  
- **仅作为「深度模式」开关**，默认关。

### 5.3 备选 B：无群 UI 的并行 Delegate

- Host 一次 `asyncio.gather` 调健身+饮食，主对话只出合并答案。  
- 优点：改动最小、最省。  
- 缺点：**没有同房气泡**，不满足本调研的用户表述。  
- 可作 Room MVP 前的临时体验，但不应标为「群聊完成」。

### 5.4 为何不首选其它栈

| 栈 | 原因 |
| --- | --- |
| CrewAI / ChatDev / MetaGPT | 任务/SOP 引擎，缺「侧栏群聊」产品语义；MetaGPT 的结构化发布可局部借鉴 |
| 纯 LightSwarm.run handoff | 与现协作安全设计冲突；失败模式已文档化 |
| OpenClaw groups | 解决的是「IM 群绑一脑」，不是多身份同房 |
| 全面移植 Grok 内部调度 | 不可见；只迁移公开产品语义 |

---

## 6. 风险与验收种子场景

### 6.1 风险

| 风险 | 缓解 |
| --- | --- |
| `:free` 烧尽 / 429 | max_speakers、日配额、默认无选麦 LLM、失败回退 mock 文案 |
| 角色串味（No.7/13） | 每 utterance 独立 system；禁共享 child agent 对象；日志打 `speaker_id` |
| 记忆污染 | 群发言默认不 admission；画像/忌口仍走既有压后分流；room digest 不写 Profile |
| 全员刷屏 | 沉默默认；强制 @ 或 Host 点名；单回合 bubble 上限 |
| 与 1:1 delegate 行为分叉 | 共用 `run_delegation`；群只多「投影到 transcript」 |
| 用户以为在「开会」实际在空转 | TurnPlan 轨迹页可见；Host 综合必须点名引用谁说了什么 |

### 6.2 验收种子（含健身+饮食）

**S1 建群**  
创建群「健康日常」，成员：习惯教练、饮食顾问；Host=主生活助手。侧栏可见；重启仍在。

**S2 @ 定向**  
用户：`@习惯教练 今晚能练什么（忌深蹲）`  
→ 仅习惯教练气泡；饮食顾问沉默；忌口来自 Profile 且未被改写。

**S3 无 @ 场景模板**  
用户：`帮我安排今日健身和饮食`  
→ TurnPlan = 教练 → 饮食 → Host 综合；三条气泡角色名正确；饮食计划引用教练运动负荷。

**S4 成本闸**  
同一用户消息不得触发 > `max_speakers` 次 child LLM；配额用尽有明确中文错误气泡。

**S5 单层**  
群内 child 的 tools 不含 `delegate_to_bot`；无法再拉第三人。

**S6 敏感动作**  
群内要求「发邮件订餐」→ Host 提示回主对话/1:1 走审批；群内无伪发送成功。

**S7 回归**  
原主对话单次 `@` delegate 行为不变；E15–E18 类测试仍过。

---

## 7. 附录：检索日志

### 7.1 本地只读

| 路径 | 用途 |
| --- | --- |
| `local/research/multi_conversation_identity_{survey,plan,acceptance}_zh.md` | 群聊后置、Delegate 优先 |
| `local/conversations/collaborate.py` | 单层 delegate、禁 Swarm.run |
| `local/tui/backend.py` | `_maybe_delegate` |
| `docs/multi_agent_failure_map.md` / `memory_trace_swarm_boundaries.md` | 失败模式与记忆边界 |
| `example/04.multi_agent.py` | LightSwarm 示例 |
| `/home/box/agent-data/managed-skills/skills/group-chat-turns/SKILL.md` | Grok 房间回合语义 |
| `channels/SKILL.md` | 外部频道投递（对照，非同房多 Bot） |

### 7.2 Web / 文档

| 主题 | URL |
| --- | --- |
| AG2 GroupChat | https://docs.ag2.ai/latest/docs/user-guide/advanced-concepts/groupchat/groupchat/ |
| MS SelectorGroupChat | https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/selector-group-chat.html |
| CrewAI Processes | https://docs.crewai.com/edge/en/concepts/processes |
| OpenAI Agents multi-agent | https://openai.github.io/openai-agents-python/multi_agent/ |
| OpenAI orchestration | https://developers.openai.com/api/docs/guides/agents/orchestration |
| ChatDev | https://github.com/OpenBMB/ChatDev 、 arXiv:2307.07924 |
| MetaGPT message pool | arXiv:2308.00352 ；role.py observe/watch |
| LangGraph supervisor/swarm | langchain 文档 / langgraph-supervisor-py |
| CAMEL societies/workforce | https://docs.camel-ai.org/key_modules/societies |
| OpenClaw multi-agent / groups | https://docs.openclaw.ai/concepts/multi-agent/ 、 `/channels/groups.md` |
| Letta group schema | https://github.com/letta-ai/letta/.../letta/schemas/group.py |
| Letta shared memory | https://docs.letta.com/concepts/shared-memory/ |
| OpenHands delegation | OpenHands TaskToolSet / agent_delegation 示例 |
| Grok Bot 协作 | https://docs.x.ai/grok-bot/chat-and-collaboration |
| Cursor Help 群聊 | https://cursor.com/help/grok-bot/group-chats |

### 7.3 X（≤25/min）

| 查询意图 | 代表帖 | 摘取 |
| --- | --- | --- |
| 多 agent 架构模式 | https://x.com/snwiki238337/status/2107436085458632723 | 主从 Supervisor / Worker 等主流模式梳理 |
| 协调税 / 电话游戏 | https://x.com/NavuluriBalaji/status/2109465204274975137 | Coordination Tax；handoff 丢 nuance |
| 路由成本 | https://x.com/0xRafy/status/2103204091065184343 | 每任务 5–15 次 routing 决策均烧 LLM |
| 共享状态腐蚀 | https://x.com/saudaziz/status/2109811264482660394 | 并发共享状态破坏工作 → 隔离 sandbox + 共享仓库 |

Reddit 未采（易 403）；以上社区信号与「默认代码编排、少选麦 LLM、隔离记忆」一致。

---

## 8. 给实现的下一跳（本文不写代码）

若拍板首选方案，下一份应是 `multi_agent_group_chat_plan_zh.md`：数据模型、TUI 交互、TurnPlan 模板表（含健身+饮食）、E1–En 验收、与 `collaborate.py` 的精确函数复用列表。

**推荐锁死句：**  
做 **Hosted Room（共享 transcript + @/模板选人 + 单层 utterance）**；把 AG2 式 LLM 选麦留作可选深度模式；不要用流水线框架冒充群聊。
