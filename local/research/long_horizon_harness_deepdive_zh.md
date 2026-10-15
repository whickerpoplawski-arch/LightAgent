# 长链路 Harness 底层深挖笔记（Codex / Claude Code / OpenHands → LightAgent）

> **主线已转向生活助手。** 长链路对话任务的主深挖与最小集修订见：
> `life_assistant_long_horizon_deepdive_zh.md` · `long_horizon_harness_minset_zh.md`。
> 本文保留作 coding agent 对照，不再作为实现主依据。


> 日期：2026-10-13（America/Martinique / AST）  
> 范围：**只读调研**；未改业务代码。  
> 方法：Codex = shallow clone `github.com/openai/codex` 读 `codex-rs/core|protocol|history|prompts`；Claude Code = 官方 docs（置信度高）+ Anthropic engineering；OpenHands = 官方 docs + `software-agent-sdk` 源码（raw）；LightAgent = `rg`/`Read` 核对行号。  
> 标注约定：**观察** = 直接读到的符号/文件；**推断** = 由观察推导的行为模型；**二手** = 社区深读/非官方，单独标置信度。

---

## 0. 读法与证据级别

| 对象 | 证据级别 | 主要路径 |
| --- | --- | --- |
| OpenAI Codex CLI | **源码 L1** | `/tmp/codex/codex-rs/core/src/**`、`protocol/src/**`、`history/src/**`、`prompts/templates/**` |
| Claude Code | **官方 docs L1**；内部二进制未审计 | `code.claude.com/docs/*`、`anthropic.com/engineering/effective-context-engineering-for-ai-agents` |
| OpenHands SDK | **源码 L1 + docs** | `openhands-sdk/.../conversation/state.py`、docs persistence/pause |
| Aider | **官方 docs** | `aider.chat/docs/repomap.html`（上下文预算对照，非完整 agent loop） |
| LightAgent | **本仓库 L1** | `LightAgent/*`、`local/tui/*`、`local/rooms/*` |

X 检索：1 次（社区 harness/context engineering 口碑），**不作硬证据**。

---

## 1. OpenAI Codex CLI（Rust，`codex-rs/core`）

### 1.1 Agent loop 状态机（观察）

**入口任务**：`tasks/regular.rs` → `RegularTask::run`

伪时序（观察自源码）：

```
RegularTask::run(sess, TurnContext, input, CancellationToken)
  emit TurnStarted
  emit_turn_start_lifecycle(...).or_cancel(token)   // 可被取消
  loop:
    last = run_turn(sess, ctx, next_input, ..., token.child_token())
    if turn.terminal_error.is_some(): return
    if !input_queue.has_pending_input: return last
    next_input = []   // 消费 pending（steer / mailbox）后继续
```

**单次 `run_turn`**（`session/turn.rs` ~164+，约 3200 行）：

1. **Pre-sampling compact**：`run_pre_sampling_compact`（compact **在**新用户消息入历史之前；失败时仍 `run_hooks_and_record_inputs` 保住 prompt）。  
2. **Capture StepContext**（模型设置、MCP、权限、world state）。  
3. **Record context updates** + skills/plugins 注入。  
4. **Hooks + record inputs**（`PersistContext::TurnStart`）。  
5. **Sampling 内环**：模型流式响应 → tool 执行 →（可选）mailbox/pending drain。  
6. **Post-sampling**：算 `context_window_token_status`；若 `needs_follow_up && (new_context_window || token_limit_reached)` → **MidTurn** `run_auto_compact` 后 `continue`。  
7. **Stop hooks**：`should_block` 可注入 continuation 再进环；`should_stop` 退出。  
8. **PostTurn compact**（可选）：`model_post_turn_compact_threshold_percent > 0` 且非 TokenBudget feature 时，在 turn 结束、无 pending、未 cancel 时跑 `CompactionPhase::PostTurn`。

**停止条件（观察）**：

