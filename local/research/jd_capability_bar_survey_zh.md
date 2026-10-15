# 实习 JD 能力尺子：充分调研与本仓映射

> 日期：2026-10-15（America/Martinique / AST）  
> 尺子：「实习 JD 级生产力 Agent」——质量缺陷可控 + Context 飞轮 + 规划/工具/记忆/RAG + Multi-Agent 动态编排 + Long-horizon 多级存储与端到端评测。  
> 方法：Web/GitHub/X + 本仓 `local/` 架构与既有 `local/eval`、`local/research/*`；**协议与可迁移指标优先，不整套搬场景**。  
> 关联：`agent_capability_eval_survey_zh.md` · `agent_capability_eval_design_zh.md` · `harness_production_eval_zh.md` · `life_assistant_long_horizon_deepdive_zh.md`

---

## 0. 一句话总判（调研结论，评测见 verdict）

以公开生产力 / Agent 基准的**能力定义**对照本仓生活助手二开：  
**A（质量缺陷）接近可测、部分可达；C（单 Agent 规划工具记忆）接近；B（自进化飞轮）与 D（高扩展 Multi-Agent）未达；E（Long-horizon + 端到端生产力 benchmark）整体未达。**  
本仓强在「可断言 store 不变量 + 单层安全 Hosted Room」；弱在「无事实/遗漏自动裁判、无 consolidate 飞轮、无递归拆原子任务、无跨 Agent 共享知识库、无 AssistantBench/WorkArena 级生产力台架」。

---

## 1. 标准条目表（JD 原文 → 操作化）

| ID | JD 表述 | 操作化定义（可测） | 主缺陷形态 |
| --- | --- | --- | --- |
| **A1** | 事实错误 | 回答与工具结果/给定文档/忌口卡不一致；无据编造 | 幻觉、过期知识 |
| **A2** | 信息遗漏 | 多约束/多子问只答一部分；检索缺关键 chunk | Context recall 低 |
| **A3** | 工具调用（错误） | 错工具、错参、该调未调、不该调却调 | AST / irrelevance 失败 |
| **A4** | 指令未遵循 | 首轮/多轮硬约束被遗忘或违反 | Instruction retention 失败 |
| **A5** | 任务未完成 | 多步目标未达终态；progress 停滞 | Success / TGC 失败 |
| **B** | Context Data 飞轮 / AI 自进化 | 交互→写入→巩固→检索→行为改进闭环；可观测经验库增长 | 仅记不进化 / stub |
| **C1** | 任务规划 / Planning | 模糊目标→可验证步骤；恰一 in_progress | 滥拆 / 不拆 |
| **C2** | Tool-use / skill | 注册工具+可选 skill 正确选用 | 错链、烧额度 |
| **C3** | 长短期记忆 + RAG | 工作记忆 vs 耐久记忆；召回增强生成 | 丢忌口、错误召回 |
| **C4** | 多步 Reasoning | 多跳推理与工具交错 | 捷径幻觉 |
| **D** | Multi-Agent 动态编排 | Swarm/Team；宏观目标递归拆原子；可扩展协作 | 仅关键词单层派发 |
| **E1** | 工作记忆+全局知识库 | 多级存储；抗遗忘 | 单层 transcript |
| **E2** | 跨 Agent 共享上下文 | 共享事实/约束/进度，非互啄全文 | 无共享 KB |
| **E3** | 持续进化框架 | Reflexion/ExpeL/技能库级 | 无 |
| **E4** | 端到端评测 + 生产力 benchmark | 统一 harness + 办公/网页生产力场景 | 仅局部 L0–L3 |

---

## 2. 外部基准与指标（充分覆盖）

### 2.1 A：事实错误 / 幻觉 /  grounding

