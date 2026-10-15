# 双产品分轨：执行 Plan 审查稿

> 日期：2026-10-15（America/Martinique / AST）  
> 性质：**审查级 plan**。不改生产代码、不启云端实现、不切供应商。  
> 用户澄清（优先于本文任何「对照表」的误读）：**不是共享底座双模式**，而是**分开实现、最终呈现两种产品**——生活助手产品 vs 公司全员提效产品。可共享调研与评测**方法论**；实现边界、发布物、代码树或包名必须能拆成两个产品。**禁止**写成一套 runtime 用开关切 persona / 切「生活模式｜公司模式」。  
> 尺子来源（深度仍以双校准为准；冲突时校准文管「做多深」，**本澄清管「能不能共代码」**）：  
> `life_assistant_depth_calibration_zh.md` · `enterprise_agent_depth_calibration_zh.md` · `jd_bar_prod_impl_gap_zh.md` · `jd_capability_bar_verdict_zh.md`  
> 现状锚点（只读抽查，未改）：`local/memory/jobs.py`（`run_due` 空返回）、`local/memory/store.py`（`enqueue_job` 无 user/tenant；`get_store()` 进程单例）、`local/constraints/card.py`（忌口主题词表 + 原地 supersede，无 ACL）、`local/rooms/plan.py`（@ → `fitness_diet` → host_only）、`local/rooms/digest.py`（≤480 字、剥离 ephemeral）、`local/goals/store.py`（workspace JSON + `space_id`）、`local/tools/__init__.py`（memory + `web_search`/`web_fetch`，无角色 allowlist）。  
> 前序 plan 若与「两产品」冲突：**生活向** `hosted_room_group_chat_plan_zh.md` / `p0_memory_impl_plan_zh.md` / `long_horizon_stable_gap_plan_zh.md` 只服务生活产品；公司轨**不得**在这些 plan 上打补丁变成第二人格。

---

## 0. 审查结论（先读）

| 产品 | 能否开工 | 条件 |
| --- | --- | --- |
| **生活助手产品** | **修订后的 P0 可以进入实现** | 以本文 §B 为执行单，不是把校准文原文丢给云端。开工前过 §D 中 L1–L9。禁止在同一 PR 里加公司 ACL/租户/制度 RAG。 |
| **公司全员提效产品** | **不可进入实现；plan 还要改一轮** | 校准文是深度尺子，不是可执行设计。缺独立代码树/包名、租户与 ACL 规格、自部署模型回归门禁、办事终态台架协议。在现有 `local/` 上加 `mode=enterprise` **判定为审查不通过**。 |

各轨最大风险见 §E。禁止事项见 §E.3。

---

## A. 两产品关系（分轨，不是双模式）

### A.1 禁止的形态（审查否决）

下列写法一律视为 **plan 未通过**，不得开工：

| 否决形态 | 为什么不行 |
| --- | --- |
| 一个进程 / 一个 TUI / 一套 `make_agent`，用 `persona=life\|enterprise` 或 `PRODUCT_MODE` 切换 | 用户明确禁止「一套 runtime 切人格」；提示词与工具 ACL 会缠在一起，串数据只是时间问题 |
| 公司能力作为 `local/` 的可选模块，默认关、企业开 | 仍是同一发布物、同一 store 单例、同一群聊运行时；「默认关」挡不住 import 与迁移脚本 |
| 共用 `ProfileStore.get_store()` / 同一 SQLite / 同一 `constraints/card.json`，靠 `namespace` 字符串区分员工与生活用户 | 现有 jobs 表甚至没有 `user_id`；生活 `namespace` 不是租户边界 |
| 把生活 Hosted Room 模板改名为「差旅/合同」就当公司产品 | 选麦仍是关键词单层；无审计、无 ACL、无终稿权转移记录 |
| 只换 `BASE_URL` 到内网模型，其余 runtime 不动 | 自部署模型是公司轨的**模型供应**，不是产品分叉；换端点 ≠ 新产品 |

### A.2 允许共享 vs 必须拆开

