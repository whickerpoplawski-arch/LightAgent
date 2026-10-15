# 稳达补丁 Plan：三缺口最小集（1:1 忌口 / 步骤对话推进 / 触发扩面）

> 给 **Cursor（grok-4.7，非 fast，reasoning_effort=xhigh）**：只修可用性评估指出的三个缺口；叠在已绿的 M0–M7 上；**每缺口测绿再进下一缺口**。  
> 依据（必读）：`long_horizon_harness_usability_eval_zh.md` §5–§6、`long_horizon_harness_acceptance_zh.md`、`long_horizon_harness_minset_zh.md`、`long_horizon_harness_impl_plan_zh.md`。  
> 日期：2026-10-14（America/Martinique / AST）  
> 真相源：本机 `/workspace/LightAgent` 已落地 M0–M7（pytest **146 passed**，六场景 mock 探针全绿）。本文件**只写 plan，不改业务代码**。  
> 环境硬闸：`LIGHTAGENT_FORBID_OPENROUTER=1`；`:free` 友好；默认零额外 LLM；**禁止** LangChain / LangGraph。

---

## 0. 一句话目标

把日用从「**勉强达**」（API/群路径能用、1:1 与对话推进要用户记显式说法）推到「**稳达**」：1:1 说的忌口自动进 ConstraintCard 并能进 `constraints_ref`；有活跃 LifeGoal 时用户用自然语言能把当前步标完成并推进下一步；goal/routine/constraint 换几种常见说法仍能触发——全程仍规则路径、不烧 `:free`。

---

## 1. 最小集约束（硬边界）

| # | 约束 | 含义 |
| --- | --- | --- |
| H1 | **只修三缺口** | Gap A 1:1 absorb；Gap B 步骤对话推进；Gap C 触发同义扩面。不做评估 §6 第 4/5 条（compact flush≠卡、真 OpenRouter 烟测） |
| H2 | **不扩新模块目录** | 不新建 `local/foo/`；逻辑落在现有 `constraints/` / `goals/` / `routines/` / `tui/app.py`（及必要时极薄 helper 同文件或同包） |
| H3 | **不改 M0–M7 对外语义** | E1–E12 语义保持；短问答仍不建 LifeGoal（E9）；例程仍确认才跑（E12）；落盘仍无 `<memory-context>`（E11）；群 absorb/compact 行为不回退 |
| H4 | **不接真 OpenRouter** | 实现与单测 `LIGHTAGENT_FORBID_OPENROUTER=1`；禁止为抽取/推进调模型 |
| H5 | **不引入 LC/LangGraph** | 规则表 + 现有 store API |
| H6 | **复用已有 API** | 忌口：`apply_utterance` / `absorb_messages` / `ConstraintStore`；步骤：`set_step_status` / `get_active_goal`；触发：只扩 `detect.py` / `extract.py` 短语表 |
| H7 | **改动面尽量小** | 优先 TUI `send` 钩子顺序 + 短语表；禁止重写 GoalStore schema、禁止改 Host 三行格式、禁止改 RunControl |
| H8 | **fail-open** | absorb / advance 异常吞掉，不得阻断用户发信与 `ask` |

---

## 2. 接线现状（实现前必对照，勿凭记忆）