| 基准 | 链接 | 测什么 | 核心指标 | → JD A |
| --- | --- | --- | --- | --- |
| **HELM**（含 Capabilities） | https://crfm.stanford.edu/helm/ · https://github.com/stanford-crfm/helm | 多场景整体评测；摘要 faithfulness（SummaC/QAFactEval）；Capabilities 含 IFEval 等 | win rate / scenario accuracy；faithfulness 子分 | A1 框架级；本仓不跑全 HELM，借「多指标+可复现」协议 |
| **FACTS Grounding / Suite** | arXiv:2501.03200 · DeepMind blog · HF `google/FACTS-grounding-public` | 长文档（≤32k）条件下回答是否**完全 grounded**；Suite 另含 Parametric / **Search** / Multimodal | eligibility 过滤 + multi-judge grounding 准确率 | A1：工具/网页结果后回答须 grounded；Search 切片对齐 `web_search` |
| **FreshQA**（+ SealQA） | https://github.com/freshllms/freshqa | 时效事实；FreshEval LLM-judge | TRUE/FALSE accuracy（relaxed/strict） | A1：生活助手「今日菜单/活动」类时效题；本仓用工具结果断言替代全量 FreshQA |
| 幻觉综述指标 | FactScore 等（对照） | 原子事实支持率 | 支持率 | 开放回答辅指标，主路径仍用 store/tool |

### 2.2 A：信息遗漏 + RAG

| 基准 | 链接 | 测什么 | 核心指标 | → JD A2/C3 |
| --- | --- | --- | --- | --- |
| **RAGAS** | arXiv:2309.15217 · docs.ragas.io | Faithfulness / Answer relevance / Context relevance·recall | 0–1 分解句支持率；context recall | A2：忌口+目标多约束是否进答；memory pack 当「检索上下文」 |
| **RGB** | arXiv:2309.01431 · AAAI · GitHub chen700564/RGB | 噪声稳健、**拒答**、信息整合、反事实稳健 | noise 下准确率；负例拒答率 | A2/A1：无依据应拒；整合多条记忆 |
| **CRUD-RAG** | arXiv:2401.17043 | 中文 RAG：续写/QA/幻觉纠正/多文档摘要 | 任务相关 | 中文生活场景改编；非照搬新闻域 |

### 2.3 A3：工具调用

| 基准 | 链接 | 测什么 | 核心指标 | → 本仓 |
| --- | --- | --- | --- | --- |
| **BFCL** V3/V4 | gorilla.cs.berkeley.edu · GitHub ShishirPatil/gorilla | AST、parallel、irrelevance、多轮 state、V4 web/memory | AST + state + subset | `TOOLS` 金标；拒调闲聊 |
| **τ-bench / τ² / τ³** | arXiv:2406.12045 · sierra-research/tau2-bench | 用户模拟+策略+终局 DB | pass^k；状态相等 | 忌口/例程/goal 终态 |
| **ToolSandbox** | 文献/社区 | 有状态工具+雷区 | 里程碑/mine | 未确认例程=雷区 |
| **API-Bank** | arXiv:2304.08244 | Plan→Retrieve→Call | Correctness + ROUGE | 先 search 再 fetch |

### 2.4 A4：指令遵循

| 基准 | 链接 | 测什么 | 核心指标 | → 本仓 |
| --- | --- | --- | --- | --- |
| **IFEval** | arXiv:2311.07911 | 可程序验证指令（字数/关键词等） | strict/loose accuracy | 生活助手改写：「不要推荐海鲜」「不要 memory_learn」 |
| **FollowBench** | ACL 2024 · YJiangcm/FollowBench | 细粒度多级约束 | HSR / SSR / CSL | 忌口+格式+情境叠加 |
| **MultiChallenge** | ACL 2025 Findings · arXiv:2501.17399 | 多轮：指令保持、散落信息、版本编辑、自洽 | instance rubric 准确率 | **忌口贯穿 / 改口 supersede** 主协议 |

### 2.5 A5：任务完成

| 基准 | 链接 | 测什么 | 核心指标 | → 本仓 |
| --- | --- | --- | --- | --- |
| **GAIA** | arXiv:2311.12983 | 工具链助手题 L1–L3 | 准 exact-match | 少量生活查证题 |
| **AgentBench** | THUDM/AgentBench | 多环境 | Overall | 只借环境成功定义 |
| **AppWorld** | StonyBrookNLP/appworld | 多 App + 单元测试终局 | TGC/SGC | expected_state JSON |
| **AgentBoard** | NeurIPS 2024 D&B | 部分可观测 progress | progress rate | LifeGoal 步骤进度 |

### 2.6 B：自进化 / Context 飞轮

