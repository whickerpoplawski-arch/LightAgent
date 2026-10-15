# 长链路日用体验评估：4 天 × 10 段（MX 真模型试用）

日期：2026-10-15（America/Martinique, UTC-4 / AST）  
评估方：Grok Bot executor  
剧本：`local/research/long_horizon_4day_dialogue_script_zh.md`  
对照 mock：`long_horizon_4day_ux_eval_zh.md`（40/40 PASS，总评「稳达」）  
对照上次 live：`long_horizon_4day_live_ux_eval_zh.md`（OpenRouter KEY 过期，总评「勉强」，成功真模型回复 0）  
探针：`/tmp/lh_4day_mx_probe.py` → 日志 `/tmp/lh_4day_mx_out.txt` / 汇总 `/tmp/lh_4day_mx_summary.json`  
环境：`LIGHTAGENT_ALLOW_OPENROUTER=1`（未设 FORBID），`PROVIDER=mx`，`PYTHONPATH=.`，`/workspace/la-venv/bin/python`  
workspace：`/tmp/lh_4day_mx_ws`（同一目录跨 4「天」）  
后端：Textual `run_test` + `GuardedOpenRouterBackend` → MX `https://api.mxzzz.xyz/v1`  
模型：`deepseek-v4.1-flash`，`reasoning_effort=low`  
说明：父进程已确认 MX smoke「用一句中文说你好」OK，本探针跳过再 smoke，直接跑剧本。

---

## 1. 总评

**总评：稳达（相对 mock「稳达」持平；相对上次 live「勉强」回升两档）。**

两层都过关：

1. **Harness / TUI 发送钩子**：40/40 PASS（0 PARTIAL / 0 FAIL）。忌口 absorb、口语推进、例程先记账后确认、cancel/resume 同 `goal_id`、Host 三行、compact 保忌口、Memory pin「小Q」、落盘无 `<memory-context>`、短问不建目标 —— 与 mock「稳达」一致。  
2. **真模型回复**：成功 live 回复 **21/21**（另 D3-01 走 TUI confirm 的 live `_routine_runner`，usage+1，非 chat 气泡）。抽检 10 段「是否顺着忌口/步骤」启发式 **yes=10 / weak=0 / no=0**。助手会主动记忌口、避开海鲜/花生、在推进时提「下一步」，短问答不乱建一周计划。

上次「勉强」的根因（OpenRouter KEY 过期、0 次可读回复）已消除。本轮可评「说人话」的日用体感。

D3-01 首跑曾因探针只在 `LIVE_AUTH_DEAD` 时挂 mock runner 而误标 FAIL；核对 `last_run_at` / `next_due_at` 后确认 TUI live confirm 已成功，汇总已更正为 PASS，探针逻辑已补丁避免再误判。

---

## 2. 跑测摘要

| 项 | 结果 |
| --- | --- |
| 段数 | 40（Day1–4 × 10） |
| PASS / PARTIAL / FAIL | **40 / 0 / 0** |
| live 对话段（backend.chat） | 21 成功 |
| live 例程 confirm（_routine_runner） | 1（D3-01，称重） |
| harness-only 段 | 18 |
| 成功真模型回复 | **21**（chat）+ 1 confirm runner |
| usage_today | 开始 **1** → 结束 **26**（本探针 burn **25**） |
| 日限 / 预留 / 上限 | 200 / 30 / 有效预算 170 |
| provider / model / effort | mx / deepseek-v4.1-flash / low |
| Follow 抽检 | yes=10 weak=0 no=0 no-live=0 |
| LifeGoal | 建成 2；均 completed；短问从未新建 |
| SoftRoutine | weekly「称重」创建零 chat；确认后 live runner 跑 1 次 |
| 落盘 | workspace 内无 `<memory-context>` |
| auth_dead | False |

---

## 3. 分天结果表

### Day 1 — 建目标 + 忌口 + 推进一步 + 负例