| 钩子 | 文件:符号 | 现状 | 与缺口关系 |
| --- | --- | --- | --- |
| 1:1 `send` | `local/tui/app.py` `send` ≈1486–1536 | `_consume_routine` →（非群）`_maybe_resume` → **`_maybe_open_goal`** → compact → `ask` | **无** `apply_utterance` / `absorb_messages` → Gap A |
| `_maybe_open_goal` | `app.py:1292` → `goals.store.maybe_open_goal` | 创建时 `_snapshot_constraints` 读卡 | 卡空则 `constraints_ref=[]` |
| 群 absorb | `rooms/digest.py` `prepare_room_transcript` ≈147–149 | 已 `absorb_messages(workspace, items)` | 群路径绿；1:1 未对齐 |
| `apply_utterance` | `constraints/extract.py:32` | 规则 remember/supersede/forget | API 齐，缺 TUI 调用 |
| `set_step_status` | `goals/store.py:215` | 标 status；`completed` 全满则 goal `completed`；至多一 `in_progress` | **仅测试/库 API**；TUI 零调用 → Gap B |
| `default_steps` | `goals/store.py:107` | 健身+饮食：`s1 定训练日` / `s2 配一日三餐` | 推进应对齐标题短语 |
| goal 触发 | `goals/detect.py` `should_create_goal` | `/goal`、`帮我制定`+`计划`、`开始追踪/计划`、模板句 | 面窄 → Gap C |
| routine 触发 | `routines/detect.py` `parse_routine` | 需 cadence 词 +（`提醒` 或 `/routine`）；问句拒绝 | 面窄 → Gap C |
| constraint 触发 | `constraints/extract.py` `_REMEMBER/_LIFT/_FORGET` | 忌口/过敏/不能吃…；其实可以…；忘掉忌口… | 「别再给我海鲜」等漏 → Gap C |
| 1:1 compact flush | `compact/flush.py` | 写 Profile/daily note，**不写** `constraints/card.json` | 评估缺口 4；**本 plan 不做**（H1） |

---

## 3. Gap A — 1:1 吸收忌口进 ConstraintCard

### 3.1 现状（文件/函数级）

- `send`（1:1 分支）在 `touch(s)` 后只调 `_maybe_resume`、`_maybe_open_goal`，**从不**读/写 `constraints/card.json`。
- 群侧 `prepare_room_transcript` 已 absorb；可用性探针复现：先 `remember` 再 `maybe_open_goal` → `constraints_ref` 含海鲜；仅 `maybe_open_goal` 无卡 → `[]`。
- M5 测试覆盖 card/extract API，**不覆盖** TUI 1:1 接线。

### 3.2 根因假设（假设，实现方可证伪）

> **假设 A1**：缺口不是 extract 失效，而是 **1:1 send 漏接 absorb**；与 M5「用户改口即写卡」设计不一致。  
> **假设 A2**：同轮「先开口头忌口再开 goal」要 **absorb 先于 `_maybe_open_goal`**，否则 `_snapshot_constraints` 仍拍到空卡。  
> **假设 A3**：单条消息若同时含忌口词与开 goal 词，`apply_utterance` 会把整句 `remember` 进卡（text=整句）；可接受为最小集；后续可用 topic 归一，**本缺口不强制拆句**。

### 3.3 方案（结果导向）

**主方案 A（推荐，改动最小）**

1. 在 `local/tui/app.py` 增加薄方法，例如 `_absorb_user_constraints(self, text: str) -> None`：
   - `from local.constraints.extract import apply_utterance` + `ConstraintStore`
   - `store = ConstraintStore(self._workspace_dir)`；`card = store.load()`；`updated = apply_utterance(card, text)`；若 `updated is not None`：`store.save(updated)`
   - 或等价：`absorb_messages(workspace, [{"role":"user","content":text}])`（已实现循环，单条即可）
2. 在 1:1 `send` 中，**顺序**固定为：
   ```text
   _consume_routine → … → _maybe_resume → _absorb_user_constraints → _maybe_open_goal → _maybe_advance_step(Gap B) → …
   ```
3. 群路径：`_send_room_turn` **不重复** absorb（仍只靠 `prepare_room_transcript`），避免双写竞态；本缺口验收以 1:1 为主。
4. 异常：`try/except` fail-open，与 `_maybe_open_goal` 同风格。

**备选 A'**：把 absorb 放进 `maybe_open_goal` 内部（开 goal 前对 `user_text` apply）。不推荐：非开 goal 的忌口句（「忌口：海鲜」单独一句）仍写不进卡；且污染 M1 职责。

### 3.4 非目标

- 不把 `memory_flush` 改成写 ConstraintCard（评估缺口 4，另案）。
- 不改 card schema / supersede 语义。
- 不在 assistant 回复上 absorb。
- 不要求同句拆出「纯忌口子串」再 remember（可后续）。

### 3.5 验收标准（可测断言）