- 无 pending input 且模型不再要求 follow-up。  
- `CancellationToken` 取消 → `CodexErr::TurnAborted` / `Interrupted`。  
- `SessionBudgetExceeded` / usage limit。  
- Stop hook `should_stop`。  
- terminal_error 已记录。

**错误回灌（观察）**：工具/流错误经 `EventMsg::Error`；compact ContextWindowExceeded 时 **从历史头部删 item 重试**（保 prefix cache）；中断不把失败当可续跑的同一 input（注释：preserve pending input instead of restarting failed turn）。

**启示 → LightAgent**：日用层缺的是「turn 边界上的 cancel 检查 + pending steer 队列」，不是再写一套 tool loop（库已有 `max_tool_iterations`）。

---

### 1.2 会话 / 事件 / Rollout（观察）

**持久化模型**：thread rollout = **append-only JSONL**（`history/src/lib.rs` `RolloutItem`）：

```text
RolloutItem::
  SessionMeta(SessionMetaLine)
  | ResponseItem(ResponseItemEnvelope)   // 带 CodexHarnessMetadata
  | Compacted(CompactedItem)
  | TurnContext(TurnContextItem)
  | TokenUsageRecord(...)
  | WorldState(WorldStateItem)
  | RetainedContext(...)
  | EventMsg(EventMsg)                   // 含 TurnAborted、PlanUpdate 等
  | InterAgentCommunication(...)
  | RealtimeItem(...)                    // 模型不可见，仅 UI 重建
```

**`SessionMeta` 关键字段**（`protocol/src/protocol.rs` ~3245）：

- `session_id` / `id: ThreadId` / `forked_from_id` / `parent_thread_id`  
- `cwd`, `runtime_workspace_roots`, `base_instructions`  
- `agent_nickname` / `agent_role` / `agent_path`（子代理）  
- `subagent_history_start_ordinal`：子代理 **自己投影历史** 的起点；更早 ordinal 是继承的父上下文，不进 child turn 投影  
- `history_base` / `history_mode`：分页/继承前缀  
- `context_window`：compact 前消费者可读的窗口身份  

**Resume（观察）**：`agent/control/resume.rs` `resume_agent` → `resume_agent_from_rollout`；fork 用 `forked_from_id` + ordinal 边界。

**Live history vs rollout（观察）**：`context_manager/history.rs` 注释 — tool output truncation **只作用于 live history**，rollout 可保留全量 payload；`history_version` 在 compaction/rollback 时递增。

**启示**：生活助手不必抄全量 RolloutItem；最小集要有 **append-only 检查点事件** + **可 resume 的 goal/constraint 快照**，与 transcript 分离。

---

### 1.3 Plan / Goal（观察）

#### A. `update_plan` 工具（agent 侧 checklist）

- Spec：`tools/handlers/plan_spec.rs` — `plan: [{step, status∈{pending,in_progress,completed}}]`，描述写明 **At most one step can be in_progress**。  
- Handler：`tools/handlers/plan.rs` — 解析 `UpdatePlanArgs`；**Plan mode 禁止**（`ModeKind::Plan` → RespondToModel 错误）；成功发 `EventMsg::PlanUpdate(args)`，工具回执固定 `"Plan updated"`。  
- 类型：`protocol/src/plan_tool.rs` — `StepStatus::{Pending,InProgress,Completed}`，`UpdatePlanArgs { explanation?, plan }`。  
- System prompt（`core/gpt_5_1_prompt.md` / `gpt_5_2_prompt.md`）：**exactly one `in_progress` until done**；勿在工具后复述整表（harness 已渲染）。

**注意（观察）**：handler **不在 Rust 侧强制**「恰好一个 in_progress」——约束在 **tool description + system prompt**；UI/协议层消费 `PlanUpdate` 事件。

#### B. `UserGoalUpdate` / `ThreadGoal`（用户侧目标，窗外）