| 层 | 生活助手产品 | 公司全员提效产品 | 能否共享 |
| --- | --- | --- | --- |
| 调研笔记 / 社区对照 | 读 `local/research/*` | **只读同一批调研**，不把调研目录当运行时依赖 | **可共享（文档）** |
| 评测方法论 | 启发式切片、否定探针、离线优先、live 限量 | 金标 grounded、ACL 负例、办事终态；协议思想可借鉴（断言与数据不可混） | **方法论可借鉴；用例、报告、CI 门禁分开** |
| 代码树 | 继续在现有 LightAgent 二开：`local/` = **生活产品实现** | **新包或新仓库**（建议名仅作计划：`workagent` / `orgagent`，落点不在本审查内敲死路径，但**不得**是 `local/enterprise/` 开关） | **不共享运行时代码** |
| 发布物 | 个人日用 TUI / 生活助手 | 公司内部全员客户端或服务；独立版本号 | **两个制品** |
| 身份与提示 | 生活 Host、忌口、例程、健身饮食群 | 员工角色、制度、工单、审批口吻 | **两套系统卡，禁止运行时拼接** |
| 记忆存储 | Profile SQLite + 忌口卡 + LifeGoal + pin | 租户/部门/角色作用域的制度卡、办事单、审计日志 | **物理隔离**（不同库、不同密钥域） |
| 模型 | 用户现用 MX `deepseek-v4.1-flash` / effort=medium（可换，但是**生活产品配置**） | 公司内自部署后训练 checkpoint；版本写入审计 | **配置与密钥分开**；禁止生活 key 打内网、禁止内网权重配置进生活默认 |
| 工具 | `web_search` / `web_fetch` / memory / goal | 内网邮件草稿、工单、制度检索、日历；角色 allowlist | **工具注册表分开**；生活工具不得出现在公司默认集，反之亦然 |
| 群聊 / 多角色 | Hosted Room（规则选麦、少回声） | 受限 handoff / 角色 Team（另起协作运行时） | **概念可对照，代码不复用为同一 `TurnPlan`** |
| 飞轮 | 忌口/偏好 merge+supersede，门闩，默认不调 LLM | 制度摘要 merge+supersede，**禁止跨租户**，人审后才可进再训语料 | **算法笔记可参考；作业、门闩阈值、审计格式各写各的** |

### A.3 和「共享底座」说法的关系

双校准文里的「相对生活助手升降级」是**深度对照**，不是架构。执行时改读成：

1. **生活产品**按生活校准的深度做，代码留在现有 `local/`。  
2. **公司产品**按企业校准的深度做，**另起实现**；需要类似能力时是**重做一版符合 ACL 的**，不是 import `local.memory.jobs` 再加 `if tenant`。  
3. 允许的复用上限：**抄写后切断**（vendoring 一段纯函数并改名、改测试），且审查记录写明「复制点 / 分叉点」。禁止运行时依赖生活包。  
4. 现有 LightAgent **上游内核**（工具循环、取消、预算库）若两产品都要，各自 pin 版本、各自接线；不在生活 TUI 里为公司预留钩子。

### A.4 默认日用

用户日常仍是**生活助手产品**（当前仓库、当前 TUI）。公司产品是**并列的另一个产品假设**，在独立树里从零设计到可验收，不占用生活默认路径，也不把生活 TUI 变成双入口。

---

## B. 生活助手产品 — 执行 plan（审查稿）

定位尺子：`life_assistant_depth_calibration_zh.md`。实现面：**仅**现有生活二开（`local/` 及生活 TUI 接线）。模型供应保持生活产品自己的配置（当前 MX medium）；**不**为公司内网模型改默认。

### B.1 P0（日用不立住就做；可开工）