| ID | 断言 |
| --- | --- |
| A-T1 | 空 workspace：对文本 `"忌口：海鲜"` 走与 TUI 相同的 absorb 助手函数后，`ConstraintStore(ws).active_texts()` 含 `"忌口：海鲜"`（或 remember 后的等价 active 文本） |
| A-T2 | **顺序**：先 absorb `"忌口：海鲜"`，再 `maybe_open_goal(..., "帮我制定一周健身与饮食计划")` → `goal.constraints_ref` 含海鲜相关 active 文本 |
| A-T3 | 仅 `maybe_open_goal`、从未 absorb/remember → `constraints_ref` 可为 `[]`（行为不变，作对照） |
| A-T4 | absorb `"其实可以吃虾"` 在已有海鲜卡上 → active 为抬升句，旧条 `superseded`（复用现有 extract 语义） |
| A-T5 | `"今天吃什么"` absorb 后卡不变（`classify_utterance` None） |
| A-T6 | 原 E1 / E7 / 群 `prepare_save_absorbs…` 仍绿 |

### 3.6 预期结果（用户可感知）

1:1 聊天直接说「忌口：海鲜」，再开健身饮食计划，Host/注入/`constraints_ref` 能见到忌口，**不必**先 `ConstraintStore.remember` 或绕群路径。

---

## 4. Gap B — 步骤对话驱动推进

### 4.1 现状（文件/函数级）

- `set_step_status(workspace, goal_id, step_id, status)` 已实现：改一步；若标 `in_progress` 则其它 `in_progress`→`pending`；若全部 `completed` 则 `goal.status=completed`。
- TUI / backend / rooms **零调用** `set_step_status`；进度只靠测试或手改 JSON。
- `inject.render_goal_line` / Host「下一步」读 `current_step_title`，窗外清单不随对话前进。
- `default_steps`：健身+饮食 → `s1 定训练日 (in_progress)`，`s2 配一日三餐 (pending)`。

### 4.2 根因假设（假设，实现方可证伪）

> **假设 B1**：缺的是 **send 路径上的规则推进器**，不是 store API。  
> **假设 B2**：最小集用「完成当前步」显式口语 + 可选「下一步」足够；不需要 LLM 判完成。  
> **假设 B3**：匹配应优先对照 **当前 `in_progress` 步的 title 关键词**，避免闲聊误推进。

### 4.3 方案（结果导向）

**主方案 B（推荐）**

1. 在 `local/goals/` 增加纯函数（建议 `store.py` 旁或同文件底部，**不新建包**），例如：
   - `parse_step_advance(user_text: str) -> str | None`  
     返回 `"complete_current"` | `"complete_and_next"` 语义即可；或直接暴露：
   - `maybe_advance_goal(workspace, space_id, user_text) -> LifeGoal | None`
2. 规则（零 LLM，中英文可只做中文最小集）：
   - **无** `get_active_goal` → 返回 None。
   - 完成类短语（示例，实现可微调但测试钉死）：`定好了`、`训练日定好了`、`这步完成了`、`完成了`、`好了，下一步`、`下一步`、`继续下一步`、以及 **当前步 title 子串 +（好了/定了/完成）**（如 title=`定训练日` 且文本含 `训练日` 且含 `定好|好了|完成`）。
   - 命中后：找唯一 `in_progress` 步 → `set_step_status(..., step_id, "completed")`；若存在后续 `pending`，再 `set_step_status(..., next_id, "in_progress")`；若无后续且全完成，依赖现有 store 把 goal 标 `completed`。
   - **拒绝**：纯问句（含 `吗`/`？`/`什么`）、短问答黑名单（与 E9 对齐的「今天吃什么」等）、无活跃 goal。
3. TUI：`send` 在 `_maybe_open_goal` **之后**调 `_maybe_advance_step(s, text)`（内部调 `maybe_advance_goal`）；可选 `notice` 一行「已完成：定训练日 → 下一步：配一日三餐」（fail-open，无 notice 也可，但建议有便于探针）。
4. **不**在 routine 消费路径、compact 命令路径推进。

**备选 B'**：仅 `/done`、`/step done` 斜杠命令。更稳但日用不如口语；可作为短语表补充，**不能**作为唯一入口（否则难称稳达）。