- `context/user_goal.rs`：`UserGoalUpdate::{Set{objective,status}, Clear}`；**禁止**从 tool output 构造。  
- 内容 kind：`user.goal`；超大 objective → **整段省略**为 `user.goal.omitted`（`MAX_OBJECTIVE_BYTES=700` JSON 串长度），注释：**truncation cannot turn a restriction into a grant**。  
- Compact 边界：`UserGoalUpdate::message_ids(history)` 收集 goal message id，写入 `CompactedHistoryMetadata.input_goal_ids`。  
- 协议：`ThreadGoalStatus::{Active,Paused,Blocked,UsageLimited,BudgetLimited,Complete}`；`ThreadGoal { objective, status, token_budget?, tokens_used, time_used_seconds, ... }`；objective 最长 `MAX_THREAD_GOAL_OBJECTIVE_CHARS=4000`。

**Plan vs Goal（推断，有证据支撑）**：`update_plan` = 执行中 checklist（可被 Plan mode 关掉）；`ThreadGoal`/`UserGoalUpdate` = 用户权威目标，compact 时显式保 id；二者正交。

**启示 → LifeGoalStore**：状态枚举对齐 `GoalManager` + 吸收 Codex 的 `BudgetLimited`/`UsageLimited` 语义到检查点 reason；**忌口等约束不可截断成「看起来允许」**。

---

### 1.4 Context / Compact（观察）

**触发相位**：`CompactionPhase::{PreTurn, MidTurn, PostTurn, StandaloneTurn}`；`CompactionTrigger::{Auto, Manual}`；`CompactionReason`（含 `ContextLimit`, `UserRequested`, model hash 变化等）。

**实现分流**：

| 路径 | 文件 | 行为 |
| --- | --- | --- |
| Responses 摘要 compact | `compact.rs` | 独立模型调用；`SUMMARIZATION_PROMPT`；结果加 `SUMMARY_PREFIX`；重建 history |
| Token-budget compact | `compact_token_budget.rs` | **跳过摘要**，`start_new_context_window`；仍走 Pre/PostCompact hooks + `ContextCompaction` turn item |
| Remote v2 | `compact_remote_v2.rs` | 服务端 compact |

**钩子**：`run_pre_compact_hooks` → `PreCompactHookOutcome::{Continue,Stopped}`；Stopped → `TurnAborted`。Post 同理。

**摘要 prompt**（`prompts/templates/compact/prompt.md`，全文很短）：

- progress / key decisions  
- constraints / user preferences  
- remaining next steps  
- critical data/references  

**替换历史组装**（`assemble_compaction_history`）：prefix（world state）+ compacted items；`insert_initial_context_before_last_real_user_or_summary`；保留 **retained tool outputs**（`compact_retained_tool_outputs.rs`：`client_authored` 且 `FunctionCallOutput{call_id:None, name:Some}`）。

**用户消息截断**：`COMPACT_USER_MESSAGE_MAX_TOKENS = 20_000`。

**失败路径**：ContextWindowExceeded → 删 oldest history item 重试；SessionBudgetExceeded / Interrupted 直接返回；成功后 Warning：「多次 compact 降准，尽量新开 thread」。

**AutoCompactWindow**（`state/auto_compact_window.rs`）：`window_id` / `previous_window_id` / `prefill_input_tokens` 用于相对增长计量。

**启示**：LightAgent 1:1 已有 `>0.85` + `local/compact`；缺口是 **群路径未接线**、**压前 hook（flush）**、以及 **goal/constraint id 级保留**（而非只靠摘要文字）。

---

### 1.5 Interrupt / Cancel / Checkpoint（观察）

- 每层 `tokio_util::sync::CancellationToken`；`or_cancel` 包住 lifecycle / MCP / sampling。  
- `RegularTask` 用 `cancellation_token.child_token()` 传给 `run_turn`。  
- 中断语义注入：`context/turn_aborted.rs` — `TurnAborted` fragment，kind `generic.turn_aborted`，文案明确：**工具/命令可能已部分执行**；unified exec 可能仍在后台。  
- 子代理：`agent/control/interrupt.rs` — **不能 interrupt 自己**；root 不是 spawned agent；目标已死算成功。  
- CompactedHistoryMetadata = compact **检查点元数据**（goal ids、window ids、response id、model hash），与 replacement history 分离赋值。  
- Guardian 另有 `GuardianHistoryCheckpoint`（审查证据轨）。

