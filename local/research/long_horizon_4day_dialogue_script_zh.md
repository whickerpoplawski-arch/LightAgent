# 长链路日用体验：4 天 × 10 段对话剧本（预期结果）

日期：2026-10-14（America/Martinique, UTC-4）  
环境：`LIGHTAGENT_FORBID_OPENROUTER=1`，解释器 `/workspace/la-venv/bin/python`，`PYTHONPATH=.`  
测法：库 API / mock 探针（不依赖 Textual GUI；禁止真 OpenRouter）  
workspace：同一目录跨 4「天」（探针用 `/tmp/lh_4day_ws`，day 边界用注释时间戳，不换库）  
依据：`long_horizon_stable_gap_*`、`local/goals|constraints|routines|harness|checkpoints|memory|rooms`

## 0. 覆盖能力对照

| 能力 | 主要段 |
| --- | --- |
| LifeGoal 创建 / 短问答不建 | D1-01/03，D2-04/07，D3-05/06，D4-02/04 |
| 1:1 忌口 absorb → constraints_ref | D1-02/03，D2-02/03，D4-01 |
| 口语步骤推进 | D1-05，D3-04/08，D4-03 |
| SoftRoutine 创建不跑、确认才跑 | D2-05/06，D3-01 |
| cancel / resume checkpoint | D3-02/03/07 |
| Host 三行 / 群 compact | D1-08，D2-08，D4-05/06 |
| 同义触发正例 + 负例闲聊 | D1-07，D2-07，D3-05/06/09，D4-02 |
| 跨天延续 goal/约束；Memory pin | D2-01/09/10，D4-01/07 |
| 落盘无 memory-context | D1-09，D4-09 |

群聊步骤推进：**本剧本不测**（稳达评估已注明群不挂 `maybe_advance_goal`）；群路径以 Host/compact/absorb 库测为主。

---

## Day 1 — 建目标 + 忌口 + 推进一步 + 闲聊负例

| ID | 用户原话 | 预期 | 测法 |
| --- | --- | --- | --- |
| D1-01 | 今天吃什么 | `should_create_goal` False；`maybe_open_goal` 返回 None；goals 目录无新文件 | `should_create_goal` / `maybe_open_goal` |
| D1-02 | 忌口：海鲜 | `absorb_user_text` 后 `active_texts` 含「海鲜」 | `absorb_user_text` + `ConstraintStore.active_texts` |
| D1-03 | 帮我制定一周健身与饮食计划 | 建 active LifeGoal；`constraints_ref` 含海鲜；恰 1 个 `in_progress`（s1 定训练日） | `maybe_open_goal` |
| D1-04 | 今天天气呢 | 不推进步骤；goal 状态不变 | `maybe_advance_goal` → None；对比 steps |
| D1-05 | 训练日定好了 | s1=`completed`，s2=`in_progress`；至多一个 in_progress | `maybe_advance_goal` |
| D1-06 | 现在几点 | 不推进 | `maybe_advance_goal` → None |
| D1-07 | 提醒我一下 | `parse_routine` → None（无 cadence） | `parse_routine` |
| D1-08 | （库）Host 汇总 | 恰三行：`动作：` / `忌口：` / `下一步：`；忌口含海鲜相关 | `render_host_summary` |
| D1-09 | （库）脏 transcript | `sanitize_transcript` 后无 `<memory-context>`；`assert_transcript_clean` 通过 | `sanitize_transcript` / `assert_transcript_clean` |
| D1-10 | （状态检查）跨段残留 | goal 仍 active；卡仍含海鲜；s2 in_progress | `get_active_goal` + card |

---

## Day 2 — 续跑 / 改口忌口 + 例程创建待确认

| ID | 用户原话 | 预期 | 测法 |
| --- | --- | --- | --- |
| D2-01 | （跨天续）无新话，读状态 | 与 D1 同一 `goal_id`；s2 仍 in_progress | `get_active_goal` |
| D2-02 | 其实可以吃虾 | 海鲜相关条 superseded；active 为抬升句 | `absorb_user_text` + card items |
| D2-03 | 别再给我花生 | active 含该句（同义忌口） | `absorb_user_text` |
| D2-04 | 吃什么好 | 不建 goal；不推进 | detect + advance |
| D2-05 | 每周一叫我称重 | `parse_routine` cadence=`weekly`；`RoutineStore.create` 成功；**不**调 runner | `parse_routine` + `create` |
| D2-06 | （查 due，不确认） | `due_routines` 可列出（next_due 置过去）；runner 调用次数仍 0 | `set_next_due` + `due_routines` |
| D2-07 | 我想健身 | `should_create_goal` False | `should_create_goal` |
| D2-08 | （库）群 prepare | `prepare_room_transcript` 压缩后仍保留花生/忌口线索 | `prepare_room_transcript` |
| D2-09 | （库）Memory pin | `ProfileStore.learn`「叫我小Q」+ `pin`；跨天可再读 | `ProfileStore` 落在同 workspace |
| D2-10 | （状态检查） | goal 仍 active（未完成）；例程存在；花生在 active | stores |

