# 生活助手向长链路对话任务：机制深挖（OpenHuman / Grok Bot / OpenClaw / Mem0 / ChatGPT）

> 日期：2026-10-14（America/Martinique / AST）  
> 定位：**全方位个人生活助手**的长链路 ≠ coding agent 的长任务（写代码/改仓库）。重点是：跨多轮与跨天目标、忌口/偏好保真、主动续聊不骚扰、多角色协作不互啄、可中断/可改主意/可忘记。  
> 范围：**只读调研**；未改业务代码。  
> 主线转向：本文件为生活助手主文。Coding 向底层文见 `long_horizon_harness_deepdive_zh.md`（仅作对照，不再扩写）。最小集见 `long_horizon_harness_minset_zh.md`（已按本文重写）。  
> 标注：**观察** = 源码/官方 docs 直接读到；**产品观察** = 公开产品能力与文档可归纳、**不**声称未公开内部实现；**推断** = 由观察推导。

---

## 0. 证据级别与仓库地图

| 对象 | 证据级别 | 主要路径 / URL |
| --- | --- | --- |
| OpenHuman + TinyMemory | **源码 L1**（本机 clone） | `/workspace/openhuman` · TinyMemory `vendor/tinymemory` · commit 笔记见 `openhuman_memory_source_notes_zh.md`（本轮已再核 `lifecycle/hooks.rs`、`jobs.rs`、`prefetch.rs`、goals/notifications docs） |
| OpenHuman 产品/架构 docs | **官方 GitBook L1** | `tinyhumans.gitbook.io/openhuman/...` · `gitbooks/features/{memory,personalization,goals-and-todos,notifications-and-activity,workflows,orchestration}.md` |
| Grok Bot / Cursor 个人助手 | **产品公开 docs（产品观察）** | `cursor.com/docs/grok-bot` · `cursor.com/help/grok-bot/routines` · `docs.x.ai/grok-bot/*` |
| OpenClaw | **官方 docs L1** | `docs.openclaw.ai/concepts/{memory,compaction,active-memory}` · GitHub `openclaw/openclaw` concepts |
| Mem0 | **官方 docs + 架构 skill + arXiv** | `docs.mem0.ai/core-concepts/how-it-works` · mem0 architecture skill · arXiv:2504.19413 |
| ChatGPT Memory / Tasks | **OpenAI Help / Learn（产品观察）** | Memory FAQ · Scheduled tasks help · Tasks and memory（Dots） |
| LightAgent 二开 | **本仓库 L1** | `local/memory/*` · `local/compact/*` · `local/rooms/*` · `local/tui/*` |
| Codex / Claude Code | **一句对照** | 窗外进度 + 可中断 + compact hooks；细节不扩 |

纠偏（相对旧笔记/产品口号）：OpenHuman **无** 名为 Dreaming / 两车道 preference / Space 的实现模块；巩固 = `BackgroundJob` + belief/consolidate；Personalization = Learnings + pack + Persona 文件（`personalization.md` + 源码边界）。

---

## 1. 生活助手「长链路」问题分解（与 coding 对照一句）

| 维度 | Coding agent（对照一句） | 生活助手长链路对话 |
| --- | --- | --- |
| 目标载体 | ThreadGoal / plan / repo 文件 | **Memory 事实** + **会话目标/todo** + **跨天日程/提醒** 三套，职责不同 |
| 失败代价 | 半执行写盘/半 PR | 丢忌口、重复追问、骚扰推送、多 Bot 互啄烧额度 |
| 跨天 | checkpoint / rollout 续跑 | routine / scheduled task / daily note / belief 后台巩固 |
| 压缩 | 保 tool 对、保 plan id | 保 **偏好/忌口/开放问题**；压前 **flush 到窗外** |
| 协作 | 子代理回摘要 | 群聊选麦 + Host 短总结；**禁止默认 LLM 互啄** |

---

## 2. OpenHuman（+ TinyMemory）：生活助手记忆与回合生命周期

### 2.1 三层边界（观察）

| 层 | 位置 | 职责 |
| --- | --- | --- |
| Host | `crates/openhuman-core/src/memory/` | 绑引擎、身份/scope、turn 生命周期、后台 job、RPC/`memory` tool、scrub、consent |
| TinyMemory Tools | `vendor/tinymemory/crates/tinymemory-tools` | `AgentMemory`、`ContextPack`、Brain、`BackgroundJob` |
| Engine | `tinymemory-api` + integrations | store/fetch/recall/forget/consolidate/beliefs |

