# 长链路日用体验评估：4 天 × 10 段（真 TUI / 真模型试用）

日期：2026-10-14（America/Martinique, UTC-4 / AST）  
评估方：Grok Bot executor  
剧本：`local/research/long_horizon_4day_dialogue_script_zh.md`  
对照 mock：`long_horizon_4day_ux_eval_zh.md`（40/40 PASS，总评「稳达」）  
探针：`/tmp/lh_4day_live_probe.py` → 日志 `/tmp/lh_4day_live_out.txt` / 汇总 `/tmp/lh_4day_live_summary.json`  
环境：`LIGHTAGENT_ALLOW_OPENROUTER=1`（未设 FORBID），`PYTHONPATH=.`，`/workspace/la-venv/bin/python`  
workspace：`/tmp/lh_4day_live_ws`（同一目录跨 4「天」）  
后端：Textual `run_test` + `GuardedOpenRouterBackend`（继承 `OpenRouterBackend`；认证死亡后不再烧额度）

---

## 1. 总评

**总评：勉强（相对 mock「稳达」回落一档）。**

理由分两层：

1. **Harness / TUI 发送钩子（absorb → open → advance → routine/resume）**：按剧本跑完 **40 段 → 39 PASS / 1 PARTIAL / 0 FAIL**；忌口进卡、口语推进、例程先记账后确认、cancel/resume 同 `goal_id`、Host 三行、compact 保忌口、Memory pin、落盘无 `<memory-context>`、短问不建目标等与 mock「稳达」一致。**产品侧门禁未回退。**
2. **真模型回复**：开跑前 smoke `run_free("用一句中文说你好")` 即返回 `[LA-401] Authentication failed`；OpenRouter `auth/key` 探测明确 **`API key expired`**。为遵守「预留 ≥5、勿死循环烧额度」，后续 21 段本应 live 的用户原话经 TUI `prompt+enter` 走完整 send 路径，但 **chat 层短路为 `[LIVE BLOCKED]`，0 次成功模型回复、models_used=[]**。因此「真模型体感」无法兑现，相对「按剧本真 TUI/真模型试用」目标只能标 **勉强**，不能维持 mock 的「稳达」标签。

不是业务回归：是 **密钥过期阻断**。换有效 `:free` KEY 后应可原探针复跑。

---

## 2. 跑测摘要

| 项 | 结果 |
| --- | --- |
| 段数 | 40（Day1–4 × 10） |
| PASS / PARTIAL / FAIL | **39 / 1 / 0** |
| live 标注段（含 live-blocked） | 21 |
| harness-only 段 | 19 |
| 成功真模型回复 | **0** |
| usage_today | 开始 **1** → 结束 **2**（本探针 burn **1** = smoke） |
| 日限 / 预留 / 上限 | 45 / ≥5 / 有效预算 40 |
| NETWORK_CALLS（进程内） | smoke 计入；后续 live 短路不再 `_check_and_count` |
| 用过的模型 | smoke 尝试 `nvidia/nemotron-3-super-120b-a12b:free`（401）；成功列表空 |
| LifeGoal | 建成 2；均 completed；短问从未新建 |
| SoftRoutine | weekly 创建零模型；确认 mock runner=1（live runner 因 auth 改走安全 runner） |
| 落盘 | workspace 内无 `<memory-context>` |

PARTIAL 仅 **D3-01**：harness 确认门闩 PASS，但真模型例程 runner 未跑（auth blocked）→ 标 PARTIAL。

---

## 3. 分天结果表（live vs harness）

图例：`live-blocked` = TUI send 已执行 harness，模型层因 KEY 过期短路；`harness` = 纯库/状态检查。

### Day 1 — 建目标 + 忌口 + 推进一步 + 负例

| ID | 结果 | 模式 | 证据摘要 |
| --- | --- | --- | --- |
| D1-01 | PASS | live-blocked | 「今天吃什么」不建 goal |
| D1-02 | PASS | live-blocked | absorb → `['忌口：海鲜']` |
| D1-03 | PASS | live-blocked | goal `9e747d1862fc`，`constraints_ref` 含海鲜 |
| D1-04 | PASS | live-blocked | 「今天天气呢」步骤不变 |
| D1-05 | PASS | live-blocked | 「训练日定好了」→ s1 completed / s2 in_progress |
| D1-06 | PASS | live-blocked | 「现在几点」不推进 |
| D1-07 | PASS | live-blocked | 「提醒我一下」parse_routine None |
| D1-08 | PASS | harness | Host 三行，忌口含海鲜 |
| D1-09 | PASS | harness | sanitize 无 memory-context |
| D1-10 | PASS | harness | 跨段 goal/海鲜/s2 残留 OK |

**日体验**：钩子侧与 mock 同顺；对话气泡仅为 LIVE BLOCKED，无助手自然语言可读感。

### Day 2 — 续跑 / 改口忌口 + 例程待确认

| ID | 结果 | 模式 | 证据摘要 |
| --- | --- | --- | --- |
| D2-01 | PASS | harness | 同 goal_id，s2 in_progress |
| D2-02 | PASS | live-blocked | 海鲜 superseded；active=「其实可以吃虾」 |
| D2-03 | PASS | live-blocked | 「别再给我花生」入卡 |
| D2-04 | PASS | live-blocked | 「吃什么好」不建不推 |
| D2-05 | PASS | harness | 「每周一叫我称重」weekly，usage_delta=0 |
| D2-06 | PASS | harness | due 可列，runner=0 |
| D2-07 | PASS | live-blocked | 「我想健身」不建 |
| D2-08 | PASS | harness | prepare 109→41，花生保留 |
| D2-09 | PASS | harness | pin「叫我小Q」 |
| D2-10 | PASS | harness | goal/例程/花生齐 |

