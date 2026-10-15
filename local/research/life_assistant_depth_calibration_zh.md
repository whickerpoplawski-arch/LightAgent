# 生活助手定位：各维开发优化深度校准

> 日期：2026-10-15（America/Martinique / AST）  
> 定位尺子：**全方位个人生活助手**（能放进日常生活长久使用）  
> 对标学习：OpenHuman / Grok Bot / OpenClaw / Mem0（生活助手向）；coding agent、实习 JD 生产力 Agent **仅作对照**  
> 前序：`jd_capability_bar_verdict_zh.md` · `jd_bar_prod_impl_gap_zh.md` · `jd_bar_community_eval_survey_zh.md` · `personal_life_assistant_memory_zh.md` · `life_assistant_long_horizon_deepdive_zh.md` · `harness_production_eval_zh.md` · `hosted_room_acceptance_zh.md`  
> 源码抽查（本轮只读）：`local/memory/jobs.py`（`run_due=[]` stub）、`local/rooms/plan.py`（关键词单层选麦）、`local/constraints/card.py`（ConstraintCard + supersede）、`local/goals/store.py`（LifeGoal）  
> **本文件不改生产飞轮 / 多智能体代码**；只校准「做多深」。

---

## 1. 尺子声明

| 尺子 | 问什么 | 本文件是否采用 |
| --- | --- | --- |
| **生活助手日用达标** | 跨天仍懂忌口/偏好；例程不骚扰；群聊少回声；可中断可改主意；省额度可长久用 | **是（主尺子）** |
| 实习 JD 级生产力 Agent | FACTS/RAGAS/GAIA、递归 Swarm、THE AGENT COMPANY / WorkArena 终局台架 | **否**——仅作「哪些可降级」对照 |

**关系**：JD 总评「不够格」（A/C 接近，B/D/E 未达）仍然成立，但那是**另一把尺子**。按生活助手定位重评时：

- 忌口 / 偏好 / 跨天记忆 / 例程 / 多身份日用协作 → **该深**  
- 职场生产力终局台架、递归 Swarm、FACTS 全榜 → **不当产品必达**（除非能改写成生活场景可测子集）  
- 「测评绿」仍只证明切片行为；深度校准看的是**用户体感目标态**，不是 `jd_bar_v2` 全绿。

---

## 2. 各维深度档

深度档四选一：

| 档 | 含义 |
| --- | --- |
| **必做到位** | 不做则「长久日用」立不住；P0/P1 产品债 |
| **做到够用即可** | 有体感收益，但到验收线就停，防过度工程 |
| **刻意不做或后置** | 对生活助手 ROI 低，或易烧额度/引混沌；明确砍掉或 P2+ |
| **只建评测不建产品** | 用生活向子集探针盯回归；不接外部大榜产线、不建企业 env |

### A. 质量缺陷（事实 / 遗漏 / 工具 / 遵指 / 完成）

| 项 | 内容 |
| --- | --- |
| **生活助手目标态** | 「别推海鲜、别漏忌口、该搜就搜、说不做就不做、把这周健身目标推完」——用户感觉靠谱，而不是论文分。 |
| **建议深度** | **做到够用即可**（日用事实/遗漏用启发式 + ConstraintCard；**不必**先上完整 RAGAS/FACTS 产线） |
| **具体要做什么（可验收）** | 1. ConstraintCard 主题覆盖与 supersede 保真（已有海鲜/乳糖等；扩常见过敏/忌口词表到日用够用集） 2. 回复侧忌口启发式回归（`reply_avoid_*` 类）常绿 3. 工具 must/forbid AST 对生活工具面（web_search/fetch、goal、约束写入）保绿 4. 否定遵指：「别记」「别搜」「别改忌口」探针 5. LifeGoal 推进/暂停/恢复终态可测（非 GAIA 多跳） 6. （评测）生活 20–30 题「 grounded 于卡/pack 」启发式裁判，**不**接 FACTS multi-judge |
| **做到什么程度就停** | **不要做成**：FACTS Grounding 全流水线、RAGAS 生产裁判、BFCL 全榜、τ 用户模拟、GAIA/AppWorld 终局。编码向 ToolBench 无关。 |
| **相对 JD** | **降级**：JD「接近→达标」靠外部裁判；生活助手 **持平于「切片够用」** 即可宣布日用质量过关。 |

### B. Context 飞轮 / 自进化