| 系统/工作 | 链接 | 机制 | 飞轮形态 | → 本仓差距 |
| --- | --- | --- | --- | --- |
| **Voyager** | 技能库 curriculum | 可执行技能累积 | 程序记忆增长 | 无 skill 自动沉淀库 |
| **Generative Agents** | 记忆流+反思+计划 | 日终反思 | 信念巩固 | consolidate **stub** |
| **Reflexion** | 语言反思记忆 | 失败→反思→再试 | 回合级进化 | 无自动反思环 |
| **ExpeL** | 成功/失败轨迹抽取 | 经验池 | 跨任务迁移 | 无 |
| **A-MEM / Mem0 / MemoryBank** | 结构化记忆管线 | extract→index→retrieve | 语义层飞轮 | 有 learn/forget/pin；**无**自动 consolidate |
| **LoCoMo / LongMemEval** | 长对话记忆 QA | Hit / judge / abstain | 评测飞轮效果 | 可迁探针；未产品化套件 |

**飞轮判据（建议）**：写入量↑ ∧ 矛盾 supersede 正确 ∧ 召回 Hit@K↑ ∧ 下游任务错误率↓。缺任一环则「未达自进化」。

### 2.7 C：规划 / 推理 / skill（对照）

| 基准/能力 | 说明 | 本仓落点 |
| --- | --- | --- |
| PlanBench | PDDL 可验证计划 | 不测 Blocksworld；借 LifeGoal 步骤可验证 |
| LightFlow / LightDAG / ToT | 库内有 | **日用默认关** ToT；不用 Flow/DAG |
| browser-use skill | 多轮烧额度警告 | 可选 skill；测评默认不强制 |

### 2.8 D：Multi-Agent 编排

| 框架 | 特征 | 相对本仓 Hosted Room |
| --- | --- | --- |
| **AutoGen / AG2** | 对话式多 Agent、可事件驱动 | Room **禁止**子互啄；无选择器 LLM |
| **CrewAI** | 角色工作流 | 本仓仅 `fitness_diet` 关键词模板 |
| **OpenAI Swarm → Agents SDK** | 轻量 handoff | 有 `delegate_to_bot`；**非**递归 Swarm 日用主路径 |
| **ChatDev / MetaGPT** | 软件团队模拟、SOP 拆解 | 无宏观→原子递归编排器 |
| 本仓 **LightSwarm** | 库内存在 | Hosted Room **不跑** `LightSwarm.run`；单层 `run_delegation` |

**JD「高扩展 Agent Swarm/Team + 递归拆原子」**：外部框架能力 ⊃ 本仓日用；本仓刻意安全 MVP ≠ JD 完整条。

### 2.9 E：Long-horizon + 生产力 benchmark

| 基准 | 链接 | 测什么 | 对本仓 |
| --- | --- | --- | --- |
| **BrowserGym / WebArena** | 真实网页工作流 | 成功率 | 对照；默认 API mock |
| **THE AGENT COMPANY** | the-agent-company.com · arXiv:2412.14161 | 175 职场任务；同事交互；长程 checkpoint | **生产力尺子标杆**；本仓无对等台架 |
| **SWE-bench** | 仅对照 | 编码 Agent | 非生活助手主分 |
| **AssistantBench** | assistantbench.github.io · arXiv:2407.15711 | 214 现实耗时网页任务；SOTA ~25% | 生活助手「办事」上限参照 |
| **WorkArena** | 企业知识工作 | 企业 UI | 未接 |
| **OfficeBench** | 跨 Office 应用 | 办公流 | 未接 |
| 本仓 **4day 剧本** | `long_horizon_4day_*` | 忌口/例程/goal/resume | **局部** long-horizon；非职场生产力 |

### 2.10 X 实践（抽样，非学术分）

工程共识与既有调研一致：评测须覆盖 **tool 轨迹 + 状态 + 失败模式 + 成本**；多轮 fixture 要跟状态转移与 memory decay；单调 tool accuracy ≠ 有状态多步成功（参见既有 survey 中 MaryamMiradi / Memoraxis / sudheerdotai 等）。本轮 X 检索另见时效帖（本地模型长程、benchmark≠现实安全），不改变上表协议。

---

## 3. 本仓现状（能测 / 不能测 / 未实现）