**非 memory、但强相关**：聊天线程在 `threads/`；Persona 在 `agent/prompts/{SOUL,IDENTITY,ROLE,STYLE,USER}.md`。产品 Personalization = **Learnings + pack + Persona**（`gitbooks/features/personalization.md`）。

### 2.2 硬不变量（主张 → 证据 → 对 LightAgent）

1. **Pack 永不写回 transcript**  
   - 证据：GitBook Architecture/Memory：「pack … never into the transcript」；middleware `memory_pack.rs` ephemeral；本机笔记硬规则 #1。  
   - LightAgent：`local/memory/inject.py` 已声明「never concatenated onto the user question」；`strip_ephemeral` / Room `digest.strip_ephemeral` 必须保持。任何把 pack 拼进 user 再 store 的路径禁止。

2. **Live turn 不 await 远程记忆 I/O**  
   - 证据：`lifecycle/prefetch.rs`：pre_turn 取 **已完成** cache；冷缓存 → 无 pack；后台 refresh；`hooks::pre_turn` 有 `pre_turn_timeout_ms`，超时 turn 仍跑。  
   - 启示：长链路日用路径优先 **fail-open**；不要为了「更完整记忆」堵死第一句回复。

3. **拒绝 ≠ 空记忆**  
   - 证据：`hooks.rs` PreTurn：credits/unauthorized → pack 是 refusal notice，禁止模型说「我什么都不记得」。  
   - 启示：额度耗尽/记忆不可用时注入 **notice**，与「无偏好」区分。

4. **Persona ≠ User memory**  
   - 证据：`personalization.md`；ROLE 主要给 orchestrator。  
   - 启示：身份 YAML/MD 与 Learnings/Profile 分栏；群成员身份 ≠ 用户忌口。

5. **写入一律 scrub；learn/forget 本地出盒异步**  
   - 证据：`ScrubbingEngine`；tool_writes 出盒语义「queued; not yet saved」。  
   - 启示：忌口写入可同步本地、异步巩固；UI 勿承诺「已永久写入远端」。

6. **Belief / consolidate 离线 BackgroundJob**  
   - 证据：`lifecycle/jobs.rs`：`post_turn` 返回 job → `jobs.json` → `memory_background` cron，延迟 `build_delay_secs`；scheduler_gate Paused 可停。  
   - 启示：跨天「变聪明」靠后台，不靠每轮 LLM consolidate（`:free` 友好）。Dreaming 是产品加厚名，**勿谎称 OH 有同名模块**。

7. **Pack 排除仍在 prompt 的窗口**  
   - 证据：`PreTurnInput.in_prompt_from`；TinyMemory `exclude_thread` / `HolisticRecall`。  
   - 启示：压缩后 `resumed_after_compaction` 用「线程仍持有什么」带头；避免双重注入污染 prefix cache。

8. **Turn 索引稳定可重放**  
   - 证据：user=`2n`，reply=`2n+1`；同输入重试 = replay。  
   - LightAgent：`inject.turn_index` 已对齐。

### 2.3 Goals / Todos：会话工作态 ≠ 耐久记忆（观察）

`gitbooks/features/goals-and-todos.md`：

- **Session todo**：Claude/Codex 同形；一次 `todo` 写整表；`pending|in_progress|completed`；**进程内存**。  
- **Thread goal**：`goal_set` / `goal_get` / `goal_complete`；banner 显示 active / paused / **budget reached** / complete。  
- **明确不是** kanban；**明确**：耐久偏好在 Memory learnings，goals/todos **只活会话**。  
- UI 读线程里最新 tool 结果 JSON（跨 turn 仍显示）——「进度在窗外但仍可被 pane 读到」。

源码锚点：`agent/goals/tools.rs`、`agent/goals/store.rs`、`harness_tool_registration.rs` 注册三工具。

**对 LightAgent**：LifeGoalStore ≈ thread goal（可持久化到 workspace，比 OH 会话内存更强一点，因生活助手跨天）；SessionTodo 可薄封装库 `GoalManager` 步骤；**忌口放 Learnings/ConstraintCard，不放 todo 正文当唯一真相**。

### 2.4 主动与防骚扰：通知阈值 + 路由门（观察）

`notifications-and-activity.md` + `desktop/notifications/rpc.rs`：