| ID | 条目 | 验收（生活产品自己的） | 明确不做 |
| --- | --- | --- | --- |
| **L-P0-1** | `run_due` 最小巩固：对 **Profile learnings + 忌口卡已有 supersede 语义** 做近重复 merge、同主题 supersede 可观测；pin / `[PINNED]` 跳过 | 1. 单测：入队 → `run_due` 非空返回或明确「本批跳过」原因；重复忌口折叠为一条 active 2. 旧 `test_consolidate_job_is_a_stub` 与 `JD-B03/B07/B08` 的 `run_due=[]` **同一变更集改写**为「巩固后可观测」；禁止留着绿 stub 又声称飞轮完成 3. 巩固前后 diff 可从 store 读出（不必先做完整 UI） | 不调 LLM 做每轮 consolidate；不做 Voyager 技能库；不做部门 synthesis；**不**加 `tenant_id` |
| **L-P0-2** | 门闩：最短间隔 / 最少新记忆（具体数字写进生活配置，建议起步 ≥6h 或 ≥N 条，实现时写死可测默认）+ 现有 store 锁 | 风暴用例：连续 `run_due` 第二次 no-op；并发双调用不双写 | 不引入新队列中间件 |
| **L-P0-3** | 跨会话抗遗忘边界说清楚并补探针：忌口卡、pin、进行中 LifeGoal 重启后仍在；`share_user_profile=False` 的 Bot **读不到**用户硬事实块 | 离线：新进程重开 store 仍命中；关共享的 child system **不含**忌口/pin 原文 | 不做组织级 KB；digest 仍 ≤480 且继续剥离 ephemeral |
| **L-P0-4** | Hosted Room 少回声：Host 综合去重，不复述任务原文两遍；仍规则选麦 | 现有房间单测加一条：综合稿与 speaker 正文重复度下降（可用规则断言：Host 文本不得整段复制任一 speaker 前 80 字）；`fitness_diet` 与 `@` 行为不回退 | **不**接 Agents SDK handoff；**不**把宏观报销从 `fallback_host_only`「修」成 Swarm；可选第二模板最多一个且仍是生活场景（如作息），不是差旅/合同 |

### B.2 P1（体感；P0 绿后再开，不与 P0 捆一个云端任务）

| ID | 条目 | 验收 | 做到就停 |
| --- | --- | --- | --- |
| **L-P1-1** | 生活向 20–30 题启发式：卡 grounded、否定遵指（别记/别搜/别改忌口）、多约束 | 进生活 eval yaml；失败即回归红 | 不上 FACTS/RAGAS 产线 |
| **L-P1-2** | 1:1 compact 压前 flush 与巩固分工：flush 写 profile/note，**不**替代 `run_due`；不把 pack 写回 transcript | 现有 compact 不变量仍绿；文档一句写清谁写卡、谁写 learning | 不重写 compact |
| **L-P1-3** | 例程防骚扰复核：静默时段 / 去重 / 确认才跑（已有方向则只补缺口探针） | 重复触发不双提醒 | 不做企业「非工作时间」策略（那是公司产品） |
| **L-P1-4** | 4 日 harness / 生活改写长程子集常驻**离线**；live 限量且单独开关 | 离线剧本绿；报告标明不是 JD 达标 | 不接 WorkArena / THE AGENT COMPANY |

### B.3 P2（后置，默认不排期）

- 向量 recall 增强（不替换 ConstraintCard）。  
- 可选 LLM 选麦，默认关，且仍在生活产品内。  
- FACTS/RAGAS/BFCL/GAIA/WorkArena：只留在调研笔记。  
- Space 隔离若做，只防「家/工作**话题**串味」，**不是**公司租户。

### B.4 审查意见（生活轨）

**可落地（对照源码）**

- L-P0-1/2 落点明确：`local/memory/jobs.py` 的 `run_due` 今日是 `return []`；`ProfileStore.enqueue_job` 已能入队。忌口 supersede 已在 `constraints/card.py`，巩固应**调用**它或与其主题键对齐，不要另起一套「海鲜」规则。  
- L-P0-4 落点明确：`local/rooms/host_summary.py` + `plan.py`；选麦结构不要改成图。  
- L-P0-3 多数是**补探针与边界**，不是新存储。Goal 已按 workspace + `space_id` 过滤。

**缺口（不补则 P0 验收会假绿）**

1. **jobs 无作用域**：`enqueue_job` 不写 `user_id`。生活多身份日用会把两个 Bot 的巩固任务倒进同一张表。P0 至少要在 payload 或表字段带上**生活 user_id**（仍不是租户）。否则「可观测 diff」无法归因。  
2. **`get_store()` 进程单例**：测试与 TUI 若混用会串库。巩固实现必须继续允许 `set_store` / 显式传入 store，禁止在 `run_due` 里偷偷 `get_store()`。  
3. **否定探针债**：`jd_bar_v2` 与 `test_consolidate_job_is_a_stub` 把 stub 写成 PASS。不改断言就等于「飞轮未做但测评绿」。这是开工清单的一部分，不是收尾文档。  
4. **1:1 absorb 与巩固的顺序**：`long_horizon_stable_gap_plan_zh.md` 曾指出 1:1 send 是否吸收忌口要对照当前 `app.py`。P0 巩固**假设卡里已有 active 行**；若 1:1 仍不写卡，巩固没有输入。开工第一步是**读**当前 `send` 钩子：已接线则写进验收前提；未接线则把「1:1 absorb」列为 L-P0-1 的前置小步，而不是另开公司向 RAG。

