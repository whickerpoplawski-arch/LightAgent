# 实现 Plan：长链路 Harness 生活助手最小集（M0–M7）

> 给 **Cursor 云端**：**逐模块实现 → 该模块测试全绿 → 再进下一模块**；代码精简；复用库原语不平行造轮子。  
> 依据（必读，勿空想）：  
> - `long_horizon_harness_minset_zh.md`（7 模块、E1–E12、接线表）  
> - `life_assistant_long_horizon_deepdive_zh.md`  
> - `harness_production_eval_zh.md`（已知缺口）  
> 风格对齐：`hosted_room_group_chat_plan_zh.md` / `p0_memory_impl_plan_zh.md` / `compact_impl_plan_zh.md`  
> 日期：2026-10-14（America/Martinique / AST）  
> 落点：`local/` 二开为主；**尽量不改**上游 `LightAgent/` 内核；`:free` 路径**默认零额外 LLM**  
> **实现与单测默认不调 OpenRouter**（`LIGHTAGENT_FORBID_OPENROUTER=1`）。

---

## 0. 给 Cursor 的 12 行摘要

1. **做什么**：在现有 TUI + Hosted Room + memory/compact 上，落地生活助手长链路最小集 **M0–M7**，使跨轮/跨天任务可收敛、可中断、不丢忌口、群不回声、有轻例程。  
2. **真相源**：本机 `/workspace/LightAgent` 已有大量 `local/` 二开；云端若用 **new Origin draft**，以**上传的本 plan + 现有 local 目录结构**为实现真相，勿假设空仓。  
3. **拍板默认**：Q1A–Q7A 全部采用推荐（见 §2）；勿再开讨论。  
4. **顺序（可独立 merge/测）**：批次 A `M0+M4` → B `M3+M5` → C `M1+M2` → D `M6` → E `M7` → 全局回归 + acceptance。  
5. **硬规则**：每完成**一个模块**就跑**该模块专属测试**；不过**禁止**进入下一模块。  
6. **复用**：`CancellationToken`（`LightAgent/cancellation.py`）、`BudgetLimits`/`BudgetExceeded`（`LightAgent/runtime.py:292+`）、`inject.strip_ephemeral`、`compact/flush.py`、`rooms/digest.compact_room_messages`、`ProfileStore.learn/forget`。  
7. **已知致命缺口**（eval）：`backend.py:409` `agent.run` 未传 cancel/budget；`app.py:1426` `_save_rooms` 未调群 compact；Host `host_summary.py` 易回声；忌口改主意无 supersede。  
8. **默认零 LLM**：群 compact、Host 三行、Constraint 抽取均规则路径；`LIGHTAGENT_ROOM_HOST_LLM` 保持默认关。  
9. **短问答不建 LifeGoal**（E9）；LifeGoal 仅显式指令或房间模板。  
10. **交付**：代码 + `local/research/long_horizon_harness_acceptance_zh.md`（E1–E12 勾选）+ sync tarball 说明。  
11. **全局回归**：见 §5。  
12. **代码精简**：能接上就不重造；禁止 OS sandbox / ToT / Dreaming / 默认 Host LLM / 推送风暴。

---

## 1. 目标与非目标

### 1.1 目标（最小集做完应有）

| ID | 能力 | 对应模块 |
| --- | --- | --- |
| T1 | Pack/persona 只走 ephemeral 车道，transcript **永不**落盘 `<memory-context>` | M0 |
| T2 | TUI/`make_agent` 接上单次 run `BudgetLimits` + `CancellationToken`；停止有半执行文案 | M4 |
| T3 | 群 `_save_rooms` 调用零 LLM compact；压前 flush；忌口句保真 | M3 |
| T4 | ConstraintCard 为忌口唯一真相源；`supersede` in place；注入/ Host / compact 同读 | M5 |
| T5 | 显式/模板建 LifeGoal；窗外步骤；短问答不建 | M1 |
| T6 | Checkpoint + `pending_side_effects`；「继续」续跑不重建 goal | M2 |
| T7 | Host 固定三行（动作/忌口/下一步），无整段回声 | M6 |
| T8 | SoftRoutine：显式创建、pause、due-on-open、确认才跑模型 | M7 |
| T9 | E1–E12 离线可勾选；全局 pytest 绿 | 验收 |

### 1.2 非目标（刻意不做清单）