- 每 provider：`enabled`、`importance_threshold`、`route_to_orchestrator`。  
- 只有 score ≥ threshold **且** route_to_orchestrator 才转给 agent。  
- Notice tray：同类问题 **bump count** 不堆叠。  
- 后台工作分流：Schedules / Workflow Runs / Memory Background / 线程 inbox——避免「一切都弹聊天」。

**对 LightAgent**：主动续聊最小核 = **显式用户创建的提醒/例程** + **重要性门** + **日/周上限**（对齐 `:free` 日限 45）；禁止模型自行决定「每天问候」。

### 2.5 Workflows / Cron：跨天自动化在聊天外（观察）

- Workflows：agent `propose_workflow` **不能**直接 enable；创建默认 off；跑前确认（`workflows.md`）。  
- Cron 与 Flow 调度在 Workflows→Schedules；memory background 是 system job。  
- Runs durable + approval card；「later today」可恢复。

**对 LightAgent 最小集**：不做 tinyflows；只借「**聊天外持久化调度 + 默认关闭 + 审批**」。SoftRoutine 存 JSON + TUI 列表即可。

### 2.6 Compaction 与记忆交接（观察）

- `prefetch::compaction` / `hooks` compaction：用 completed cache，不堵 summarizer。  
- `resumed_after_compaction`：下一 turn pack 带头「线程仍持有」。  
- TokenJuice = 内容压缩路由（架构图），与 memory pack 正交。

**对 LightAgent**：已有 `local/compact/flush.py`（rules-first，fail-open，忌口 pin `compact=never`）——应对齐 OpenClaw memoryFlush **语义**，接到每次 compact 前；群 `compact_room_messages` 仍未进 `_save_rooms`（`app.py:1426`）。

---

## 3. Grok Bot（产品形态）：命名角色、例程、群聊、审批边界

> **产品观察**：以下来自 Cursor / xAI 公开文档。不编造未公开 harness 源码。

### 3.1 上下文如何「复利」（产品观察）

- 每个 Bot：**名字 + 工作 + 跨会话累积**的 memory / preferences / files / browser sessions。  
- **对话与 learned context 按 Bot 隔离**；**共享一台 cloud computer**（文件/登录跨 Bot 可见）——交接靠共享盘与群聊，不靠偷看对方私聊。  
- 拷贝 Bot：**不拷** conversation / learned memory / attachments。  
- Memory **不是**权威源：重大决策要回查当前系统；安全靠 approvals / Auto-review，不靠记忆。

**对 LightAgent**：多身份 Bot ≈ `ConversationMeta` + persona；共享 workspace 文件；群聊可见交接；忌口进用户 Profile/Learnings（全局），角色技能进身份文件。

### 3.2 Routines：何时跑，而非如何跑（产品观察）

- **Skill** = 如何做；**Routine** = 何时跑（cron 或事件：Slack/GitHub/邮件/webhook…）。  
- 用自然语言在聊天里创建；Details 里 Pause / Resume / Test / Edit / Delete。  
- 上限：每 Bot **≤50** routines；保留最近 **20** 次 run；调度间隔 **≥5 分钟**。  
- **久未使用会询问是否继续**，无应答则 pause——防额度与骚扰。  
- 测试 = 真执行；窄化 Slack 触发，避免「全频道任意消息」烧光周额度。

**对 LightAgent**：SoftRoutine 最小集字段：`instruction`、`when`（cron 字面或「每日窗口」）、`paused`、`last_run`、`owner_bot_id`；交付先做 **打开 App 时的 due 列表**（无推送也可）；默认创建后 **paused 或等下次窗口**（对齐「创建不立刻跑」）。

### 3.3 群聊 2–6：可见交接，一人一阶段（产品观察）

- New chat 选 2–6 Bots；自然语言让其自决谁答；`@` 点名；`@everyone` 少用。  
- Kickoff：**每阶段一个 owner**。  
- 并行：各 Bot 可并行推理；computer-use 每 Bot 一屏一次一任务。

**对 LightAgent Hosted Room**：已有选麦 plan + Host 规则总结；缺口是 Host 易回声、缺「阶段 owner / 忌口行 / 下一步」结构化，且无 LifeGoal 绑定。**禁止**默认再开一层 LLM 互评。

### 3.4 可中断与审批（产品观察）

- 外发/购买/删除/发布走 approval；draft→approve 模式。  
- 关电脑不杀云端 turn/routine——生活助手「跨天」靠云调度；本机 TUI 则靠 SoftRoutine + 下次打开。

---