| ID | 结果 | 模式 | 证据摘要 |
| --- | --- | --- | --- |
| D1-01 | PASS | live | 「今天吃什么」不建 goal；模型给快餐建议 |
| D1-02 | PASS | live | absorb→`忌口：海鲜`；回复「海鲜记下了…避开鱼虾蟹贝」 |
| D1-03 | PASS | live | goal 建起 + `constraints_ref` 含海鲜；回复点名「定训练日」并提避开海鲜 |
| D1-04 | PASS | live | 「今天天气呢」步骤不变；模型追问城市 |
| D1-05 | PASS | live | 「训练日定好了」→ s1 completed / s2 in_progress；模型确认进度但要具体天数 |
| D1-06 | PASS | live | 「现在几点」不推进；报了本地时间 |
| D1-07 | PASS | live | 「提醒我一下」parse_routine None；模型坦诚无定时推送 |
| D1-08 | PASS | harness | Host 三行，忌口含海鲜 |
| D1-09 | PASS | harness | sanitize 无 memory-context |
| D1-10 | PASS | harness | 跨段 goal/海鲜/s2 残留 OK |

**日体验**：忌口进卡后模型立刻改口；建计划时对齐「下一步」。小摩擦：用户说「训练日定好了」后 harness 已推进，模型仍追问「哪几天」——状态机与对话理解略脱节。

### Day 2 — 续跑 / 改口忌口 + 例程待确认

| ID | 结果 | 模式 | 证据摘要 |
| --- | --- | --- | --- |
| D2-01 | PASS | harness | 同 goal_id，s2 in_progress |
| D2-02 | PASS | live | 海鲜 superseded；active=「其实可以吃虾」；模型改为「虾能吃」 |
| D2-03 | PASS | live | 花生入卡；回复明确「不会再出现花生」 |
| D2-04 | PASS | live | 「吃什么好」不建不推；按忌口给两套快选（含虾仁、无花生） |
| D2-05 | PASS | harness | 「每周一叫我称重」weekly，usage_delta=0 |
| D2-06 | PASS | harness | due 可列，runner=0 |
| D2-07 | PASS | live | 「我想健身」不建；模型续挂着的训练日线程 |
| D2-08 | PASS | harness | prepare 109→41，花生保留 |
| D2-09 | PASS | harness | pin「叫我小Q」 |
| D2-10 | PASS | harness | goal/例程/花生齐 |

**日体验**：改口抬升（虾可吃）与新增花生忌口，模型都跟上；「吃什么好」短答带忌口，体感最好的一天。

### Day 3 — 确认例程 + cancel/resume + 同义再建

| ID | 结果 | 模式 | 证据摘要 |
| --- | --- | --- | --- |
| D3-01 | PASS | live | TUI confirm「称重」；`last_run_at` 写入，next_due+7d，usage+1 |
| D3-02 | PASS | harness | paused + checkpoint `user_cancel` |
| D3-03 | PASS | live | 「继续」resume 同 goal_id；模型给出一周训练草稿 |
| D3-04 | PASS | live | goal1 completed；回复「下一步…三餐」 |
| D3-05 | PASS | live | 同义建新 goal2；完整一周模板 |
| D3-06 | PASS | live | 已有 open → 复用同一 goal_id |
| D3-07 | PASS | live | cancel+「接着来」同 id；细化周一克数 |
| D3-08 | PASS | live | 「定好了」→ s1 done / s2 in_progress |
| D3-09 | PASS | live | 裸词「海鲜」不入卡；模型复述当前忌口规则 |
| D3-10 | PASS | harness | 新 goal active；旧 completed；花生仍在 |

**日体验**：cancel/resume 与同义再建钩子稳；模型长回复偏「一次给完整周计划」，信息密度高但略抢步。

### Day 4 — 综合回顾、负例、完成、残留