| 不做 | 原因 |
| --- | --- |
| OS / 容器 sandbox、Guardian 第二模型 | 非生活助手最小核 |
| 默认 ToT / LightDAG / LLM 互啄选麦 | `:free` 烧额度；Room 已禁 |
| Host / 群 compact **默认** LLM | Q3A/Q5A；扩展 X4/X5 |
| Dreaming / belief 全量 cron / Mem0 每轮 LLM extract | 贵且非最小 |
| 系统推送 / Slack webhook / monitoring 爬网 | M7 仅 due-on-open |
| 短问答自动建 LifeGoal；每条消息写 checkpoint | Q1A；噪声 |
| 把 pack 拼进 user 再 store；合并 1:1 与 Room 物理 transcript | M0 硬不变量 |
| 立刻杀线程式取消 | Q6A 协作边界 |
| 忌口只追加靠模型消歧 | Q7A 必须 supersede |
| 改坏 OpenRouter 日限 45 / `:free` 强制后缀 | 既有安全闸 |

---

## 2. 拍板默认表（用户已确认，Cursor 勿改）

| 议题 | 决定 | 实现含义 |
| --- | --- | --- |
| **Q1A** | 仅显式/模板建 LifeGoal | 触发短语见 §C（如「开始计划…」「今日健身和饮食」模板）；闲聊「今天吃什么」**不**建 |
| **Q2A** | SoftRoutine = due-on-open + 确认才跑模型 | 打开 App/进会话列 due；用户确认或一键跑 → 走 M4；**无**后台偷跑 |
| **Q3A** | 群 compact 零 LLM：尾窗 + 用户句 + Constraint | 扩展 `compact_room_messages`；禁止默认 summarizer LLM |
| **Q4A** | 单次 run 预算偏紧可配 | 默认 `BudgetLimits(model_calls=8, seconds=120)`；可用 env 覆盖 |
| **Q5A** | Host 默认不 LLM | 规则三行；`LIGHTAGENT_ROOM_HOST_LLM` 保持默认关且本最小集**不实现** LLM 分支 |
| **Q6A** | 协作边界取消 + 半执行文案 | `CancellationToken` 在模型/工具边界生效；UI 文案承认「建议可能已展示」 |
| **Q7A** | 忌口 supersede in place | 同主题旧条 `status=superseded`（或等价不可注入）；注入只看 `active` |

---

## 3. 模块实现顺序（可独立 merge/测）

```text
批次 A ── M0 EphemeralPackLane + M4 RunControl
批次 B ── M3 CompactPreFlush + M5 ConstraintCard
批次 C ── M1 LifeGoalStore + M2 CheckpointStore
批次 D ── M6 HostedProgress
批次 E ── M7 SoftRoutineGate
收尾   ── 全局回归 + acceptance 勾选 + sync tarball 说明
```

**同批次内**：先实现两个模块的纯库/存储，再接线，再**分别**跑各模块测试；任一侧红则停。  
**跨批次**：上一批次全部绿才开下一批次。

---

## 4. 已核实接线锚点（实现时对照，勿凭记忆）

| 钩子 | 文件:行（本机 tree 核实） | 现状 | 本 plan 动作 |
| --- | --- | --- | --- |
| `agent.run` | `local/tui/backend.py:409–415` | 无 `cancellation_token` | M4 传入 |
| `make_agent` | `local/openrouter_config.py:78–106` | 无 `budget_limits` / `context_budget` | M4 传入可配 BudgetLimits |
| `LightAgent.__init__` | `LightAgent/core.py:175` | 已支持 `budget_limits` | 接线即可 |
| `LightAgent.run` | `LightAgent/core.py:526` | 已支持 `cancellation_token` | 接线即可 |
| `BudgetLimits` | `LightAgent/runtime.py:292–360` | 有 `BudgetExceeded` | 复用 |
| `CancellationToken` | `LightAgent/cancellation.py:11–50` | 协作式 | 复用 |
| `_save_rooms` | `local/tui/app.py:1426–1438` | **未** compact | M3 调 `compact_room_messages` |
| `_send_room_turn` | `local/tui/app.py:1510+` | 末尾 `_save_rooms` | 间接受益 |
| `compact_room_messages` | `local/rooms/digest.py:40–44` | 纯尾窗 keep=40 | M3 扩展保真 |
| `strip_ephemeral`（room） | `local/rooms/digest.py:17–19` | 已有 | M0 守住 |
| `strip_ephemeral`（inject） | `local/memory/inject.py:34–43` | 已有 | M0 验收加固 |
| `compose_system` 顺序 | `local/memory/inject.py:72–75` | base→persona→identity→pack | M0 不变量 |
| `flush` | `local/compact/flush.py` | 规则 flush + pin never | M3 挂入口 |
| `render_host_summary` | `local/rooms/host_summary.py:11–28` | 截断回声 + 固定下一步 | M6 改三行 |
| `run_user_turn` | `local/rooms/runtime.py:34–169` | 末尾 Host | M1/M5/M2/M6 读写入 |
| `ProfileStore.forget` | `local/memory/store.py:265` | **硬删** | M5 增 supersede（软替换），forget 可保留硬删 |
| workspace | `local/tui/app.py:564–565` | `local/data/workspace` | goals/routines 挂其下或同级 `local/data/` |
| 日限 | `openrouter_config.py:25` | `DAILY_LIMIT=45` | 不动；M4 是单次 run 闸 |
| TUI cancel | `identity_ui.py` `action_cancel` | 只关弹层 | M4 需**对话中**取消入口 |