### 4.4 非目标

- 不自动根据模型回复内容推进（禁 LLM 判完成）。
- 不支持任意跳步/重排 steps schema。
- 不每条消息写 checkpoint（仍只 M2 取消/预算事件）。
- 不把「今天吃什么」建成 goal 或推进步。

### 4.5 验收标准（可测断言）

| ID | 断言 |
| --- | --- |
| B-T1 | 建默认健身饮食 goal 后，`maybe_advance_goal(..., "训练日定好了")` → `s1.status==completed` 且 `s2.status==in_progress`；仍至多一个 `in_progress` |
| B-T2 | 再 `"一日三餐配好了"` 或 `"这步完成了"`（在 s2 in_progress 时）→ s2 completed；若仅两步则 `goal.status==completed` |
| B-T3 | `"今天吃什么"` / `"现在几点"` → goal 步骤不变 |
| B-T4 | 无活跃 goal 时 advance → None，不抛、不建 goal |
| B-T5 | 直接 `set_step_status` 的 E2 行为不变 |
| B-T6 | Host/注入读到的「下一步」标题在推进后变为新 `in_progress` 标题（可用 `current_step_title` / `render_goal_line` 断言） |

### 4.6 预期结果（用户可感知）

说「训练日定好了」后，窗外步骤从「定训练日」切到「配一日三餐」，群 Host「下一步」与 ephemeral 目标行同步更新，不必手改 JSON 或调测试 API。

---

## 5. Gap C — 触发偏关键词（goal / routine / constraint）

### 5.1 现状（文件/函数级）

- `goals/detect.py`：硬编码少量短语；`"一周锻炼餐单"` 类不命中；`"帮我做个健身饮食安排"` 可能不命中（无「计划」且无「制定一个计划」整句）。
- `routines/detect.py`：无「提醒」且非 `/routine` → None；「每周一叫我称重」易漏。
- `constraints/extract.py`：`_REMEMBER` 无「别再给我」「不要再上」等；「别再给我海鲜」→ `classify_utterance` None。

### 5.2 根因假设（假设，实现方可证伪）

> **假设 C1**：稳达只需 **同义短语表扩面**（仍规则、仍拒短问答），不需要分类模型。  
> **假设 C2**：扩面必须带 **负例钉死**（E9、例程问句、闲聊），否则误建 goal/误建 routine 比漏触发更伤日用。  
> **假设 C3**：constraint 扩面与 Gap A 正交：先能 classify，再靠 A 写入；只扩 extract 不接 TUI 仍不稳达。

### 5.3 方案（结果导向）

**主方案 C（推荐）：三处短语表最小扩面 + 负例测试**

| 文件 | 扩面方向（示例，实现以测试为准） | 必须仍为 False/None |
| --- | --- | --- |
| `goals/detect.py` | 增加计划同义：`做个…计划/安排`、`安排一周…健身/饮食/锻炼`、`一周…餐单/饮食计划`、`帮我安排…训练+饮食`；保留 `/goal` 与模板 | `今天吃什么`、`吃什么好`、`今天天气呢`；无「计划/安排/追踪/制定」的纯闲聊 |
| `routines/detect.py` | cadence 同义保持；触发动词扩：`叫我`、`喊我`、`提醒我`（已有）、`到点告诉我`；`/routine` 不变 | 含 `吗/？/什么`；无 cadence 的「提醒我一下」（无每天/每周/一次） |
| `constraints/extract.py` | `_REMEMBER` 增：`别再给`、`不要再`、`别给我`、`以后别`、`千万别再`；必要时 `_LIFT` 增口语 | 问句；纯「海鲜」无限制动词 |

**备选 C'**：每轮 LLM 分类。**禁止**（H4/H5）。

实现注意：

- 只改元组/条件，**不**改 store 对外 API。
- goal：继续「短问答硬拒」优先于正例（现有 `吃什么` 且无计划/追踪 → False 逻辑保留并覆盖新正例冲突时以测试表为准）。
- constraint：`别再给我海鲜` → `remember`；topic_key 若抽不到主题，整句入卡可接受（与现 remember 一致）。

### 5.4 非目标