| 项 | 内容 |
| --- | --- |
| **生活助手目标态** | 用几周后少重复问偏好；改口忌口能合并不打架；后台偶尔「整理记忆」但不烧爆额度。 |
| **建议深度** | **必做到位**（consolidate 要有；但是 **Mem0 Dream 生活子集**，不是 Voyager 技能库） |
| **具体要做什么（可验收）** | 1. `run_due` 真正执行：近重复 **merge** + supersede 链可观测（忌口/learnings） 2. **门闩**：minHours / minSessions / minMemories（或等价）+ 文件锁，防风暴巩固 3. 可选日终/低频 **synthesis**（pattern 条，默认关或极低频；`:free` 友好） 4. pin / `[PINNED]` 跳过 consolidate（对齐 Mem0 plugin 精神） 5. UI 或 store 可审：巩固前后 diff / 队列状态 6. 压前 memory flush 与巩固分工清晰（compact ≠ 记忆） |
| **做到什么程度就停** | **不要做成**：Voyager 可执行技能库、ExpeL 跨任务经验池、Reflexion 每失败必反思环、Generative Agents 全量日终信念仿真。不要每轮 LLM consolidate。 |
| **相对 JD** | **对齐子集**：JD B「未达」里真正该补的是 consolidate；**不对齐**技能库级自进化叙事。 |

### C. 规划 · Tool-use · 记忆/RAG · Reasoning

| 项 | 内容 |
| --- | --- |
| **生活助手目标态** | 单聊里：目标不滥拆、工具不乱点、画像能注入、闲聊不把周计划推歪。 |
| **建议深度** | **做到够用即可**（日用单 Agent 主路径；深规划/向量 RAG **后置**） |
| **具体要做什么（可验收）** | 1. LifeGoal：拒滥拆 + 单 in_progress + cancel/resume（已有方向，保回归） 2. 默认 TOOLS 面稳定；browser skill 默认不进日用（额度） 3. Profile pack / ConstraintCard / pin 注入与 ephemeral 剥离保绿 4. 无关闲聊不推进 goal（C 类探针） 5. 1:1 compact：spill + 尾部裁剪 + 可选摘要关默认；压前 flush 接线 6. （可选 P1）Space/Project 隔离，防家/工作串味 |
| **做到什么程度就停** | **不要做成**：默认 ToT / LightFlow / LightDAG 进 TUI 主路径；PlanBench 级深规划；向量 RAGAS 主路径；把 coding agent「计划模式」整套搬来。库里有 Flow/DAG 可留作高级开关，**日用默认关**。 |
| **相对 JD** | **降级持平「接近」**：JD 要深规划+RAG 主路径；生活助手 **够用即可停**。 |

### D. Multi-Agent（Hosted Room）

| 项 | 内容 |
| --- | --- |
| **生活助手目标态** | 「健身+饮食」群：该说话的说、少回声、忌口进对的人、综合可读；不是开会式递归拆原子。 |
| **建议深度** | **做到够用即可**（**加强 Hosted Room**）；递归 Swarm / 通用 Multi-Agent **刻意不做或后置** |
| **具体要做什么（可验收）** | 1. 少回声：Host 综合去重引用、限制复述任务原文 2. 一键/内置模板扩 1–2 个日用场景（不止 `fitness_diet`），仍关键词/规则优先 3. `@` 与 `max_speakers` 行为保持可测 4. digest 继续剥离 ephemeral；**可选** Constraint/Goal/Pin **只读共享层**（按 space，禁止 transcript 互啄） 5. 敏感子串门闩保持（外发类回 1:1） 6. （评测）群侧少回声/忌口落点 UX 探针，不测 handoff 图 |
| **做到什么程度就停** | **不要做成**：Agents SDK 式 LLM handoff 默认开、LangGraph 递归子图、CrewAI 流水线画成群聊、ReDel 运行时生原子 Agent、`LightSwarm.run` 默认进房。宏观出差/报销无关键词 → host_only **可接受**（诚实边界）。 |
| **相对 JD** | **大幅降级**：JD「未达」要动态编排；生活助手 **Room 够用 > Swarm 达标**。 |

### E. Long-horizon · 共享 KB · 评测体系

| 项 | 内容 |
| --- | --- |
| **生活助手目标态** | 跨会话仍记得忌口与进行中目标；例程准时不刷屏；多 Bot 共享「用户硬事实」而不互啄全文。 |
| **建议深度** | **必做到位**（跨会话抗遗忘 + 用户级共享硬事实）；生产力 benchmark **刻意不做**；生活向评测 **只建评测不建产品台架** |
| **具体要做什么（可验收）** | 1. 多 store 并存：Constraint / Goal / Profile pin / Routine 不互相冲掉（已有切片，保绿） 2. cancel→resume 同 goal_id；跨「天」（harness 时钟）忌口仍在 3. 用户级只读共享：忌口/pin 对 `share_user_profile` 成员可见；digest ≠ 共享 KB 4. 例程门闩：防骚扰（静默时段 / 预算 / 去重）对齐 Grok Bot·OpenHuman 精神 5. 4 日长链路剧本 + harness 离线/限量 live 常绿 6. （评测）LoCoMo/LongMemEval **生活改写子集**（多忌口、改口、跨会话问答）10–30 题；**不**接 THE AGENT COMPANY / WorkArena Docker |
| **做到什么程度就停** | **不要做成**：WorkArena / AssistantBench / THE AGENT COMPANY 企业 env；组织级 Graphiti 全图当必达；为刷 LongMemEval 全榜而改产品形态。共享 KB 先做 **scoped 硬事实只读层**，不做通用企业知识中台。 |
| **相对 JD** | **拆开**：抗遗忘+共享硬事实 **对齐生活子集**；生产力台架 **刻意降级为不做**。 |

