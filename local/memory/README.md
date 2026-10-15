# 用户画像记忆（P0）

个人生活助手的用户画像地基。助手人格在 `local/persona/`（`SOUL.md`、`IDENTITY.md`），和这里的库不是一回事。Agent 的 `self_learning` 反思也不是用户画像。

不调用 OpenRouter。单测全部离线。

## 不变量

1. **Memory pack 是当次请求的临时块。** 它进模型请求的 system / instruction（`<memory-context>`）。不会拼进用户提问，也不会被当成 user 消息写进会话记录。内核 `_add_memory_context` 只把原始用户句子交给 `store`。
2. **Persona ≠ User Profile。** 人格是文件；画像是 `local/memory/store/` 里的 SQLite。
3. **谁可以写，由 host 盖章。** 工具参数里的 `user_id` / `namespace` 会被丢掉。
4. **写入前会清洗。** 明显的密钥直接拒写；邮箱、手机号、身份证号打码；过敏、诊断、工资这类敏感句先变成「待确认」，确认前不注入。
5. **`self_learning` / reflection 不能写入画像。** 网页或工具结果（untrusted）也不能自动进画像。
6. **两条偏好车道。** `general` 换会话还在；`situational` 只在当前问题和主题对得上时进入本轮 pack。
7. **钉住优先。** 预算不够时从 pack 末尾裁，pinned / veto 靠前保留。
8. **取不到不是失忆。** 存储失败时 pack 是「memory unavailable」说明，禁止模型说「我什么都不记得」。
9. **巩固是空队列。** `jobs.enqueue` 只记账，`run_due` 不做合并，也不调模型。

## 用法

库默认在 `local/memory/store/profile.sqlite`，也可用环境变量 `LIGHTAGENT_PROFILE_DB`。

```bash
python -m local.memory.cli learn "以后简称我小Q" --lane general --facet identity
python -m local.memory.cli learn "出差喜欢靠窗" --lane situational --facet life --topics 出差,飞机
python -m local.memory.cli list
python -m local.memory.cli edit <id> "以后简称我小七"
python -m local.memory.cli pin <id>
python -m local.memory.cli forget <id>
python -m local.memory.cli recall "下周出差"
```

单独打开面板：

```bash
python -m local.memory.tui_panel
```

TUI 里是第三个页签「记忆」（Ctrl+3）：列表、记住、改、忘记、钉住、确认。对话工具和天气、联网工具在一起：`memory_learn`、`memory_forget`、`memory_recall`、`memory_pin`、`memory_edit`、`memory_list`。

`local.openrouter_config.make_agent` 仍只接受 `:free` 模型，并会挂上画像注入。测试不要调用 `run_free`。

## 测试

在仓库根目录：

```bash
python -m pytest local/memory/tests -q
```

这组测试不访问网络，也不消耗 OpenRouter 额度。
