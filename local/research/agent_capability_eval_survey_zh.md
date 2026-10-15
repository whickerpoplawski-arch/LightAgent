# LightAgent 能力测评集前期调研（意图 / 拆解 / 选工具 / 多轮上下文）

> 日期：2026-10-15（America/Martinique / AST）  
> 定位：个人生活助手 LightAgent 二开；**非** coding agent 全量复刻。  
> 范围：只读调研（Web / GitHub / X + 本仓库 `local/research` · `local/harness` · 工具挂载入口）；**未改业务代码**。  
> 产出用途：后续设计最小测评集的协议/指标依据，不是最终用例清单。

---

## 0. 结论摘要

1. **生活助手四维**与公开基准的可迁移核是「协议 + 判定器」，不是整套领域场景：  
   - 意图识别 ← 拒调/无关（BFCL irrelevance）、策略遵循（τ-bench）、短问不建目标（本仓 `should_create_goal`）  
   - 任务拆解 ← 多步最小可行路径（BFCL multi-turn subset）、goal/todo 分栏（OH / 本仓 LifeGoal）  
   - 工具选择 ← AST/参数匹配（BFCL）、Pass Rate（ToolBench）、状态终局（τ-bench / AppWorld）  
   - 多轮上下文 ← MultiChallenge 四类 + LoCoMo/LongMemEval 跨会话记忆 + 本仓 Constraint/compact 不变量  
2. **本仓已有 harness**强在：离线结构不变量（M0–M7、忌口卡、cancel/resume、pack 不进 transcript）；弱在：模型级意图/选工具轨迹、live 多轮判据、pass^k 稳定性、mock 工具状态机。  
3. **最小测评集**建议双轨：`mock`（可复现、CI、`LIGHTAGENT_FORBID_OPENROUTER=1`）+ `live`（真 API、额度闸、人工/LLM-rubric 抽检）；先覆盖本地工具面（`web_search`/`web_fetch`/`memory_*`/`compact`/`hosted room`），不照搬 WebArena DOM。

**最关键的 5 个基准（生活助手向）**

| 排名 | 基准 | 为何最相关 |
| --- | --- | --- |
| 1 | **τ-bench（含 τ²/τ³）** | 用户模拟 + 策略 + 工具 + **终局状态** + **pass^k**；最接近「对话式生活助手可靠性」 |
| 2 | **BFCL V3/V4** | 工具选择 AST、多轮状态/子集路径、irrelevance、V4 memory/web_search；可直接映射本仓 tool schema |
| 3 | **MultiChallenge** | 指令保持 / 散落用户信息 / 版本编辑 / 自洽；与忌口、改口、计划迭代几乎同构 |
| 4 | **LoCoMo / LongMemEval** | 跨会话记忆 QA；对齐 learn/forget、pin、compact 后召回 |
| 5 | **AppWorld（对照）** | 多 App API + 单元测试终局；可借「状态断言」协议，场景需改写成日历/饮食/提醒假世界 |

---

## 1. 参考基准表

协议说明：每条写清「测什么 / 评分方式 / 对四维的可迁移点」。链接以官方仓库或论文页为准。

### 1.1 Tool-use / Function-calling

