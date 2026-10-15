# Compact 离线验收自测（2026-10-12）

对照实现 plan §7。摘要全部用 mock 或本地模板填充，进程内 `NETWORK_CALLS` 保持不变，没有请求 OpenRouter。

## 怎么跑

```bash
cd LightAgent
python -m pytest local/compact/tests local/memory/tests local/conversations/tests -q
```

只跑验收场景：

```bash
python -m pytest local/compact/tests/test_acceptance.py local/compact/tests/test_policy_prompts.py local/compact/tests/test_compactor.py -q
```

本次结果：`local/compact/tests`、`local/memory/tests`、`local/conversations/tests`，以及 `tests/test_v010_session.py`、`tests/test_v010_core_integration.py` 共 **99 passed**。

## E1–E10 映射

| ID | 测试 | 结果 | 覆盖了什么 |
| --- | --- | --- | --- |
| E1 | `test_e1_auto_above_85_percent_uses_short_template` | 通过 | 假预算占比 >85% 才自动压缩；summarizer 收到极短模板 `AUTO_SHORT`；prompt 不含完整模板的「已确认偏好」；≤85% 不触发 |
| E2 | `test_e2_manual_focus_keeps_safety_sections` + `test_parse_compact_command` | 通过 | `/compact 焦点：…` 使用完整生活模板 + 不可信焦点块；焦点文案明确不能删「禁止事项」；即使用户焦点写「删除禁止事项」，本地摘要仍保留该节 |
| E3 | `test_e3_summarizer_input_strips_ephemeral_and_next_turn_can_inject` + `test_kernel_auto_compact_strips_then_reinjects` | 通过 | summarizer 输入没有 `<identity>` / `<persona>` / `<memory-context>` 正文；压后的会话副本也不留这些正文；下一轮 `prepare_turn` 仍能注入 memory pack；内核自动路径会把权威块重新挂回 system |
| E4 | `test_e4_spill_can_be_recalled` + `test_recent_tool_stays_inline_and_older_tool_spills` | 通过 | 旧的大 tool 结果 spill 成 `tool-result:sha256:…`；`recall_spilled` 能按 query 取回片段；最近 1 条 tool 结果留在窗口里 |
| E5 | `test_e5_allergy_pin_survives_window` + `test_never_compact_survives_aggressive_max_messages` | 通过 | 「我对花生过敏」flush 后打上 `compact=never`，K=6 窗口外仍保留；`max_messages=2` 也不会裁掉 pin |
| E6 | `test_e6_keeps_six_user_turns_and_prefers_users_under_budget` + `test_user_turn_window_keeps_six_user_utterances` | 通过 | 8 条 user 里保留最近 6 条原话及配对；预算装不下长 assistant 时先丢 assistant，user 原话优先留 |
| E7 | `test_e7_summary_failure_keeps_pruned_history` | 通过 | summarizer 抛错、返回空白、或写进 ephemeral 标签，都丢弃摘要，保留裁剪后的历史，回执「已裁剪未摘要」 |
| E8 | `test_e8_diet_goes_to_memory_without_skill_prompt` | 通过 | 「我素食」写入 Memory（active learning，space=home）；`procedural_pending` 为空，不弹 skill 确认 |
| E9 | `test_e9_procedural_waits_for_confirm_then_becomes_skill` | 通过 | 「下次订票按这三步…」只进待确认队列，不写 Profile；`promote_skill` 之后 `SKILL.md` 存在，且 `SkillManager.discover_skills()` 能发现 |
| E10 | `test_e10_flush_and_summary_stay_inside_space` | 通过 | home 压缩不把 work 消息送进 summarizer，也不把「王总」写成 home/work 的新 learning；已有 work 画像原样保留；home 的「我素食」只落在 home |

## 质量点 Q1–Q4

| ID | 结论 |
| --- | --- |
| Q1 | 自动走 `prompts.AUTO_SHORT`（§C.1 极短保守原文）。`/compact` 走 `prompts.FULL_LIFE`（§C.2）+ 可选 `FOCUS_BLOCK`（§C.3）。硬约束是 §C.5。`ZERO_LLM_POLICY` 只作为失败回退的策略说明，不是自动路径的唯一实现。 |
| Q2 | 单测设置 `LIGHTAGENT_FORBID_OPENROUTER=1`，默认 summarizer 是 `local_summarizer`。`NETWORK_CALLS` 在 E1 和内核用例里没有增加。真实 `:free` 需要 `LIGHTAGENT_COMPACT_LLM=1`，本次未调用。 |
| Q3 | 新逻辑在 `local/compact/`。内核只改了 `LightAgent/session.py`（user 轮窗口、`compact=never`、最近 tool 不 spill）和 `LightAgent/core.py`（compact 输入先 strip，>85% 走本地 pipeline，压后再挂回 ephemeral）。`local/memory/tests` 与 `local/conversations/tests` 通过。 |
| Q4 | 本文档。用法见 `local/compact/README.md`。 |

## 已知限制

- 默认摘要是从被移出的 user 句里摘引，不是模型生成。字段会按模板写「无」，不会发明 learning_id。
- TUI 自动压缩看的是实时估算（系统 + 工具 + 消息），默认窗口 1_000_000。底部百分比条会保持曾经的高水位，避免截图演示值被抹掉；是否压缩不看那条高水位，只看实时估算。要用自动压缩做手工验收，设置 `LIGHTAGENT_CONTEXT_WINDOW`。
- `min_keep_tool_steps` 暂定为 1。更早的大 tool 结果会 spill；错误结果（`metadata.is_error`）先不剪。
- 同一句 user 话在 flush/extract 后打上标记，下次 compact 不会再次询问 skill。拒绝保存后也不会自动再问。
- 过敏、诊断、工资等继续走 Memory scrub：可以入库，但是待确认，确认前不注入。
- 标了其他 `space_id` 的消息不进摘要、不进本次 Memory。若它落在最近 6 条 user 轮之外，压缩后的模型视图里不再出现。
- `LightAgent.compact_session(max_messages=…)` 仍是原来的按条数裁尾（会先 strip）。生活模板要走 TUI `/compact`、自动 85%，或 `compact_session(life=True, focus=…)`。
- 没有做 dreaming / 巩固，也没有摘要质量失败后的第二次付费重试。
