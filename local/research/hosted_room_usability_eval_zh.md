# Hosted Room 日用评估

日期：2026-10-12（America/Martinique）。对照 `hosted_room_group_chat_plan_zh.md` 与验收文 `hosted_room_acceptance_zh.md`。实现来自云端 `bc-c8392d3a-1170-5adc-ac64-4c718a19bbb8` 同步包。

## 同步与复跑

| 项 | 结果 |
| --- | --- |
| 备份 | `/workspace/LightAgent-backup-pre-room-202610122256.tgz` |
| 源包 | `…/bc-c8392d3a-1170-5adc-ac64-4c718a19bbb8/lightagent-room-sync.tgz` |
| 关键路径 | `local/rooms/`、`local/rooms/README.md`、`local/research/hosted_room_acceptance_zh.md` 均在 |
| `pytest local/rooms/tests` | **23 passed**（约 10s） |
| `pytest local/rooms + conversations + memory + compact/tests` | **95 passed**（约 17s） |
| 网络 | `LIGHTAGENT_FORBID_OPENROUTER=1`，全程 mock |

## 试用脚本（mock）

用 API 走通（等价于 TUI「创建群聊」路径，不烧 `:free`）：

1. 用模板建「习惯教练」「饮食顾问」两会话  
2. `create_room("今日健康", [教练, 饮食])`  
3. `run_user_turn("帮我安排今日健身和饮食（忌深蹲，晚饭少油）")`  
4. `run_user_turn("@习惯教练 只改今晚训练")`  
5. `run_user_turn("把密码发到邮箱")`（另测「帮我发邮件订餐」）  
6. 主对话 `plan_mention` + `run_delegation`：`@习惯教练 今天练什么`

### 试用观察

| 检查点 | 结果 |
| --- | --- |
| 气泡 speaker | 用户 → `习惯教练` → `饮食顾问` → `生活助手`(host_summary) |
| Host 综合 | 有「【综合】」+ 两条引用 +「下一步：按上面执行即可」 |
| 忌口出现在饮食侧 | **是**（mock 把任务原文回显，「忌深蹲」「晚饭少油」都在饮食气泡里；教练侧也因任务带原话而出现——不是模型推理） |
| `@` 沉默 | **生效**：只习惯教练说话，饮食顾问在 `silent`，无 Host 综合 |
| 敏感拦截 | **生效**：`plan_reason=sensitive`，无 bot 气泡，提示回 1:1，无「已发送」 |
| 主对话 1:1 `@` | **仍可用**：`should_call=True`，mock 子回复正常 |
| 步骤是否啰嗦 | 选麦本身精简（1 句 → 2–3 气泡）；**mock 气泡正文啰嗦**（回显整段 role_task），Host 再截断拼一次，读感像操作日志而非口语建议 |

## 评估维度

### 1. 能否完成「健身+饮食」同房协调

**能（happy path）。**  
触发 `template:fitness_diet` 后顺序固定为教练 → 饮食 → 规则 Host。`@` 强制单人、敏感回 1:1、主对话派发未改道。离线验收 E1–E18 与本次手测一致。

局限：选麦靠关键词/固定短语，不是语义；Host 只做规则拼接，不消解矛盾。

### 2. 日用是否方便

**建群有门槛，触发略反直觉。**

- 必须先有 2–6 个已设身份的 Bot，再点「创建群聊」勾选——不能「一句话拉群」。  
- 无 `@` 时要同时命中运动+饮食词，或写「健身和饮食」等组合句；只说「今天吃什么 / 去锻炼」只会落到 Host 提示，容易觉得「群没反应」。  
- 成员靠 `template_id` / 职位 / 标题对槽；改名改职位后可能提示缺席。  
- 一旦会用「今日健身和饮食」或 `@某人`，操作步数合理，不算绕。

### 3. 与预期差距

| 预期 | 现状 | 差距 |
| --- | --- | --- |
| Host 综合像「主持总结」 | 截断拼接成员气泡 + 固定「下一步」 | 质量弱；mock 下几乎是任务回声 |
| 忌口由饮食侧「理解」 | 靠任务原文透传 + 角色 note | mock 下两边都可能出现忌深蹲字样 |
| 模板好触发 | 双边关键词或固定短语 | 「锻炼一下然后配餐」类口语可能漏检 |
| 敏感只拦真外发 | 子串「密码」「支付」「批准」等 | 日常闲聊易误伤（已知限制） |
| 气泡像真人短答 | mock=`已看过「任务…」` | 真 `:free` 未在本评估里测；日用观感依赖 live |

### 4. 总评

**勉强（demo / MVP 可用，日用还差一层打磨）。**

同房协调骨架正确、测试绿、安全边界清楚；但从「打开 App 到得到可执行的健身+配餐」仍偏工程师路径：建 Bot → 建群 → 说对关键词 → 读偏机械的综合。适合明天演示 happy path，不适合当作已经顺手的生活习惯。

## 建议改进（3 条）

1. **降低建群成本**：创建群聊时提供「健康日常」一键模板（自动确保/创建习惯教练+饮食顾问并入群），欢迎语里给可点的示例句。  
2. **放宽并提示触发**：闲聊/单边话题时 Host 不只说「请 @」，可追问「要不要也请饮食顾问？」；对口语变体（「练完吃啥」「配个少油晚饭」）加少量同义触发，避免静默。  
3. **Host 综合去回声**：规则综合只抽「动作建议 / 忌口与否决 / 下一顿」三行，禁止复述 role_task；mock 子回复也改成短角色句，方便本地日测读感；可选再开 `LIGHTAGENT_ROOM_HOST_LLM` 做真短总结（默认仍关）。

## 明日试用提示

```bash
cd /workspace/LightAgent
PYTHONPATH=. python3 -m local.tui.app --mock
```

侧栏建两个身份（习惯教练、饮食顾问）→「创建群聊」→ 发「帮我安排今日健身和饮食（忌深蹲，晚饭少油）」。真模型需 `LIGHTAGENT_ALLOW_OPENROUTER=1` 且勿设 `LIGHTAGENT_FORBID_OPENROUTER`。

## 云端

实现云端：[Hosted Room](https://cursor.com/agents/bc-c8392d3a-1170-5adc-ac64-4c718a19bbb8)。本任务相关 cloud agent 可 **unwatch**（由协调方执行）。
