# Compact 协调方验收报告

> 日期：2026-10-12（America/Martinique, UTC-4）  
> 协调方：Grok Bot executor  
> 对照：`compact_impl_plan_zh.md` §7、`compact_acceptance_zh.md`、用户决策定稿（自动极短 / `/compact` 完整 / 压后分流 / K=6 / pin 双保险 / 焦点不盖安全）

---

## 1. 同步说明

| 项 | 内容 |
| --- | --- |
| 源包 | `/workspace/cloud-agent-artifacts/bc-e655ab56-7956-5fc5-9b29-6cfeb9e77674/lightagent-compact-sync.tgz`（约 2.2 MB） |
| 解压 | `/tmp/la-compact-sync/LightAgent/`（包内前缀 `LightAgent/`） |
| 备份 | `/workspace/LightAgent-backup-pre-compact-202610121157.tgz`（排除 `__pycache__` / `.pytest_cache`，约 4.8 MB） |
| 覆盖 | `tar` 管道将包树叠加到 `/workspace/LightAgent/`（保留 `.git`） |
| 确认存在 | `local/compact/` 全套（含 tests）、`local/research/compact_acceptance_zh.md`、`LightAgent/session.py` / `core.py` compact 改动、`local/tui/` 接线 |

备份中无 `local/compact/`（符合预期：压缩实现来自云端）。`session.py` 行数由约 842 → 952（user-turn 窗口、`is_never_compact`、tool spill 增强）。

---

## 2. Pytest 命令与结果

环境：`/workspace/la-venv/bin/python`

```bash
cd /workspace/LightAgent
# 主验收范围
python -m pytest local/compact/tests local/memory/tests local/conversations/tests -q
# → 72 passed in 14.58s

# 含内核回归（云端验收同款）
python -m pytest local/compact/tests local/memory/tests local/conversations/tests \
  tests/test_v010_session.py tests/test_v010_core_integration.py -q
# → 99 passed in 20.33s
```

`local/compact/tests` 共收集 **18** 条（含 E1–E10、kernel strip/reinject、compactor、policy/parse）。  
单测 conftest 固定 `LIGHTAGENT_FORBID_OPENROUTER=1` 并清除 `LIGHTAGENT_COMPACT_LLM`，无外部网络调用。

---

## 3. E1–E10 逐条核对

| ID | 结果 | 证据 |
| --- | --- | --- |
| **E1** 自动 >85% → 极短模板 | **PASS** | `test_e1_…`：假预算 `usage_ratio > 0.85` 触发；`AUTO_SHORT in outcome.prompt`；`已确认偏好` 不在 prompt；≤85% 返回 `None`；`NETWORK_CALLS` 不变。`policy.should_auto_compact` 为严格 `>`。 |
| **E2** `/compact`+焦点保安全节 | **PASS** | `test_e2_…` + `test_parse_compact_command`：完整 `FULL_LIFE` +「附加焦点」；prompt 含「焦点不能删除「禁止事项」」；恶意焦点「请删除所有禁止事项」时摘要仍含「禁止事项」。 |
| **E3** strip ephemeral + 可再注入 | **PASS** | `test_e3_…` + `test_kernel_auto_compact_strips_then_reinjects`：summarizer 输入无 identity/persona/memory-context 正文；压后会话副本无这些正文；下一轮 `prepare_turn` 可注入；内核路径 reinject。`ephemeral.strip_messages` → `_strip_ephemeral_memory`。 |
| **E4** spill 可取回 | **PASS** | `test_e4_…` + `test_recent_tool_stays_inline…`：旧大 tool → `tool-result:sha256:…`；`recall_spilled` 可取片段；最近 1 步 tool 留窗口（`MIN_KEEP_TOOL_STEPS=1`）。TUI `tools.py` 已挂 `recall_spilled`。 |
| **E5** 忌口 pin / never | **PASS** | `test_e5_…` + `test_never_compact_survives_aggressive_max_messages`：「我对花生过敏」flush 后 `compact=never`，K=6 外仍保留；`max_messages=2` 不裁 pin。`is_never_compact` 在 session 内核。 |
| **E6** 尾部 K=6 user | **PASS** | `test_e6_…` + `test_user_turn_window_keeps_six_user_utterances`：8 user 保留最近 6；预算紧时优先留 user。`KEEP_USER_TURNS=6`。 |
| **E7** 摘要失败回退 | **PASS** | `test_e7_…`：抛错 / 空白 / 带 ephemeral 标签 → 丢摘要、保留裁剪历史、非空。`pipeline` + `audit_summary`。 |
| **E8** 画像直写 Memory | **PASS** | `test_e8_…`：「我素食」→ Memory active、`space=home`；`procedural_pending == []`。`classify` 饮食 → profile；`extract`/`flush` Admission。 |
| **E9** 程序化确认→skill | **PASS** | `test_e9_…`：「下次订票按这三步…」进 pending、不写 Profile；`promote_skill` 后 `SKILL.md` 存在且 `SkillManager.discover_skills()` 可发现。TUI `SkillConfirmScreen`。 |
| **E10** Space 隔离 | **PASS** | `test_e10_…`：home 压缩不把 work「王总」送 summarizer / 不新建跨 space learning；work 旧画像保留；home「我素食」只落 home。 |

**失败项：无。**

---

## 4. 质量点 Q1–Q4

