# 多对话身份编排验收

阶段：P0.5 + P1 + P2

身份以用户填写的 `role_title` / `job_description` 为准。模板只负责把草稿填进编辑框，改过的文字会清掉 `template_id` 并原样注入。

| 项 | 结果 | 证据 |
| --- | --- | --- |
| E1 | PASS | `test_e1_custom_identity_saves_role_without_a_template`，TUI `test_colon_opens_the_session_menu_and_identity_save_is_custom` |
| E2 | PASS | `test_e2_template_is_an_optional_starter_and_edits_win` |
| E3 | PASS | `test_e3_identity_is_on_system_and_user_text_is_unchanged`，`test_e3_agent_provider_keeps_identity_out_of_the_transcript` |
| E4 | PASS | `test_e4_identity_is_not_stored_as_a_profile_learning` |
| E5 | PASS | `test_e5_inherit_keeps_soul_and_override_replaces_it` |
| E6 | PASS | `test_e6_rename_changes_title_only` |
| E7 | PASS | `test_e7_delete_needs_confirm_and_cancel_keeps_the_row` |
| E8 | PASS | `test_e8_pin_moves_into_the_pinned_zone` |
| E9 | PASS | `test_e9_move_sets_project_and_nests_in_the_sidebar` |
| E10 | PASS | `test_e10_unread_clears_when_the_conversation_is_opened` |
| E11 | PASS | `test_e11_hidden_rows_stay_out_until_shown` |
| E12 | PASS | `test_e12_copy_id_matches_the_session` |
| E13 | PASS | `test_e13_reload_keeps_identity_pin_group_and_hidden` |
| E14 | PASS | `test_e14_private_bot_skips_profile_pack_but_keeps_identity` |
| E15 | PASS | `test_e15_delegate_writes_a_step_without_leaking_the_pack` |
| E16 | PASS | `test_e16_missing_bot_is_an_error` |
| E17 | PASS | `test_e17_disabled_mention_stays_plain_text` |
| E18 | PASS | `test_e18_suite_does_not_call_openrouter`（`NETWORK_CALLS` 未增加；`mode=live` 在禁止哨兵下失败） |

回归：`local/memory/tests` 与 `local/conversations/tests` 一起 54 passed。

OpenRouter 调用次数：0

风险：Textual 右键仍可能因终端而不同，所以菜单动作在 `apply_action`，键盘 `:` / `m` 是一级入口。在线派发默认关闭，避免测试和 mock 烧额度。

结论：达标

## 本地复验（/workspace/LightAgent，America/Martinique）

- 时间：2026-10-12 06:19 AST
- `pytest local/conversations/tests local/memory/tests`：54 passed
- `python -m local.tui.shot`：OK
- `python -m local.tui.ux_probe`：ALL INTERACTIONS PASSED
- 说明：云端 patch 与本机 P0 `core.py` 有 3 处冲突；已补 `_dispatch_chat_completion`，并扩展 `_strip_ephemeral_memory` 去掉 `<persona>`/`<identity>`，E3 通过。
- 结论：达标
