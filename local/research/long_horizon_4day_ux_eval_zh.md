# 长链路日用体验评估：4 天 × 10 段对话

日期：2026-10-14（America/Martinique, UTC-4）  
评估方：Grok Bot executor  
剧本：`local/research/long_horizon_4day_dialogue_script_zh.md`  
探针：`/tmp/lh_4day_probe.py` → 日志 `/tmp/lh_4day_probe_out.txt` / 汇总 `/tmp/lh_4day_probe_summary.json`  
环境：`LIGHTAGENT_FORBID_OPENROUTER=1`，`PYTHONPATH=.`，`/workspace/la-venv/bin/python`  
workspace：`/tmp/lh_4day_ws`（同一目录跨 4「天」，day 边界为注释时间戳）  
对照：`long_horizon_stable_gap_usability_eval_zh.md`（先前总评「稳达」）

---

## 1. 总评

**总评：稳达（维持）。**

理由：按生活助手向剧本，同一 workspace 连续跑完 **40 段对话探针 → 40 PASS / 0 PARTIAL / 0 FAIL**；覆盖建目标与短问不建、1:1 忌口 absorb→`constraints_ref`、口语推进、例程「创建不跑 / 确认才跑」、cancel/resume 同 `goal_id`、Host 三行与群 compact 保忌口、同义正例与闲聊负例、跨天 goal/约束/Memory pin、落盘无 `<memory-context>`、全程 `NETWORK_CALLS` 0→0。未改生产业务代码。相对「稳达」补丁后的日用预期，**未回退**。

仍属「日用可感、非万能」：群路径不推进步骤；忌口靠规则短语非整句语义；无真 OpenRouter 烟测——与先前稳达残留一致，不挡本标签。

---

## 2. 跑测摘要

| 项 | 结果 |
| --- | --- |
| 段数 | 40（Day1–4 × 10） |
| PASS / PARTIAL / FAIL | **40 / 0 / 0** |
| NETWORK_CALLS | 0→0 |
| LifeGoal | 建成 2；均走完 completed；短问从未新建 |
| ConstraintCard | 海鲜→抬升「其实可以吃虾」；「别再给我花生」跨天仍 active |
| SoftRoutine | weekly 创建零 runner；确认后 mock runner=1 |
| Checkpoint | user_cancel → resume 同 id（「继续」「接着来」） |
| Host / compact | 三行结构稳；109→41 且忌口线索保留 |
| Memory pin | 「叫我小Q」learn+pin，Day4 重开 sqlite 仍在 |
| 落盘 | workspace 内无 `<memory-context>` |

---

## 3. 分天结果表

### Day 1 — 建目标 + 忌口 + 推进一步 + 负例

| ID | 结果 | 证据摘要 |
| --- | --- | --- |
| D1-01 | PASS | 「今天吃什么」不建 goal |
| D1-02 | PASS | absorb → `['忌口：海鲜']` |
| D1-03 | PASS | goal `997b4771c4a5`，`constraints_ref` 含海鲜 |
| D1-04 | PASS | 「今天天气呢」不推进 |
| D1-05 | PASS | 「训练日定好了」→ s1 completed / s2 in_progress |
| D1-06 | PASS | 「现在几点」不推进 |
| D1-07 | PASS | 「提醒我一下」parse_routine None |
| D1-08 | PASS | Host 三行，忌口行含海鲜 |
| D1-09 | PASS | sanitize 后无 memory-context |
| D1-10 | PASS | 跨段：goal active + 海鲜卡 + s2 |

**日体验**：开场短问安全；先说忌口再开计划能进 ref；口语推进一步清晰；闲聊不误触。

### Day 2 — 续跑 / 改口忌口 + 例程待确认

| ID | 结果 | 证据摘要 |
| --- | --- | --- |
| D2-01 | PASS | 跨天同一 goal_id，s2 仍 in_progress |
| D2-02 | PASS | 海鲜 superseded；active=「其实可以吃虾」 |
| D2-03 | PASS | 「别再给我花生」入卡 |
| D2-04 | PASS | 「吃什么好」不建不推 |
| D2-05 | PASS | 「每周一叫我称重」weekly，create 零网 |
| D2-06 | PASS | due 可列，runner 仍 0 |
| D2-07 | PASS | 「我想健身」不建 goal |
| D2-08 | PASS | prepare 109→41，花生保留 |
| D2-09 | PASS | pin_id 落盘 |
| D2-10 | PASS | goal/例程/花生约束齐 |

**日体验**：改口抬升符合预期；例程「先记账不跑」正确；负例「我想健身」护住。

### Day 3 — 确认例程 + cancel/resume + 同义再建