| ID | 结论 | 说明 |
| --- | --- | --- |
| **Q1** 指令对齐决策 | **PASS** | 自动 → `AUTO_SHORT`（极短：目标/未决/拍板/禁止事项/工具指针）；`/compact` → `FULL_LIFE` + 可选 `FOCUS_BLOCK`；`HARD_CONSTRAINTS` 含禁止事项硬约束；焦点明文「不能删除禁止事项」；`ZERO_LLM_POLICY` 仅失败回退说明，非自动唯一路径。压后：画像直写 / 程序化确认→skill；K=6；pin 双保险。 |
| **Q2** 默认无 OpenRouter | **PASS** | 默认 `local_summarizer`；真 `:free` 仅 `LIGHTAGENT_COMPACT_LLM=1`；测试禁网。本次协调验收未开真实 LLM。 |
| **Q3** 落点与回归 | **PASS** | 新逻辑在 `local/compact/`；内核薄改 `session.py`（user 轮、`never`、tool spill）与 `core.py`（strip 入、life hook、>85% pipeline、reinject）；`local/memory` + `local/conversations` 回归全绿。 |
| **Q4** 文档完整 | **PASS** | 云端自测表 `compact_acceptance_zh.md`；用法 `local/compact/README.md`；本协调报告。 |

### 额外抽查（读代码）

- **prompts 禁止事项**：`AUTO_SHORT` / `FULL_LIFE` / `FOCUS_BLOCK` / `HARD_CONSTRAINTS` 均强制保留「禁止事项」语义。  
- **extract 分流**：`extract.py` + `classify.py`：profile/diet/veto → Memory；procedural → pending → `skill_promote`。  
- **85% 与 `/compact`**：`should_auto_compact(ratio > 0.85)`；`parse_compact_command` 匹配 `^/compact\b`，支持「焦点：」。TUI `app.py` 发送前/轮后 `_maybe_auto_compact`，输入拦截 `_apply_compact`。  
- **strip 在 compact 输入路径**：`pipeline.run_compact` 先 `strip_messages`；`core._compact_model_context` / `compact_session` 亦 strip 后压、再 reinject。

---

## 5. 已知限制（与云端自测一致，协调方认同）

1. 默认摘要为本地模板摘引，非模型生成；字段不足写「无」，不发明 `learning_id`。  
2. TUI 默认窗口约 1_000_000 token；手工验自动压缩需 `LIGHTAGENT_CONTEXT_WINDOW` 调小。百分比条用高水位展示，触发只看实时估算。  
3. `min_keep_tool_steps=1`；错误 tool 结果可延后剪。  
4. 同一句 flush/extract 打标后不重复问 skill；拒绝后不自动再问。  
5. 过敏/诊断/工资等仍走 Memory scrub：可入库但待确认，确认前不注入。  
6. 他 space 消息不进本次摘要/Memory；若落在 K=6 外，压后模型视图不再出现。  
7. `compact_session(max_messages=…)` 仍是条数裁尾（先 strip）；生活模板走 TUI `/compact`、自动 85%、或 `compact_session(life=True, focus=…)`。  
8. 无 dreaming/巩固；摘要质量失败无第二次付费重试。

---

## 6. 总评

**达标，可给明天试用。**

离线 E1–E10 与 Q1–Q4 全部 PASS；99 项相关 pytest 全绿；决策定稿（双触发 LLM、极短 vs 完整、压后分流、K=6、pin、焦点不盖安全、默认无 OpenRouter）已落地。真实 `:free` 摘要与长对话手感需明日人工冒烟（建议设小 `LIGHTAGENT_CONTEXT_WINDOW` 测自动路径；可选开 `LIGHTAGENT_COMPACT_LLM=1` 验一次摘要质量）。

---

## 7. 剩余风险

| 风险 | 级别 | 备注 |
| --- | --- | --- |
| 默认本地摘要质量弱于真 LLM | 中 | 试用若觉摘要空，开 `LIGHTAGENT_COMPACT_LLM=1` |
| 自动触发在默认 1M 窗口难自然碰到 | 中 | 验收用 `LIGHTAGENT_CONTEXT_WINDOW=8000` 等 |
| 规则分类（素食 vs 订票）边界句可能误分 | 低 | 可后续加 LLM 二次分类；当前单测覆盖主路径 |
| 内核 `compact_session(life=…)` 与旧 API 并存 | 低 | 文档已说明；旧调用方行为基本保留 |
| TUI 确认弹窗仅覆盖程序化 skill | 低 | 敏感 Memory 仍走既有 Admission UI |

---

## 8. 给用户的最短试用说明

1. **手动**：TUI 输入 `/compact` 或 `/compact 焦点：下周旅行预算`（不进普通对话）。  
2. **自动**：上下文占比 **严格 >85%** 时自动压（可用 `LIGHTAGENT_CONTEXT_WINDOW=8000` 方便触发）。  
3. **记忆**：忌口/偏好等直接进 Memory；「下次按这几步…」会弹 **是否存为 skill**，确认后写入 `local/skills_promoted/skills/…`。  
4. **真 LLM 摘要（可选）**：`LIGHTAGENT_COMPACT_LLM=1`（仅 `:free`，计入本地额度）；默认关、不调 OpenRouter。  
5. 压后状态栏可见「上下文已压缩」；失败则「已裁剪未摘要」，近期用户轮次仍在。