---

## Day 3 — 确认例程 + cancel/resume + 同义再建

| ID | 用户原话 | 预期 | 测法 |
| --- | --- | --- | --- |
| D3-01 | 确认提醒 | `routine_action`→confirm；`confirm_first_due` mock runner **恰好 1 次**；带 budget/token | `routine_action` + `confirm_first_due` |
| D3-02 | （取消）user_cancel | goal→`paused`；checkpoint reason=`user_cancel` | `record_run_event("life","user_cancel")` + `latest_checkpoint` |
| D3-03 | 继续 | `is_resume_request` True；`resume` 同 `goal_id`；status→active | `is_resume_request` + `resume` |
| D3-04 | 这步完成了 | s2 completed → goal `completed` | `maybe_advance_goal` |
| D3-05 | 做个一周健身饮食计划 | 同义触发建**新** goal（旧已 completed）；active | `should_create_goal` + `maybe_open_goal` |
| D3-06 | 帮我安排一周锻炼和饮食 | detect True；因已有 open goal，返回**同一** goal_id（不新建第二个） | `maybe_open_goal` 对比 id 集合 |
| D3-07 | cancel 后再「接着来」 | paused→checkpoint→resume 同 id | cancel + `is_resume_request("接着来")` + resume |
| D3-08 | 定好了 | 新 goal 的 s1 completed、s2 in_progress | `maybe_advance_goal` |
| D3-09 | 海鲜 | 单独一词不入卡（`classify_utterance` None） | `classify_utterance` / absorb 后卡不变 |
| D3-10 | （状态检查） | 新 goal active；花生约束仍在；已 completed 旧 goal 可列出 | stores |

---

## Day 4 — 综合回顾、负例、完成、残留

| ID | 用户原话 | 预期 | 测法 |
| --- | --- | --- | --- |
| D4-01 | （跨天读） | 花生仍在 active；goal 仍为 D3 新 goal | card + `get_active_goal` |
| D4-02 | 今天吃什么 | 不建、不推进 | detect + advance |
| D4-03 | 一日三餐配好了 | 若短语命中则完成当前步；goal→completed（或「完成了」等价） | `maybe_advance_goal`（「完成了」在短语表） |
| D4-04 | 吃什么好 | 无新 active goal | `maybe_open_goal` None；`get_active_goal` None |
| D4-05 | （库）Host 三行 | 结构仍三行；忌口行非空（花生） | `render_host_summary` |
| D4-06 | （库）compact 109→~41 | 压缩后仍含忌口线索 | `prepare_room_transcript` |
| D4-07 | （库）Memory pin 仍在 | 再开同 sqlite，pinned 学习含「小Q」 | `ProfileStore` reopen |
| D4-08 | （网闸） | `NETWORK_CALLS` 相对探针起点无增加 | `local.openrouter_config.NETWORK_CALLS` |
| D4-09 | （落盘残留） | workspace 内 goals/constraints/routines/checkpoints json **不含** `<memory-context>` | 扫文件 |
| D4-10 | （总检） | completed≥1；例程曾跑过；卡 active 非空；无 open 半残 goal 或仅 completed/paused 符合预期 | 汇总断言 |

---

## 预期总览（跑前）

- **理想**：40/40 PASS → 总评倾向「稳达」  
- **可接受 PARTIAL**：D4-03 若「一日三餐配好了」未进短语表但「完成了」可替（脚本测法允许用「完成了」）；Memory 若环境缺 sqlite 夹具则标 PARTIAL 并注明  
- **硬 FAIL 红线**：短问答建 goal；例程未确认就跑；resume 换 goal_id；落盘出现 memory-context；NETWORK_CALLS 增加

探针：`/tmp/lh_4day_probe.py` → 日志 `/tmp/lh_4day_probe_out.txt`  
评估：`local/research/long_horizon_4day_ux_eval_zh.md`
