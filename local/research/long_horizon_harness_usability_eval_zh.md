# 长链路 Harness（M0–M7）可用性评估

日期：2026-10-14（America/Martinique, UTC-4）  
评估方：Grok Bot executor  
云端：`bc-a7e50eab-1b8d-5087-b5de-f9c4f66105be`  
本机包：`/workspace/cloud-agent-artifacts/bc-a7e50eab-1b8d-5087-b5de-f9c4f66105be/lightagent-long-horizon-harness.tgz`  
sha256：`15286f2080e31bc1c3b9b4c2540fbc1fbcd4c6cf91add2e482650b4e1de2e070`  
备份：`/workspace/LightAgent-backup-pre-long-horizon-202610140306.tgz`  
环境：`LIGHTAGENT_FORBID_OPENROUTER=1`，`PYTHONPATH=.`，解释器 `/workspace/la-venv/bin/python`

---

## 1. 同步状态

| 项 | 结果 |
| --- | --- |
| 覆盖进 `/workspace/LightAgent` | **已完成**（解压覆盖 `local/` 等 long-horizon 产物） |
| sha256 | 与任务声明一致 |
| M0–M7 目录 | 均在：`goals` / `checkpoints` / `constraints` / `routines` / `harness` + rooms/digest・host_summary 接线 |
| 先前「同步阻塞」版 | **作废**，本文件覆盖 |

---

## 2. Pytest（本机复跑）

命令：

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. \
  /workspace/la-venv/bin/python -m pytest \
  local/rooms local/conversations local/memory local/compact/tests \
  local/goals local/routines local/constraints local/checkpoints \
  local/harness/tests -q
```

**结果：146 passed in 16.35s**（日志：`/tmp/long_horizon_pytest.txt`）

验收文 E1–E12 与套件一致，见 `long_horizon_harness_acceptance_zh.md`。

---

## 3. Mock 可用性探针（pytest 以外）

脚本：`/tmp/lh_probe.py` → `/tmp/lh_probe_out.txt`  
对照验收六场景 + harness README；全程 mock，`NETWORK_CALLS` 不因 create/confirm 增加。

| 场景 | 结果 | 证据摘要 |
| --- | --- | --- |
| 1. 显式健身+饮食+忌口海鲜 → LifeGoal + Constraint | **PASS** | `maybe_open_goal` 后 `constraints_ref=['忌口：海鲜']`，一步 `in_progress` |
| 2. 「今天吃什么」不建 LifeGoal | **PASS** | `should_create_goal` False；goal 目录不增 |
| 3. cancel → checkpoint；继续不重建 | **PASS** | `record_run_event(user_cancel)` → status=paused；`resume` 同 goal_id；半执行 detail 入 notice |
| 4. Host 三行；群 compact 后忌口仍在 | **PASS** | `动作/忌口/下一步`；109→41 条；`prepare_room_transcript` 仍含「海鲜」 |
| 5. SoftRoutine 创建不跑模型；确认才跑 | **PASS** | parse+create 零网络；`确认提醒` → runner 一次且带 `budget_limits`/`cancellation_token` |
| 6. 落盘无 `<memory-context>` | **PASS** | `sanitize_transcript` + MockBackend 落盘断言干净 |

**探针汇总：6 PASS / 0 PARTIAL / 0 FAIL**

---

## 4. M0–M7 分项

| 模块 | 判定 | 证据 |
| --- | --- | --- |
| **M0** EphemeralPackLane | **PASS** | `local/harness/ephemeral.py`；TUI `sanitize_transcript`；E11 + S6 |
| **M1** LifeGoalStore | **PASS** | `local/goals/`；TUI `_maybe_open_goal`；E1/E2/E9 + S1/S2 |
| **M2** CheckpointStore | **PASS** | `local/checkpoints/`；`record_run_event`←backend/TUI；E3/E4 + S3 |
| **M3** CompactPreFlush（群） | **PASS** | `prepare_room_transcript` absorb+compact；E6/E7 + S4 |
| **M4** RunControl | **PASS** | `execute_controlled` 接 TUI/backend；`action_stop_run`；E3/E5 |
| **M5** ConstraintCard | **PARTIAL** | 卡/supersede/注入与群 absorb **PASS**；**1:1 send 未调用 `apply_utterance`/`absorb_messages`**，仅靠群 `prepare_room_transcript` 或 API `remember` 才会写入卡。用户在 1:1 说「忌口：海鲜」再开 goal，`constraints_ref` 可能为空（探针复现：先 open 无卡 → `[]`；先 `remember` 再 open → 有海鲜） |
| **M6** HostedProgress | **PASS** | `render_host_summary` 三行；runtime 接线；E8/E10 + S4 |
| **M7** SoftRoutineGate | **PASS** | TUI `_consume_routine` / due-on-open；E12 + S5 |

---

## 5. 总评

**总评：勉强达「可长久用的个人助手」预期。**

最小集六（七）块已落地、本机 **146 passed**、六场景 mock 探针全绿，取消/预算/群三行/例程门闩与落盘洁净达到验收。  
尚未敢称「稳达」：1:1 忌口未自动进 ConstraintCard、步骤进度几乎不靠对话推进（需 `set_step_status` API）、触发仍偏关键词——跨天真用仍要用户记得显式说法与群/API 路径。

---

## 6. 缺口（按影响，最多 5）

1. **1:1 不吸收忌口进 ConstraintCard**（影响最大）— `local/tui/app.py` send 只 `_maybe_resume` / `_maybe_open_goal`，无 `apply_utterance`；与 M5「用户改口即写卡」设计不一致。  
2. **LifeGoal 步骤无对话驱动推进** — `set_step_status` 仅库 API/测试；TUI 不根据「训练日定好了」自动 completed→下一 in_progress，长任务易停在窗外清单层。  
3. **触发面偏窄** — goal/routine/constraint 靠中文关键词与模板句；换说法（「一周锻炼餐单」「别再给我海鲜」）易漏建或漏记。  
4. **compact flush ≠ ConstraintCard** — 1:1 `memory_flush` 写 Profile/daily note，不写 `constraints/card.json`；忌口双通道可能漂移。  
5. **未做真 OpenRouter 日用烟测**（本任务禁网）— mock 绿不等于 `:free` 额度/延迟下的体感；上线前仍需短烟测。

---

## 7. 证据索引

- Pytest：`/tmp/long_horizon_pytest.txt` → `146 passed in 16.35s`  
- 探针：`/tmp/lh_probe.py`，`/tmp/lh_probe_out.txt` → 6 PASS  
- 验收：`local/research/long_horizon_harness_acceptance_zh.md`  
- 说明：`local/harness/README.md`  