## 4. OpenClaw：文件即真相、压前 flush、Active Memory、Dreaming

### 4.1 分层文件记忆（观察）

| 文件 | 寿命 | 注入策略 |
| --- | --- | --- |
| `USER.md` | 长期偏好指令 | 小预算，会话开头；**supersede in place** 改偏好 |
| `MEMORY.md` | 精选耐久非 profile | 会话开头；**群聊上下文永不加载** |
| `memory/YYYY-MM-DD.md` | 日笔记 | 索引检索；bare `/new` 可带今昨 |
| `DREAMS.md` | 巩固审计 | 给人看，不替代 MEMORY |

行动敏感记忆：写清 **何时可行动 / 过期 / 谁授权**——记忆保存审批语境，**不**替代硬门控。

### 4.2 Compaction + memoryFlush（观察，高密度）

- Compact 改「模型下一轮看见什么」，**全文 transcript 仍在盘**。  
- 保 tool_call↔toolResult 成对；safeguard 质量审计；失败可 degraded + 用户可见警告。  
- **压前 silent memory flush**：提醒模型写入耐久笔记；常用 `NO_REPLY`；flush 失败 **不阻断** compact。  
- 取消：**不是 rollback**——已完成的 compact 保留。

**对 LightAgent**：`local/compact/flush.py` 已是 rules-first 版 memoryFlush；接上 1:1 compact 与群 save；群保持 **零 LLM 尾窗** + ConstraintCard 保真。

### 4.3 Active Memory（观察）

- 跨 **同一 agent 的其它私聊** 有界召回；排除当前会话；默认随个人 DM scope。  
- 群/频道需显式 opt-in；无命中时给 **hidden outcome note**，不假装召回成功。

**对 LightAgent**：跨会话召回 = Profile/Learnings search；群只用房间 digest + 用户全局忌口，**不**把其它 1:1 全文灌进群。

### 4.4 Dreaming / Standing intents（扩展槽）

- Dreaming：后台晋升短记忆→`MEMORY.md`，有阈值；默认 cron。  
- Standing intents：事件条件意图；**精确时间提醒仍用 scheduled tasks**。

**最小集不做 Dreaming**；SoftRoutine ≈ scheduled tasks 的本地薄实现。

---

## 5. Mem0：消息 ≠ 记忆；user vs run 双层

### 5.1 核心环（观察）

`search`（模型前）→ 应用挑选注入 → 回复 → `add`（提取耐久事实）。默认存 **提取后的 memories**，不是 verbatim transcript（`infer=False` 才原样）。

### 5.2 分层（观察）

- Conversation memory：单轮，应用管。  
- User memory：`user_id`，周～永久。  
- Session/task：`run_id`，任务结束可删。

提取默认 **additive**（搬家可并存新旧）；纠正用显式 update/delete。

检索信号：semantic / keyword / entity / temporal。

**对 LightAgent**：Learnings ≈ user 层；LifeGoal/Checkpoint ≈ run 层；compact 摘要 ≠ 自动 learn（需 flush 规则提升）。勿每轮全量 transcript `add`（烧 `:free`）。

---

## 6. ChatGPT Memory / Tasks（产品观察）：记忆与日程分家

### 6.1 Memory

- Saved memories（用户明示）+ 自动有用上下文；Settings 可关/删；Temporary Chat 不用 saved memory。  
- Memory summary ≠ 全部记忆；可问「你记得什么」。

### 6.2 Scheduled tasks

- 一次性 / 周期 / monitoring（有变化才通知）/ 事件触发（付费档）。  
- **计划级 active 上限**（Free/Go=3 …）；Free：**至多每日一次** + 柔性时段（早/午/晚）。  
- 闲置可自动 pause；删关联聊天 → pause 任务。  
- 外发动作可要求 approval，任务暂停至审批。  
- Dot 的 notes **独立于** ChatGPT saved memory。

**对 LightAgent**：跨天目标用 SoftRoutine + LifeGoal，不把一切塞进 memory；频率默认对齐 Free 精神（少、可 pause、可删）。

---

## 7. 横切问题：主张 → 证据 → 最小核 vs 扩展

### 7.1 用户目标如何跨多轮/跨天保持？