**粒度（推断）**：取消在 async 边界协作式生效；正在跑的 shell 可能幸存（TurnAborted 明文告知模型）。

**启示**：TUI 停按钮 = `token.cancel("user")`；checkpoint reason ∈ `{step_done, user_cancel, budget, room_turn_end}`；resume 必须假设 **副作用可能半完成**（生活助手侧：已发出的建议不算事务回滚）。

---

### 1.6 Approval × Sandbox（观察，只借「门控正交」）

- `AskForApproval::{UnlessTrusted("untrusted"), OnRequest(default), Granular{...}, Never}`（`protocol.rs` ~1092）。  
- `SandboxPolicy` / `FileSystemSandboxPolicy` / `NetworkSandboxPolicy` 与 approval **分层**（官方 docs + config）。  
- 子代理：`apply_spawn_agent_runtime_overrides` **强制拷贝**父 turn 的 approval_policy / sandbox / cwd，避免孩子与父母策略漂移（`child_config.rs` ~175）。  
- Auto-review（guardian）是 **第三层**：只审「已需要审批」的动作；失败默认 fail-closed（docs）。

**启示（生活助手）**：不引入 OS sandbox；把「外发 / 写记忆晋升 / 烧额度」做成与 run 正交的 **approval 门**，默认只读本地。

---

### 1.7 子代理（观察）

- `spawn_agent`（`agent/control/spawn.rs`）：继承 environments / exec_policy / instructions；**不继承父累计 usage**（注释）。  
- `SessionMeta.subagent_history_start_ordinal`：隔离投影。  
- Full-history fork 禁止改 `agent_type`（`reject_full_fork_agent_type_override`）。  
- Feature `SubagentDefaultContextLimits` 可清掉 child 的 context window / auto_compact limit。

**启示**：Hosted Room 子 Bot = 短上下文派发 + 摘要回 Host；不要把整群 transcript 塞进每个 child。

---

## 2. Claude Code（官方文档为主）

### 2.1 Agent loop / Harness 定义（观察·官方）

- Docs 明确定义：**agentic harness** = 环绕模型的「工具层 + 上下文管理层」。  
- 循环三相：gather context → take action → verify；用户可随时打断。  
- 工具五类：File / Search / Execution / Web / Code intelligence + 编排（subagent、AskUserQuestion）。

置信度：**高**（官方 how-claude-code-works）。

### 2.2 会话与事件（观察·官方）

- 路径：`~/.claude/projects/` 下 **plaintext JSONL**；每条消息、tool use、result 写入。  
- Resume：`--continue` / `--resume` **同 session ID 追加**；`--fork-session` / `/branch` **新 ID 拷贝历史**。  
- 新 session **不带**上一会话对话历史；跨会话靠 CLAUDE.md + auto memory（MEMORY.md 前 200 行或 25KB）。  
- Transcript 异步落盘；hooks 文档警告：hook 读 transcript 可能滞后，Stop 事件用 `last_assistant_message`。

### 2.3 Plan / Todo / Goal（观察·官方）

- **Plan mode**（permission）：只探索提案，不改源文件；`Shift+Tab` 切换。  
- **Explore → Plan → Implement → Verify** 工作流（best-practices）。  
- **`/goal`**：验收条件；**独立 evaluator** 每 turn 后检查；停滞则停 run 但 goal 仍在。  
- **Stop hook**：确定性脚本门闸，可连续 block 直到测试通过。  
- Skills 可带 hooks；`TaskCreate` / `TaskCompleted` 事件（hooks 表）。

**推断**：goal/plan 是 **窗外状态**；compact 后靠磁盘 CLAUDE.md / plan 文件 / goal 再注入。

### 2.4 Context / Compact（观察·官方 + engineering）

Anthropic engineering（Effective context engineering，2025-09-29）：