---

## 5. 全局回归与环境

每批次结束后，以及最终收尾，必须：

```bash
cd /workspace/LightAgent   # 或云端等价根目录
export LIGHTAGENT_FORBID_OPENROUTER=1
export PYTHONPATH=.
pytest local/rooms local/conversations local/memory local/compact/tests \
  local/goals/tests local/checkpoints/tests local/constraints/tests \
  local/routines/tests local/harness/tests \
  -q
```

说明：

- 新目录若某批次尚未创建，该路径可暂时省略，但**不得**跳过已存在套件。  
- 最终收尾时上列路径（已实现的）必须全绿。  
- **禁止**测试默认打 OpenRouter；mock/`mode="mock"`/纯存储单测优先。

---

## 6. 批次 A — M0 EphemeralPackLane + M4 RunControl

### 6.1 M0 — EphemeralPackLane

#### 行为

1. **不变量**（已有则加固测试；缺则补）：  
   - 注入顺序：`compose_system` = base → persona → identity → `<memory-context>`（`inject.py:72–75`）。  
   - `strip_ephemeral`（inject + rooms/digest）在 store / Room digest / 子委派前必须跑。  
   - Pack 构建失败 → fail-open 无 pack；额度/不可用类可注入短 notice（与「无偏好」区分）。  
   - 子 Bot：host stamp 用户 scope；禁止子改全局 namespace。  
2. **本模块以验收加固为主**：若现网路径已满足，只加测试与一处审计钩（可选：`assert not user_text_contains_pack(saved_history)` 在 backend 存盘前）。  
3. **禁止**把 pack 拼进 user 再持久化。

#### 改哪些文件

| 操作 | 路径 |
| --- | --- |
| 修改（薄） | `local/memory/inject.py`（仅当发现漏洞时修；否则不动逻辑） |
| 修改（薄） | `local/tui/backend.py`（存盘前 strip / assert 可选） |
| 修改（薄） | `local/rooms/digest.py` / `utterance.py`（确认委派 digest 已 strip） |
| 新建 | `local/harness/tests/test_m0_ephemeral_pack.py`（或扩 `local/memory/tests/test_inject.py`） |

#### JSON / API

无新持久化。可选：

```python
def assert_transcript_clean(messages: list[dict]) -> None:
    """Raise if <memory-context> appears in any persisted user/assistant content."""
```

#### 本模块测试与通过标准

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. pytest local/memory/tests/test_inject.py local/harness/tests/test_m0_ephemeral_pack.py -q
```

| 验收 | 标准 |
| --- | --- |
| **E11** | 模拟一轮 prepare_turn → 持久化副本经 strip 后 **无** `<memory-context>`；故意注入脏 user 消息时 strip 清掉 |
| 回归 | 现有 `test_inject.py` / `test_acceptance_invariants.py` 仍绿 |

#### 失败回滚

- 仅测试新增：删测试文件即可。  
- 若改了 inject：回退到「pack 只进 system、永不拼 user」的旧行为；勿引入「拼进 user」。

---

### 6.2 M4 — RunControl

#### 行为

1. `make_agent(..., budget_limits=...)`：默认  
   `BudgetLimits(model_calls=8, seconds=120)`（Q4A）；  
   可用 env：`LIGHTAGENT_RUN_MODEL_CALLS`、`LIGHTAGENT_RUN_SECONDS`（缺省即上值）。  
2. `backend.py` 每次 `agent.run(..., cancellation_token=child_token)`。  
3. TUI：对话进行中提供**停止**（绑定或按钮）→ `token.cancel(reason="user_cancel")`。  
4. 捕获 `BudgetExceeded` → 用户可见提示；状态留给 M1/M2（本批次可先写 `run_control` 事件/回调钩，M1 批次接 `budget_reached`）。  
5. 取消文案（Q6A）：明确「已在协作边界停止；若刚才已展示建议，请以界面已显示内容为准，勿假定未执行」。  
6. SoftRoutine 触发的 run（批次 E）**必须**同样走本路径——本批次先把 helper 抽成可复用函数。

#### 改哪些文件

| 操作 | 路径 |
| --- | --- |
| 修改 | `local/openrouter_config.py`（`make_agent` 注入默认 BudgetLimits；允许 kwargs 覆盖） |
| 修改 | `local/tui/backend.py`（持有/传入 CancellationToken；处理 BudgetExceeded / cancelled） |
| 修改 | `local/tui/app.py`（停止动作接到 token，非仅关弹层） |
| 新建 | `local/harness/run_control.py`（`default_budget_limits()`、`make_run_token()`、用户可见文案常量） |
| 新建 | `local/harness/tests/test_m4_run_control.py` |

#### JSON / API

```python
# local/harness/run_control.py
def default_budget_limits() -> BudgetLimits: ...
USER_CANCEL_NOTICE = "已停止。若刚才已展示建议，请以界面内容为准（半执行）。"
BUDGET_REACHED_NOTICE = "本轮额度/时间用尽，已暂停。可稍后再说「继续」。"
```

#### 本模块测试与通过标准

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. \
  pytest local/harness/tests/test_m4_run_control.py -q
```