---

## 3. 深度一览表

| 维 | 生活助手深度档 | 一句话 | 相对 JD |
| --- | --- | --- | --- |
| **A 质量** | 做到够用即可 | 卡+启发式+工具 AST；不上 FACTS/RAGAS 产线 | 降级 |
| **B 飞轮** | **必做到位** | consolidate=merge/supersede(+门闩)；非 Voyager | 对齐子集 |
| **C 规划记忆** | 做到够用即可 | 单 Agent 日用主路径；Flow/DAG/ToT 默认关 | 降级持平接近 |
| **D 多智能体** | 够用 Room / **刻意不做 Swarm** | Hosted Room 加强；递归编排后置 | 大幅降级 |
| **E 长程评测** | **必做到位**（抗遗忘+共享硬事实）；台架 **不做**；生活子集 **只建评测** | 4day/LoCoMo 子集；不接 WorkArena | 拆开：子集对齐 / 台架不做 |

---

## 4. 优先级排序（生活助手 ROI，非 JD 缺口照抄）

### P0（日用立不住就先做）

1. **B 飞轮 consolidate 最小闭环**：`run_due` 执行 merge + supersede 可观测 + 门闩；pin 跳过；可选低频 synthesis。  
2. **E 跨会话抗遗忘 + 硬事实只读共享**：忌口/pin/goal 跨会话与 Room 成员可见边界清晰；例程防骚扰门闩复核。  
3. **D Hosted Room 日用体验**：少回声 Host 综合 + 1–2 个模板场景；**不做** handoff/Swarm。

### P1（体感明显、风险可控）

1. **A 生活向质量探针集**：20–30 题卡 grounded + 否定遵指 + 多约束；仍启发式。  
2. **C 压前 flush + 1:1 compact 接线完备**；Space 隔离防串味。  
3. **E 4 日 harness / LoCoMo 生活子集** 常驻 CI（离线为主，live 限量）。

### P2（后置或只评测）

1. 可选受限 LLM Host / 语义选麦（默认关）。  
2. 向量检索式 recall（Zep/Mem0 风格）作增强，非替换 ConstraintCard。  
3. FACTS/RAGAS/BFCL/GAIA/WorkArena/THE AGENT COMPANY：**只作外部对照笔记**，不建产品必达；若做评测仅生活改写题。

---

## 5. 校准原则（写入约束）

1. **该深**：忌口/偏好/跨天记忆/例程/多身份协作日用场景。  
2. **不当产品必达**：THE AGENT COMPANY / WorkArena、递归 Swarm、FACTS 全榜——除非转化为生活场景可测子集。  
3. **B**：需要 consolidate（忌口合并、偏好蒸馏），不必 Voyager 技能库级。  
4. **D**：Hosted Room 加强优先于通用递归 Multi-Agent。  
5. **E**：跨会话抗遗忘 + 用户级共享记忆优先于生产力 benchmark；可建生活向 4day/LoCoMo 子集评测。  
6. **A**：日用事实/遗漏用启发式 + 约束卡即可；不必先上完整 RAGAS 产线。

---

## 6. 一句话总判

按**生活助手**定位：应深挖的是 **B 巩固飞轮（生活子集）**、**E 跨会话抗遗忘 + 硬事实共享**、以及 **D 的 Hosted Room 体验**；A/C 维持「够用」切片即可。  
JD 式 **递归 Swarm、WorkArena/THE AGENT COMPANY、FACTS 全榜** —— **可以不做**（最多改写成生活向评测子集，不当产品终局）。

---

## 7. 现状锚点（实事求是，便于对照「做多深」）

| 组件 | 现状一句话 |
| --- | --- |
| ConstraintCard | 主题词表 + 原地 supersede；注入只见 active |
| LifeGoal | workspace JSON；单 in_progress；可暂停恢复 |
| Memory jobs | `enqueue` 有；`run_due` **故意 return []** |
| Hosted Room | `@` → `fitness_diet` 关键词 → host_only；单层；无 Swarm |
| 评测 | L0/L3/jd_bar_v2 切片绿；外部大榜未跑；4 日 harness 有剧本 |

**本校准不要求本轮改上述生产行为**；改深度目标与优先级，供后续排期。
