# 主持式同房群聊验收

日期：2026-10-13。对照 `hosted_room_group_chat_plan_zh.md` 的 E1–E18。实现在 `local/rooms/`，复用 `local/conversations/collaborate.py` 的单层 `run_delegation`。

## 结论

离线验收通过。建群后发「今日健身和饮食」，transcript 顺序是用户 → 习惯教练 → 饮食顾问 → 主持人综合；`@` 只让被点名的人说话。主对话里的 `@` 派发没有改道。

主持人综合是规则拼接，不是开会。mock 回复会把交给该角色的任务原文带出来，所以「忌深蹲」出现在饮食顾问气泡里，是因为任务保留了用户原话，不是因为模型做了推理。真 `:free` 不在这套单测里。

## 改了什么

| 位置 | 改动 |
| --- | --- |
| `local/rooms/` | 新目录：类型、TurnPlan、场景、digest、utterance、综合、runtime、存储、动作、敏感词、TUI 弹层 |
| `local/conversations/templates.py` | 增加 `nutrition_advisor`（饮食顾问） |
| `local/conversations/store.py` | 保存会话时保留 workspace.json 里的 `rooms` |
| `local/tui/app.py` | 启用「创建群聊」；群行、群气泡、群内发送走 `run_user_turn` |
| `local/tui/identity_ui.py` | 重命名 / 确认框可以换标题，供群菜单使用 |
| `local/tui/app.tcss` | 群成员列表和说话人名字 |
| `LightAgent/core.py` | 未改。不默认调用 `LightSwarm.run` |

群内没有 AG2 式选麦，没有子再派发，没有 ToT，没有把 Crew 流水线画成群聊。

## E 表

| ID | 测试 | 期望 |
| --- | --- | --- |
| E1 | `test_room_plan.py::test_e1_mention_selects_only_the_named_member` | `@习惯教练` 只请教练，饮食顾问沉默 |
| E2 | `test_e2_fitness_diet_template_orders_coach_then_advisor` | 无 @ 的「今日健身和饮食」按教练 → 饮食顾问 |
| E3 | `test_e3_idle_chat_falls_back_to_host`、`test_e3_single_topic_does_not_pull_everyone` | 闲聊或单话题不拉全员 |
| E4 | `test_e4_max_speakers_runs_one_child` | `max_speakers=1` 只跑一个 child |
| E5 | `test_room_utterance.py::test_e5_mock_bubble_hides_identity_and_memory_pack` | `speaker=bot:…`，气泡里没有身份块和画像包 |
| E6 | `test_e6_child_is_single_level_and_swarm_run_stays_unused` | depth 0；depth 1 拒绝；不跑 `LightSwarm.run` |
| E7 | `test_room_store.py::test_e7_create_save_load_keeps_members_and_title` | 保存再读，标题和成员还在；会话保存不冲掉 rooms |
| E8 | `test_room_runtime.py::test_e8_fitness_turn_orders_user_coach_diet_host` | user → 教练 → 饮食 → host_summary |
| E9 | `test_e9_quota_is_a_chinese_bubble` | 额度用尽是中文气泡，不抛异常 |
| E10 | `test_e10_missing_member_is_skipped` | 缺成员则跳过并提示 |
| E11 | `test_room_tui.py::test_e11_create_room_shows_a_sidebar_row_and_welcome` | 点创建、选 2 人，侧栏出现群和欢迎语；重启仍在 |
| E12 | `test_e12_fitness_turn_shows_two_speakers_and_host` | 两个身份气泡 + 综合；忌深蹲留在饮食侧 |
| E13 | `test_e13_mention_keeps_the_other_member_silent` | `@饮食顾问` 时教练不发言 |
| E14 | `test_e14_main_chat_mention_still_delegates` | 主对话 `@` 仍走原来的 delegate |
| E15 | `test_room_acceptance.py::test_e15_sensitive_turn_does_not_send_or_delegate` | 「发邮件订餐」不派发、不出现「已发送」 |
| E16 | `test_e16_digest_and_task_drop_ephemeral_tags` | digest / task 不含 ephemeral 标签 |
| E17 | `test_e17_forbid_openrouter_blocks_live_room_turns` | 哨兵打开时 live 拒绝，网络计数不变 |
| E18 | 下面这条命令 | rooms + conversations + memory + compact 全绿 |

房间测试文件名带 `room_`，避免和 `local/conversations/tests/test_store.py` 在同一次 pytest 里模块名冲突。

## 命令

在 `LightAgent/` 目录：

```bash
PYTHONPATH=. python3 -m pytest local/rooms/tests -q
PYTHONPATH=. python3 -m pytest local/rooms local/conversations local/memory local/compact/tests -q
```

2026-10-13 本机结果：房间 23 通过；上面四套一起 **95 passed**。全程 `LIGHTAGENT_FORBID_OPENROUTER=1`，没有 OpenRouter 请求。

## 限制

- 选麦是关键词和 `@`，不是语义理解。「锻炼一下然后配餐」会命中，「今天吃什么」不会。
- 综合默认引用 mock/成员回复的截断，不判断两边有没有互相矛盾。
- 敏感拦截是子串规则。「支付」「密码」「批准」写进句子就会被拦回 1:1，即使不是真的要外发。
- 群 transcript 的压缩只留尾部窗口，没有走 1:1 那套 compact 流水线。
- `space_id` 存在房间上，没有新的画像写入路径。
- 成员按 `template_id`、职位、标题匹配。职位改得对不上槽位时，这轮会提示缺人。
- 真模型综合（`LIGHTAGENT_ROOM_HOST_LLM=1`）这版不调用，仍走规则。
