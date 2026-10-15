# 实现 Plan：生活助手上下文压缩（Compact）

> 给 Cursor 云端：**边实现边调试**，直到验收场景可跑通。  
> 依据：`compact_keep_priority_and_prompts_zh.md`（含「决策定稿」）、`personal_assistant_compact_direction_zh.md`  
> 日期：2026-10-12 · 落点：`local/` 为主，必要时薄改 `LightAgent/session.py` / `core.py`  
> **实现与单测默认不调 OpenRouter**；LLM 路径用 mock summarizer；真调用仅走 `:free` 且可关。

---

## 0. 用户已定决策（不可违背）

| 项 | 决定 |
| --- | --- |
| 手动触发 | 用户输入 `/compact`（可带焦点）→ **LLM** 智能压缩 |
| 自动触发 | 总 token 占上下文窗口 **>85%** → **也走 LLM**（极短保守模板） |
| 自动摘要 | **极短保守**模板（目标/未决/拍板/禁止事项/工具指针） |
| `/compact` | **完整**生活结构化模板；焦点不可信，**不能**盖掉禁止事项 |
| 尾部保留 | 最近约 **K=6** 条 **user** 轮 + 配对 assistant/tool |
| 忌口/用药/Never | **Memory 直写 + 会话 `compact=never` pin 双保险** |
| 压后分流 | **画像/偏好/忌口/否决 → 直接写 Memory**；**程序化流程 → 询问用户 → 确认后存 LightAgent skill** |
| 失败 | 摘要失败 → 回退 strip + prune + 尾部窗口；不静默全擦 |
| API | 只用 `:free`；压缩 LLM 计入额度逻辑，失败可降级 |

划分口径：
- **画像/偏好**：用户是谁、爱什么、永远不要什么（稳定事实）→ Memory
- **程序化**：这类事下次按哪几步做（可执行流程）→ 确认后 skill

---

## 1. 目标与非目标

### 目标
1. 接线 `ContextBudget`（85% 阈值）到助手/TUI 路径；超阈值自动 compact。
2. 实现 `/compact [焦点…]` 命令（TUI 与/或 chat 输入解析）。
3. Compact 流水线：`memory_flush` → strip ephemeral → tool prune/spill → turn_window(K=6 user) → LLM summarizer（按触发选模板）→ 压后分流。
4. Summarizer 输入**必须** strip `<identity>`/`<persona>`/`<memory-context>`；压后权威再注入。
5. Spill 可取回（tool 或 API）；pin/`compact=never` 不被裁掉。
6. 压后：画像类 Admission 直写；程序化候选弹确认 UI/回调，确认后写入 LightAgent skill 目录。
7. 离线单测全绿；提供可人工走的验收脚本/清单（mock LLM）。

### 非目标
- 默认依赖 Mem0/Zep 云
- 服务端 Anthropic/OpenAI compaction API
- Dreaming/巩固全量（可留 hook）
- 改坏 `run_free` / `:free` 只允许逻辑
- 照搬 OpenClaw 源码

---

## 2. 建议目录

```
local/compact/
  __init__.py
  types.py              # CompactTrigger, CompactResult, ExtractedMemory, ProceduralCandidate
  policy.py             # 85% 阈值、K=6、min_keep_tool_steps、模板选择
  prompts.py            # 自动极短 /compact 完整 / 焦点追加 / 压后抽取 指令原文
  flush.py              # 压前规则 flush → Admission / 日笔记候选
  pipeline.py           # 编排 ContextCompactor + summarizer + 失败回退
  extract.py            # 压后分流：画像 vs 程序化（可与摘要同次或二次 mockable LLM）
  skill_promote.py      # 确认后写入 local skills（对齐 plugins_system skills_directories）
  recall_spill.py       # recall_spilled tool
  chat_commands.py      # 解析 /compact
  tests/                # 纯本地，无网络
```

薄改内核（尽量小）：
- `LightAgent/session.py`：`ContextCompactor` 支持「按 user 轮保留」「skip metadata.compact=never」、可选增强 prune
- `LightAgent/core.py`：compact 输入走 strip；注入 budget；调用 local pipeline 钩子

复用：
- `local/memory/` Admission / pack / inject / scrub
- `_strip_ephemeral_memory`
- 现有 spill 结构；`local/openrouter_config.py` 的 free-only

---

## 3. 流水线（实现必须一致）