**风险**

| 风险 | 表现 | plan 约束 |
| --- | --- | --- |
| 飞轮风暴 | 每轮或每次启动全量 LLM 合并，烧 MX 额度 | P0 **零 LLM**；门闩 + 纯规则 merge（规范化空白/同主题键） |
| 误删偏好 | merge 把两条真不同的 veto 折成一句 | 只合并**同 topic_key** 或规范化后完全相同的 text；不确定则 KEEP 并记 `skipped` |
| 与 pin 冲突 | 巩固改写用户钉住的称呼 | pin 行不进入候选集；单测覆盖 |
| 范围蠕变 | 「顺手」加制度卡、handoff、内网 URL | 见 §E.3；PR 描述若出现 tenant/ACL/制度即拒 |

**过度工程（建议删掉，不要写进生活开工单）**

- 日终信念仿真、Reflexion 环、技能库。  
- 为生活巩固上 Celery/Redis。  
- 在生活 Room 做 agents-as-tools。  
- 把 Graphiti 时序图当 P0。

**建议改写（相对校准文原文）**

- 校准文 P0 第 2 条「Room 成员可见硬事实」容易做成共享 KB。改成：**仅** `share_user_profile=True` 的成员在 child system 看到只读硬事实块；digest 不升级成 KB。  
- 「可选低频 synthesis」从生活 **P0 删掉**，放到 P2 且默认关。P0 只做 merge/supersede。  
- 第二生活模板不是 P0 必做；少回声是 P0，模板扩展是 P0 可选、失败不挡门闩。

**生活轨审查结论：** 按 §B.1 改写后的 P0 **可以进入实现**。P1/P2 不在第一次开工范围。

---

## C. 公司全员提效产品 — 执行 plan（审查稿）

定位尺子：`enterprise_agent_depth_calibration_zh.md`。  
**本审查不授权在 `/workspace/LightAgent/local` 落地任何公司代码。** 下面条目是**下一轮设计必须写清的合同**；写不清则继续「还需改 plan」。

### C.1 开工前必须先有的设计页（仍属 plan，不是实现）

| ID | 设计合同 | 通过标准 | 现在缺什么 |
| --- | --- | --- | --- |
| **W-PRE-1** | 独立包名/仓库与发布物 | 文档给出根目录、禁止 import 生活 `local.*`、独立版本号 | 无 |
| **W-PRE-2** | 租户模型 | `tenant_id` + `dept_id` + `actor_id` + 角色；**任何**读写 API 强制作用域；无默认租户 | 生活 store 无此列 |
| **W-PRE-3** | 工具 ACL 与审计 | 每个工具：allow 角色、读/写、是否要确认；拒绝与成功都落审计（谁、何时、工具、参数摘要、结果码） | 生活工具无矩阵 |
| **W-PRE-4** | 自部署模型回归门禁 | checkpoint id 写入每次运行；换权重必跑：制度 grounded 子集 + 越权负例 + 办事终态子集；失败不得标为可发布 | 当前跑次是 MX 公网/代理，不能当内网证据 |
| **W-PRE-5** | 数据不出域 | 默认无公网搜索；生活 `web_search` 不在公司工具表 | 若计划「先用 MX 打通」须单独风险接受，且**不得**用员工真数据 |

在 W-PRE-1..5 未写成可审查规格之前，**没有 P0 实现票**。

### C.2 拟定 P0（设计冻结后才允许实现；本次不可开工）