**日体验**：例程「先记账不跑」在 TUI `_consume_routine` 路径正确且不烧额度；改口抬升正确。仍无真模型口吻。

### Day 3 — 确认例程 + cancel/resume + 同义再建

| ID | 结果 | 模式 | 证据摘要 |
| --- | --- | --- | --- |
| D3-01 | PARTIAL | harness | confirm runner=1+budget/token；live runner 未用 |
| D3-02 | PASS | harness | paused + checkpoint `user_cancel` |
| D3-03 | PASS | live-blocked | 「继续」同 GOAL1 active |
| D3-04 | PASS | live-blocked | GOAL1 completed |
| D3-05 | PASS | live-blocked | 新 goal `2e82abefa55c` |
| D3-06 | PASS | live-blocked | 复用同一 open goal |
| D3-07 | PASS | live-blocked | cancel +「接着来」同 id |
| D3-08 | PASS | live-blocked | 「定好了」→ s1 done / s2 in_progress |
| D3-09 | PASS | live-blocked | 裸词「海鲜」不入卡 |
| D3-10 | PASS | harness | 新 active；旧 completed；花生仍在 |

**日体验**：打断续跑与同义复用门禁完整；确认例程的真模型执行未验到。

### Day 4 — 综合回顾 / 负例 / 完成 / 残留

| ID | 结果 | 模式 | 证据摘要 |
| --- | --- | --- | --- |
| D4-01 | PASS | harness | 花生 + GOAL2 |
| D4-02 | PASS | live-blocked | 「今天吃什么」不建不推 |
| D4-03 | PASS | live-blocked | 「一日三餐配好了」→ completed |
| D4-04 | PASS | live-blocked | 无 active goal |
| D4-05 | PASS | harness | Host 三行忌口非空 |
| D4-06 | PASS | harness | 109→41 保忌口 |
| D4-07 | PASS | harness | pin「小Q」仍在 |
| D4-08 | PASS | harness | usage=2 ≤ cap40（live 变体：不再要求 NETWORK_CALLS==0） |
| D4-09 | PASS | harness | 落盘无 memory-context |
| D4-10 | PASS | harness | completed=2；constraints/routines 齐；无残留 active |

---

## 4. 真模型体感（幻觉 / 漏触发 / 步骤 / 忌口 / 例程门闩）

| 维度 | 结论 |
| --- | --- |
| 幻觉 / 文风 / 是否认忌口 | **未测**：0 次有效助手正文 |
| 漏触发（用户以为说了但门闩未动） | 钩子侧未复现剧本内漏触发；模型是否用自然语言「听见」无法评 |
| 步骤口语推进 | TUI `_maybe_advance_step` 与 mock 一致；无模型旁白可评 |
| 忌口 absorb | 1:1 进卡与抬升正常 |
| 例程门闩 | 创建不跑 ✓；确认 harness ✓；**确认后真 runner ✗（auth）** |

Smoke 原文摘要：`[LA-401] Authentication failed...`（模型名仍回落显示为 `nvidia/nemotron-3-super-120b-a12b:free`，非成功对话）。

---

## 5. 用量

| 项 | 值 |
| --- | --- |
| usage_today 开始（进探针时） | 1（此前独立 smoke 探测已计 1） |
| 本探针 smoke | +1 → 2 |
| 本探针后续 live chat | +0（auth_dead 短路） |
| usage_today 结束 | **2** |
| 本探针 burn | **1** |
| 日限 / 预留余量 | 45 / 剩余 43（远高于预留 5） |
| 用过的模型 | 仅 smoke 尝试 `nvidia/nemotron-3-super-120b-a12b:free`（失败） |

---

## 6. 最痛 3 点

1. **OpenRouter API KEY 已过期（401）**：`auth/key` 与 smoke 双确认；真模型试用整轮停在闸门外，是本轮「勉强」的主因。  
2. **无法观察助手是否「顺着忌口/步骤说话」**：门禁对了，但用户日用体感一大半在自然语言；KEY 修复前不能升级回「稳达」。  
3. **（产品残留，与 mock 同）偏说法漏触发 / 群不推进步骤 / 忌口整句入卡略生硬**：本轮未因真模型暴露新问题，也未证伪；仍是下一轮有效 KEY 试用时要盯的口语面。

---

## 7. 复跑建议

1. 轮换有效的 OpenRouter `:free` KEY（写入 `OPENROUTER_API_KEY` / card secrets）。  
2. 确认 `LIGHTAGENT_ALLOW_OPENROUTER=1` 且无 FORBID。  
3. 重跑：`PYTHONPATH=. /workspace/la-venv/bin/python /tmp/lh_4day_live_probe.py`  
4. 额度策略保持：smoke 后若仍 401 立即 `auth_dead`，勿让 `OpenRouterBackend` 对 9 个 FREE_MODELS 各 `_check_and_count` 一次。

---

## 8. 产物路径

| 产物 | 路径 |
| --- | --- |
| 探针 | `/tmp/lh_4day_live_probe.py` |
| 日志 | `/tmp/lh_4day_live_out.txt` |
| 汇总 JSON | `/tmp/lh_4day_live_summary.json` |
| 本报告 | `local/research/long_horizon_4day_live_ux_eval_zh.md` |
| workspace | `/tmp/lh_4day_live_ws` |
