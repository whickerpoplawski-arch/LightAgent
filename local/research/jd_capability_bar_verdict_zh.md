# 实习 JD 能力尺子：总评结论（社区扩搜 + jd_bar_v2 再测）

> 日期：2026-10-15（America/Martinique / AST）  
> 模型/供应商：**MX** `deepseek-v4.1-flash` + `effort=medium`（`https://mxzzz.xyz/v1`，`MX_API_KEY`）  
> 证据：`local/eval/reports/l0_store_*` · `jd_bar_v2_live_*` · 调研 `jd_bar_community_eval_survey_zh.md` · `jd_bar_prod_impl_gap_zh.md` · `jd_capability_bar_survey_zh.md`  
> 尺子：**实习 JD 级生产力 Agent**（非「生活助手 MVP 够用」）

---

## 0. 一句话总评

**以实习 JD 级生产力 Agent 为尺子：本生活助手二开当前仍不够格。**  
`jd_bar_v2` 自建切片 **52/52 PASS**（含飞轮 stub、单层 Room≠递归 Swarm 等**否定性探针**）；社区调研确认生产级缺口仍在 **B 巩固飞轮、D 动态多智能体、E 共享 KB + 生产力台架**。  
**测评绿 ≠ JD 达标**；外部大榜（BFCL/GAIA/AssistantBench/WorkArena/LoCoMo/LongMemEval/THE AGENT COMPANY）**本轮未整榜跑**。

---

## 1. 跑次汇总

| 跑次 | 命令要点 | PASS | PARTIAL | FAIL | ERROR | 报告 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| L0 store（jd_bar_v2） | `l0_store --file jd_bar_v2` | **39** | 0 | 0 | 0 | `local/eval/reports/l0_store_latest.md`（以该次为准时重跑） |
| L0 store（all yaml，含 v1∪v2 重叠） | `l0_store --tier all` | **86**（unique id≈60） | 0 | 0 | 0 | 同上；**勿把 86 当成不重叠条数** |
| jd_bar_v2 全量 live | `l2_live_tools --file jd_bar_v2 --tier all`（MX medium） | **52** | 0 | 0 | 0 | `local/eval/reports/jd_bar_v2_live_latest.md` |
| 对照：jd_bar v1（早前 ScienceEdu） | `--file jd_bar` | 34 | 0 | 0 | 0 | `jd_bar_live_latest.md`（旧供应商） |

`jd_bar_v2.yaml`：**52** 条（A13 / B8 / C11 / D10 / E10）；相对 v1 **+18**。  
store 39 + live_agent 13。新增覆盖：多约束/否定遵指、飞轮「应巩固未巩固」、单层 Swarm 边界、digest 卫生、三 store 并存。

供应商注意：默认 **MX**；`openrouter_config` 在 `PROVIDER=mx` 时 **只用 `MX_BASE_URL`**，并优先 `MX_API_KEY`，避免残留 ScienceEdu `LIGHTAGENT_BASE_URL` / key 串台。

---

## 2. 标准逐条判定（扩搜后未改档）

判定档：`达标` / `接近` / `未达`。  
PASS 只证明「该切片可测且当前行为符合断言」。

### A. 质量缺陷类 — **接近**

| 子项 | 判定 | 证据 |
| --- | --- | --- |
| 事实错误 | **接近** | `JD-A07/A10` 忌口 heuristic PASS；**无** FACTS Grounding multi-judge |
| 信息遗漏 | **接近** | `JD-A05` 双工具、`JD-A09` 多约束 PASS；**无** RAGAS context-recall |
| 工具调用 | **接近→局部达标** | A03/A06/A11/A13、C10 等 AST PASS；未跑 BFCL 全榜 / τ pass^k |
| 指令未遵循 | **接近** | 否定探针 A04/A11、改口保乳糖 A12 PASS；非 IFEval/FollowBench 全量 |
| 任务未完成 | **接近** | 多工具集合 PASS；无 GAIA/AppWorld/THE AGENT COMPANY 终局 |

### B. Context 飞轮 / 自进化 — **未达**

| 判定 | **未达** |
| --- | --- |
| 证据 | `JD-B03/B07/B08` **刻意断言** `run_due=[]`（`local/memory/jobs.py` stub）。对照 Mem0 Dream（Supersede/Merge/Synthesis）、Letta 分层、Zep 时序边、Voyager 技能库：**有写入无可观测巩固进化**。 |

### C. 规划 / Tool-use / 记忆 / Reasoning — **接近**

| 子项 | 判定 | 证据 |
| --- | --- | --- |
| 规划 | **接近** | 拒滥拆 C04/C09、推进 C02/C11 PASS；日用关 ToT/Flow/DAG |
| Tool-use | **接近→局部达标** | live 工具切片绿；browser skill 未进默认集 |
| 记忆+RAG | **接近** | pin/卡/sanitize PASS；无向量 RAGAS |
| Reasoning | **接近** | 无关插入不推进 C03；无 PlanBench/GAIA 多跳 |
| skill | **未达/未测** | 默认 TOOLS 面 |

