# 长链路 harness 验收（E1–E12）

日期：2026-10-14。环境：`LIGHTAGENT_FORBID_OPENROUTER=1`，`PYTHONPATH=.`。默认路径零额外 LLM。

| ID | 结果 | 命令 | 日期 | 说明 |
| --- | --- | --- | --- | --- |
| E1 | 通过 | `pytest local/goals/tests/test_m1_life_goal.py::test_e1_explicit_goal_records_active_constraints local/harness/tests/test_e2e_long_horizon_offline.py::test_same_day_goal_cancel_resume_and_clean_transcript -q` | 2026-10-14 | 显式目标写入 goal JSON，`constraints_ref` 含 active 忌口 |
| E2 | 通过 | `pytest local/goals/tests/test_m1_life_goal.py::test_e2_only_one_step_stays_in_progress -q` | 2026-10-14 | 至多一个 `in_progress` |
| E3 | 通过 | `pytest local/harness/tests/test_m4_run_control.py local/checkpoints/tests/test_m2_checkpoint.py::test_e3_cancel_writes_a_checkpoint_and_pauses -q` | 2026-10-14 | 协作取消无未捕获异常；checkpoint `reason=user_cancel`；目标 paused |
| E4 | 通过 | `pytest local/checkpoints/tests/test_m2_checkpoint.py::test_e4_resume_keeps_the_goal_and_completed_steps -q` | 2026-10-14 | 「继续」不新建 goal；已完成步骤保持完成 |
| E5 | 通过 | `pytest local/harness/tests/test_m4_run_control.py::test_e5_kernel_budget_string_is_translated local/goals/tests/test_m1_life_goal.py::test_e5_budget_event_marks_the_goal -q` | 2026-10-14 | 额度用尽可见提示；goal `budget_reached` |
| E6 | 通过 | `pytest local/rooms/tests/test_m3_room_compact.py::test_e6_constraint_sentence_survives_the_tail_window -q` | 2026-10-14 | compact 后短于原文，忌口句仍在；上限 keep+keep_user+8 |
| E7 | 通过 | `pytest local/compact/tests local/rooms/tests/test_m3_room_compact.py::test_prepare_save_absorbs_and_compacts_without_dropping_the_card -q` | 2026-10-14 | flush 钉住忌口；压完卡片仍在 |
| E8 | 通过 | `pytest local/rooms/tests/test_m6_host_progress.py::test_e8_three_lines_use_active_constraints_and_skip_the_long_reply -q` | 2026-10-14 | 主持三行，不含子 Bot 长文 |
| E9 | 通过 | `pytest local/goals/tests/test_m1_life_goal.py::test_e9_short_questions_do_not_create_a_goal -q` | 2026-10-14 | 「今天吃什么」不建 LifeGoal |
| E10 | 通过 | `pytest local/rooms/tests/test_m6_host_progress.py::test_e10_host_flag_does_not_call_out -q` | 2026-10-14 | `LIGHTAGENT_ROOM_HOST_LLM=1` 仍不打网络 |
| E11 | 通过 | `pytest local/harness/tests/test_m0_ephemeral_pack.py local/harness/tests/test_e2e_long_horizon_offline.py::test_ephemeral_pack_is_stripped_before_persist -q` | 2026-10-14 | 落盘 transcript 无 `<memory-context>` |
| E12 | 通过 | `pytest local/routines/tests/test_m7_soft_routine.py -q` | 2026-10-14 | 显式创建、pause、due-on-open；确认走预算令牌；无定时偷跑 |

全局回归（2026-10-14）：146 passed。

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. python -m pytest \
  local/rooms local/conversations local/memory local/compact/tests \
  local/goals local/routines local/constraints local/checkpoints \
  local/harness/tests -q
```

## 稳达补丁（E13–E15，不改上面 E1–E12）

| ID | 结果 | 日期 | 说明 |
| --- | --- | --- | --- |
| E13 | 通过 | 2026-10-14 | 1:1 absorb 先于开目标，`constraints_ref` 能见到忌口 |
| E14 | 通过 | 2026-10-14 | 「训练日定好了」完成当前步并推进下一步 |
| E15 | 通过 | 2026-10-14 | 计划 / 叫我 / 别再给 等同义说法可触发；短问答仍拒绝 |

补丁后同一全局命令：**164 passed**（146 + 18）。逐条见 `long_horizon_stable_gap_acceptance_zh.md`。
