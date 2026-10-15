# 稳达三缺口验收（A-T / B-T / C-T）

日期：2026-10-14。环境：`LIGHTAGENT_FORBID_OPENROUTER=1`，`PYTHONPATH=.`。叠在 M0–M7 之上。E1–E12 语义未改。

全局：`python -m pytest local/rooms local/conversations local/memory local/compact/tests local/goals local/routines local/constraints local/checkpoints local/harness/tests -q` → **164 passed**（13.62s）。原 146 仍在，新增 18。

探针 `python -m local.harness.lh_probe`：S1–S9 与 NET 共 **10 PASS / 0 FAIL**。S4 仍是 109→41。`NETWORK_CALLS` 0→0。

| ID | 结果 | 断言 |
| --- | --- | --- |
| A-T1 | PASS | `absorb_user_text("忌口：海鲜")` 后 active 含该句 |
| A-T2 | PASS | 先 absorb 再 `maybe_open_goal`，`constraints_ref` 含海鲜 |
| A-T3 | PASS | 只开 goal、不 absorb 时 `constraints_ref==[]` |
| A-T4 | PASS | 「其实可以吃虾」把海鲜条标为 superseded，active 为抬升句 |
| A-T5 | PASS | 「今天吃什么」不改卡、不落文件 |
| A-T6 | PASS | E1、compact/flush、群 `prepare_room_transcript` 仍绿 |
| B-T1 | PASS | 「训练日定好了」→ s1 completed、s2 in_progress，至多一个 in_progress |
| B-T2 | PASS | 「一日三餐配好了」或「这步完成了」走完两步后 goal completed |
| B-T3 | PASS | 「今天吃什么」「现在几点」不推进 |
| B-T4 | PASS | 无活跃 goal 时返回 None，不建目标 |
| B-T5 | PASS | 直接 `set_step_status` 的 E2 行为仍是至多一个 in_progress |
| B-T6 | PASS | `current_step_title` / `render_goal_line` 变为「配一日三餐」 |
| C-T1 | PASS | 「帮我安排一周锻炼和饮食」为 True；「今天吃什么」为 False |
| C-T2 | PASS | 「做个一周健身饮食计划」为 True |
| C-T3 | PASS | 「每周一叫我称重」为 weekly；「今天吃什么」为 None |
| C-T4 | PASS | 「别再给我海鲜」分类 remember，apply 后 active 含该句 |
| C-T5 | PASS | E9、E12 原测绿；负例含「我想健身」「提醒我一下」「海鲜」 |

17 / 17 PASS。0 FAIL。