| 验收 | 标准 |
| --- | --- |
| **E5** | 构造极紧 `BudgetLimits(model_calls=0)` 或 mock consume → 抛/转译为可见 `BUDGET_REACHED_NOTICE`；不落未捕获异常 |
| **E3***（本批部分） | `token.cancel()` 后 `agent.run` 协作路径可测（可用 stub agent 检查 token 传入与通知文案）；全链路半执行文案存在 |
| 单元 | `default_budget_limits()` 默认 8 / 120；env 可覆盖 |

\* E3 完整（写 checkpoint）在批次 C 与 M2 闭合；本批至少：**无未捕获异常 + 文案 + token 传入**。

#### 失败回滚

- `make_agent` 去掉 budget 默认（kwargs 不传则与旧行为一致）。  
- backend 去掉 token 参数即回退。  
- 勿为「通过测试」假造同步杀线程。

---

## 7. 批次 B — M3 CompactPreFlush + M5 ConstraintCard

### 7.1 M5 — ConstraintCard（建议本批先做存储，再给 M3 保真用）

#### 行为

1. ConstraintCard = 忌口/过敏/硬限制的 **active** 集；**唯一真相源**供：注入、Host「忌口」行、群 compact keep。  
2. API：`remember` / `forget` / **`supersede`**（Q7A）：同主题 supersede in place——旧条标 `superseded`（不可注入），新条 `active`。  
3. 优先规则抽取（忌口关键词）；失败则保留显式写入的原文列表。  
4. 可落在 `ProfileStore` 扩展（learning `status`）或独立 JSON；**推荐**：独立薄卡 JSON + 可选同步到 learnings，避免大改 SQLite schema；若扩 schema，status 枚举含 `superseded`。  
5. `forget`：用户明确忘记 → 硬删或标 superseded 且不注入（与现 `forget` 硬删兼容）。

#### 改哪些文件

| 操作 | 路径 |
| --- | --- |
| 新建 | `local/constraints/__init__.py` |
| 新建 | `local/constraints/card.py`（load/save/remember/forget/supersede/active_texts） |
| 新建 | `local/constraints/extract.py`（规则抽取，零 LLM） |
| 新建 | `local/constraints/tests/test_m5_constraint_card.py` |
| 修改（薄） | `local/memory/inject.py` 或 pack 组装：active constraints 进入 ephemeral（短列表） |
| 可选修改 | `local/memory/store.py`（若选 schema 扩展 superseded；否则可不改） |

#### JSON / API

路径建议：`{workspace}/constraints/card.json`（或 `local/data/workspace/constraints.json`）。

```json
{
  "items": [
    {
      "id": "c1",
      "text": "忌口：海鲜",
      "status": "active",
      "updated_at": "2026-10-14T06:00:00+00:00",
      "supersedes": null
    }
  ],
  "open_questions": [],
  "source": ["explicit", "learning"]
}
```

```python
def supersede(card, *, old_id_or_text: str, new_text: str) -> ConstraintCard: ...
def active_texts(card) -> list[str]: ...  # 仅 status==active
```

#### 本模块测试与通过标准

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. \
  pytest local/constraints/tests/test_m5_constraint_card.py -q
