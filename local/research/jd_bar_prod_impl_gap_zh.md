# JD 未达标维：社区成熟生产级实现对照（底层）

> 日期：2026-10-15（America/Martinique / AST）  
> 范围：**B 飞轮 · D Multi-Agent · E 长程/共享 KB/生产力台架**（A/C 为「接近」，本文件只深挖未达维）  
> 方法：官方文档 / 源码路径 / GitHub 星数 / X 工程叙事；对照本仓 `local/memory/jobs.py`、`local/rooms/plan.py`、`local/rooms/digest.py`  
> 原则：**实事求是**——绿切片 ≠ 飞轮/Swarm/生产力台架；本任务不改生产飞轮/多智能体代码。

---

## 0. 总览

| 维 | LightAgent 现状（源码） | 社区生产级典型 | 差距本质 |
| --- | --- | --- | --- |
| **B** | `enqueue` 入队；`run_due` **故意 return []** | Mem0 Dream / Letta tiers / Zep 时序边 / Voyager skill lib | **有写入无巩固进化** |
| **D** | `build_turn_plan`：@mention → 关键词模板 → host_only | Agents SDK handoff / LangGraph / CrewAI / MetaGPT SOP | **单层规则选麦 ≠ 递归拆原子** |
| **E** | 卡+pin+goal+routine 多 store；Room digest ≤480 字 | LoCoMo/LongMemEval 评测 + THE AGENT COMPANY/WorkArena 台架 + 跨 Agent 共享图 | **局部不变量有；共享 KB 与生产力 benchmark 无** |

---

## 1. B — Context 飞轮 / consolidate

### 1.1 Mem0（~67k★）— Dream 巩固管线

