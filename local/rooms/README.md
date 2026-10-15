# 主持式同房群聊

侧栏「创建群聊」开一间 Room：2–6 个已经存在的 Bot 共用一条 transcript。用户说一句，规则主持人按 `@` 或场景模板请最多 3 个人各说一轮，再给一段短综合。每个人的气泡带着自己的名字。没被点到的人这轮保持沉默。

群发言不是另一套协作内核。每一轮成员发言都是一次现有的单层 `run_delegation`：子 Bot 没有 `delegate_to_bot`，也不开 Tree-of-Thought，更不会去跑 `LightSwarm.run`。

## 怎么选人

只看代码，不请模型选麦。

1. 句里有 `@`：按出现顺序解析，只留本房成员，去重，截到 `max_speakers`（默认 3）。被点名的人说，其余沉默，不再加主持人综合。
2. 没有 `@`，但句子同时碰到运动和饮食，或写了「健身和饮食 / 运动和饮食 / 锻炼和饮食」：先习惯教练（`habit_coach`），再饮食顾问（`nutrition_advisor`）。缺谁就跳过，并留一条系统提示。
3. 对不上：这轮只有主持人，用一句话告诉你怎么 `@`，或怎么说「今日健身和饮食」。

只说「健身」或只说「吃什么」不会把全员拉进来。

## 主持人综合

默认不调用模型。有人说话时拼一段，最多 5 行：

```text
【综合】
- 习惯教练：…
- 饮食顾问：…
下一步：按上面执行即可
```

`LIGHTAGENT_ROOM_HOST_LLM` 默认关闭。单测不走这条。

## 边界

- 发邮件、下单、支付、密钥、审批：系统气泡请你回主对话或该 Bot 的 1:1。群里不调用外发工具，也不说「已发送」。
- 传给成员的任务和短 digest 会去掉 `<identity>` / `<persona>` / `<memory-context>`。这些块可以进该成员自己的 system（沿用 `share_user_profile`），不进房间气泡。
- 群气泡默认不写入用户画像。
- `LIGHTAGENT_COLLAB=0` 时不请成员发言。
- 在线子调用仍要 `LIGHTAGENT_ALLOW_OPENROUTER=1`。`LIGHTAGENT_FORBID_OPENROUTER=1` 时 live 直接拒绝。
- 房间消息过长时，`compact_room_messages` 只留尾部。它不和 1:1 会话混在一起压。

## 存在哪

```text
local/data/workspace/workspace.json   # rooms 数组，和会话列表放在一起
local/data/workspace/rooms/<id>.json  # 该群的 messages 和 trace
```

删掉一个成员 Bot 之后再发言：缺的席位跳过并提示，房间不崩。成员自己的 1:1 会话还在。

保存普通会话时会把已有的 `rooms` 键留住，避免把群索引写丢。

## 本地看

在 `LightAgent/` 下：

```bash
PYTHONPATH=. python3 -m local.tui.app --mock
```

先给两个会话设好「习惯教练」和「饮食顾问」（身份模板里有），再点「创建群聊」。群里发「帮我安排今日健身和饮食（忌深蹲，晚饭少油）」，应看到两个人的气泡和主持人综合。

## 测试

```bash
cd LightAgent
PYTHONPATH=. python3 -m pytest local/rooms local/conversations local/memory local/compact/tests -q
```

房间单测默认不访问 OpenRouter。