```

| 验收 | 标准 |
| --- | --- |
| 写入 | remember「忌口：海鲜」→ active 含该句 |
| **Q7A** | supersede 为「其实可以吃虾」→ 旧条 superseded，active 仅新条；`active_texts` 不含旧忌口 |
| forget | forget 后 active 消失 |
| 注入 | pack/ephemeral 模拟只含 active（可单测 card→markdown） |

#### 失败回滚

- 删除 `local/constraints/`；inject 去掉 constraints 段。  
- 勿破坏现有 `learn`/`forget` 硬删语义（若未改 store）。

---

### 7.2 M3 — CompactPreFlush

#### 行为

```text
on_before_model / on_save_room:
  1. flush → Profile/Learnings/daily（fail-open；忌口 pin never）— 复用 local/compact/flush.py
  2. 确保 ConstraintCard active 可抽取
  3. 1:1：现有 ContextCompactor / >85% 路径（不拆），仅保证压前调 flush
  4. room: compact_room_messages(keep=N)
       + 强制保留：最近 K 条用户句 + 命中 Constraint active 的句子
       + strip ephemeral
  5. 可选：标记 space resumed_after_compact（文件旗标即可）
```

1. **`_save_rooms`（`app.py:1426`）必须**在 `save_transcript` 前对 `self.room_messages[room.id]` 调用 compact。  
2. 群默认 **零 LLM**（Q3A）。  
3. compact 失败 → 保留原文；**不得**清空 Constraint 源文件。

#### 改哪些文件

| 操作 | 路径 |
| --- | --- |
| 修改 | `local/rooms/digest.py`（扩展 `compact_room_messages`：keep 尾窗 + 保用户句 + 保 constraint 命中句；去重保序） |
| 修改 | `local/tui/app.py` `_save_rooms`（调用 compact；可选压前 flush） |
| 修改（薄） | `local/compact/` 或 `local/tui/app.py` `_maybe_auto_compact`：确保 1:1 压前 `flush` 已调用（若尚未） |
| 新建 | `local/rooms/tests/test_m3_room_compact.py` |
| 新建或扩 | `local/compact/tests/test_flush_hooks.py`（可选） |

#### JSON / API

```python
def compact_room_messages(
    messages: list[RoomMessage],
    *,
    keep: int = 40,
    constraint_texts: list[str] | None = None,
    keep_user: int = 10,
) -> list[RoomMessage]:
    """Zero-LLM. Preserve tail window, recent user lines, and constraint hits."""
```

#### 本模块测试与通过标准

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. \
  pytest local/rooms/tests/test_m3_room_compact.py local/rooms/tests/test_room_store.py -q
```

| 验收 | 标准 |
| --- | --- |
| **E6** | 构造 >keep 条消息，含用户忌口句；compact 后 `len <= keep`（或 ≤ keep+保真溢出的文档化上限）；**Constraint 句仍在** |
| **E7**（联调可后置） | 1:1：flush+pin 后忌口仍在——可复用 compact 既有验收；本批至少测 pin/flush 不被新钩子破坏 |
| 无 LLM | 测试中无 OpenRouter；无 mock LLM summarizer 调用 |
| `_save_rooms` | 单测或轻集成：spy/调用 compact（可用临时 workspace） |

#### 失败回滚

- `_save_rooms` 去掉 compact 调用即回退旧行为。  
- `compact_room_messages` 签名保持兼容：无 `constraint_texts` 时 = 旧纯尾窗。

---

## 8. 批次 C — M1 LifeGoalStore + M2 CheckpointStore

### 8.1 M1 — LifeGoalStore

#### 行为

1. **创建门槛（Q1A）**：仅  
   - 显式用户意图（建议命令/前缀：`/goal …`、或解析「帮我制定…计划」「开始追踪…」等**白名单短语**，写死在 `local/goals/detect.py`，可测）；  
   - 或房间模板（如 `fitness_diet` 场景欢迎后用户确认「今日健身和饮食」→ 建 goal）。  
2. **短问答不建**（E9）：「今天天气呢」「吃什么好」→ 无文件。  
3. Schema 见 minset；路径：`{workspace}/goals/{goal_id}.json`。  
4. **至多一个** `in_progress` step（E2）。  
5. 注入：每轮 ephemeral **一行** objective + 当前 step 标题 + ConstraintCard active（非整份历史）。  
6. `BudgetExceeded` / cancel → `status=budget_reached|paused`（与 M4 钩上）。

#### 改哪些文件