| 名字 | 链接 | 测什么 | 评分方式 | 生活助手四维可迁移点 |
| --- | --- | --- | --- | --- |
| **BFCL V1–V4**（Berkeley Function Calling Leaderboard / Gorilla） | https://gorilla.cs.berkeley.edu/leaderboard.html · https://github.com/ShishirPatil/gorilla · V3 多轮博客 https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html · V4 Web Search https://gorilla.cs.berkeley.edu/blogs/15_bfcl_v4_web_search.html | 单轮 simple/parallel/multiple；Live/Non-Live；**Irrelevance**；多轮多步；V4 **agentic**（memory backend、web search、format sensitivity） | **AST** 匹配函数名+参数；多轮：**state-based**（写删后后端状态）+ **response-based subset**（最小可行调用集合 ⊆ 模型轨迹）；web 类 exact-match 归一化 `answer` 字段；总分加权（V4 约 Agentic 40% / Multi-Turn 30% / Live·Non-Live·Irrelevance 各 10%） | **工具选择**：schema 对齐 `tool_info`；**意图**：irrelevance=不该调工具时拒调；**拆解**：parallel / multi-step；**多轮**：state+subset 协议可套在假日历/忌口 store 上 |
| **API-Bank** | https://arxiv.org/abs/2304.08244 · EMNLP 2023 | Call / Retrieve+Call / Plan+Retrieve+Call；多轮多调用；API 调用与自然语言回复 | 调用 **Correctness** + 回复 **ROUGE-L**；分能力分层报分 | **拆解+选工具**：Plan→Retrieve→Call 三层与「先搜再 fetch」一致；勿只抄 ROUGE 当生活助手主指标 |
| **ToolBench / ToolEval（ToolLLM）** | https://github.com/OpenBMB/ToolBench · https://arxiv.org/abs/2307.16789 · Leaderboard https://openbmb.github.io/ToolBench/ | 大规模真实 API 指令；多工具检索与链式调用 | **Pass Rate**（预算内完成指令比例）；**Win Rate**（ChatGPT 对两条轨迹偏好，相对 ReACT 基线） | **工具选择**主指标可借 Pass Rate；Win Rate 仅作辅，生活助手应用 **状态断言** 替代纯 LLM 偏好 |
| **τ-bench / τ²-bench / τ³-bench**（Sierra） | https://arxiv.org/abs/2406.12045 · τ² https://arxiv.org/abs/2506.07982 · 代码 https://github.com/sierra-research/tau2-bench · 博客 https://sierra.ai/blog/bench-advancing-agent-benchmarking-to-knowledge-and-voice | 用户模拟器 + 领域 API + **策略文档**；airline/retail/telecom；τ² 双控（用户也动工具）；τ³ 知识库检索 + voice | 对话结束 **DB 状态 vs 标注目标状态**；**pass^k**（k 次独立试验全过）；可拆 reasoning vs communication 消融 | **四维一体**：意图（问清/遵策）、拆解（多步交易）、选工具（API）、多轮（用户随机表述）。本仓应优先学 **终局状态 + pass^k**，场景改成忌口/例程/目标，而非航空零售原文 |
| **AgentBench** | https://github.com/THUDM/AgentBench · https://arxiv.org/html/2308.03688 | 8 类环境（OS、DB、KG、家居、网页等）里的 agent 交互 | 环境相关 success / F1 / reward；再加权成 Overall | **对照**：环境多样性；生活助手只借「环境成功定义」写法，不做 OS/家居全套 |
| **ToolSandbox / MetaTool 等**（对照） | 文献常与 BFCL 并列 | 交互式工具状态、工具选择歧义 | 版本相关的轨迹/状态检查 | 提醒：单调准确率 ≠ 多步有状态准确率（X 实践帖亦强调） |

### 1.2 多轮 / 长上下文 / 记忆