```text
[触发: usage > 85% 或 /compact Focus?]
  1. memory_flush（规则优先；失败不阻断）
  2. COPY messages → strip_ephemeral
  3. tool_spill / prune（min_keep_tool_steps 暂定 1；错误结果可延后剪）
  4. orphan tool 修复
  5. turn_window：1× head system + 最近 K=6 user 轮及配对；尊重 compact=never
  6. LLM summarizer(removed)：
       - auto → prompts.AUTO_SHORT
       - /compact → prompts.FULL_LIFE [+ FOCUS block]
  7. 质量闸：禁 ephemeral 标签正文、禁晋升 untrusted、须有禁止事项/未决（空则写「无」）
  8. 失败 → 丢弃摘要，保留 3–5 步结果
  9. 压后 extract：
       - profile/prefs/veto → Memory Admission（直写）
       - procedural → 待确认队列 → UI 询问 → skill_promote
 10. 下一轮 prepare：权威 ephemeral 再注入
```

---

## 4. 指令原文位置

以 `compact_keep_priority_and_prompts_zh.md` §C.1 极短保守、§C.2 完整、§C.3 焦点、§C.5 硬约束为准，落到 `local/compact/prompts.py` 常量。  
自动路径**不要**用「零 LLM」策略文当唯一路径（用户已否决）；ZERO_LLM 仅作失败回退。

---

## 5. TUI / 产品接线

- 输入以 `/compact` 开头：拦截，不送普通 chat；可选焦点文本。
- 自动 compact：状态栏或 toast「上下文已压缩」（可先状态栏）。
- 程序化候选：Modal/确认列表「是否存为 skill？」→ 是则写入 skill 文件并可选刷新 skills_directories。
- 忌口类 flush 成功后：对关键 user 消息打 `metadata.compact=never`（或等价 pin）。

---

## 6. 实现顺序（边做边调）

1. `policy` + `prompts` + 单测（模板字符串、触发判定）
2. 扩展 `ContextCompactor` 或包装器：user-turn window + never-compact + prune 参数
3. `flush` + 忌口 pin
4. `pipeline` + mock summarizer 端到端
5. `/compact` 解析 + TUI/agent 接线 + 85% budget 接线
6. 压后 extract + Memory 直写 + skill 确认流
7. `recall_spilled` tool
8. 对照 §7 验收清单修到全绿；真 `:free` 冒烟可选、默认可跳过

---

## 7. 验收标准（协调方将据此验收）

### 离线必须（pytest，无网络）

| ID | 场景 | 期望 |
| --- | --- | --- |
| E1 | 构造 >85% 假预算 | 触发 auto compact；调用极短模板 summarizer（mock） |
| E2 | `/compact` 带焦点 | 完整模板 + 焦点块；焦点不能删掉禁止事项字段要求 |
| E3 | 消息含 `<identity>` 等 | summarizer **输入**无 ephemeral 正文；下一轮仍可注入 |
| E4 | 大 tool 结果 | spill；`recall_spilled` 可取回片段 |
| E5 | `compact=never` / 忌口 pin | 激进 max_messages 下仍保留 |
| E6 | 尾部 | 最近 6 条 user 原话仍在 kept（或预算不足时尽可能多但优先 user） |
| E7 | 摘要失败 | 回退纯裁剪；历史不空 |
| E8 | 压后画像 | 「我素食」类 → Memory 有 learning；**不问** skill 确认 |
| E9 | 压后程序化 | 「下次订票按这三步」→ 出现待确认；确认后 skill 文件存在且可被 skills 发现 |
| E10 | Space | 摘要/flush 不串其他 space_id（有 space 则测） |

### 质量评估（协调方人工）

- Q1 指令与决策定稿一致（自动极短 vs /compact 完整）
- Q2 `:free` 路径：单测零外部调用；可选冒烟 ≤1 次摘要/触发
- Q3 代码主要在 `local/compact/`；内核改动有说明且回归 `local/memory` + `local/conversations` 测试仍过
- Q4 文档：`local/research/compact_acceptance_zh.md` 写清如何跑测与已知限制

### 交付物

- 实现代码 + 测试
- `local/research/compact_acceptance_zh.md`（自测结果表）
- 简短 CHANGELOG / 使用说明：如何 `/compact`、自动 85%、skill 确认

---

## 8. 给云端的工作方式

1. 解压附件中的 LightAgent 源码树为工作区基础（已含 P0 记忆、多对话身份、`local/` 二开）。
2. **边实现边跑** `pytest local/compact/tests local/memory/tests local/conversations/tests`（及你新增的），失败就修。
3. 不要默认调 OpenRouter；mock summarizer 覆盖 LLM 分支。
4. 做完后在 artifacts 留下：补丁说明、验收自测表、关键新文件列表。
5. 若与 `core.py` 现有 ephemeral strip / `_dispatch_chat_completion` 冲突，保持 strip 含 persona/identity，并保证 compact 输入也 strip。

---

## 9. 成功定义（一句话）

用户明天能在助手里：对话变长自动（>85%）或手动 `/compact` 压缩；重要偏好进 Memory；可复用流程经确认变成 skill；身份包不被摘要吃掉；本地测试与协调方验收清单通过。