- 不做模糊语义检索 / embedding。
- 不降低「显式意图」门槛到任何含「健身」就建 goal。
- 不改 SoftRoutine「确认才跑」门闩。

### 5.5 验收标准（可测断言）

| ID | 断言 |
| --- | --- |
| C-T1 | `should_create_goal("帮我安排一周锻炼和饮食")` 或钉死的等价扩面句 → True；`should_create_goal("今天吃什么")` → False |
| C-T2 | `should_create_goal("做个一周健身饮食计划")` → True（若采用该扩面句） |
| C-T3 | `parse_routine("每周一叫我称重")` → dict 且 `cadence=="weekly"`（或文档钉死的同义句）；`parse_routine("今天吃什么")` is None |
| C-T4 | `classify_utterance("别再给我海鲜") == "remember"`；`apply_utterance` 后 active 含该限制 |
| C-T5 | 原 E9、E12 相关用例全绿；新增负例不少于 3 条（goal/routine/constraint 各 ≥1） |

### 5.6 预期结果（用户可感知）

换几种常见说法仍能：建计划、记忌口、建提醒；问句与「今天吃什么」仍安静。

---

## 6. 实现顺序（依赖）

```text
① Gap A（1:1 absorb）     —— 无依赖；立刻让 constraints_ref 日用可用
② Gap C-constraint 扩面   —— 可与 A 同批；先有 classify 再 absorb 才有体感
③ Gap B（步骤推进）       —— 依赖活跃 goal；不依赖 A，但建议 A 之后测注入行
④ Gap C-goal / C-routine  —— 与 B 并行亦可；最后统一回归
收尾：原 146 + 新测全绿；六场景探针不回退 + 扩展探针；打 tarball
```

**同批规则**：每完成一个 Gap 的代码 + 该 Gap 测试全绿，才进下一 Gap；禁止三缺口一把梭再测。

---

## 7. Cursor 交办清单

### 7.1 Model 设置（用户偏好，勿改）

- Cursor 模型：**grok-4.7**
- **非** fast
- `reasoning_effort=**xhigh**`
- 附件：本文件 + `long_horizon_harness_usability_eval_zh.md` + `long_horizon_harness_acceptance_zh.md`

### 7.2 逐项测命令（实现中）

```bash
cd /workspace/LightAgent
export LIGHTAGENT_FORBID_OPENROUTER=1
export PYTHONPATH=.

# Gap A
/workspace/la-venv/bin/python -m pytest local/constraints/tests local/goals/tests/test_m1_life_goal.py -q

# Gap B
/workspace/la-venv/bin/python -m pytest local/goals/tests -q

# Gap C
/workspace/la-venv/bin/python -m pytest \
  local/goals/tests/test_m1_life_goal.py \
  local/routines/tests/test_m7_soft_routine.py \
  local/constraints/tests/test_m5_constraint_card.py -q

# 全局回归（必须）
/workspace/la-venv/bin/python -m pytest \
  local/rooms local/conversations local/memory local/compact/tests \
  local/goals local/routines local/constraints local/checkpoints \
  local/harness/tests -q
```

### 7.3 须新增/扩展的 pytest（建议文件名，可合并进现有 test 文件）

| 文件 | 内容 |
| --- | --- |
| `local/constraints/tests/test_m5_constraint_card.py` 或 `test_stable_gap_a_absorb.py` | A-T1…A-T5；可用纯库函数测 absorb 顺序，不必起 Textual |
| `local/goals/tests/test_stable_gap_b_advance.py`（或并入 `test_m1_life_goal.py`） | B-T1…B-T6 |
| `local/goals/tests/…` / `routines/tests/…` / `constraints/tests/…` | C-T1…C-T5 正负例表 |
| 可选 | 对 `app.py` 抽取出的 `_absorb_user_constraints` / advance 若难测 UI，则把核心逻辑放纯函数，TUI 只调用——**推荐** |

### 7.4 Mock 探针扩展（pytest 以外，对齐 `/tmp/lh_probe.py` 风格）

在原六场景不回退前提下新增：