| ID | 条目 | 验收 | 明确不做 |
| --- | --- | --- | --- |
| **W-P0-1** | 制度卡（不是忌口卡换皮）：条款 id、密级、有效期、supersede、**注入前 ACL 过滤**；无命中则拒答或标「未找到条款」 | 金标 20 题：答对必须带条款 id；越权角色注入块为空；无检索不编造数字 | 不把 `TOPICS` 海鲜词表扩成制度引擎 |
| **W-P0-2** | 工具 ACL 最小集：制度检索（读）、工单草稿（写，需确认）、越权硬拒 | 负例：低权限角色调用写工具 → 拒绝且审计一行；参数里的跨租户 id 无效 | 不接真实客户外发；不把 `web_fetch` 当制度源 |
| **W-P0-3** | 办一件事的终态探针（mock 状态机即可）：例如「差旅报销草稿」步骤可恢复、跨会话同一单号 | cancel→resume 同 id；终态字段断言；**不**依赖生活 LifeGoal JSON 路径 | 不把 THE AGENT COMPANY 全榜当门禁 |
| **W-P0-4** | checkpoint 回归脚本：固定内网模型 id（或 CI 假模型）跑 W-P0-1..3 | 脚本失败即非发布候选 | 不接受「生活 jd_bar_v2 52/52 所以公司也绿」 |

### C.3 拟定 P1（仍不可与生活 P0 并行塞进同一树）

| ID | 条目 | 验收 | 停点 |
| --- | --- | --- | --- |
| **W-P1-1** | 企业 consolidate：同租户同密级内 merge/supersede；跨租户合并**测试必须失败**；pin/红线跳过或人审 | diff + 回滚一条；门闩防 GPU 风暴 | 不自动写入基座权重 |
| **W-P1-2** | 受限 handoff / 一个角色 Team 模板（建议只做一个：差旅**或**合同，不要两个一起） | 发言顺序、终稿权、越权静默可测；LLM 自由选麦默认关 | 不做 ReDel/无界 Swarm |
| **W-P1-3** | 流程类浅规划只对**该模板**打开 | 闲聊不推进该单；步骤图可关 | 默认 ToT 不开 |

### C.4 拟定 P2

无界 Swarm、WorkArena/TAC/GAIA 全榜、无 ACL 的全员图、Voyager 式自动执行技能、公网 FACTS 全流水线。与企业校准 §6 P2 一致，保持后置。

### C.5 审查意见（公司轨）

**与现状源码的距离（实事求是）**

| 生活里已有的 | 能不能当公司 P0 | 审查判断 |
| --- | --- | --- |
| ConstraintCard supersede | 只证明「原地作废」这一种数据结构可行 | **不可扩展**。词表、无密级、无租户。公司要新类型 |
| LifeGoal 单 in_progress | 可借鉴「一张进行中的单」 | **不可复用文件布局** `{workspace}/goals/*.json` |
| Hosted Room | 证明单层规则选麦能防互啄 | **不能**加几个关键词就叫 Team。handoff 是另一运行时 |
| `run_due` stub | 生活 P0 会把它做成忌口巩固 | 公司若等待生活飞轮再 import，会把忌口语义带进制度库。**公司飞轮另写** |
| `BudgetLimits` / `CancellationToken`（上游库有，生活 TUI 未接） | 公司产品应在**自己的**对话入口接线 | 不要先改生活 TUI 为了公司预算 |
| 评测 runner `local/eval` | 方法论可抄 | 公司用例不得放进 `jd_bar_v2.yaml` 充数 |

**风险**

| 风险 | 若按「在生活树上加模式」会怎样 | plan 必须改成 |
| --- | --- | --- |
| 租户串数据 | 单例 SQLite + jobs 无 user 列；一个员工看见另一个忌口或制度 | 独立库；API 无 tenant 即拒绝；禁止默认租户 |
| 审计缺失就上线 | 工具调用只在 TUI 轨迹里 | P0 审计是发布门，不是 P2 |
| 自部署模型能力上限 | 后训练模型工具格式更脆；用 MX flash 绿了不等于内网绿 | W-P0-4；schema 变更=再跑门禁 |
| 飞轮污染基座 | consolidate 自动变 SFT | 人审队列；默认不导出 |
| 幻觉制度 | 参数记忆编造条款 | 无条款 id 则拒答，写进系统卡**与**测试 |
| 范围蠕变 | 第一期就做合同+差旅+客服+图数据库 | P0 只有制度检索+一个 mock 办事终态+ACL；Team 放 P1 且只一个模板 |

**过度工程（公司轨也要砍）**