| 名字 | 链接 | 测什么 | 评分方式 | 可迁移点 |
| --- | --- | --- | --- | --- |
| **MultiChallenge**（Scale） | https://arxiv.org/abs/2501.17399 · https://github.com/ekwinox117/multi-challenge · Leaderboard https://labs.scale.com/leaderboard/multichallenge | ≤10 轮；四类：**指令保持、散落用户信息推理记忆、可靠版本编辑、自洽（反谄媚）** | 人工 + **instance-level 二元 rubric** 的 LLM-as-judge（与人对齐 ~94%）；报告类别准确率 | **直接映射生活助手**：忌口贯穿=Instruction Retention；过敏散落=Inference Memory；计划改口=Versioned Editing；前后矛盾建议=Self-Coherence。建议本测评集每用例挂一条 yes/no rubric |
| **MT-Bench** | https://arxiv.org/abs/2306.05685（Judging LLM-as-a-judge…） | 8 主题双轮对话 | GPT-4 打分 1–10 | **已饱和**；只作回归烟雾，不作区分度主集 |
| **MT-Bench-101** | https://github.com/mtbench101/mt-bench-101 · ACL 2024 | 13 任务、细粒度多轮能力 taxonomy（~1388 对话 / 4208 turns） | 任务/能力维细粒度分 | 可借 taxonomy 命名本仓「澄清 / 纠正 / 追问」子技能 |
| **LongBench / LongBench v2** | https://github.com/THUDM/LongBench · https://arxiv.org/html/2308.14508 · v2 https://arxiv.org/html/2412.15204 | 双语长上下文多任务（QA/摘要/代码等） | 任务相关 F1/EM/ROUGE/Acc；超窗截断头尾 | 测 **窗口极限**；生活助手更关心「压缩后关键事实是否仍在」，应叠本仓 ConstraintCard 断言 |
| **LoCoMo** | https://aclanthology.org/2024.acl-long.747 · 数据/评测社区实现如 https://github.com/lancedb/locomo-eval | 极长多会话对话（约 600 turns / 16K tokens / ≤32 sessions）；QA、事件摘要、多模态生成 | QA 准确、摘要质量、生成指标；对比 long-context vs RAG | **跨天记忆**：对齐 Memory pin / learn / compact 后 recall；会话切分可对应本仓 conversation space |
| **LongMemEval / V2** | https://github.com/xiaowu0162/LongMemEval | 长程 agent 记忆问答（含 abstain / gotcha） | 结构化答案归一化匹配；自由答 LLM judge 0/1；延迟；leaderboard LAFS | **记忆正确性 + 该拒则拒**；可测 `memory_forget` / superseded 后不再召回 |
| **MemoryBank** | https://arxiv.org/abs/2305.10250 | 15 虚拟用户 × 10 天史；194 探针问（中英） | 检索准确、回答正确、上下文连贯、相对排名分 | 探针题库形态可借；实现上本仓已有 Profile/Learnings，不必搬其存储 |
| **Mem0 memory-benchmarks** | https://github.com/mem0ai/memory-benchmarks | 记忆增强 LLM 开源评测套件 | 仓库级 suite（星数低，作编排参考） | 编排思路；指标仍应以 LoCoMo/LongMemEval 为准 |
| **OpenClaw memory-bench** | https://github.com/phenomenoner/openclaw-memory-bench | OpenClaw 记忆插件对比 | Hit@K / Recall@K / MRR / nDCG / 延迟；可选 E2E judge | **检索层指标**可测 pack/recall；与对话终局指标分栏 |
| **OmniMemEval** | https://github.com/MemTensor/OmniMemEval | 多后端用户记忆 + AgentBench 式 agent 记忆 | 多数据集统一 harness | 若未来换记忆后端，作对照台架 |

### 1.3 意图 / 规划（对照，生活助手改写后用）

| 名字 | 链接 | 测什么 | 评分方式 | 可迁移点（勿整套搬） |
| --- | --- | --- | --- | --- |
| **PlanBench** | https://arxiv.org/abs/2206.10498 · NeurIPS 2023 | PDDL 域计划生成/最优/验证；区分「检索常识」vs「真规划」 | Fast-Downward 金标准；**VAL** 验证；Success / Validity / Optimality | 借「可验证计划」思想 → LifeGoal 步骤序列 + 约束可满足；不测 Blocksworld |
| **GAIA** | https://arxiv.org/abs/2311.12983 · HF `gaia-benchmark/GAIA` | 需工具的助手题；L1–L3 难度 | 准 exact-match 终答（数字/列表/字符串归一化） | 对照「搜+算+答」；生活助手加 **过程约束**（忌口、勿骚扰），不能只看终答 |
| **AgentBoard** | NeurIPS 2024 D&B · PDF https://proceedings.neurips.cc/paper_files/paper/2024/file/877b40688e330a0e2a3fc24084208dfa-Paper-Datasets_and_Benchmarks_Track.pdf | 多轮、部分可观测；细粒度 **progress rate** | 逐步进度 + 子技能分析 | **进度条协议**可对齐 LifeGoal step；替代「只看最后成功」 |
| **AppWorld** | https://github.com/StonyBrookNLP/appworld · https://arxiv.org/abs/2407.18901 | 可控多 App + 人；交互式 coding/agent | 起终 DB 差 + **单元测试**（必改 + 无附带伤害）；TGC / SGC | **状态断言模板**黄金参考；场景改成假「日历/购物/健康笔记」API |
| **WebArena** | https://arxiv.org/abs/2307.13854 | 真实网站工作流 | URL/内容/状态任务相关检查；成功率 | 仅对照浏览器 skill；默认生活助手路径以 API mock 为主，控额度 |