| 载体 | 谁用 | 最小核？ |
| --- | --- | --- |
| Transcript | 近期对话 verbatim | 是（但会涨） |
| Ephemeral pack / Learnings | 忌口、偏好、事实 | **是**（OH/Mem0） |
| Thread LifeGoal + steps | 多步完成契约 | **是**（OH goals） |
| Checkpoint | 中断续跑 | **是**（半执行语义借 coding） |
| SoftRoutine / Tasks | 跨天触发 | **是（薄）**（Grok/ChatGPT） |
| Dreaming / belief cron | 巩固 | 扩展 |
| Workflow DAG | 复杂自动化 | 扩展 |

### 7.2 主动续聊如何不骚扰？

- 显式创建；默认窄触发；importance threshold；久用 pause；同类合并；计划级上限。  
- **最小核**：仅显式 SoftRoutine + 打开时 due 列表 + 日上限；**不做**模型自发「关心一下」。

### 7.3 压缩与忌口保真？

- 压前 flush（OpenClaw / LA flush.py）。  
- 偏好用 USER/Learnings **整条 supersede**，禁止截断改义（对照 Codex goal omit-whole）。  
- 群：尾窗 + ConstraintCard；MEMORY 不进群（OpenClaw）。

### 7.4 多角色（健身+饮食）如何协调不互啄？

- Grok：阶段 owner、`@`、共享盘、Host 短更新。  
- OH：orchestrator / workflows，approval。  
- LA Room：规则选麦 + Host 三行；**默认关 Host LLM**；每轮预算与日限双闸。

### 7.5 可中断、可改主意、可忘记？

- Cancel → checkpoint + `pending_side_effects`（建议可能已展示）。  
- 改主意：goal_complete/cancel + learning forget/supersede。  
- 忘记：显式 forget；Temporary/无 pack 模式；删 SoftRoutine。

---

## 8. LightAgent 现状锚点（本仓库）

| 能力 | 状态 | 路径 |
| --- | --- | --- |
| Ephemeral pack 注入 | 已有 | `local/memory/inject.py` |
| Persona / scrub / jobs | 已有 | `local/memory/{persona,scrub,jobs,pack}.py` |
| Compact flush（规则） | 已有模块 | `local/compact/flush.py`；需确认挂上所有 compact 入口 |
| 群 `compact_room_messages` | **函数在、save 未接** | `digest.py:40`；`app.py:1426 _save_rooms` |
| Host 总结 | 规则五行星，易回声 | `host_summary.py` |
| Cancel / Budget | 库有，TUI 日用未接满 | 见 coding deepdive 接线表 |
| LifeGoal / SoftRoutine | **缺** | 最小集新增 |

---

## 9. 证据缺口

1. Grok Bot / ChatGPT **内部** compact、memory 存储格式、routine 调度器实现未公开——仅产品行为。  
2. OpenHuman TinyAgents ContextLadder / TokenJuice 与 compaction 的逐步时序未全文精读（有 hooks 接口）。  
3. OpenClaw 本轮以官方 docs 为主，未 shallow clone 全仓核对每个符号。  
4. 未做跨天 live 长跑（`:free`）。  
5. 旧笔记 `openhuman_memory_source_notes_zh.md` 与本轮 hooks/jobs 再核一致；Dreaming 纠偏仍成立。

---

## 10. 置信度

- OpenHuman 记忆/goal/通知机制：**~0.9**（源码+docs）。  
- Grok / ChatGPT 产品形态归纳：**~0.8**（docs 充分，无内部源码）。  
- OpenClaw / Mem0：**~0.85**（docs 密；OpenClaw 未全仓 clone）。  
- 映射到 LightAgent 最小集可开工性：**~0.86**。


---

## 11. OpenHuman 回合时序（机制级，观察）

```text
before_turn (memory_ingest)
  └─ prefetch.pre_turn：只取 completed cached pack（≤60s TTL，≤64 entries/context，≤64KiB/pack）
       未命中 → 本轮无 pack；排队后台 refresh（8 workers，队列≤16，op deadline 120s）
  └─ 显式 timeout 路径 hooks.pre_turn（pre_turn_timeout_ms）：超时丢 pack，日志仍后台完成

model request（每请求）
  └─ memory_pack middleware：ephemeral <memory-context>… 注入 instruction 车道
       绝不写入 threads store

finalize_after_durable_commit
  └─ post_turn：记 reply；enqueue BackgroundJob（belief/ingest）
  └─ jobs.json + memory_background cron；build_delay_secs 后跑；gate=Paused 则跳过

compaction
  └─ recall_for_compaction / prefetch.compaction：用 completed cache
  └─ 下一轮 PreTurnInput.resumed_after_compaction=true → pack 带头「线程仍持有」
```