| ID | 结果 | 证据摘要 |
| --- | --- | --- |
| D3-01 | PASS | 确认提醒，runner=1，带 budget/token |
| D3-02 | PASS | paused + checkpoint `user_cancel` |
| D3-03 | PASS | 「继续」同 goal_id，半执行 notice 在 |
| D3-04 | PASS | 「这步完成了」→ goal completed |
| D3-05 | PASS | 「做个一周健身饮食计划」新 goal `7881fd027dde` |
| D3-06 | PASS | 「帮我安排一周锻炼和饮食」复用同一 open goal |
| D3-07 | PASS | 再 cancel +「接着来」同 id |
| D3-08 | PASS | 「定好了」→ s1 done / s2 in_progress |
| D3-09 | PASS | 单字「海鲜」不入卡 |
| D3-10 | PASS | 新 goal active；旧 completed；花生仍在 |

**日体验**：打断续跑叙事完整；同义建目标与「已有则复用」符合最小集；裸词忌口不误记。

### Day 4 — 综合回顾 / 负例 / 完成 / 残留

| ID | 结果 | 证据摘要 |
| --- | --- | --- |
| D4-01 | PASS | 跨天花生 + 同 GOAL2 |
| D4-02 | PASS | 「今天吃什么」不建不推 |
| D4-03 | PASS | 「一日三餐配好了」标题命中 → completed |
| D4-04 | PASS | 无 active goal |
| D4-05 | PASS | Host 三行，忌口含花生/抬升 |
| D4-06 | PASS | 109→41 忌口保留 |
| D4-07 | PASS | pin「叫我小Q」仍在 |
| D4-08 | PASS | NETWORK_CALLS 0→0 |
| D4-09 | PASS | 落盘无 memory-context |
| D4-10 | PASS | completed=2；约束 2；例程 1；无 open |

**日体验**：收束干净；跨天 pin/约束/已完成目标可回顾；网闸与落盘红线未破。

---

## 4. 能力覆盖核对

| 能力 | 覆盖段 | 判定 |
| --- | --- | --- |
| LifeGoal 创建 / 短问不建 | D1-01/03，D2-04/07，D3-05/06，D4-02/04 | 达 |
| 1:1 忌口 → constraints_ref | D1-02/03，D2-02/03，D4-01 | 达 |
| 口语步骤推进 | D1-05，D3-04/08，D4-03 | 达 |
| SoftRoutine 创建不跑 / 确认才跑 | D2-05/06，D3-01 | 达 |
| cancel / resume | D3-02/03/07 | 达 |
| Host 三行 / 群 compact | D1-08，D2-08，D4-05/06 | 达（库测） |
| 同义正例 + 负例 | D1-07，D2-07，D3-05/06/09，D4-02 | 达 |
| 跨天 goal/约束；Memory pin | D2-01/09/10，D4-01/07 | 达 |
| 落盘无 memory-context | D1-09，D4-09 | 达 |
| 群聊步骤推进 | — | **未测**（已知 1:1 才挂 advance；报告注明） |

---

## 5. 使用体验：痛点（最痛 3 点）

即便 40/40，从「真人连聊四天」角度仍有感：

1. **触发仍靠短语表，说法一偏就「没反应」**  
   「我想健身」「提醒我一下」「海鲜」单独出现都正确地不触发——但对用户像「助手没听见」。要稳达到「懂你」，还需更多同义或显式引导话术（本评估不改代码）。

2. **群聊不能靠说话推进步骤**  
   剧本刻意以 1:1 为主；若用户在 Host 群里说「训练日定好了」，当前设计不会改 step。跨场景一致性仍是日用裂缝。

3. **忌口整句入卡、抬升靠整句主题**  
   Host 忌口行会出现「其实可以吃虾、别再给我花生」并列；语义正确但展示略生硬；同句「忌口+开计划」未做拆条（稳达 plan 已接受）。compact flush 仍**不**写忌口卡——忘了 absorb 的路径会空。

次要：无 GUI/真模型烟测，回复文案质量本评估不评分；例程确认话术固定「确认提醒」，更口语的「跑吧」未覆盖。

---

## 6. 是否仍「稳达」

| 维度 | 结论 |
| --- | --- |
| 相对 stable_gap 补丁后「稳达」 | **维持稳达**，未回退 |
| 相对「个人助手日用预期」 | 规则路径下连续四天脚本行为可预期、可续跑、可取消恢复 |
| 相对「懂自由对话的真人助理」 | 仍差一口气（痛点 1–3）；不降至「勉强」，因红线能力全绿且跨天状态机稳 |

**一句话**：40 段 mock 日用全绿，长链路状态与约束续得住，**总评稳达**；最影响体感的是短语触发面、群不推进、忌口展示/flush 缺口。

---

## 7. 路径索引

| 用途 | 路径 |
| --- | --- |
| 剧本 + 预期 | `local/research/long_horizon_4day_dialogue_script_zh.md` |
| 本评估 | `local/research/long_horizon_4day_ux_eval_zh.md` |
| 探针脚本 | `/tmp/lh_4day_probe.py` |
| 探针日志 | `/tmp/lh_4day_probe_out.txt` |
| 汇总 JSON | `/tmp/lh_4day_probe_summary.json` |
| 跑测 workspace | `/tmp/lh_4day_ws` |