### 1.4 生活助手向产品 / 社区实践

| 名字 | 链接 | 测什么 / 讨论什么 | 评分或主张 | 可迁移点 |
| --- | --- | --- | --- | --- |
| **OpenHuman + TinyMemory**（本仓已深挖） | 源码 `/workspace/openhuman` · 笔记 `local/research/openhuman_memory_source_notes_zh.md` · `life_assistant_long_horizon_deepdive_zh.md` | Pack 永不进 transcript；goal⊥todo⊥learnings；通知阈值；compaction recall | 不变量 / 验收清单（非公开 leaderboard） | **测评不变量**：sanitize transcript、fail-open pack、拒绝 notice≠空记忆、forget/supersede |
| **OpenClaw** | https://docs.openclaw.ai/concepts/memory · compaction / active-memory | memoryFlush、Dreaming、USER.md | 产品概念 + 社区 memory-bench | 压前 flush；跨会话 USER 事实 |
| **Mem0** | https://docs.mem0.ai · arXiv:2504.19413 · memory-benchmarks | user_id 记忆层；增式写入陷阱 | 官方 docs + 社区评测 | 显式 learn/forget；防重复矛盾条 |
| **ChatGPT Memory / Tasks** | OpenAI Help（产品观察） | Memory ⊥ Scheduled tasks | 产品行为观察 | 三栏分家：耐久记忆 / 任务 / 例程——已写入本仓 minset |
| **X 实践帖（抽样）** | MaryamMiradi https://x.com/MaryamMiradi/status/2107913943335272521（agent eval 要覆盖 tool/retrieval/路径/失败/成本）· Memoraxis https://x.com/Memoraxis/status/2108917794612122044（多轮 fixture 要跟状态转移与 memory decay）· sudheerdotai https://x.com/sudheerdotai/status/2108050618552320261（单调 tool accuracy ≠ 多步有状态）· YunTechX https://x.com/YunTechX/status/2108605206317658367（加载态/回执是产品层信号）· CaleraLabs https://x.com/CaleraLabs/status/2104259851375542372（向量记忆生产矛盾/延迟）· Colourpixels https://x.com/Colourpixels/status/2106636574423503176（OpenClaw 前后对照评测） | 工程向可靠性叙事 | 非学术分数 | 测评集应记 **轨迹+状态+成本+重复试验**；UI 回执可作为观测项而非主成功条件 |

### 1.5 本仓库已有「准测评」资产（非外部基准）

| 资产 | 路径 | 已覆盖 | 缺口相对四维 |
| --- | --- | --- | --- |
| 生产级 harness 评估 | `local/research/harness_production_eval_zh.md` | A–H 分项 PARTIAL；库能力 vs 日用接线 | 几乎无模型意图/选工具轨迹分 |
| 长链路深挖 / minset | `life_assistant_long_horizon_deepdive_zh.md` · `long_horizon_harness_minset_zh.md` | M0–M7 不变量 | 缺可复现「模型行为」评分表 |
| 4 日对话剧本 | `long_horizon_4day_dialogue_script_zh.md` | 目标创建负例、忌口、例程、cancel/resume、Host | 多为库 API 探针，非完整 agent loop |
| 离线 E2E | `local/harness/tests/test_e2e_long_horizon_offline.py` | MockBackend 结构路径 | 无真实 tool-call AST |
| Usability / live UX | `long_horizon_*_usability_eval_zh.md` · `*_live_ux_eval_zh.md` | 人工/探针体验 | 样本少、无 pass^k |

**参考条数统计（本表计入）**：外部基准/套件 **22**（BFCL、API-Bank、ToolBench、τ/τ²/τ³、AgentBench、MultiChallenge、MT-Bench、MT-Bench-101、LongBench、LoCoMo、LongMemEval、MemoryBank、Mem0-benchmarks、OpenClaw-memory-bench、OmniMemEval、PlanBench、GAIA、AgentBoard、AppWorld、WebArena）+ 生活助手产品/深挖 **4**（OpenHuman、OpenClaw docs、Mem0、ChatGPT Memory）+ X 实践 **6** + 本仓资产 **5** ≈ **37** 条可追溯参考。正文表格以协议深度为准，不追求堆名。

---