**预算与饱和**：tool 显式 recall 有 15s/call、30s 聚合、8 attempts；饱和时 **跳过** best-effort 自动工作而非阻塞——生活助手长链路的关键气质是 **降级继续聊**。

**Host stamp**：learn 的 workspace/thread/agent/tool_call/namespace 由 host 盖章；模型参数改不了 reach（`confine`）。防「子 Bot 写穿用户全局忌口命名空间」——群聊委派时尤重要。

---

## 12. OpenHuman Goals 与预算到达（观察）

- Banner 状态含 **budget reached**（`goals-and-todos.md`）——目标可因预算停，而不必 completed。  
- Pane **无独立 RPC**：靠线程内最新 `goal_*` / `todo` tool JSON——进度「窗外」但仍可从 transcript 工具结果重建 UI。  
- LightAgent 若把 LifeGoal 落到独立 JSON，应 **同时** 能在 TUI 渲染 banner，且 compact 时用 **goal_id** 保真，禁止只靠摘要句子。

---

## 13. Grok Bot 与额度：例程是长链路的第一燃烧点（产品观察）

公开帮助明确：

- 过密 schedule / 宽 Slack 触发可「一天烧光一周额度」。  
- Pause 不花钱；Test 花钱。  
- 久离询问 + 无应答 pause。

映射 `:free` 日限 45：

| 规则 | 最小集取值建议 |
| --- | --- |
| SoftRoutine 创建 | 仅用户显式 |
| 默认频率 | ≤1/日（对齐 ChatGPT Free 精神） |
| 全局 due 执行 | 计入日限；超额只列 due 不自动跑模型 |
| 久未打开 App | 下次打开时提示 pause/resume，不补跑堆积 |

---

## 14. OpenClaw Compact 输入拼装优先级（观察，可借鉴群/1:1）

官方 compaction 文档（内置 summarizer 输入封顶 ~160k chars）填充顺序：

1. 最新消息 verbatim（约一半预算）  
2. 更早的 **用户** 消息（要求/决定/纠正，约 1/4，单条 trim）  
3. 最旧（约 1/10）  
4. 均匀抽样剩余  

并明确：**不要臆造被省略内容**；保留 previous summary 事实。CJK 按近似 token 权重。

**对 LightAgent 群零 LLM 尾窗**：可在 keep=N 之外加「始终保留最近用户句 + ConstraintCard 命中句」的规则提升（仍零 LLM）——列入最小集 M3。

---

## 15. Mem0 与「改主意」（观察）

- ADD-only 提取 → 搬家/改忌口可能并存矛盾事实。  
- 应用层必须：用户说「我现在不忌海鲜了」→ **显式 update/delete/supersede**（OpenClaw USER.md 也强调 supersede in place）。  
- ConstraintCard 应带 `updated_at` / `superseded_by`，注入时只取 active。

---

## 16. ChatGPT：Memory ⊥ Tasks ⊥ Dot notes（产品观察）

三套并行：

1. ChatGPT saved/auto memory —— 跨聊天偏好  
2. Scheduled tasks —— 跨天触发与 monitoring  
3. Dot 私有 notes —— 任务工作态，改 memory 设置未必改 notes  

**启示**：LightAgent 不要用一个 `memory` JSON 糊所有长链路；最小集分栏：

`Profile/Learnings` | `LifeGoal+Checkpoint` | `SoftRoutine`

---

## 17. 多身份协作：反互啄清单（综合）

| 做法 | 来源 | 最小集？ |
| --- | --- | --- |
| 每阶段单一 owner | Grok | 是（Room plan 已部分） |
| Host 短结构化三行，禁整段粘贴 | Grok/OH UI 气质 | 是 M6 |
| 子发言前 strip ephemeral | OH/LA digest | 是 |
| 委派配额 DelegateQuota | LA 已有 | 保持 |
| 默认 Host/评委第二模型 | — | **否** |
| 全员每轮必答 | — | **否** |
| Workflow/DAG 自动编排 | OH | 扩展 |

---

## 18. 从生活助手反推：coding 共性只留三句

1. **进度必须可放在上下文窗外**（goal/todo/checkpoint）。  
2. **可中断 + 硬预算是底线**（库原语未接线 = 没有）。  
3. **Compact 是带压前钩子的状态机**，不是删尾巴。  

其余 Seatbelt、ExecPlan、Guardian 第二模型、完整 EventLog —— 生活助手最小集不搬。