| 标准 | 能测（已有或易加） | 不能测（缺裁判/环境） | 未实现（产品能力） |
| --- | --- | --- | --- |
| A1 事实错误 | 工具 must + 忌口卡；海鲜回复 heuristic | FACTS/FreshQA 级 multi-judge；Search grounded 全自动 | 无 grounding 过滤器 |
| A2 信息遗漏 | 双工具 must；多 store 断言 | RAGAS context recall 自动化 | 无独立向量 RAG 评测索引 |
| A3 工具错误 | BFCL 风格 must/forbid（L2/L3/jd_bar） | 大规模 Live AST leaderboard | — |
| A4 指令遵循 | MultiChallenge 改写：忌口/拒调 | IFEval 541 程序指令全量 | — |
| A5 任务完成 | goal 步骤 advance；cancel/resume | GAIA/AppWorld 全环境 | 日用无 checkpoint 预算接线完整生产级 |
| B 飞轮 | pin/learn/forget/supersede；job **入队** | 巩固后下游 uplift A/B | `memory/jobs.run_due` **空 stub**；无 Reflexion |
| C 规划/工具/记忆 | detect/advance；TOOLS；Constraint+Profile | PlanBench；完整 RAGAS | 日用关 ToT/Flow/DAG |
| D Multi-Agent | `build_turn_plan` 规则；Host 三行；单层派发测试 | Swarm 递归拆解评测 | 无 AgentTeam 编排器；Host 非 LLM |
| E Long-horizon | 4day store；compact sanitize；例程门闩 | THE AGENT COMPANY / AssistantBench | 群 compact 未接保存；无跨 Agent 共享 KB；无持续进化框架；无生产力 E2E 台架 |

架构锚点（证据路径）：

- 意图/拆解：`local/goals/{detect,advance,store}.py` · `local/constraints/` · `local/routines/`
- 工具：`local/tui/tools.py` · `local/tools/web.py` · `local/memory/tools.py`
- 记忆：`local/memory/{pack,inject,store,jobs}.py`（jobs=stub）
- 多 Agent：`local/rooms/{plan,host_summary,runtime}.py`；库 `LightSwarm` 日用旁路
- 长链路：`local/harness/` · `local/compact/` · `local/checkpoints/`
- 既有评测：`local/eval/` L0/L2/L3；`harness_production_eval_zh.md` 总分 **接近未达生产级**

---

## 4. 差距（相对实习 JD）

| 优先级 | 差距 | 影响标准 |
| --- | --- | --- |
| **P0** | 无 FACTS/RAGAS 级事实与遗漏自动裁判；live 仅 heuristic | A1 A2 |
| **P0** | consolidate / 反思 / 技能沉淀未实现 → **无数据飞轮** | B E3 |
| **P0** | Hosted Room = 关键词单层；无递归宏观→原子；无共享 KB | D E2 |
| **P1** | 日用未接 Flow/DAG/ToT；规划靠 LifeGoal 浅层 | C1 D |
| **P1** | 无 AssistantBench/WorkArena/THE AGENT COMPANY 生产力台架 | E4 A5 |
| **P1** | 群侧 compact 未接保存；长协作易漂 | E1 |
| **P2** | pass^k、用户模拟器、假世界 DB schema 未产品化 | 全维可靠性 |
| **P2** | skill（browser-use）无安全默认评测子集 | C2 |

---

## 5. 建议测评集扩面（已落地 `jd_bar.yaml`）

| 包 | 条数目标 | 模式 | 覆盖 |
| --- | --- | --- | --- |
| L0/L3 store 回归 | 既有 | store | 意图/忌口/例程/goal/sanitize |
| L2/L3 live | 既有 | live_agent | 工具 AST + 忌口软约束 |
| **jd_bar** | ≥30 | store + live_agent | **A–E 标签**；能 store 不烧 token；必须轨迹的标 live |
| 下一阶段（未本轮跑） | +40 | live + rubric | MultiChallenge 30；RAGAS 探针；Room 语义选麦混淆集；4day×pass^3 |

判定原则不变：**终态可断言 > LLM-as-judge**；judge 仅用于开放复述与 FACTS 类题。

---

## 6. 参考条目计数

外部基准/套件（本表）：HELM、FACTS、FreshQA、RAGAS、RGB、CRUD-RAG、BFCL、τ-bench、ToolSandbox、API-Bank、IFEval、FollowBench、MultiChallenge、GAIA、AgentBench、AppWorld、AgentBoard、Voyager、Generative Agents、ExpeL、Reflexion、A-MEM、Mem0、MemoryBank、LoCoMo、LongMemEval、AutoGen/AG2、CrewAI、Swarm、ChatDev、MetaGPT、BrowserGym/WebArena、THE AGENT COMPANY、SWE-bench（对照）、AssistantBench、WorkArena、OfficeBench ≈ **40+**；加本仓资产与 X 实践。细节协议以正文为准。