| ID | 结果 | 模式 | 证据摘要 |
| --- | --- | --- | --- |
| D4-01 | PASS | harness | 跨天花生 + GOAL2 |
| D4-02 | PASS | live | 「今天吃什么」不建不推；按休息日给清淡餐 |
| D4-03 | PASS | live | 「一日三餐配好了」直接 completed（未走 fallback） |
| D4-04 | PASS | live | 无 active goal；仍给忌口友好快答 |
| D4-05 | PASS | harness | Host 三行，忌口行含花生相关 |
| D4-06 | PASS | harness | 109→41 保忌口 |
| D4-07 | PASS | harness | pin「小Q」仍在 |
| D4-08 | PASS | harness | usage 26 ≤ cap 170 |
| D4-09 | PASS | harness | 落盘无 memory-context |
| D4-10 | PASS | harness | completed=2；constraints≥1；routines≥1；无 open |

**日体验**：跨天忌口与 pin 仍在；收尾干净。模型在 goal 已完成后仍能按忌口答「吃什么好」。

---

## 4. 「顺着忌口 / 步骤」专项

| 抽检 | 期待 | 得分 | 摘要 |
| --- | --- | --- | --- |
| D1-01 | short_qa | yes | 短答不建计划 |
| D1-02 | avoid_seafood | yes | 明确记下并避开海鲜 |
| D1-03 | avoid_seafood | yes | 建计划时提避开海鲜 + 定训练日 |
| D1-05 | step_progress | yes | 确认进度并追问细节 |
| D2-03 | avoid_peanut | yes | 花生（含花生油）写入回避 |
| D2-04 | short_qa | yes | 按忌口给快选 |
| D3-04 | step_progress | yes | 宣布下一步配三餐 |
| D3-05 | avoid_peanut | yes | 新计划上下文保留忌口线索 |
| D3-08 | step_progress | yes | 当作定稿并挂待办 |
| D4-02 | short_qa | yes | 休息日清淡餐、不新建 goal |

**结论**：在 MX `deepseek-v4.1-flash` + effort=low 下，对话层能跟着约束卡与步骤走；这是上次 live「勉强」缺的关键能力，本轮补上。

---

## 5. 最痛 3 点（仍可改进）

1. **状态机推进 vs 模型理解脱节**：用户说「训练日定好了」后 harness 已把 s1→completed，模型仍说「还没收到具体哪几天」。口语完成信号没有可靠注入到 prompt/系统说明，助手会「没听见」已完成的步骤。  
2. **粘性续聊偏强**：短句如「我想健身」「今天天气呢」时，模型常把挂起的训练日/城市追问再扯回来，短问答体感略吵（虽未误建 LifeGoal）。  
3. **例程 confirm 探针易误判 / live runner 必烧 1 次**：TUI live `_routine_runner` 会 `_check_and_count`+`make_agent`；探针若只在 auth_dead 时挂 mock，会把成功 confirm 计成 FAIL。产品侧「确认才跑」正确，但观测与额度预期要写清（本轮已修探针）。

次要：忌口整句入卡（「别再给我花生」）Host 行略生硬；compact flush 仍不写忌口卡（与稳达边界一致，未测破）。

---

## 6. 与既往评估对照

| 轮次 | 条件 | 段结果 | 真模型成功 | 总评 |
| --- | --- | --- | --- | --- |
| mock 4 天 | FORBID，库测 | 40/40 | 0（故意） | 稳达 |
| OpenRouter live | KEY 过期 | 39/1/0 | 0 | 勉强 |
| **MX live（本轮）** | mx + flash + low | **40/0/0** | **21 chat + 1 confirm** | **稳达** |

---

## 7. 产物路径

- 探针：`/tmp/lh_4day_mx_probe.py`  
- 日志：`/tmp/lh_4day_mx_out.txt`  
- 汇总：`/tmp/lh_4day_mx_summary.json`  
- 本报告：`local/research/long_horizon_4day_mx_live_ux_eval_zh.md`  
- workspace：`/tmp/lh_4day_mx_ws`