## 2. 生活助手四维映射

本仓日用工具面（入口）：

- 联网：`local/tools/web.py` → `web_search` / `web_fetch`（SSRF 校验）；挂载 `local/tui/tools.py` → `TOOLS`
- 记忆：`local/memory/tools.py` → `memory_learn` / `memory_forget` / recall / pin / edit；Host 盖章 scope
- 压缩：`local/compact/*`（`kernel_hook.compact_model_messages`、`flush`、`/compact`）
- 群：`local/rooms/*`（`plan.build_turn_plan`、`digest`、`host_summary`）
- 长链路：`local/harness/`（ephemeral、run_control）+ `goals` / `constraints` / `checkpoints` / `routines`

| 四维 | 操作化定义（本仓） | 外部协议来源 | 主判定器（建议） | 负例 / 陷阱 |
| --- | --- | --- | --- | --- |
| **意图识别** | 短问答 vs 建 LifeGoal；闲聊 vs 忌口写入；该搜 vs 该记 vs 该拒调；群选麦 | BFCL irrelevance；τ 策略澄清；本仓 `should_create_goal` / `classify_utterance` / `parse_routine` | 标签准确率 + 误触发率；工具「零调用」断言 | 「今天吃什么」建目标；「提醒我一下」无 cadence 却建 routine；过敏未提却乱记 |
| **任务拆解** | 多步目标步骤顺序；先 search 再 fetch；goal 步骤至多一个 in_progress | BFCL multi-step subset；API-Bank Plan 层；AgentBoard progress；OH goal⊥todo | 步骤序列 ⊆ 金标；progress rate；中断后续跑同 goal_id | 并行乱序写忌口；重复新建 goal；把偏好写进 todo 当唯一真相 |
| **工具选择** | 在 `TOOLS` 内选对函数+参数；不造未注册工具；memory 不写错 scope | BFCL AST；ToolBench Pass Rate；τ / AppWorld 终局状态 | AST/JSON schema；终局 store 快照；非法 URL 被 web_fetch 拒绝 | 该 fetch 却只 search；learn 时伪造 user_id；浏览器 skill 无故狂烧额度 |
| **多轮上下文** | 散落忌口仍遵守；改口 supersede；compact 后约束仍在；跨「天」pin；群 Host 三行 | MultiChallenge 四类；LoCoMo/LongMemEval；OpenClaw flush；本仓 ConstraintCard | Rubric yes/no；active_texts；transcript 无 `<memory-context>`；跨会话 QA | 压缩丢忌口；谄媚推翻自己上轮建议；pack 污染落盘 |

**交叉矩阵（精简）**

|  | 意图 | 拆解 | 选工具 | 多轮 |
| --- | --- | --- | --- | --- |
| BFCL | irrelevance | multi-step | AST | multi-turn state |
| τ-bench | 遵策/追问 | 多 API | 正确写库 | 用户模拟多轮 |
| MultiChallenge | 首轮指令 | 版本迭代 | （弱） | 四类核心 |
| LoCoMo/LME | — | — | recall 工具 | 跨会话记忆 |
| 本仓 4day 剧本 | 建/不建 goal | 步骤推进 | （mock） | 忌口/例程/resume |

---

## 3. 对本仓库现有 harness / 脚本的缺口

对照 `harness_production_eval_zh.md`、`long_horizon_harness_*`、`local/harness/tests`、4day 剧本与 live UX 文：