| 操作 | 路径 |
| --- | --- |
| 新建 | `local/goals/__init__.py` |
| 新建 | `local/goals/store.py` |
| 新建 | `local/goals/detect.py`（显式/模板检测，零 LLM） |
| 新建 | `local/goals/inject.py`（ephemeral 一行） |
| 新建 | `local/goals/tests/test_m1_life_goal.py` |
| 修改 | `local/tui/backend.py` 或 app 发送路径：run 前读 goal、组装 ephemeral |
| 修改 | `local/rooms/runtime.py`：模板路径可 `ensure_goal_for_room_turn` |
| 修改（薄） | `local/memory/inject.py` `compose_system` 可多一段 goal 行（仍 ephemeral） |

#### JSON / API

```json
{
  "goal_id": "hex",
  "space_id": "session_or_room",
  "objective": "一周健身与饮食",
  "constraints_ref": ["忌口：海鲜"],
  "steps": [
    {"id": "s1", "title": "定训练日", "status": "completed"},
    {"id": "s2", "title": "配一日三餐", "status": "in_progress"}
  ],
  "status": "active",
  "acceptance": ["有可执行训练计划", "有忌口合规菜单"],
  "updated_at": "ISO-8601",
  "source": "explicit_user"
}
```

```python
def create_goal(...) -> LifeGoal: ...
def get_active_goal(space_id: str) -> LifeGoal | None: ...
def set_step_status(goal_id, step_id, status) -> LifeGoal: ...  # 强制至多一个 in_progress
def should_create_goal(user_text: str, *, room_scenario: str | None) -> bool: ...
```

#### 本模块测试与通过标准

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. \
  pytest local/goals/tests/test_m1_life_goal.py -q
```

| 验收 | 标准 |
| --- | --- |
| **E1** | 显式创建后存在 goal JSON；`constraints_ref` / 忌口可追溯到 M5 active |
| **E2** | 试图两步同时 `in_progress` → 自动纠正或拒绝，结果至多一个 |
| **E9** | `should_create_goal("今天吃什么") is False`；模板/显式为 True |
| **E5 闭合** | budget 钩把 goal.status 置 `budget_reached`（可单测 store API） |

#### 失败回滚

- 删除 `local/goals/`；发送路径去掉 goal 注入。  
- 检测函数默认 False → 无 goal 即旧行为。

---

### 8.2 M2 — CheckpointStore

#### 行为

1. 写时机：步完成 / user_cancel / budget / room 轮末 / 用户改目标 / compact_pre（可选）。  
2. 「继续」→ 读最近 checkpoint：跳过 `completed` steps；提示 `pending_side_effects`。  
3. **不** snapshot 文件系统。  
4. 与 M4 文案对齐：`pending_side_effects` 可含 `advice_shown`。

#### 改哪些文件

| 操作 | 路径 |
| --- | --- |
| 新建 | `local/checkpoints/__init__.py` |
| 新建 | `local/checkpoints/store.py` |
| 新建 | `local/checkpoints/tests/test_m2_checkpoint.py` |
| 修改 | `local/harness/run_control.py` / backend：cancel/budget 时 `write_checkpoint` |
| 修改 | `local/tui/app.py`：解析「继续」 |
| 修改 | `local/rooms/runtime.py`：轮末可选写 checkpoint |

#### JSON / API

路径：`{workspace}/checkpoints/{checkpoint_id}.json`（或按 goal_id 索引最新）。

```json
{
  "checkpoint_id": "hex",
  "goal_id": "hex",
  "step_id": "s2",
  "room_id": null,
  "constraints_snapshot": ["忌口：海鲜"],
  "pending_side_effects": [
    {"kind": "advice_shown", "detail": "已展示三分训练草案"}
  ],
  "reason": "user_cancel",
  "ts": "ISO-8601"
}
```

#### 本模块测试与通过标准

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. \
  pytest local/checkpoints/tests/test_m2_checkpoint.py local/goals/tests/test_m1_life_goal.py -q
```

| 验收 | 标准 |
| --- | --- |
| **E3*** | cancel → 写 checkpoint（`reason=user_cancel`）；无未捕获异常；goal 可查 paused/cancelled |
| **E4*** | 「继续」API：不 `create_goal` 新 id；已 completed 步不回到 pending |
| 半执行 | checkpoint 含 `pending_side_effects` 时可被 resume 文案读出 |

#### 失败回滚

- 去掉写/读 checkpoint 调用；「继续」退化为普通用户句。

---

## 9. 批次 D — M6 HostedProgress

### 9.1 行为

规则输出（Q5A，**无 LLM**）：

```text
动作：...     # 本轮实际发言成员的一句话动作，非粘贴全文（建议 ≤40 字/人）
忌口：...     # 必须来自 M5 active_texts()；无则「（无）」
下一步：...   # LifeGoal 下一 pending/in_progress 标题，或短指令提示
```

