# LightAgent Harness 生产级评估（尤其长任务）

日期：2026-10-13（America/Martinique）  
范围：上游 `LightAgent/` 内核 + 本地日用层 `local/`（TUI、Hosted Room、compact、memory、conversations）  
方法：读实现（非仅调研文）+ 复跑 pytest；对照既有验收与日用评估。

---

## 结论摘要

**接近但未达生产级。**  
单 Agent 工具循环、协作式取消/预算/压缩/画像的**库能力**和离线单测骨架扎实；本地日用路径（TUI + Hosted Room）把长任务所需的规划层、可中断、群侧长上下文、真 live 长程 E2E **刻意做成了 MVP**。对「健身+饮食」一类短 happy path 可用；对跨多轮、跨小时、需收敛与可恢复的长任务，**达不到可宣称的生产级标准**。

---

## 分项打分

| ID | 维度 | 评分 | 一句话 |
| --- | --- | --- | --- |
| A | 任务完成可靠性 | **PARTIAL** | 库有 `max_retry`/`max_tool_iterations`/明确失败；TUI 未接 `BudgetLimits`/`cancellation_token`，无长程检查点 |
| B | 长上下文 | **PARTIAL** | 1:1 有 >85% 自动 + `/compact` + pin；群只尾部窗口且**未接入保存路径**；默认 1M 窗口难触发自动压 |
| C | 规划与分解 | **PARTIAL** | `LightFlow`/`LightDAG`/`GoalManager` 在库里；日用路径默认关 ToT、不用 Flow/DAG；Room 选麦是关键词 |
| D | 工具与沙箱 | **PARTIAL** | `web_search`/`web_fetch` 真联网+SSRF；Python 执行默认 `LA-SANDBOX` 阻断；无 OS 级隔离 |
| E | 多智能体 | **PARTIAL** | Hosted Room E1–E18 绿、单层派发防混沌；Host 规则拼接易回声；长协作会漂 |
| F | 可观测与可中断 | **PARTIAL** | TUI 轨迹可用；取消令牌未接到对话中断；`:free` 日限有本地闸 |
| G | 测试与验收 | **PARTIAL** | 本地 95 + 核心子集 74 离线绿；几乎无长任务 live E2E |
| H | 业内对照 | **缺口清晰** | 相对 Claude Code / Cursor Agent：缺沙箱深度、计划模式、长程检查点；相对 AG2：选麦更弱但更安全 |

---

## A. 任务完成可靠性 — PARTIAL

**证据**

- 主循环：`LightAgent.run(..., max_retry=10, max_tool_iterations=...)`；非流式 `for _ in range(max_retry)`，流式另计 `max_tool_iterations`，耗尽写 `max_retry_reached` / `max_tool_iterations_reached`（`LightAgent/core.py` 约 508–560、2058–2254、2530–2540）。
- 工具失败：JSON 解析失败会 `LA-JSON` 记入 tool 结果并继续，而不是静默吞掉（同文件约 2097–2104）。
- 库级预算：`BudgetLimits` / `BudgetExceeded`（`LightAgent/runtime.py` 291–360）；协作取消：`CancellationToken`（`LightAgent/cancellation.py` 全文）。
- **日用断点**：`local/tui/backend.py` 的 `agent.run(...)`（约 409–415）**不传** `cancellation_token` / `budget_limits`；`local/openrouter_config.py` 的 `make_agent` 同样不传 `context_budget` / `budget_limits`。

**判断**：多步工具在单次 `run` 内可收敛或明确失败；跨会话长任务缺少检查点/恢复与运行期硬预算接线 → 非生产级长任务可靠性。

---

## B. 长上下文 — PARTIAL

**证据**

- 内核：`context_budget is None` 则 `_compact_model_context` 直接 return（`LightAgent/core.py` 1180–1183）；`usage_ratio > 0.85` 走 `local.compact.kernel_hook.compact_model_messages`（1187–1216）。
- TUI：`should_auto_compact` 阈值 0.85（`local/compact/policy.py` 9、17–19）；发送前 `_maybe_auto_compact`（`local/tui/app.py` 1269–1274、1303）；`/compact` 经 `parse_compact_command`（1288–1293）。
- Pin / user 轮：`metadata.compact == "never"`、`keep_user_turns`（`LightAgent/session.py` 709–714、781–842）；compact 验收 E1–E10（`local/research/compact_acceptance_zh.md`）。
- **群侧致命缺口**：`compact_room_messages(..., keep=40)` 仅在测试与 README 出现（`local/rooms/digest.py` 40–44）；`_save_rooms` / `_send_room_turn` **未调用**（`local/tui/app.py` 1426–1438、1510–1567）。消化窗口仅最近 6 条、480 字（`digest.py` 14、22–37）。
- 默认展示窗口 `1_000_000`（`local/tui/trace.py` 76–85），自动压缩在日常很难碰到。
- Memory consolidate 仍是 stub（`local/memory/jobs.py` 1–20）。

