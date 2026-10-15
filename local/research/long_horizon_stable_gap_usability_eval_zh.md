# 稳达三缺口可用性短评

日期：2026-10-14（America/Martinique, UTC-4）  
评估方：Grok Bot executor  
云端 agent：`bc-a7e50eab-1b8d-5087-b5de-f9c4f66105be`  
本机包：`/workspace/cloud-agent-artifacts/bc-a7e50eab-1b8d-5087-b5de-f9c4f66105be/lightagent-stable-gap-abc.tgz`  
sha256：`03977fec73b5612a1b92c878433eb82fe4f277ad941ae59f963a5d3b2c9b93ae`（**匹配**）  
备份：`/workspace/LightAgent-backup-pre-stable-gap-202610140439.tgz`  
环境：`LIGHTAGENT_FORBID_OPENROUTER=1`，`PYTHONPATH=.`，解释器 `/workspace/la-venv/bin/python`  
对照：先前「勉强达」评估见 `long_horizon_harness_usability_eval_zh.md`；plan 见 `long_horizon_stable_gap_plan_zh.md`；验收 17 条见 `long_horizon_stable_gap_acceptance_zh.md`。

---

## 1. 同步状态

| 项 | 结果 |
| --- | --- |
| 覆盖进 `/workspace/LightAgent` | **已完成**（解压覆盖 `local/constraints` `local/goals` `local/harness` `local/research` `local/routines` `local/tui`） |
| sha256 | 与任务声明一致 |
| 关键产物 | `goals/advance.py`、`constraints` absorb 接线、`harness/lh_probe.py`（S7–S9）、stable_gap 测试与 research 文 |
| 用户本机 `desire` | 评估时不可达；本文件与代码落在 box `/workspace/LightAgent`，待本机恢复后再镜像 |

未改业务代码以外的实现；全程未调 OpenRouter。

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

**结果：164 passed in 16.40s**（日志：`/tmp/stable_gap_pytest.txt`）

相对先前 146，新增约 18（A/B/C stable_gap 测）。E1–E12 语义仍绿；A-T / B-T / C-T 共 17 条与包内验收文一致。

---

## 3. 扩展探针（`local.harness.lh_probe`）

```bash
LIGHTAGENT_FORBID_OPENROUTER=1 PYTHONPATH=. \
  /workspace/la-venv/bin/python -m local.harness.lh_probe
```

日志：`/tmp/stable_gap_probe_out.txt`。`NETWORK_CALLS` 0→0。

| 场景 | 结果 | 证据摘要 |
| --- | --- | --- |
| S1 显式 goal + 忌口卡 | **PASS** | `constraints_ref=['忌口：海鲜']` |
| S2 短问不建 goal | **PASS** | 「今天吃什么」无 goal 文件 |
| S3 cancel / 续跑 | **PASS** | checkpoint + 同 goal_id |
| S4 Host 三行 + compact | **PASS** | 109→41，忌口仍在 |
| S5 例程确认才跑 | **PASS** | create 零调用；confirm runner=1 |
| S6 落盘无 memory-context | **PASS** | transcript clean |
| **S7** 1:1 absorb 再开 goal | **PASS** | absorb「忌口：海鲜」→ ref 含海鲜 |
| **S8** 口语推进步骤 | **PASS** | 「训练日定好了」→ s1 completed / s2 in_progress |
| **S9** 同义触发正例 | **PASS** | 「别再给我海鲜」入卡；「每周一叫我称重」weekly |
| NET | **PASS** | 全程无网络 |

**探针汇总：10 PASS / 0 FAIL**（含原六场景 + 稳达 S7–S9 + NET）

日用三缺口对照：

| 缺口 | 判定 | 说明 |
| --- | --- | --- |
| A 1:1 忌口进约束卡 | **达** | `absorb_user_text` 后开 goal 拍进 `constraints_ref`（S7） |
| B 口语推进步骤 | **达** | `maybe_advance_goal` 对「训练日定好了」等（S8） |
| C 同义触发扩面 | **达** | 忌口/例程/目标同义正例 + 「今天吃什么」负例仍稳（S2/S9） |

---

## 4. 总评

**总评：稳达。**

相对「勉强达」：三缺口已闭合，本机 **164 passed**、探针 **10/10**，1:1 忌口→卡→goal、口语推进、同义触发均在 mock 日用路径可用，且零额外 LLM / 零 OpenRouter。

仍残留（不挡「稳达」标签，但跨天真用需知）：

1. **compact flush 不写忌口卡**——仍只写 Profile；忌口依赖 absorb / 群 transcript / 显式 remember。
2. **群聊不推进步骤**——`maybe_advance_goal` 挂在 1:1 send；群里说「完成了」不改 step。
3. **短语误触风险仍在**——关键词+同义扩面，极端短句偶发误触可能；负例「今天吃什么」已护住，未做大规模语料。
4. **同句忌口整句入卡**——未做规范化拆条；抬升/supersede 靠整句匹配。
5. **无真 OpenRouter 烟测**——本评估刻意禁网。

---

## 5. 路径索引

| 用途 | 路径 |
| --- | --- |
| 包 | `.../lightagent-stable-gap-abc.tgz` |
| 备份 | `/workspace/LightAgent-backup-pre-stable-gap-202610140439.tgz` |
| pytest 日志 | `/tmp/stable_gap_pytest.txt` |
| 探针日志 | `/tmp/stable_gap_probe_out.txt` |
| 本报告 | `local/research/long_horizon_stable_gap_usability_eval_zh.md` |
| 云端短评（参考） | `local/research/long_horizon_stable_gap_usability_note_zh.md` |
