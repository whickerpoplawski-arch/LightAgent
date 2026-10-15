# 长链路 harness（生活助手最小集）

默认路径零额外 LLM。`LIGHTAGENT_FORBID_OPENROUTER=1` 时测试不打 OpenRouter。

## 模块

| 模块 | 包 | 作用 |
| --- | --- | --- |
| M0 | `local/harness/ephemeral.py` | pack 只进 system，落盘前去掉 `<memory-context>` |
| M4 | `local/harness/run_control.py` | `BudgetLimits` + `CancellationToken`，停止与额度文案 |
| M5 | `local/constraints/` | 忌口卡；remember / forget / supersede；只注入 active |
| M3 | `local/rooms/digest.py` | 群 compact：尾窗 + 用户句 + Constraint，零 LLM |
| M1 | `local/goals/` | 显式或房间模板才建 LifeGoal |
| M2 | `local/checkpoints/` | 取消 / 额度写断点；「继续」不新建目标 |
| M6 | `local/rooms/host_summary.py` | 主持三行：动作 / 忌口 / 下一步 |
| M7 | `local/routines/` | 显式提醒；打开时列出 due；确认后才跑 |

## 不变量

- Pack / persona / identity 只走 system 车道。落盘前 `sanitize_transcript` / `scrub_room_messages` 去掉 `<memory-context>`。
- 单次 run 预算走库 `BudgetLimits`，不另写计数器。默认 `model_calls=8`、`seconds=120`，可用 `LIGHTAGENT_RUN_MODEL_CALLS` / `LIGHTAGENT_RUN_SECONDS` 覆盖。
- 取消是协作边界：`CancellationToken.cancel(reason="user_cancel")`。文案承认建议可能已经展示（半执行）。
- 日限 45 仍在 `openrouter_config`，与单次 run 预算分开。
- 一个 space 同时最多一个未完成 LifeGoal，步骤里最多一个 `in_progress`。短问答不建目标。
- 忌口以 `constraints/card.json` 为准。同主题改口就地 supersede，注入只读 `status==active`。
- 群 compact 与主持总结不调用模型。`LIGHTAGENT_ROOM_HOST_LLM` 被忽略。
- SoftRoutine 只在用户写出「每周 / 每天 / 一次提醒」或 `/routine` 时创建。到点只提示。回复「确认提醒」才执行，并带上本轮预算和取消令牌。Mock 与 `LIGHTAGENT_FORBID_OPENROUTER=1` 不调用模型。没有定时器，错过的周期不补跑。

## 非目标

OS sandbox、默认 ToT / LightDAG、Host 或群 compact 的默认 LLM、Dreaming、系统推送、把 1:1 和群 transcript 合成一份、把 pack 写进用户消息、短聊自动建 LifeGoal、每条消息都写 checkpoint、杀线程、改日限 45 或 `:free` 门闩。