1. **Compaction**：近满窗 → 摘要 → 新窗 + 摘要；Claude Code 保留架构决策/未决 bug/实现细节，丢冗余 tool 输出；继续时带 **最近访问的 5 个文件**。  
2. **Structured note-taking**：NOTES.md / todo 窗外持久。  
3. **Sub-agents**：子代理可用数万 token，只回 1–2k 摘要。  
4. **JIT context**：路径/查询指针 + 工具按需加载；CLAUDE.md 预注入。  
5. **Context rot**：注意力预算；n² attention。

产品行为（how-claude-code-works / best-practices）：

- 先 **清旧 tool outputs**，再 **summarize**。  
- `/compact` 可带 focus；CLAUDE.md 可写 Compact Instructions。  
- **Thrashing**：单文件过大导致 compact 后立刻再满 → 几次后停止 auto-compact 报错。  
- Hooks：`PreCompact` / `PostCompact`（matcher `manual|auto`）；`PreCompact` exit 2 **可阻止** compact；`SessionStart` matcher 含 `compact`。

置信度：docs/engineering **高**；具体摘要 prompt / JSONL schema 字段级 **未在公开源码核实** → 标 **推断/二手缺口**。

### 2.5 Interrupt / Checkpoint（观察·官方）

| 机制 | 语义 |
| --- | --- |
| `Esc` | **立刻**停；取消当前 tool；上下文保留 |
| 队列消息 | 不 Esc：当前 tool 批结束后本 turn 内读入（steer-at-boundary） |
| Checkpoint | **每个开启 turn 的用户 prompt** 前快照文件；会话内保留约 **100** 个；随会话 resume |
| `/rewind` / EscEsc | Restore code / conversation / both；Summarize from/up to here |
| 限制 | Bash 改文件 **不**进 checkpoint；多数 subagent 编辑不恢复；symlink/hardlink skip |

**与 Codex 对比（观察）**：Claude Esc = 硬中断 tool；Codex TurnAborted 承认后台进程可能仍跑。LightAgent 应明确选一种并向用户说明。

### 2.6 Approval / Permissions（观察·官方）

模式：`auto`（分类器）/ `manual` / `acceptEdits` / `plan` /（`dontAsk`/`bypassPermissions` 见 hooks）。Sandbox 减审批。与 Codex 一样：**权限模式 ⊥ 工具调度**。

### 2.7 子代理（观察·官方）

- 独立 context；fork 可拷贝父对话。  
- 工具调用不进主上下文；结束回摘要。  
- Hooks：`SubagentStart` / `SubagentStop`；Stop→SubagentStop 转换。  
- 主会话用 subagent 做调查，避免主窗被 exploration 填满。

---

## 3. OpenHands SDK（对照：状态机 + 事件日志）

### 3.1 执行状态机（观察·源码）

`ConversationExecutionStatus`（`state.py`）：

```text
idle → running ⇄ paused
         ↘ waiting_for_confirmation
         → finished | error | stuck
deleting
```

`is_terminal` = finished | error | stuck（**idle 不是 terminal**）。

`max_iterations` 默认 **500**；`stuck_detection` 默认 True。

### 3.2 持久化（观察）

```text
{persistence_dir}/{conversation_id}/
  base_state.json          # 整状态快照（agent/config/status/stats/secrets/agent_state）
  events/event-NNNNN-<id>.json   # append-only
```

- 改 public Field → `__setattr__` autosave `base_state.json`。  
- `append_event`：stamp `parent_id`、写 EventLog、推进 `leaf_event_id`（对话树）。  
- Events 惰性加载；View 按 active branch `path_to_root(leaf)` 投影。  
- Pause：`conversation.pause()`；paused 时可 `send_message` 再 `run()`。

### 3.3 Confirmation 正交（观察）

`confirmation_policy: ConfirmationPolicyBase`（默认 `NeverConfirm`）与 `execution_status=waiting_for_confirmation` 配合；security_analyzer 可选。

### 3.4 启示

最小集 CheckpointStore ≈ 「缩小版 base_state + 少量事件」，不必上完整 EventLog 树；但 **paused 可改指令再继续** 值得学。

