# JD 尺子：X + GitHub 社区测评集扩搜（底层协议）

> 日期：2026-10-15（America/Martinique / AST）  
> 方法：WebSearch/WebFetch + GitHub API 星数 + X `search_posts_all` / `search_news`  
> 目的：为 `jd_bar_v2` 提供**足够测评集协议**与「本仓切片 vs 外部榜」对照；**不假装跑了未跑的榜**。  
> 关联：`jd_capability_bar_survey_zh.md` · `jd_bar_prod_impl_gap_zh.md` · `jd_capability_bar_verdict_zh.md`

---

## 0. 一句话

社区成熟评测把 Agent 能力拆成：**工具 AST/可执行（BFCL/τ）· 指令保持（IFEval/MultiChallenge）· 接地/遗漏（FACTS/RAGAS）· 多步终局（GAIA/AppWorld）· 长记忆（LoCoMo/LongMemEval）· 职场生产力（THE AGENT COMPANY/WorkArena/AssistantBench）· 自进化叙事（Voyager/ExpeL/Reflexion）**。  
本仓 `local/eval` 只覆盖其中**可本地断言的生活助手切片**；外部大榜本轮**未整榜接入**。

---

## 1. 测评集总表（协议级）

| 基准 | 链接 / 热度 | 核心机制（评什么） | 主指标 | → JD | 本仓是否跑 |
| --- | --- | --- | --- | --- | --- |
| **BFCL V4** | [gorilla BFCL](https://gorilla.cs.berkeley.edu/leaderboard.html) · [repo](https://github.com/ShishirPatil/gorilla) · ICML'25 | AST + live + multi-turn state；V4=Web Search / Memory / Format Sensitivity | Overall Accuracy（子类平均） | A3 C2 | **否**（借 must/forbid AST） |
| **τ-bench / τ²** | [sierra-research/tau-bench](https://github.com/sierra-research/tau-bench) · arXiv:2406.12045 | 用户模拟 + 策略约束 + **终局 DB 相等** | pass^k | A3 A5 | **否**（忌口/goal 终态近似） |
| **ToolBench** | Qin et al. · ToolLLM | 大规模工具检索与调用 | 工具正确率等 | A3 | **否** |
| **API-Bank** | arXiv:2304.08244 | Plan→Retrieve→Call | Correctness + ROUGE | A3 A5 | **否**（先 search 再 fetch 切片） |
| **GAIA** | arXiv:2311.12983 | 真实助手题 L1–L3，工具链 | exact-match | A5 C4 | **否** |
| **AppWorld** | [StonyBrookNLP/appworld](https://github.com/StonyBrookNLP/appworld) | 多 App + 单元测试终局 | TGC/SGC | A5 E | **否**（expected_state JSON 思想） |
| **THE AGENT COMPANY** | [GitHub ~796★](https://github.com/TheAgentCompany/TheAgentCompany) · arXiv:2412.14161 | 模拟软件公司 175 任务；Web+终端；**checkpoint 评分**；评测脚本加密 | 结果分 + 子 checkpoint | E4 A5 | **否**（协议对照） |
| **AssistantBench** | assistantbench.github.io · arXiv:2407.15711 | 214 耗时现实网页任务；公开 SOTA 约 ~25% 量级 | 任务成功率 | E4 | **否** |
| **WorkArena / ++** | [ServiceNow/WorkArena](https://github.com/servicenow/workarena/) · BrowserGym | ServiceNow 知识工作；++ 组合规划 | env.step 成功 | E4 | **否** |
| **WebArena** | Zhou et al. | 自托管网站任务 | 成功率 | E | **否** |
| **BrowserGym** | ServiceNow 等 | 浏览器 Agent 统一 env | 任务成功 | E | **否** |
| **FACTS Grounding** | DeepMind · HF `google/FACTS-grounding-public` · arXiv:2501.03200 | 长文档条件下回答是否**完全 grounded**；multi-judge | grounding accuracy | A1 | **否**（忌口 heuristic） |
| **FreshQA** | [freshllms/freshqa](https://github.com/freshllms/freshqa) | 时效事实 | FreshEval | A1 | **否** |
| **RAGAS** | docs.ragas.io · arXiv:2309.15217 | Faithfulness / Answer·Context relevance·recall | 0–1 | A2 C3 | **否** |
| **IFEval** | arXiv:2311.07911 | 可程序验证指令 | strict/loose | A4 | **否**（禁工具/禁记改写） |
| **FollowBench** | ACL'24 · YJiangcm/FollowBench | 细粒度多级约束 | HSR/SSR/CSL | A4 | **否**（双忌口切片） |
| **MultiChallenge** | ACL'25 Findings · arXiv:2501.17399 | 多轮指令保持/散落信息/改口 | rubric | A4 B | **部分**（忌口贯穿/supersede） |
| **LoCoMo** | arXiv:2402.17753 | 超长对话记忆 QA / 事件图 | F1 / FactScore | E1 B | **否**（多忌口耐久切片） |
| **LongMemEval** | [xiaowu0162/LongMemEval ~1154★](https://github.com/xiaowu0162/LongMemEval) · ICLR'25 | 500 题：抽取/跨会话/时间/更新/拒答 | accuracy + Recall@k | E1 B | **否**（cancel/resume 切片） |
| **Mem0 benches** | 平台自报 LoCoMo/LongMemEval（X/社区常引，需独立复核） | 记忆层产品评测叙事 | Hit / accuracy | B E | **否** |
| **AgentBench** | THUDM/AgentBench | 多环境 | Overall | 对照 | **否** |
| **SWE-bench** | 编码 Agent | resolve rate | **仅对照**（非生活助手主分） | **否** |
| **Voyager** | [MineDojo/Voyager](https://github.com/MineDojo/Voyager) | 技能库 curriculum | 技能库增长 / 解锁 | B E3 | **否**（叙事对照） |
| **ExpeL / Reflexion** | arXiv:2308.10144 / Reflexion | 经验池 / 语言反思再试 | 跨任务 uplift | B E3 | **否** |

### 1.1 X 社区热度信号（2026-09～10，非学术分）

| 帖子 | 要点 | 对尺子 |
| --- | --- | --- |
| [yumizjx](https://x.com/yumizjx/status/2107026764941697281) | 2026 记忆补三块：Zep 有效期作废旧边；Letta 分页；Mem0 增删改合并 | B 飞轮缺 consolidate |
| [fincken](https://x.com/fincken/status/2109671081871081778) | LoCoMo 已卷满；盯 BEAM 10M token | E 勿只报自建绿 |
| [Unibase Membase](https://x.com/Unibase_AI/status/2108797514967293990) | 自报 LoCoMo 93% 等 | 厂商分需独立跑 |
| [0xpipimd ReMe](https://x.com/0xpipimd/status/2102042669279310316) | 记忆应 refine/prune；BFCL-V3+AppWorld Pass@4 | B≠只增长 |
| [HuiningYuan ActionOPD](https://x.com/HuiningYuan/status/2110606719378419937) | BFCL / ToolSandbox / AppWorld / τ² 作未见任务集 | 外部榜矩阵 |
| [snwiki238337](https://x.com/snwiki238337/status/2107750274509242388) | 多 Agent 入门：LangGraph 图；Swarm/CrewAI handoff | D 拓扑对照 |
| [RoundtableSpace](https://x.com/RoundtableSpace/status/2104311365066453343) | CrewAI/AutoGen/MetaGPT 等编排榜单帖 | D 生态 |

---

## 2. 本仓切片 vs 外部榜（诚实对照）

| JD 维 | 外部榜「生产级尺子」 | 本仓 `jd_bar` / `jd_bar_v2` 实际跑什么 | 结论 |
| --- | --- | --- | --- |
| A1 事实 | FACTS multi-judge | 忌口卡 + 回复 heuristic（`reply_avoid_seafood_primary`） | **切片接近，非 FACTS** |
| A2 遗漏 | RAGAS context-recall | 双工具 must；多约束 `constraint_contains_all` | **无 RAGAS** |
| A3 工具 | BFCL AST / τ pass^k | TOOLS must/forbid；无 parallel/state DB | **AST 子集** |
| A4 遵指 | IFEval / FollowBench / MultiChallenge | 禁工具否定探针；多忌口；改口 supersede | **改写子集** |
| A5 完成 | GAIA / AppWorld / THE AGENT COMPANY | goal advance / cancel-resume | **无职场终局** |
| B 飞轮 | Mem0 Dream / Voyager skill growth | **故意断言** `run_due=[]` stub | **否定探针 PASS=未达** |
| C 规划 | PlanBench / LightFlow | LifeGoal 拒滥拆 + 推进 | **浅层** |
| D 编排 | Swarm handoff / LangGraph / ReDel 递归 | `build_turn_plan` 关键词+mention；`no_recursive_swarm` | **单层边界诚实测** |
| E 长程 | LoCoMo / LongMemEval / WorkArena | 多 store、digest 卫生、4day 剧本（另文） | **局部；无生产力台架** |

---

## 3. 对 `jd_bar_v2` 扩集映射

| 新增方向 | 用例 id（示例） | 借自协议 |
| --- | --- | --- |
| 多约束 / 否定遵指 | A09–A13 | FollowBench + IFEval 改写 |
| 飞轮「应巩固未巩固」 | B07–B08 | Mem0 Dream / Generative Agents 对照 |
| 拒滥拆 / 精准工具 | C09–C11 | PlanBench 精神 + BFCL irrelevance |
| 无递归 Swarm | D07–D10 | Swarm/ReDel 边界否定 |
| 跨 store / digest | E07–E10 | LoCoMo/LongMemEval 精神 |

**未接入（明确）**：BFCL 全榜、τ 用户模拟、GAIA、AppWorld、THE AGENT COMPANY Docker 任务、WorkArena、AssistantBench、LoCoMo/LongMemEval 全量、RAGAS/FACTS 裁判流水线。

---

## 4. 可信度与复现

- 星数取自 2026-10-15 GitHub API：Mem0 **67232**、CrewAI **59733**、LangGraph **43310**、Graphiti **31781**、openai-agents-python **30056**、Letta **25152**、LongMemEval **1154**、THE AGENT COMPANY **796**。  
- X 帖文热度随时间变；协议以论文/仓库 README 为准。  
- 厂商自报 LoCoMo/LongMemEval 分数**不当作本仓达标证据**。



## 5. GitHub 星数快照（2026-10-15 API）

| 仓库 | ★ | 用途 |
| --- | ---: | --- |
| mem0ai/mem0 | 67232 | 记忆层 / Dream 巩固 |
| crewAIInc/crewAI | 59733 | 角色多智能体 |
| langchain-ai/langgraph | 43310 | 图编排 |
| getzep/graphiti | 31781 | 时序知识图记忆 |
| openai/openai-agents-python | 30056 | Swarm 生产演进 / handoff |
| letta-ai/letta | 25152 | MemGPT 分层记忆 |
| xiaowu0162/LongMemEval | 1154 | 长记忆基准 |
| TheAgentCompany/TheAgentCompany | 796 | 职场生产力基准 |

## 6. 本仓未跑外部榜的原因（实事求是）

1. **环境成本**：THE AGENT COMPANY / WorkArena / WebArena 需 Docker 或企业 UI / 自托管站。  
2. **裁判缺失**：FACTS/RAGAS/FreshQA 需 multi-judge 或检索语料管线。  
3. **范围**：本轮任务是调研 + 可本地断言扩集 + 再测；**不**整榜搬迁。  
4. **可信替代**：`jd_bar_v2` 用协议改写切片 + **否定探针**暴露 B/D/E 缺口，避免假绿。