| 缺口 ID | 描述 | 影响四维 | 建议补齐形态 |
| --- | --- | --- | --- |
| G1 | **无模型轨迹 AST 层**：现测多为 store/API（`maybe_open_goal`、`absorb`），很少断言「模型发出的 tool_call JSON」 | 选工具、意图 | mock LLM 回放金标 tool_calls；或 live 录制后 AST 比对 |
| G2 | **无 pass^k**：单次 mock 绿 ≠ 稳定；τ-bench 核心启示未落地 | 全维可靠性 | 同用例 k=3/5，报 pass^1 与 pass^k |
| G3 | **无用户模拟器**：4day 是固定剧本，非 τ 式策略用户 | 意图、多轮 | 轻量脚本用户（规则机）+ 可选 LLM 用户（live） |
| G4 | **无终局「假世界」DB**：Constraint/Goal/Routine 有，但缺统一 EpisodeState schema 与金标 diff | 拆解、选工具 | 学 AppWorld/τ：`expected_state` JSON + 单测断言 |
| G5 | **1:1 忌口自动进卡仍弱**（usability：PARTIAL）：意图「记住忌口」链路不闭合 | 意图、多轮 | 测评显式分「卡写入成功」与「回复口头承认」 |
| G6 | **工具选择金标集缺失**：`web_search`/`web_fetch`/`memory_*` 无 BFCL 风格用例包 | 选工具 | 20–40 条 schema 用例（含 irrelevance、坏 URL、空 query） |
| G7 | **MultiChallenge 类对话未产品化**：无 instruction retention / version edit 固定集 | 多轮 | 用生活场景重写 30 条 + instance rubric |
| G8 | **记忆检索指标缺失**：无 Hit@K / 错误召回（已 forget 仍注入） | 多轮 | 对齐 OpenClaw-memory-bench / LongMemEval abstain |
| G9 | **群路径语义选麦未测**：`build_turn_plan` 偏关键词 | 意图、拆解 | 混淆集：@ / 健身饮食关键词 / Host 兜底 |
| G10 | **Live 与额度**：`:free` 日限 45；无「测评预算」门面 | 全维 live | `LIGHTAGENT_EVAL_*` 预算；默认 CI 只跑 mock |
| G11 | **成本/延迟未入库**：X 实践强调 tool 路径成本 | 观测 | 可选副指标，不进主成功条件 |
| G12 | **compact 后能力回归**：有 compact 单测，缺「压后仍通过 MultiChallenge 子集」 | 多轮 | compact 前后成对用例 |

已有强项（测评应保留为 **regression gate**）：M0 transcript 洁净、M4 cancel/budget、M5 supersede 语义、M7 确认才跑、Host 三行格式、离线 4day 结构剧本。

---

## 4. 建议的最小测评集骨架

### 4.1 设计原则

1. **双轨**：`mock`（CI 必绿）/ `live`（发版抽检）。  
2. **状态优先、自然语言为辅**：主成功 = EpisodeState 断言；回复质量用 rubric 二元题。  
3. **工具面真实、世界假**：真 `tool_info` schema；后端用 tmp workspace + stub search/fetch。  
4. **先 40–60 条核心，再扩**：覆盖四维 × 正负例；不追求 GAIA/WebArena 规模。  
5. **与 M0–M7 正交**：结构不变量继续用现有 pytest；本集专打「agent 决策」。

### 4.2 用例类型（建议目录）

```
eval/
  schemas/           # 工具 JSON schema 快照
  episodes/
    intent/          # I-*
    decompose/       # D-*
    tool_select/     # T-*
    multiturn/       # C-*（context）
  oracles/
    states/          # expected_state.json
    rubrics/         # yes/no 题
  runners/
    mock_episode.py
    live_episode.py
```