---

## 4. Aider（上下文预算对照，简）

- Repo map：图排序 + `--map-tokens`（默认 ~1k）裁剪。  
- 启示映射：生活助手把「画像/忌口/活跃目标」当 **预算化必留段**，而非代码符号图。

---

## 5. 横切对比表（机制级）

| 维度 | Codex | Claude Code | OpenHands | LightAgent 现状 |
| --- | --- | --- | --- | --- |
| Loop 边界 | Turn + pending 内环 | Tool 批 + Stop hook | iteration ≤ max_iterations | `agent.run` tool 环；TUI 无 cancel |
| 窗外进度 | `update_plan` + `ThreadGoal` | `/goal` + plan 文件 + todo | `agent_state` dict | `GoalManager` 有，日用未挂 |
| Compact | Pre/Mid/Post + hooks + goal ids | tool-clear→summary；PreCompact | condenser 配置（API 可见） | 1:1 >85%；群函数未接线 |
| 中断 | CancellationToken；部分执行警告 | Esc 立刻；队列 steer | pause 状态机 | Token 有，TUI 未传 |
| 持久化 | Rollout JSONL append | Session JSONL | base_state + events/ | rooms/conversations JSON；无 run checkpoint |
| 门控 | approval ⊥ sandbox | permission ⊥ sandbox | confirmation_policy | SSRF/LA-SANDBOX；无日用审批 UI |
| 子代理 | 继承策略；history ordinal | 独立窗；回摘要 | — | Room 派发短上下文 |

---

## 6. LightAgent 可接线符号（本仓库核对）

### 6.1 已有原语

| 符号 | 路径:行（约） | 能力 |
| --- | --- | --- |
| `CancellationToken` | `LightAgent/cancellation.py:11–61` | `cancel`/`child`/`cancelled`/`reason`；协作边界 |
| `BudgetLimits` / `BudgetManager` / `BudgetExceeded` | `LightAgent/runtime.py:292–360+` | model_calls/tool_calls/tokens/seconds/cost |
| `GoalManager` / `Goal` / `GoalStatus` | `runtime.py:166–280` | pending/active/completed/blocked/cancelled；事件 `goal.*`；`restore(Session)` |
| `AgentRuntime.budget` | `runtime.py:905–915` | ctor 注入 `budget_limits` |
| `LightAgent.__init__(..., budget_limits=, context_budget=)` | `core.py:175–176, 268, 363` | 预算与上下文预算 |
| `LightAgent.run(..., cancellation_token=)` | `core.py:526–548` | run 级取消（**无** budget 参数；budget 在 ctor） |
| `_compact_model_context` | `core.py:1180–1231` | `usage_ratio>0.85` 或 `!fits` → `local.compact` / `ContextCompactor` |
| `ContextBudget` | `session.py:732–756` | max_tokens/reserved/chars_per_token |
| `compact_room_messages` | `local/rooms/digest.py:40–44` | `keep` 尾窗；**纯函数** |
| `build_room_digest` | `digest.py`（同文件） | 近 6 条 / 480 字量级 |
| `_save_rooms` | `local/tui/app.py:1426–1438` | `save_rooms` + `save_transcript`；**未调 compact** |
| TUI `agent.run` | `local/tui/backend.py:409–415` | **未传** `cancellation_token`；`make_agent` **未传** `budget_limits`/`context_budget` |
| `make_agent` | `local/openrouter_config.py:78–119` | 只挂 profile memory |

### 6.2 缺口（观察，与 harness 评测一致）

1. 日用路径取消/单次 run 预算未接线。  
2. 群 `compact_room_messages` 未进保存路径。  
3. `GoalManager` 未映射到生活任务 LifeGoal JSON。  
4. 无步级 CheckpointStore。  
5. Host 摘要易回声（产品层，见既有评测）。

### 6.3 建议接线伪时序（实现留给 Cursor，此处只设计）