- 第一期上 Graphiti 全图、LangGraph 全公司流程平台、多租户 SaaS 控制面。  
- 与生活产品「统一记忆中台」。  
- 用公网 FACTS 榜代替内网金标。

**建议改写（相对企业校准文）**

- 校准文 P0 把 A+C+E 并列，体量是**多个季度**。执行 plan 改成：**先冻结 W-PRE，再只做 W-P0-1..4**。RAG 若无内网语料，P0 用**脱敏夹具条款**，不要假接生产 KB。  
- 「Flow/DAG 进主路径」降为 **W-P1**，除非 W-P0 的 mock 终态证明单循环不够。避免第一行代码就接上游 LightFlow。  
- 模型：公司 plan 写明**不继承**生活 `PROVIDER=mx`。内网 endpoint、密钥保管、日志脱敏单独一节。未定供应商之前不得写「先用现有 key 冒烟真制度」。

**公司轨审查结论：** **还需改 plan，不可进入实现。** 下一轮只允许写 W-PRE 规格（仍是文档）），规格再审过才有实现票。

---

## D. 交叉审查清单（开工前必过）

每一条：检查问题 → 通过标准 → 不通过则如何改 plan。  
生活 P0 开工过 **L** 列；公司在 W-PRE 再审过 **W** 列。两边都过的才算「交叉通过」。生活开工**不**等待公司 W 列（否则两产品又绑死）。

| ID | 检查问题 | 通过标准 | 若不通过，如何改 plan |
| --- | --- | --- | --- |
| **D1 范围蠕变** | 这张实现票是否同时改生活人格与公司办事？ | 一张票只属于一个产品根目录；diff 不跨两个产品树 | 拆票。公司内容移出生活 plan；生活 PR 模板加禁词：tenant、制度卡、handoff、内网 base url |
| **D2 租户串数据** | 是否存在无 tenant 的默认库、或生活 SQLite 被公司代码打开？ | 公司 API 缺 tenant 即 4xx；生活库路径不出现在公司配置；无共享单例 | 公司 plan 补 W-PRE-2；删掉任何 `import local.memory` |
| **D3 飞轮风暴** | 巩固是否每轮、是否调用模型、是否无锁？ | 生活 P0 零 LLM + 门闩 + 锁；公司 P1 同样且按租户加锁；pin/红线排除 | 把 synthesis/LLM 移出该阶段；补风暴单测为验收门 |
| **D4 Room 回声** | Host 或 Team 终稿是否复读专员原文？ | 生活：规则去重断言。公司：终稿权角色明确，专员输出是附件不是第二份正文 | 生活只改 `host_summary`；公司不要复用该函数充终稿 |
| **D5 评测绿≠达标** | 是否用 stub 否定探针或生活 52/52 宣称产品达标？ | 断言与目标行为一致；报告标题写产品名与尺子；外部大榜未跑就写未跑 | 改断言再改实现，禁止先改实现留着旧 PASS；公司不得引用 `jd_bar_v2_live_latest.md` 当发布证据 |
| **D6 自部署模型上限** | 公司验收是否跑在 MX/生活 key 上？ | 发布门禁日志含内网 checkpoint id；工具 schema 用该公司模型跑通写路径与拒答 | 未接内网前，公司票状态保持「设计」；禁止用生活冒烟代替 |
| **D7 密钥与串台** | `LIGHTAGENT_*` / `MX_API_KEY` / 内网 key 是否会进同一环境、同一日志？ | 两套 env 文件；日志打码；生活默认配置不读公司 key 变量名 | plan 写密钥矩阵；实现票若要改 `openrouter_config.py` 的默认供应商，**单独生活票**，不得夹带公司 endpoint |
| **D8 与既有 stub 冲突** | `run_due` 空实现、`consolidate_job_queued_not_run`、Host 三行规则是否被静默破坏？ | 变更集包含测试改写说明；行为变化写进生活 eval 报告 | 先改 plan 的验收表再写代码；stub 与新行为不能同时为真 |
| **D9 回滚** | 巩固写坏或公司 ACL 误放行能否退回？ | 生活：巩固前快照（job id → payload），失败 job 保持 queued 或标 failed 不删原行；公司：审计可指向变更前条款版本，一键标记回滚（P0 至少是「恢复 JSON/行」的测试） | 无快照则 P0 不收；禁止 consolidate 物理 DELETE 唯一副本 |
| **D10 双人格** | 运行时能否在不重新部署的情况下从生活助手变成公司员工助手？ | **不能。** 无 `PRODUCT_MODE`。两个进程配置指向两个包 | 发现开关设计则整段 plan 退回 §A.1 |
| **D11 复制后分叉** | 若从生活抄了纯函数，是否仍 import 生活包？ | 复制进公司树并改测试；CI 禁止公司包依赖生活 `local` | 改 plan 的「复用」一节为 vendoring 清单，否则删复用 |
| **D12 数据与评测夹具** | 生活忌口对话是否进公司金标，或员工制度进生活 yaml？ | 两套 cases 目录；无交叉 id 前缀（生活 `L-` / 公司 `W-`） | 移文件；共享的只有评测**写法**说明 |