| 前缀 | 类型 | 例（生活助手） | mock | live | 主判定 |
| --- | --- | --- | --- | --- | --- |
| I1 | 短问不建目标 | 「今天吃什么」 | ✓ | 抽检 | `should_create_goal==False`；无 goal 文件 |
| I2 | 显式建目标 | 「帮我制定一周健身饮食计划」 | ✓ | ✓ | 恰 1 active goal；1 in_progress |
| I3 | 忌口意图 | 「忌口：海鲜」 | ✓ | ✓ | ConstraintCard active 含海鲜 |
| I4 | 拒调工具 | 「背诵一首静夜思」（无网无记） | ✓ | ✓ | tool_calls==[]（BFCL irrelevance 态） |
| I5 | 该搜 | 「下周本地马拉松报名截止？」 | stub | ✓ | 调用 `web_search` 且 query 含关键槽 |
| D1 | 搜→读链 | 「根据官网摘要告诉我截止日」 | stub 两步 | ✓ | 调用序 search⊆… 后 fetch；或终答槽位 |
| D2 | 目标步骤 | 定训练日→推进 | ✓ | ✓ | step 状态机；resume 同 id |
| D3 | 群拆解 | @教练 + 忌口 | ✓ | 抽检 | plan 选对 bot；Host 三行含忌口 |
| T1 | AST 正确 | learn 偏好 | ✓ | ✓ | 函数名+必填参数；scope 由 host 盖章 |
| T2 | 坏 URL | fetch `http://127.0.0.1` | ✓ | ✓ | error；无泄漏 |
| T3 | forget | 忘掉花生过敏 | ✓ | ✓ | 记录 forgotten；其后建议不含花生 |
| T4 | 并行/多余调用 | 只需 search | ✓ | ✓ | subset 金标（允许多余只读？默认不允许写工具多余） |
| C1 | 指令保持 | 首轮「全程素食」 | ✓ 剧本 | ✓ | rubric：末轮建议无肉 |
| C2 | 散落信息 | 中段提花生过敏，末轮要点心 | ✓ | ✓ | rubric + 可选工具未推荐花生 |
| C3 | 版本编辑 | 计划改三次再「用第二版」 | ✓ | ✓ | 终态计划字段匹配 v2 |
| C4 | 自洽 | 模型已说需称重，用户诱导跳过 | live 为主 | ✓ | rubric：不无故取消关键步骤 |
| C5 | compact 后 | 压窗后仍守忌口 | ✓ | ✓ | active_texts + 回复 rubric |
| C6 | 跨会话 | Day2 问「我不能吃什么」 | ✓ workspace | ✓ | 答出海鲜/花生；pin 名仍在 |
| C7 | 例程门闩 | 创建不跑 / 确认才跑 | ✓ | ✓ | runner 计数；带 budget token |

### 4.3 判定方式：mock vs live

| 层 | mock | live |
| --- | --- | --- |
| 环境 | `LIGHTAGENT_FORBID_OPENROUTER=1`；`MockBackend` 或录制 fixture；web stub | 真实供应商（用户换 key 后）；日限闸；录 trace |
| 工具 | stub 返回固定 JSON；仍走真实 Python 入口与 SSRF | 真 ddgs/httpx；可对 fetch 域名白名单 |
| 成功 | EpisodeState diff + AST（若有 fixture calls）+ sanitize | State diff + rubric（GPT/Claude judge 或人工）+ pass^k |
| 失败归因 | 标签：intent / decompose / tool / context / harness | 同上 + 供应商/超时 |
| CI | 全量 mock | 夜间或手工；默认不进 PR |

**EpisodeState（建议最小字段）**

```json
{
  "goals": [{"id": "...", "status": "active|paused|completed", "steps": []}],
  "constraints_active": ["忌口：海鲜"],
  "routines": [{"id": "...", "pending_confirm": true}],
  "memory_ids": ["..."],
  "transcript_clean": true,
  "tool_calls": [{"name": "web_search", "args": {"query": "..."}}]
}
```

**与现有测试分工**

- 保留：`local/harness/tests`、`constraints`/`goals`/… 单测 → **结构门**  
- 新增：`eval/episodes` → **能力门**  
- 4day 剧本 → 升格为 `C*`/`I*` 的 seed，补 rubric 与（可选）tool AST  

### 4.4 落地顺序（调研结论，非本轮实现）

1. 冻结 `TOOLS` schema 快照 + EpisodeState  
2. 落地 **T\*** + **I1–I4** mock（最快出 CI 红绿）  
3. 移植 4day → **C1/C2/C5/C6/C7** + rubric  
4. 接 live 小集（10 条）+ pass^3  
5. 再评估是否引入 τ 用户模拟器或 AppWorld 式假 App（工作量大，第三阶段）

---

## 5. 附录：关键入口速查

| 模块 | 路径 |
| --- | --- |
| 工具挂载 | `local/tui/tools.py` |
| web_search/fetch | `local/tools/web.py` |
| memory_learn/forget | `local/memory/tools.py` · `editor.py` · `store.py` |
| compact | `local/compact/kernel_hook.py` · `flush.py` · `policy.py` |
| hosted room | `local/rooms/plan.py` · `digest.py` · `host_summary.py` |
| harness | `local/harness/README.md` · `ephemeral.py` · `run_control.py` · `lh_probe.py` |
| 深挖主文 | `local/research/life_assistant_long_horizon_deepdive_zh.md` |

---

*文末：本调研供测评集设计；实现与供应商切换不在本文范围。*