```
TUI turn start:
  token = parent.child(run_id=...)
  agent = make_agent(..., budget_limits=BudgetLimits(model_calls=8, seconds=120),
                       context_budget=ContextBudget(...))
  inject ConstraintCard + LifeGoal ephemeral
  try:
    res = agent.run(..., cancellation_token=token)
  except/on cancel:
    CheckpointStore.write(reason=user_cancel|budget)
Room save:
  msgs = compact_room_messages(msgs, keep=N)  # after ConstraintCard keep
  save_transcript(...)
Before compact (1:1 or room):
  memory_flush(); snapshot constraints into card
```

---

## 7. 主张 → 证据 → 启示（浓缩）

1. **主张**：进度必须活在 transcript 外。  
   **证据**：Codex `ThreadGoal`+`update_plan`+compact `input_goal_ids`；Claude `/goal`+CLAUDE.md；Anthropic note-taking。  
   **启示**：LifeGoalStore + ConstraintCard。

2. **主张**：Compact 是带钩子的状态机，不是「删尾巴」。  
   **证据**：Codex Pre/Mid/Post + PreCompact Stop；Claude tool-clear→summary + PreCompact；OpenHands event log 与 view 分离。  
   **启示**：CompactHooks；群必须接线；压前 flush。

3. **主张**：可中断是生产底线，且需定义半执行语义。  
   **证据**：Codex `TurnAborted` 文案；Claude Esc；OpenHands `paused`。  
   **启示**：RunControl + Checkpoint reason。

4. **主张**：门控与循环正交。  
   **证据**：Codex approval⊥sandbox；Claude permission modes；OpenHands confirmation_policy。  
   **启示**：最小集只留审批槽位，不做 OS sandbox。

5. **主张**：子代理隔离上下文、汇总回父。  
   **证据**：三家一致；Codex `subagent_history_start_ordinal`。  
   **启示**：Room 派发保持短 prompt。

---

## 8. 证据缺口（诚实）

| 缺口 | 说明 |
| --- | --- |
| Claude Code 闭源 | JSONL 字段级 schema、compact 精确 token 阈值、checkpoint 磁盘格式未直接读源码 |
| Codex `update_plan` 单 in_progress | Prompt 强制；Rust handler **未** schema-enforce（观察） |
| Codex ExecPlan / PLANS.md | cookbook 页 fetch 空；未纳入硬证据 |
| OpenHands condenser 实现细节 | API 暴露 `LLMSummarizingCondenser`；未深读 condenser 源码 |
| 未跑 live `:free` 长任务 | 本任务禁实现、控额度 |

**文档置信度：~0.88**（Codex/OpenHands/LightAgent 源码硬；Claude 官方 docs 硬；产品阈值数字以 docs 为准）。


---

## 9. Codex `run_turn` 关键片段与配置键（补强）

### 9.1 配置键（观察·`session/step_settings.rs` / config）

| 键 / 字段 | 作用 |
| --- | --- |
| `model_auto_compact_token_limit` | 自动 compact token 阈值 |
| `model_auto_compact_token_limit_scope` | 计量范围（active window vs full） |
| `model_post_turn_compact_threshold_percent` | PostTurn 触发百分比；0=关 |
| `tool_output_token_limit` | tool 输出截断 |
| `update_plan_enabled` | 是否注册 `update_plan`（`spec_plan.rs` ~1314） |
| `compact_prompt` | 覆盖默认 `SUMMARIZATION_PROMPT` |
| `Feature::TokenBudget` | 走 token-budget compact（无摘要、新窗） |
| `approvals_reviewer` | `user` \| `auto_review` |
| `approval_policy` / `sandbox_mode` | 正交门控 |

### 9.2 Mid-turn rollover 条件（观察·`turn.rs` ~609–654）

```text
should_roll_over =
  needs_follow_up
  && (take_new_context_window_request() || token_limit_reached)

if should_roll_over:
  run_auto_compact(..., CompactionReason::ContextLimit, MidTurn)
  continue  # 同一 run_turn 内继续 sampling
```

