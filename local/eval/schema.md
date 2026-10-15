# Eval case YAML schema

每条用例是 `cases:` 列表中的一个 mapping。

## 必填

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | str | 唯一 id，如 `L2-I01` |
| `dim` | str | `intent` \| `decompose` \| `tool` \| `context` |
| `tier` | str | `l2` \| `l3` \| `jd` |
| `bar` | str | 可选 JD 标签 `A`–`E`（见 jd_bar.yaml） |
| `title` | str | 短标题 |
| `mode` | str | `store`（纯库，无 API）\| `live_agent`（`make_agent`+TOOLS） |
| `turns` | list | `[{role: user, text: ...}, ...]`；store 通常一句 |

## 可选

| 字段 | 说明 |
| --- | --- |
| `setup` | 跑前 store 操作：`absorb` / `open_goal` / `create_routine` / `memory_learn_pin` / `cancel_goal` |
| `store_action` | store 模式主动作：`absorb` / `maybe_open_goal` / `advance` / `parse_routine` / `classify` / `cancel` / `resume` / `sanitize` / `confirm_routine` / `auto` |
| `create_if_parsed` | parse_routine 成功时是否 `RoutineStore.create` |
| `notes` | 自由备注 |
| `expect.tools` | `{must: [], forbid: [], extra: allow\|forbid}` — live 用 |
| `expect.stores` | `[{check: <name>, args?: {}}]` — 见 runners/common.py `_STORE_CHECKS` |
| `expect.invariants` | `no_memory_context_leak` / `no_new_goal` / `routine_not_run` / `reply_avoid_seafood_primary` |

## 判定

- **PASS**：硬断言全过  
- **PARTIAL**：软约束（如忌口回复 heuristic、extra tools）未过  
- **FAIL**：硬断言失败  
- **ERROR**：异常 / 额度 / 鉴权  

终态可断言优先于 LLM-as-judge。

## jd_bar_v2 新增 store checks

| check | 含义 |
| --- | --- |
| `constraint_contains_all` | 多 needle 均在忌口卡 |
| `room_speakers_at_most` | TurnPlan.speakers ≤ max |
| `digest_no_ephemeral` | room digest 剥离 memory-context |
| `no_recursive_swarm` | TurnPlan 无 children/sub_plans（单层边界） |