生活 P0 开工最低集合：**D1、D3、D4、D5、D7、D8、D9、D10** 针对生活票书面勾过。D2/D6/D11 在公司未开工前记为「生活侧承诺不碰」。

---

## E. 结论

### E.1 能否进入实现

- **生活助手产品：可以进入实现，但仅限 §B.1 的 L-P0-1..4**，且把 §B.4 的缺口（jobs 带生活 user_id、禁止 `run_due` 内 `get_store()`、同步改 stub 断言、确认 1:1 忌口已写入卡）写进开工说明。P1 另票。  
- **公司全员提效产品：不可进入实现。** 还需改 plan：先完成 §C.1 的 W-PRE-1..5 规格再审。在此之前任何「在 LightAgent `local/` 加企业模式」的实现都视为违反本审查。

### E.2 各轨最大风险（各一条）

- **生活：** 巩固作业与旧 stub 断言不一致，或门闩缺失，导致要么测评假绿、要么 MX 上风暴式改写偏好且难以回滚。  
- **公司：** 在生活 runtime 上切模式或复用同一 SQLite/工具表，造成租户（及生活）数据串用，且内网模型从未进入发布门禁。

### E.3 禁止事项（审查不得有失）

1. 未经本审查修订，不得把双校准文直接当云端实现提示词。  
2. 不得实现 `PRODUCT_MODE` / persona 开关 / `local/enterprise` 插件式第二人格。  
3. 不得让公司代码 import 生活 `local.memory`、`local.rooms`、`local.constraints` 作为运行时。  
4. 不得用 `jd_bar_v2` 全绿、或 `run_due=[]` 的 PASS，宣称飞轮或公司产品达标。  
5. 不得在生活 P0 调用 LLM 做 consolidate，不得物理删除唯一记忆副本。  
6. 不得把生活 `MX_API_KEY` 或公网搜索用于公司真制度、真工单、真员工数据。  
7. 不得在公司模型未纳入回归门禁时发布「全员可用」。  
8. 不得把 Hosted Room 关键词模板扩成差旅/合同来冒充受限 handoff。  
9. 不得把 THE AGENT COMPANY / WorkArena / FACTS 全榜写入任一产品的发布门禁。  
10. 本文件生效期间：**不改生产代码、不启云端实现**；下一动作只能是生活 P0 开工票（另任务）或公司 W-PRE 规格（另任务）。

---

## F. 证据与文件

| 用途 | 路径 |
| --- | --- |
| 生活深度 | `local/research/life_assistant_depth_calibration_zh.md` |
| 公司深度 | `local/research/enterprise_agent_depth_calibration_zh.md` |
| 生产级差距 | `local/research/jd_bar_prod_impl_gap_zh.md` |
| JD 总评（绿≠达标） | `local/research/jd_capability_bar_verdict_zh.md` |
| 飞轮 stub | `local/memory/jobs.py` |
| 单例 store / jobs 无 user | `local/memory/store.py` `enqueue_job` / `get_store` |
| 忌口卡 | `local/constraints/card.py` |
| 单层选麦 | `local/rooms/plan.py` |
| 短 digest | `local/rooms/digest.py` |
| 本审查 | `local/research/dual_track_execution_plan_review_zh.md` |

副本：与本文件同步到当前 agent 的 `research/`（只增加审查稿，不改其他研究文件的结论所有权）。