1. 禁止整段子 Bot 原文（当前 `host_summary.py:22–26` 的 80 字切片回声需改掉）。  
2. `LIGHTAGENT_ROOM_HOST_LLM`：**不实现**开启分支；文档声明忽略。  
3. 选麦仍规则 `plan.py`；不新增评委模型。  
4. `render_host_summary(..., constraints: list[str] | None = None, next_step: str | None = None)`。

### 9.2 改哪些文件

| 操作 | 路径 |
| --- | --- |
| 重写 | `local/rooms/host_summary.py` |
| 修改 | `local/rooms/runtime.py`（传入 constraints + next_step） |
| 修改 | `local/rooms/tests/test_room_runtime.py` 等期望文案 |
| 新建 | `local/rooms/tests/test_m6_host_progress.py` |

### 9.3 测试与通过标准

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. \
  pytest local/rooms/tests/test_m6_host_progress.py local/rooms/tests/test_room_runtime.py -q
```

| 验收 | 标准 |
| --- | --- |
| **E8** | 输出含「动作」「忌口」「下一步」三行结构；**不含**子 Bot 长文整段；忌口行 = 传入的 active 文本 |
| **E10** | 默认路径无 Host LLM 调用（无网络；无 OPENROUTER） |
| 回归 | Room E1–E18 类既有验收仍绿（更新断言适配新 Host 格式） |

### 9.4 失败回滚

- 恢复旧 `render_host_summary` 拼接逻辑（git 回退该文件）。

---

## 10. 批次 E — M7 SoftRoutineGate

### 10.1 行为（Q2A）

1. **仅**用户显式创建（聊天指令如「每周一提醒我称重」或 UI；白名单/规则解析，零 LLM）。  
2. 存储：`{workspace}/routines/{id}.json`。  
3. 字段：`title`, `instruction`, `cadence`（`daily_window|weekly|once`）, `timezone`, `paused`, `owner_space`, `last_run_at`, `next_due_at`。  
4. **交付**：打开 App / 进入对应会话时列出 due；用户**确认**或一键跑 → `make_agent`+`run` **走 M4**；**不**默认系统推送；**不**到点后台偷跑。  
5. 闸：自动 routine 模型调用计入日限；堆积 due **不补跑**，只提示。  
6. 久未使用：下次打开可询问 keep/pause（可先做简单「暂停已久」旗标）。  
7. pause/delete = 可忘记的跨天目标。

### 10.2 改哪些文件

| 操作 | 路径 |
| --- | --- |
| 新建 | `local/routines/__init__.py` |
| 新建 | `local/routines/store.py` |
| 新建 | `local/routines/detect.py` |
| 新建 | `local/routines/due.py`（due-on-open 列表） |
| 新建 | `local/routines/tests/test_m7_soft_routine.py` |
| 修改 | `local/tui/app.py`（启动/切会话时列 due；确认后 run） |
| 可选 | 侧栏/通知条最小 UI（Textual notify 即可） |

### 10.3 JSON / API

```json
{
  "id": "hex",
  "title": "周一称重",
  "instruction": "提醒我称重并记录",
  "cadence": "weekly",
  "timezone": "America/Martinique",
  "paused": false,
  "owner_space": "session_or_room",
  "last_run_at": null,
  "next_due_at": "ISO-8601",
  "created_at": "ISO-8601"
}
```

### 10.4 测试与通过标准

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. \
  pytest local/routines/tests/test_m7_soft_routine.py -q
```

| 验收 | 标准 |
| --- | --- |
| **E12** | 显式创建成功；`paused=True` 后 due 列表不含；due-on-open API 在 `next_due_at<=now` 时返回；**无**定时器自动调用 `make_agent`/`run`（测试断言无 NETWORK_CALLS 增量） |
| 改主意 | delete/pause 后不再 due |
| M4 | 确认执行入口调用 `default_budget_limits` / token（可 mock） |

### 10.5 失败回滚

- 删除 `local/routines/`；app 去掉 due 列表钩子。

---

## 11. 端到端离线场景（收尾必跑，可用纯 mock）

在 `local/harness/tests/test_e2e_long_horizon_offline.py`：

1. **同日多步**：显式建 goal + 忌口 remember → mock 两轮 → checkpoint → cancel → 继续 → 断言 E1–E4。  
2. **群**：多消息 save → compact → Host 三行含忌口（E6/E8）。  
3. **Routine**：创建 → 拨到 due → 列表有 → pause → 无；确认跑路径不偷跑（E12）。  
4. **Pack**：全程 transcript 无 `<memory-context>`（E11）。

