# LightAgent 能力测评集设计（意图 / 拆解 / 工具 / 多轮上下文）

日期：2026-10-15  
定位：全方位个人生活助手（非 coding agent 主航道；coding 仅对照）  
供应商：**已切 ScienceEdu**（`LIGHTAGENT_PROVIDER=openai`，`https://api.scienceedu.me/v1`，`deepseek-v4.1-flash`，`effort=medium`，key=`LIGHTAGENT_API_KEY`）  
依据：本仓库 `local/` 架构 + 既有长链路 harness / 4×10 剧本 + 完整调研 `agent_capability_eval_survey_zh.md`（τ-bench / BFCL / MultiChallenge / LoCoMo·LongMemEval / AppWorld 五核）

---

## 0. 测什么、不测什么

### 测（四维）

| 维 | 生活助手含义 | 本仓库主要落点 |
| --- | --- | --- |
| **意图识别** | 短问 / 建目标 / 忌口 / 例程 / 派发 / 闲聊拒识 | `goals/detect`、`constraints/absorb`、`routines/parse`、`maybe_delegate`、短问答不建 LifeGoal |
| **任务拆解** | 复合生活场景拆成可推进步骤；不滥拆 | `LifeGoal` 步骤、`maybe_advance_goal`、Host 三行「下一步」、（对照）不用默认 ToT/DAG |
| **工具选择** | 该搜搜、该记记、该派派；不乱调 | `TOOLS`：`web_search`/`web_fetch`/`get_weather`/`delegate_to_bot`/`recall_spilled` + `memory_*` |
| **多轮上下文** | 跨轮忌口/目标/记忆/压缩后仍一致 | Memory pack、ConstraintCard、compact 尾窗、checkpoint 续跑、群 Hosted Room digest |

### 不测（本轮）

- 纯编码 agent 指标（SWE-bench 等）只作对照，不进主分。
- OS 沙箱深度、默认 ToT/LightDAG、群内 LLM 互啄。
- 供应商本身质量排名（换 key 后同一套题对比模型，另表记录）。

---

## 1. 业界基准 → 四维迁移（摘要）

| 基准 | 原测点 | 我们怎么借 |
| --- | --- | --- |
| **BFCL**（AST / multi-turn / abstain） | 函数名+参数结构、拒调 | 工具选择维：期望 tool schema AST 匹配；负例「不该调」 |
| **τ-bench / τ²** | 模拟用户 + 策略遵守 + 终态 | 多轮剧本 + 策略（忌口/例程须确认）+ workspace 终态断言 |
| **ToolSandbox** | 有状态对话、里程碑/雷区 | 里程碑=goal step / memory 写入；雷区=误学忌口整句、未确认就跑 routine |
| **GAIA** | 要答案的工具链 | 少量「查网再回答」生活题；看 tool 链与最终事实 |
| **AgentBoard** | 子技能进度 | 四维分项 + 过程分，不只最终一句 |
| **LoCoMo / MemoryBank** | 长期记忆召回 | 跨「天」/compact 后仍能答偏好与忌口 |
| **既有 4×10 剧本** | 日用稳达 | 直接升格为「意图+拆解+上下文」金标子集 |

原则：**终态可断言优先于 LLM-as-judge**；judge 只用于开放表述是否违反忌口等软约束。

---

## 2. 与本 agent 代码架构对齐的观测点

```
用户话 → TUI/backend.chat
        ├─ maybe_delegate / Hosted Room
        ├─ constraints.absorb / goals.detect|advance / routines.parse
        ├─ LightAgent.run(+ tools + memory pack ephemeral)
        │     tool 轨迹 → TraceStore
        └─ compact / checkpoint / persist
```

每条用例必须声明至少一类**硬观测**：

1. **Store 终态**：`ConstraintStore.active_texts`、`LifeGoal.steps`、`RoutineStore`、`ProfileStore` pin  
2. **Tool 轨迹**：`Reply.tool_calls` / trace steps 的 `tool_name`+关键 args（允许等价顺序时注明）  
3. **Transcript 不变量**：无泄漏 `<memory-context>`；compact 后忌口仍在  
4. **拒为**：`should_create_goal=False`、无 tool、例程未 runner  

Live 跑时另记：`model`、`provider`、`usage` 消耗。

---

## 3. 测评集骨架（建议 v1：约 48–64 条）

### A. 意图识别（约 16）

| 族 | 例 | 期望 |
| --- | --- | --- |
| A1 短问答 | 「今天吃什么」「现在几点」 | 不建 LifeGoal；可闲聊/轻工具 |
| A2 显式规划 | 「帮我制定一周健身+饮食」 | 建 goal；步骤 ≥2；恰 1 个 in_progress |
| A3 忌口 | 「忌口海鲜」「其实可以吃虾」 | absorb / supersede |
| A4 例程 | 「每周一叫我称重」vs「提醒我一下」 | 有 cadence 才 create；后者拒识 |
| A5 派发 | 「@健身教练 …」 | `delegate_to_bot` 或房间选麦 |
| A6 记忆意图 | 「记住我叫小Q」「忘掉花生过敏」 | `memory_learn` / `memory_forget` 或等价卡更新 |
| A7 歧义 | 「健身」单字 | 不建 goal（与稳达负例一致） |

### B. 任务拆解（约 12）

| 族 | 例 | 期望 |
| --- | --- | --- |
| B1 复合生活 | 健身+饮食+忌口同开 | 单 goal；constraints_ref 挂上；步骤可口语推进 |
| B2 推进 | 「训练日定好了」 | s1 done → s2 in_progress |
| B3 不推进 | 天气/几点插入 | goal 步骤不变 |
| B4 取消续跑 | 取消 →「继续」 | checkpoint；不新建 goal |
| B5 过度拆解负例 | 单次天气查询 | 无 LifeGoal；≤1 个相关 tool |