**判断**：1:1 离线压缩设计接近生产；群聊与跨天巩固未闭合 → 长任务上下文 **未达生产级**。

---

## C. 规划与分解 — PARTIAL

**证据**

- 库：`LightFlow`（`LightAgent/flow.py`）、`LightDAG`（`LightAgent/dag/`）、`GoalManager`（`runtime.py` 约 166+）；`tests/test_lightflow.py` + `test_lightdag.py` 等本机 **74 passed**（与 runtime/session/guardrails/tracing 同跑）。
- 日用：`tree_of_thought=False` 默认（`openrouter_config.py` 90；`backend.py` 401；协作子 Bot 禁止 ToT，`collaborate.py` 232–233）。
- Room：`build_turn_plan` 纯规则 — `@` → `fitness_diet` 关键词 → Host（`local/rooms/plan.py` 16–49；`scenarios.py` 10–33）。无语义选麦、无矛盾消解。

**判断**：有真实规划层，但**未进入日用 harness 主路径**；长任务易靠 prompt 堆叠漂移。

---

## D. 工具与沙箱 — PARTIAL

**证据**

- `local/tools/web.py`：ddgs/httpx、SSRF 拦私网/loopback（约 29–115）。
- `browser-use` 为 skill，明确警告多轮烧额度（`skills/browser-use/SKILL.md`）。
- 任意 Python：默认不注册；调度 `LA-SANDBOX`（`docs/python_executor_security.md`；`core.py`/`tools.py`）。文档写明 **不是安全沙箱**，子进程仍是应用 OS 身份。

**判断**：联网工具可用、危险代码默认关；相对 Claude Code / Cursor 的隔离执行差距大。

---

## E. 多智能体（Hosted Room）— PARTIAL

**证据（本机复跑）**

- `pytest local/rooms/tests` → **23 passed**（约 8.5s）
- `pytest local/rooms + conversations + memory + compact/tests` → **95 passed**（约 14.6s）  
  `LIGHTAGENT_FORBID_OPENROUTER=1`，无 OpenRouter。

**行为**

- 单层 `run_delegation`，子无 `delegate_to_bot`、无 ToT、不跑 `LightSwarm.run`（验收文 + `rooms/README.md`）。
- Host：`render_host_summary` 截断拼接 + 固定「下一步」（`host_summary.py` 11–28）— **规则回声，非主持推理**。
- 敏感子串拦外发（`sensitive.py`）；误伤已知。
- 日用评估结论：**勉强 / MVP**（`hosted_room_usability_eval_zh.md` §4）。

**长协作真实水平**：短「健身+饮食」happy path **稳定（离线）**；多轮约束保持、矛盾消解、口语触发、群 transcript 压缩 **不足**，不能当生产级长协作 harness。

---

## F. 可观测与可中断 — PARTIAL

**证据**

- TUI 轨迹 Tab、筛选、跳对话（`local/tui/app.py` 轨迹相关绑定与 `refresh_trace`）。
- 库 `CancellationToken` + runtime job cancel；TUI `action_cancel` 仅身份弹层关闭（`identity_ui.py`），**不是**打断 `agent.run`。
- `:free`：`DAILY_LIMIT=45`、`PER_MIN_LIMIT=18`、强制 `:free` 后缀（`openrouter_config.py` 24–72、30–32）；`DelegateQuota.limit=45`（`collaborate.py` 56–63）。

**判断**：防爆额度够 demo；可中断与 run 级预算未接 → 长任务运维不达标。

---

## G. 测试与验收 — PARTIAL

| 套件 | 本机结果 |
| --- | --- |
| `local/rooms\|conversations\|memory\|compact/tests` | **95 passed** |
| `local/rooms/tests` | **23 passed** |
| `tests/test_v010_runtime\|session + lightflow + lightdag + guardrails + v096_tracing` | **74 passed** |

缺口：无跨小时 live 长任务 E2E；Room/compact 真 `:free` 未进单测（验收文已声明）；`LightEvaluator`（`docs/evaluation.md`）未绑到生活助手场景。