---

## 12. 交付物

| 交付 | 路径 / 说明 |
| --- | --- |
| 代码 | `local/harness/`、`local/goals/`、`local/checkpoints/`、`local/constraints/`、`local/routines/` + 接线修改 |
| 验收勾选 | **`local/research/long_horizon_harness_acceptance_zh.md`**（E1–E12 表，每项：通过/命令/日期） |
| README 薄说明 | 各新包 `__init__` 或 `local/harness/README.md`：不变量 + 非目标 |
| Sync tarball | 收尾脚本说明见下 |

### 12.1 Sync tarball 说明（给二开方本机更新）

实现完成后，在仓库根生成可同步包（**不含** `.env`、API key、`local/.openrouter_usage.json`、大型 `.git`）：

```bash
# 在 LightAgent 根目录
tar -czvf /tmp/lightagent-long-horizon-harness.tgz \
  --exclude='local/.openrouter_usage.json' \
  --exclude='**/__pycache__' \
  --exclude='.git' \
  local/harness local/goals local/checkpoints local/constraints local/routines \
  local/memory local/compact local/rooms local/tui local/openrouter_config.py \
  local/research/long_horizon_harness_*.md \
  local/research/life_assistant_long_horizon_deepdive_zh.md \
  local/research/harness_production_eval_zh.md
```

本机解压覆盖 `local/` 对应目录后：

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. pytest local/rooms local/conversations \
  local/memory local/compact/tests local/goals/tests local/checkpoints/tests \
  local/constraints/tests local/routines/tests local/harness/tests -q
```

由二开方（Grok Bot）在云电脑本地 agent 上试用，对照 acceptance 与「个人助手预期」做最终判定。

---

## 13. Cursor 工作方式（强制）

1. **每完成一个模块**（不是整批）：跑该模块「本模块测试」命令；红则修到绿，**禁止**开写下一模块。  
2. 同批次两模块：先 M_x 绿，再 M_y 绿，再跑批次相关回归。  
3. 代码精简：优先接线；禁止平行实现第二套 Budget/Cancel。  
4. `:free` 默认路径**零额外 LLM**（Host/compact/detect/extract）。  
5. 中文用户可见文案；代码标识符英文。  
6. 勿提交 API key；勿在测试里打外网。  
7. 云端若为空 Origin draft：**先**按本 plan 目录落地，并假设 `local/tui`、`local/rooms`、`local/memory`、`local/compact` 已存在（与既往 P0/Room 一致）；缺失时从用户上传/附件恢复，勿重写整仓。  
8. 每模块结束可在 acceptance 草稿勾选对应 E*（最终文件收尾一次写全）。

---

## 14. 建议 Cursor 首批 Prompt（摘要）

> 在 LightAgent 二开树（以现有 `local/` 为真相）按 `local/research/long_horizon_harness_impl_plan_zh.md` **仅实现批次 A：M0 EphemeralPackLane 验收加固 + M4 RunControl**（`make_agent` 默认 `BudgetLimits(model_calls=8,seconds=120)`，`backend.agent.run` 传 `CancellationToken`，停止半执行文案）。读 minset/eval 缺口；`LIGHTAGENT_FORBID_OPENROUTER=1` 下跑通 M0/M4 专属 pytest 再停；**不要**开始 M3/M5。

---

## 15. E1–E12 映射速查

| ID | 闭合批次 | 主测试位置 |
| --- | --- | --- |
| E1 | C | `local/goals/tests` |
| E2 | C | `local/goals/tests` |
| E3 | A 部分 + C | `harness` + `checkpoints` |
| E4 | C | `checkpoints` |
| E5 | A + C | `harness` + goals status |
| E6 | B | `rooms/tests/test_m3_*` |
| E7 | B | compact/flush + constraints |
| E8 | D | `test_m6_host_progress` |
| E9 | C | `goals/detect` |
| E10 | D（+全程） | Host 无 LLM；forbid openrouter |
| E11 | A | `test_m0_*` |
| E12 | E | `routines/tests` |

---

## 16. 证据与置信度

- 接线行号已于 2026-10-14 对本机 `/workspace/LightAgent` 用 rg/Read 核实（backend:409、app:1426、digest:40、host_summary:11、inject:34/72、openrouter make_agent:78、runtime BudgetLimits:292、cancellation:11）。  
- 产品默认来自用户拍板 Q1A–Q7A。  
- **未**在本 plan 任务中改业务代码。  
- 置信度：实现可执行性 ~0.88；云端 draft 需自带/挂载现有 `local/` 树。