### D. Multi-Agent — **未达**

| 判定 | **未达** |
| --- | --- |
| 证据 | `JD-D07/D10`：复杂宏观无关键词 → `fallback_host_only`；`no_recursive_swarm` PASS。对照 Agents SDK handoff、LangGraph、CrewAI、ReDel：**Hosted Room = 关键词单层选麦，非递归拆原子**。 |

### E. Long-horizon / 共享 KB / 生产力 — **未达**

| 子项 | 判定 | 证据 |
| --- | --- | --- |
| 多级存储 | **接近** | E06/E07 多 store PASS |
| 抗遗忘 | **接近** | E01/E08 cancel→resume；无 LoCoMo/LongMemEval 全套 |
| 跨 Agent 共享 KB | **未达** | digest 短窗剥离 ephemeral（D09/E09）；非共享图/KB |
| 持续进化 | **未达** | 同 B stub |
| 评测体系 | **接近** | L0/L3/jd_bar_v2 + 社区对照表；缺 pass^k / 用户模拟 |
| 生产力 benchmark | **未达** | **未接** AssistantBench / WorkArena / THE AGENT COMPANY |

---

## 3. 总表

| 标准块 | 判定 | 一句 |
| --- | --- | --- |
| A 质量缺陷 | **接近** | 切片更严仍绿；缺 FACTS/RAGAS/GAIA 级 |
| B 飞轮/自进化 | **未达** | consolidate stub；社区 Dream/时序边未落地 |
| C 规划·工具·记忆 | **接近** | 日用单 Agent 可用；深规划/RAG 未接主路径 |
| D Multi-Agent | **未达** | 单层关键词 Room ≠ Swarm/递归拆解 |
| E Long-horizon+生产力 | **未达** | 局部 store/4day；无职场生产力台架 |

**总判：未达实习 JD 级生产力 Agent；作为生活助手 MVP / 稳达子集则「接近可用」。**

---

## 4. 未达维：社区怎么做 vs 我们（各≤3 条）

### B 飞轮
1. **Mem0 Dream**：写入路径 Supersede/Merge + 后台 Synthesis；本仓 `run_due` 空返回。  
2. **Letta/Zep**：分层自管或时序边作废；本仓仅卡级 supersede + pin，无巩固作业。  
3. **Voyager/ExpeL/Reflexion**：技能库/经验池/反思环；本仓无。

### D Multi-Agent
1. **Agents SDK**：handoff / agents-as-tools；本仓无 LLM 交接。  
2. **LangGraph/CrewAI**：图状态或角色任务队列；本仓静态关键词模板。  
3. **ReDel 等**：运行时递归子 Agent；本仓 TurnPlan 无 children（测评诚实断言）。

### E 长程 / 共享 / 生产力
1. **LoCoMo/LongMemEval**：跨会话召回与更新；本仓仅 cancel/resume 与多忌口切片。  
2. **共享 KB**：Mem0 user 作用域 / Graphiti 图；本仓短 digest 防泄漏也无深度共享。  
3. **THE AGENT COMPANY / WorkArena / AssistantBench**：可复现终局+checkpoint；本仓未接。

---

## 5. P0（基于生产对照，本轮未改生产代码）

1. 实现 consolidate（merge + supersede 链 + 可选 synthesis；门闩防风暴）。  
2. 可选受限 handoff / 任务图（日用默认关）。  
3. Constraint/Goal/Pin **只读共享层**。  
4. FACTS 风格 grounded + RAGAS 生活探针。  
5. 生产力：自建办事 mock 终态或接 THE AGENT COMPANY 子集协议。

---

## 6. 绿切片与 JD 的关系

| 现象 | 含义 |
| --- | --- |
| jd_bar_v2 52/52 PASS | 实现符合**我们写下的断言**（含 stub / 无递归 Swarm） |
| JD 仍未达 | 断言覆盖可测切片，不是 JD 全文；否定性 PASS = 诚实暴露缺口 |
| 外部榜未跑 | 见 `jd_bar_community_eval_survey_zh.md` 对照表；勿把本仓绿当成 BFCL/GAIA/WorkArena 分 |

---

## 7. 文件索引

- 社区测评集扩搜：`local/research/jd_bar_community_eval_survey_zh.md`  
- 生产级缺口对照：`local/research/jd_bar_prod_impl_gap_zh.md`  
- 用例：`local/eval/cases/jd_bar_v2.yaml`（52）  
- 报告：`local/eval/reports/jd_bar_v2_live_latest.md` · `l0_store_latest.md`  
- Runner：`local/eval/runners/{common,l0_store,l2_live_tools}.py`（默认 MX）