---

## H. 业内对照（缺口）

| 能力 | Claude Code / Cursor Agent | LightAgent 日用路径 |
| --- | --- | --- |
| 长任务计划/检查点 | 常见（plan、todo、可恢复） | 库有 Flow/DAG/Goal，TUI 未用 |
| 上下文压缩 | 生产路径默认开启 | 1:1 有；默认 1M；群未接线 |
| 工具沙箱 | OS/容器级常见 | SSRF + AST/LA-SANDBOX，非真沙箱 |
| 多智能体 | 受控子代理 / 深集成 | 单层派发 + 关键词主持（刻意克制） |
| 可中断 | 用户可停当前 run | 令牌未接 TUI |
| 记忆巩固 | 产品化召回/整理 | P0 画像有；dreaming stub |

相对 AG2：LightAgent Room **更安全**（有界、单层），**更弱**于开放式选麦与长辩论质量。

---

## 长任务专项

| 问题 | 现状 | 风险 |
| --- | --- | --- |
| 多步工具单次 run | `max_retry`/`max_tool_iterations` 有界 | 中等：可停，但无跨 run 目标状态机 |
| 上下文膨胀 | 1:1 可压；默认窗口过大；群只 digest 尾部且未压盘 | **高**：长群聊丢忌口/目标 |
| 规划漂移 | 无日用 Goal/Flow；Room 关键词 | **高**：复合任务靠用户「说对词」 |
| 失败恢复 | 工具错误入上下文；无 checkpoint | **高** |
| 额度 | 本地日限 + 协作配额 | 低（demo）；生产需按租户硬配额 |
| 中断 | 库有、UI 无 | **高**（烧额度/挂死） |
| 记忆跨天 | Profile pack + pin；consolidate stub | 中 |

---

## 与日用场景差距

用户已认可侧栏「创建群聊」入口。差距在结果质量与长程：

1. 建群仍需先备 2–6 身份 Bot（usability eval）。  
2. 触发靠「健身+饮食」类词，口语易落到 Host 提示。  
3. Host 综合机械回声，不消解教练/饮食矛盾。  
4. 群越聊越长时无 life-compact，约束易丢。  
5. 真模型长任务手感未用自动化钉死（仅 mock + 少量验收叙述）。

---

## 若要生产级：P0 / P1（最多 7 条，按影响）

1. **P0 — 群 transcript 长上下文**：保存路径调用 `compact_room_messages`；把 1:1 的 pin/禁忌 flush 接到群 digest；禁止只靠 480 字尾部撑长协作。  
2. **P0 — TUI 接线 `cancellation_token` + `BudgetLimits`**：用户可中断；model/tool/秒级硬停；与 OpenRouter 日限并列。  
3. **P0 — 日用路径启用目标/检查点**：或轻量 Goal，或受限 LightFlow；禁止长任务纯靠无状态 prompt 堆。  
4. **P0 — Host 去回声**：规则抽「动作 / 忌口 / 下一步」三行；可选 `LIGHTAGENT_ROOM_HOST_LLM` 短总结（默认关）。  
5. **P1 — 自动 compact 默认可触发**：合理默认窗口（或按模型），勿默认 1M；live 冒烟钉 E1。  
6. **P1 — 选麦/触发**：口语同义 + Host 追问「要不要请饮食顾问」；降低建群一键模板成本。  
7. **P1 — 长任务 E2E**：固定 multi-tool + 群多轮约束保持用例（可 mock 模型）；consolidate 从 stub 升到可调度巩固。

---

## 本机命令与数字（可引用）

```bash
cd /workspace/LightAgent
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. python -m pytest \
  local/rooms local/conversations local/memory local/compact/tests -q
# → 95 passed in ~14.6s

LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. python -m pytest local/rooms/tests -q
# → 23 passed in ~8.5s

LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. python -m pytest \
  tests/test_v010_runtime.py tests/test_v010_session.py \
  tests/test_lightflow.py tests/test_lightdag.py \
  tests/test_guardrails.py tests/test_v096_tracing.py -q
# → 74 passed in ~1.4s
```

关键实现锚点：`LightAgent/core.py`（循环/压缩/取消检查）、`LightAgent/session.py`（ContextBudget/Compactor）、`LightAgent/runtime.py`（Budget/Goal）、`local/rooms/{plan,runtime,host_summary,digest}.py`、`local/tui/{app,backend}.py`、`local/openrouter_config.py`、`local/compact/policy.py`、`local/memory/jobs.py`。