### C. 工具选择（约 16）

| 族 | 例 | 期望 tool / 拒调 |
| --- | --- | --- |
| C1 必搜 | 「查一下附近有什么清淡餐厅（联网）」 | `web_search`（可再 `web_fetch`） |
| C2 必取页 | 给定 URL「摘要这篇」 | `web_fetch` |
| C3 天气 | 「上海天气」 | `get_weather`（mock 或真） |
| C4 记忆 | 「我上次说的忌口是什么」 | `memory_recall` 或 pack 已注入则**可不调**（标注 dual-ok） |
| C5 派发 | 明确 @ 身份 | `delegate_to_bot` |
| C6 召回溢出 | compact 后问旧细节 | `recall_spilled` 或 memory |
| C7 拒调 | 「随便聊聊心情」 | 无 web_* / 无 learn |
| C8 错工具雷区 | 忌口句 | **禁止**只把整句塞进 memory 替代 ConstraintCard（对标稳达痛点） |
| C9 并行 | 「查天气并搜健身课表」 | 允许 parallel；集合包含 weather+search |

判定：BFCL 风格 **name+关键 args**；允许多余 harmless tool 时在用例标 `extra_tools=allow|forbid`。

### D. 多轮上下文（约 12–16）

| 族 | 轮次形态 | 期望 |
| --- | --- | --- |
| D1 忌口贯穿 | T1 忌口 → T5 推荐菜单 | 不推荐违禁；card active |
| D2 改口 | 海鲜 → 可以吃虾 | superseded 正确 |
| D3 跨天 goal | 同 workspace 续 | 同 goal_id；步骤连续 |
| D4 compact 后 | 压后问偏好/忌口 | pin/卡仍在；无 memory-context 泄漏 |
| D5 例程门闩 | 创建 → due 提示 → 未确认 | runner=0；确认后才跑 |
| D6 群 Host | 健身+饮食房 | Host 三行；少回声 |
| D7 长对话指代 | 「还是按上次的」 | 解析到正确 goal/约束 |

---

## 4. 跑法分层

| 层 | 何时 | 怎么跑 | 成本 |
| --- | --- | --- | --- |
| **L0 库探针** | CI / 无 key | 直接调 detect/absorb/advance/parse；pytest | 0 token |
| **L1 Mock 轨迹** | 每次 UI/后端改动 | `MockBackend` + 期望 tool_calls / 状态 | 0 |
| **L2 Live 单轮工具** | 新供应商接入后 | `make_agent`+真实 tools；AST/终态 | 低 |
| **L3 Live 多轮剧本** | 发版前 | 4×10 升格 + 本设计 A–D 子集；记录 usage | 中 |
| **L4 对抗/雷区** | 稳达后 | ToolSandbox 风格 minefield | 中 |

建议：换供应商后先 L2 冒烟（8 条）→ L3 核心 24 条 → 再扩全量。

---

## 5. 评分卡（单次跑）

- 每维：`PASS / PARTIAL / FAIL` 计数 → 维得分 = PASS / (PASS+PARTIAL+FAIL)  
- 总分：四维宏平均；另报 **雷区违反率**（C8/D5 等）  
- 并列报告：token/次、工具次数、是否超 `BudgetLimits`  
- 对标标签：`稳达` ≥ 四维均 ≥0.85 且雷区违反=0；`勉强` 0.7–0.85；`<0.7` 未达

---

## 6. 目录与落地（实现时）

```
local/eval/
  README.md
  cases/           # yaml：id, dim, turns, expect.{tools,stores,invariants}
  runners/
    l0_store.py
    l2_live_tools.py
    l3_multiturn.py
  reports/         # 每次跑一份 md+json
```

金标先从 `long_horizon_4day_dialogue_script_zh.md` 机械迁移 20+ 条，再补 C 维联网与拒调。

---

## 7. 已定 / 待拍板

**已定**

1. 供应商 ScienceEdu 连通（冒烟「通了」；裸 urllib 会被 CF 1010，走 OpenAI SDK/LightAgent）。  
2. 调研文档已就绪：`agent_capability_eval_survey_zh.md`（~37 条参考）。  
3. 设计骨架：四维 × L0–L4；终态断言优先于 LLM-as-judge。

**待拍板**

1. **首跑范围**：建议 L2 冒烟 8 + L3 核心 24；全量 48+ 第二轮。  
2. **天气工具**：live 仍用 mock `get_weather`，还是接真 API。  
3. **LLM-as-judge**：是否仅用于「推荐是否踩忌口」软判（默认：有 ConstraintCard 断言则不用）。  
4. **pass^k**：核心用例默认 k=1 还是 k=3（额度敏感）。

---

## 8. 下一步

- [x] 合并调研表链接与五核基准  
- [x] 切换供应商并 L2 连通冒烟  
- [x] 写出 `local/eval/cases/*.yaml` 首批与 runner（L2×8 + L3×24）  
- [x] L0 store 探针：21/21 PASS（`local/eval/reports/l0_store_latest.md`）  
- [x] L2 冒烟（ScienceEdu / deepseek-v4.1-flash / medium）：**8/8 PASS**（`local/eval/reports/l2_live_l2_latest.md`，2026-10-15）  
- [ ] L3 live 子集（约 7 条）择机跑；控额度  
- [ ] 全量 48+ 与 pass^k 第二轮  