- 文档：[Dream](https://docs.mem0.ai/platform/features/dream)  
- 源码线索：`integrations/openclaw/dream-gate.ts`（时间/会话/记忆数门闩 + 文件锁）；plugin `DREAM_PROTOCOL`（DELETE/MERGE/REWRITE/KEEP，跳过 `[PINNED]`）  
- **机制**：
  1. **Supersede**：写入时新事实作废旧事实，保留历史，可读 `latest_only`  
  2. **Merge**：近重复折叠为规范条目  
  3. **Synthesis**（Pro+）：后台按 cadence（7d/日）蒸馏 pattern memory，≥20 条才跑；**不阻塞** add/search  
- **存储**：SQL 事实 + 向量 + entity；scoping：`user_id` / `agent_id` / `run_id` / `app_id`  
- **与本仓差**：本仓有 absorb supersede（忌口卡）与 pin/learn，但 `local/memory/jobs.py`：

```python
def run_due(store):
    """P0 stub: due jobs stay queued. Consolidation is intentionally empty."""
    return []
```

  → 无 Merge/Synthesis/Dream-gate；入队即终点。`JD-B03/B07` 刻意断言 stub。

### 1.2 Letta / MemGPT（~25k★）

- 论文：[MemGPT](https://arxiv.org/html/2310.08560v2)；产品 [letta-ai/letta](https://github.com/letta-ai/letta)  
- **机制**：OS 式分层 — Core（in-context blocks，agent 自改）/ Recall（对话检索）/ Archival（长期语义）；工具驱动换页  
- Issue #3116 社区共识：Dedup（向量，便宜，频跑）≠ Consolidation（LLM，贵，少跑）；**摘要不删原 episode**  
- **与本仓差**：本仓 pack/inject 是装配，非 agent 自管分页；无 archival consolidate 作业。

### 1.3 Zep / Graphiti（~32k★）

- [getzep/graphiti](https://github.com/getzep/graphiti) · 论文 *Zep: Temporal Knowledge Graph…*  
- **机制**：双时态有效窗口；新事实 **invalidate** 旧边（不作无版本堆积）；混合语义/关键词/图检索  
- X：[yumizjx](https://x.com/yumizjx/status/2107026764941697281) 归纳「给记忆加有效期」  
- **与本仓差**：ConstraintCard 有 supersede，但 Profile learnings **无时序边作废**；无图结构共享。

### 1.4 Voyager / Reflexion / ExpeL / Generative Agents

| 系统 | 巩固触发 | 存储 | 进化形态 |
| --- | --- | --- | --- |
| Voyager | 课程+技能成功 | 可执行技能库（嵌入索引） | 程序记忆增长 |
| Reflexion | 任务失败 | 语言反思记忆 | 回合级再试 |
| ExpeL | 轨迹抽取 | 成功/失败经验池 | 跨任务 insight |
| Generative Agents | 日终反思 | 记忆流 → 信念 | 计划–反思闭环 |

- **与本仓差**：无技能库自动沉淀、无失败反思环、无日终信念巩固；**仅「可写可改」≠飞轮**。

### 1.5 ChatGPT memory / OpenClaw（产品对照）

- ChatGPT：用户可见记忆条目 + 模型侧抽取；非开源，难复核巩固算法。  
- Mem0↔OpenClaw：`dream-gate` 以 **minHours / minSessions / minMemories** 门闩防风暴巩固。  
- **启示**：生产级飞轮 = **门闩 + 非破坏合并 + 可追溯 supersede + 后台合成**；本仓缺后三环执行体。

### 1.6 B 维「社区怎么做 vs 我们」（三条）

1. **巩固是一等公民作业**（Dream/日终反思），不是空队列。  
2. **写入路径内建 supersede/merge**，检索默认可只要「当前真」。  
3. **进化可观测**：技能库/经验池/pattern 条数↑ 且下游错误↓——本仓无此闭环。

---

## 2. D — Multi-Agent 动态编排

### 2.1 OpenAI Swarm → Agents SDK（~30k★）

- 教育版 [openai/swarm](https://github.com/openai/swarm)：Agent = instructions+tools；**handoff** = tool 返回另一 Agent。  
- 生产演进：[openai-agents-python](https://github.com/openai/openai-agents-python)  
  - **Handoffs**：专科接管用户可见下一轮  
  - **Agents as tools**：经理保留所有权，专科作有界工具  
  - Guardrails、session、可过滤历史  
- **与本仓差**：Hosted Room **无** LLM handoff；`plan.py` 纯规则；无 ownership 转移语义。

### 2.2 LangGraph（~43k★）

- 显式 **StateGraph**：条件边、环、嵌套 subgraph；编译检查点。  
- 适合「宏观→子图→聚合」的**可控递归**。  
- **与本仓差**：Room 无图状态机；复杂出差/报销类输入 → `fallback_host_only`（`JD-D07`）。

### 2.3 CrewAI（~60k★） / AutoGen·AG2 / MetaGPT / ChatDev

| 框架 | 拓扑 | 拆解方式 |
| --- | --- | --- |
| CrewAI | 角色 Crew；sequential / hierarchical | 经理委派任务列表 |
| AutoGen/AG2 | GroupChat + speaker selection | 对话式动态选麦 |
| MetaGPT | SOP / 流水线角色 | 软件团队式阶段产物 |
| ChatDev | 沟通式开发流水线 | 阶段门控 |

- ReDel / ROMA（论文）：**运行时**递归生成子 Agent / atomize-plan-execute-aggregate。  
- **与本仓差**：本仓仅 `fitness_diet` 关键词模板 + @mention；Host 三行规则摘要（非 LLM Host）；**明确不跑** `LightSwarm.run`（既有调研）。

### 2.4 本仓 Hosted Room（加深）

```text
build_turn_plan:
  @mentions → reason=mention
  else match_fitness_diet → template:fitness_diet (+ host)
  else → fallback_host_only
speakers = speakers[:room.max_speakers]
```

- `digest.py`：短窗 digest，**剥离** `<memory-context|persona|identity>`；**不是**跨 Bot 共享知识库。  
- `JD-D07/D10`：宏观多域无关键词 → host_only + `no_recursive_swarm` PASS = **诚实暴露能力边界**。

### 2.5 D 维三条摘要

1. 生产级用 **handoff / 图状态 / 角色任务队列** 做动态编排；本仓是 **静态关键词选麦**。  
2. 递归拆原子需要 **子任务图或子 Agent 生成**（ReDel/LangGraph subgraph）；本仓 TurnPlan **无 children**。  
3. 共享上下文应是 **结构化只读事实层**；本仓只有短 digest，防互啄全文但也不共享 KB。

---

## 3. E — Long-horizon · 共享 KB · 生产力台架

### 3.1 长记忆评测协议（应用级）

| 基准 | 测什么 | 可迁移探针 |
| --- | --- | --- |
| LoCoMo | 超长对话 QA / 事件一致性 | 多忌口跨轮仍在（`JD-E04/E09`） |
| LongMemEval | 跨会话、时间推理、知识更新、拒答 | cancel→resume 同 goal_id（`JD-E01/E08`） |
| Mem0 平台分 | 厂商叙事 | **不采信为达标** |

### 3.2 生产力台架（职场 E2E）

| 台架 | 机制 | 为何本仓未达 |
| --- | --- | --- |
| **THE AGENT COMPANY** (~796★) | Docker 任务；`task.md` 唯一提示；加密 `evaluator.py`；结果+checkpoint | 无模拟公司环境、无同事 NPC、无 checkpoint 评分器 |
| **WorkArena++** | BrowserGym + ServiceNow 组合任务 | 无企业 UI env |
| **AssistantBench** | 真实网页长耗时任务 | 无浏览 E2E 台架（browser-use skill 默认不进测评） |
| **WebArena / BrowserGym** | 自托管站 / 统一浏览器 API | 默认 API mock |

### 3.3 跨 Agent 共享上下文（生产做法）

- Mem0：`user_id` 级记忆可被多 agent 读；Synthesis **故意**排除带 `agent_id` 的条目以防串台。  
- Graphiti：组织级时序图作共享事实源。  
- Agents SDK：handoff 可过滤历史，避免全文倾倒。  
- **本仓**：成员任务带短 digest + 可选 `share_user_profile`；**无**独立 SharedKB 服务；constraint 在 Host 摘要里点名，非图共享。

### 3.4 E 维三条摘要

1. 长程达标看 **跨会话召回 + 更新/拒答**（LongMemEval），不只单进程 store PASS。  
2. 生产力达标看 **可复现终局环境 + checkpoint**（THE AGENT COMPANY），本仓无。  
3. 共享 KB ≠ digest：需要 **scoped 事实存储 + 权限**；本仓刻意短窗防泄漏，同时牺牲共享深度。

---

## 4. P0 建议（基于生产对照，非本轮实现）

| # | 建议 | 对齐社区 | 关掉哪条否定探针 |
| --- | --- | --- | --- |
| 1 | 实现 `run_due`：merge 近重复 + supersede 链 + 可选日终 synthesis；门闩防风暴 | Mem0 Dream / Letta | `consolidate_job_queued_not_run` 应变「巩固后可观测」 |
| 2 | 可选 LLM Host 或受限 handoff；宏观目标→原子任务图（日用默认关、可开） | Agents SDK / LangGraph | `no_recursive_swarm` / host_only 复杂任务 |
| 3 | Constraint/Goal/Pin **只读共享层**（按 space_id），禁止 transcript 互啄 | Mem0 scoping / Graphiti | E2 未达 |
| 4 | 事实/遗漏：FACTS 风格 grounded 探针 + RAGAS 生活 30 题 | FACTS/RAGAS | A 接近→达标 |
| 5 | 生产力：自建「办事」mock 终态或接 THE AGENT COMPANY 子集协议 | TAC checkpoint | E4 |

---

## 5. 证据索引

| 本仓 | 社区 |
| --- | --- |
| `local/memory/jobs.py` | https://docs.mem0.ai/platform/features/dream |
| `local/rooms/plan.py` | https://openai.github.io/openai-agents-python/multi_agent/ |
| `local/rooms/digest.py` | https://github.com/getzep/graphiti |
| `local/eval/cases/jd_bar_v2.yaml` | https://github.com/TheAgentCompany/TheAgentCompany |
| 既有 `multi_agent_group_chat_survey_zh.md` | https://github.com/xiaowu0162/LongMemEval |