含义：**工具还没做完 / 还有 pending** 时也可以 compact，再继续——长链路不是「等 turn 结束再压」。

### 9.3 Stop hook 回灌（观察·~657–705）

```text
if !needs_follow_up:
  stop_outcome = run_turn_stop_hooks(...)
  if should_block && continuation_fragments:
    record hook_prompt_message into history
    continue   # 强制再跑一轮（验证门）
  if should_stop: break
```

与 Claude Code Stop hook「测试不过不准停」同构。

### 9.4 `SUMMARY_PREFIX` 语义（观察）

`summary_prefix.md`：告诉接班模型「另一模型的摘要 + 工具状态仍可用，避免重复劳动」。Compact 后历史形态 ≈ **prefix world-state + summary message + retained outputs**。

### 9.5 PlanUpdate 与 UI（观察）

`PlanHandler` 成功路径 **只** `send_event(PlanUpdate)` + 回 `"Plan updated"`；**不**把 plan 全文写回 assistant message——进度渲染是 harness 责任。生活助手 Host 三行应对齐此模式（勿整段回声）。

---

## 10. Claude Code Hooks 与长链路相关事件（观察·官方 hooks 参考）

长链路相关事件（摘录）：

| Event | 与长链路关系 |
| --- | --- |
| `PreCompact` / `PostCompact` | 压前 flush / 压后校验；matcher `manual\|auto`；PreCompact exit2 可拦 |
| `Stop` / `StopFailure` | 验收门；exit2 阻止停止 |
| `TaskCreated` / `TaskCompleted` | 任务生命周期；可 rollback create / 阻止 complete |
| `SubagentStart` / `SubagentStop` | 隔离工作边界 |
| `SessionStart` matcher=`compact` | compact 后新窗加载指令 |
| `InstructionsLoaded` reason=`compact` | CLAUDE.md 在 compact 后重载 |

`permission_mode` 出现在 hook JSON：`default|plan|acceptEdits|auto|dontAsk|bypassPermissions`。

**启示**：LightAgent CompactHooks 至少要有 **before/after 可插回调**（先 memory flush，后断言 ConstraintCard 仍在），不必上完整 hook 市场。

---

## 11. OpenHands 事件写入契约（观察·源码）

```text
append_event(event):
  event = stamp parent_id ← leaf
  seq = EventLog.append  # 文件锁；禁止重复 id
  if not ConversationStateUpdateEvent:
    leaf_event_id = event.id
```

pending actions：`get_unmatched_actions(events)` 找无 Observation 的 ActionEvent——**崩溃恢复**时知道哪些工具半完成。

**启示**：CheckpointStore 应记录 `pending_side_effects[]`（生活助手：已展示未确认的建议、已写未确认的记忆候选）。

---

## 12. 伪状态机：适合 LightAgent 的融合模型（推断·有证据）

```text
                    ┌──────────────┐
                    │  IDLE/READY  │
                    └──────┬───────┘
           user multi-step │
                    ┌──────▼───────┐
                    │ GOAL_ACTIVE  │◄── LifeGoalStore.create
                    └──────┬───────┘
                           │ inject ConstraintCard
                    ┌──────▼───────┐
         ┌─────────►│  RUN_STEP    │◄──────────────┐
         │          └──────┬───────┘               │
         │     cancel/budget│                      │
         │          ┌──────▼───────┐               │
         │          │ CHECKPOINT   │── continue ───┘
         │          └──────┬───────┘
         │     step done   │
         │          ┌──────▼───────┐
         └──────────┤ ADVANCE_STEP │
                    └──────┬───────┘
              all done / cancel terminal
                    ┌──────▼───────┐
                    │ GOAL_DONE    │
                    └──────────────┘

并行轨道（正交）:
  CompactHooks  --on before_model-->  may shrink transcript; must keep ConstraintCard
  RunControl    --on each boundary--> CancellationToken / BudgetLimits
  HostProgress  --on room turn------> 动作/忌口/下一步（读 LifeGoal）
```

此图是 **推断的融合模型**，不是任何一家的一字不差拷贝。