| 新场景 | 期望 |
| --- | --- |
| S7 | 1:1：absorb「忌口：海鲜」→ open goal「帮我制定一周健身与饮食计划」→ `constraints_ref` 含海鲜；`NETWORK_CALLS` 不增 |
| S8 | 有默认两步 goal →「训练日定好了」→ s1 completed / s2 in_progress |
| S9 | 「别再给我海鲜」→ 卡 active 含限制；「每周一叫我称重」→ routine 可 create（仍不跑模型） |

### 7.5 完成后交付

1. 代码 + 新测全绿日志  
2. 更新或附录：`local/research/long_horizon_harness_acceptance_zh.md`（可加 E13–E15 三缺口勾选，**不改** E1–E12 原文语义）  
3. 短评：`local/research/long_horizon_stable_gap_usability_note_zh.md`（半页即可：是否达「稳达」）  
4. Tarball：`artifacts/lightagent-long-horizon-stable-gap.tgz`（含改动的 `local/`），并记录 sha256  

```bash
mkdir -p /workspace/LightAgent/artifacts
# 在 LightAgent 根打包改动树（实现方按实际路径调整）
tar -czf artifacts/lightagent-long-horizon-stable-gap.tgz \
  local/constraints local/goals local/routines local/tui/app.py \
  local/research/long_horizon_stable_gap_plan_zh.md \
  local/research/long_horizon_stable_gap_usability_note_zh.md \
  local/research/long_horizon_harness_acceptance_zh.md
sha256sum artifacts/lightagent-long-horizon-stable-gap.tgz
```

---

## 8. 回归闸

| 项 | 要求 |
| --- | --- |
| 原 pytest | **146 + 新增用例** 全绿（总数 ≥146，禁止删旧测凑绿） |
| E1–E12 | 全部仍通过 |
| 原六场景探针 | S1–S6 不回退 |
| 网络 | `LIGHTAGENT_FORBID_OPENROUTER=1` 下 create/absorb/advance/parse **零** OpenRouter |
| 落盘 | 仍无 `<memory-context>` |
| 例程 | 创建不跑模型；确认才跑 |

---

## 9. 不做清单

- 不启动本 plan 范围外的模块（Dreaming、Host LLM、OS sandbox、ToT、推送）  
- 不接真 OpenRouter / 付费模型做抽取或判步完成  
- 不引入 LangChain / LangGraph  
- 不修「compact flush ≠ ConstraintCard」双通道（另开 plan）  
- 不改 M0 ephemeral 不变量、M4 取消/预算语义、M6 三行格式  
- 不把 pack 写入 transcript  
- 不扩大 LifeGoal 到「闲聊自动建目标」  
- 本文件阶段：**不改 `.py`、不启动 Cursor**（仅文档）

---

## 10. 给 Cursor 的 10 行摘要

1. 只修三缺口：A 1:1 absorb、B 对话推进步骤、C 短语扩面。  
2. A：`send` 在 `_maybe_open_goal` **前**调用 `apply_utterance`/`absorb_messages`；fail-open。  
3. B：纯函数 `maybe_advance_goal` + 完成口语 → `set_step_status` completed → 下一 pending in_progress。  
4. C：只扩 `detect.py` / `extract.py` 元组；钉死负例。  
5. 禁止 LLM / LC / LangGraph / 真 OpenRouter。  
6. 不新建模块目录；复用现有 API。  
7. 每 Gap 测绿再进下一个。  
8. 全局：`LIGHTAGENT_FORBID_OPENROUTER=1` pytest 原套件 + 新测。  
9. 探针 S1–S6 不回退，加 S7–S9。  
10. 打 `artifacts/lightagent-long-horizon-stable-gap.tgz` 并写半页稳达判定。

---

## 11. 验收条数汇总（供回报告）

| Gap | 验收条 ID | 条数 |
| --- | --- | --- |
| A 1:1 忌口 | A-T1 … A-T6 | **6** |
| B 步骤推进 | B-T1 … B-T6 | **6** |
| C 触发扩面 | C-T1 … C-T5 | **5** |
| **合计** | | **17** |

另：回归闸（原 146、E1–E12、S1–S6、S7–S9、零网络）为交付门禁，不计入上表 17。
