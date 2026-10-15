# Coding Agent 上下文压缩（Compact）调研与 LightAgent 优化探索

> 定位：个人生活助手 + TUI + 仅 OpenRouter `:free`  
> 范围：只读本地代码 + 公开文档/源码；**未改**业务代码；**未调** OpenRouter  
> 日期：2026-10-12（America/Martinique）

---

## 1. 结论先行

**LightAgent 现状一句话：** 已有确定性两阶段压缩器（大工具结果外溢 + 保留 system / 尾部消息的滑动裁剪），可选 `summarizer` 回调，但默认不启用 LLM 摘要；自动压缩仅在注入 `ContextBudget` 时触发，本地 TUI 目前未接线，身份/画像 pack 靠 ephemeral 注入且落盘时剥离。

**最值得学的 3 点（贴合免费额度）：**

1. **分层压缩，先启发式后才 LLM** — 业界几乎都是「工具结果剪枝 / 指针化」优先于「整段对话摘要」；LightAgent 已有 spill，应默认先做、再谈摘要。
2. **摘要与「权威状态」解耦** — Claude Code / Amp / Cursor 用户实践都强调：规则、身份、任务清单、打开文件应来自磁盘/元数据再注入，而不是指望摘要记住；LightAgent 的 identity/memory pack 已是 ephemeral，压缩时绝不能把它们当「用户事实」写进 summary。
3. **可审可逆** — Roo/Cline 走向「标记隐藏、不删原文」；Amp 甚至弃 compact 改 Handoff（新开线程 + 用户审稿）。对生活助手：压缩结果要可见、可回滚、可手动触发，且默认路径零/极低 token 成本。

---

## 2. LightAgent 现状

### 2.1 机制概览

| 组件 | 路径 | 作用 |
| --- | --- | --- |
| `ContextProjector` | `LightAgent/session.py` | 从 Session 事件投影 `messages`（user/assistant/tool）；可重建某次 `model.requested` |
| `ContextBudget` | 同上 | 无依赖 token 估算：`len(json.dumps(messages))/chars_per_token`；默认 `max_tokens=8192`，`reserved_output=1024`，`chars_per_token=4` |
| `ContextCompactor` | 同上 | 两阶段：① `_spill_tool_results`；② 按 `max_messages` / budget 裁剪 |
| `LightAgent._compact_model_context` | `LightAgent/core.py` | 每次 `_prepare_model_request` 前：若配置了 `context_budget` 且 `not fits` → `compact_to_budget` |
| `LightAgent.compact_session` | 同上 | 手动压缩投影历史，写入 `context.compacted` 事件并持久化 |
| `DAGContextBudget` / `ContextBuilder` | `LightAgent/dag/context.py` | DAG 任务上下文：强制合同不可裁，只 trim 检索；与对话 compact **独立** |
| Memory pack 预算 | `local/memory/pack.py` | 画像 pack 独立 token 预算（默认 1200），与会话 compact **独立** |

### 2.2 触发条件

| 路径 | 触发 | 默认 |
| --- | --- | --- |
| 自动 | `context_budget` 非空 **且** `estimate(messages) > max_tokens - reserved` | **关闭**（`context_budget=None`） |
| 手动 API | `agent.compact_session(max_messages=20)` | 调用方显式触发 |
| TUI | 未发现接线 `ContextBudget` / `compact_session` | **未用** |

### 2.3 保留 / 丢弃规则（`ContextCompactor.compact`）

1. **Spill（始终先做）**：`role=tool` 且 `len(content) > max_inline_tool_chars`（默认 12000）→ 内容换成  
   `[Tool result stored outside context: tool-result:sha256:…, N chars]`，原文进 `spilled[]`（含 sha256/size/content）。
2. **消息数裁剪**：保留最多 1 条 `system` + 尾部 `max_messages - |system|` 条非 system；去掉的部分为 `removed`。
3. **工具孤儿修复**：若裁剪后第一条 kept 是 `tool`，继续前移到 `removed`（避免悬空 tool 结果）。
4. **可选摘要**：若构造时传入 `summarizer` 且有 `removed`，生成  
   `role=system, content="Previous conversation summary:\n…"`, `metadata.compacted=True`；  
   **默认 `summarizer=None` → 纯丢弃，无摘要。**
5. **`compact_to_budget`**：从 `max_messages=len(messages)` 递减到 2，直到 `budget.fits`；最坏保留 2 条。

本地用 venv 核验：无 summarizer 时 `max_messages=3` 只会留下 `system + 尾部`，`summary=None`；有 summarizer 才插入第二条 system 摘要。

### 2.4 与 ephemeral 身份 / 记忆 pack 的关系

- 每轮 system 组装：`instructions` + 可选 skills + **ephemeral**（`<memory-context>` / `<persona>` / `<identity>`），用户原话不改写（`core.py` + `local/memory/inject.py`）。
- 落盘 `model.requested` 时：`_strip_ephemeral_memory` 剥掉上述标签，避免 pack 进 transcript。
- **缺口：** 压缩器不知道 ephemeral。若某次 `chat_params.messages` 里的 system 仍带 pack，而 summarizer 把整段 system/历史摘要化，可能把「当次注入的身份/画像」误写成「对话事实」。当前默认无 summarizer，风险潜伏；一旦接 LLM 摘要必须显式排除。

### 2.5 测试锚点

| 测试 | 覆盖 |
| --- | --- |
| `tests/test_v010_session.py::test_compaction_spills_large_tool_results_and_meets_budget` | spill + budget |
| `tests/test_v010_core_integration.py::test_public_compact_session_reduces_projected_history_and_persists_event` | 手动 compact + `context.compacted` 持久化 |
| `tests/test_lightdag.py`（DAG budget） | 任务合同溢出，非对话 compact |

**未覆盖：** summarizer 路径、ephemeral 与 compact 交互、TUI 触发、压缩后 identity 再注入、可逆/预览。

### 2.6 缺口清单（相对业界与产品约束）

1. TUI / 生活助手路径未启用 `ContextBudget`，长对话靠模型窗口硬顶或静默裁剪（若以后打开 budget）。
2. 默认无摘要 → 激进裁剪会丢决定与用户偏好表述；有摘要又会烧 `:free` 额度。
3. Spill 的 `spilled` 留在事件里，但无「按 reference 取回」的运行时工具。
4. 压缩不可预览、不可用户焦点指令（对比 Claude `/compact focus on …`）。
5. Session 全量事件仍在增长；compact 只改送模 messages，不替代「权威状态」（任务清单/身份元数据）。
6. Token 估算是字符启发式，对中文偏乐观/悲观不定，与 OpenRouter 实际计费可能偏差大。

---

## 3. 业界对照表

> 公开信息稀疏处已标明；不臆造内部实现细节。

| 产品 | 触发 | 策略 | 保留 vs 丢弃 | 用户控制 | 主要风险 | 信息密度 |
| --- | --- | --- | --- | --- | --- | --- |
| **Cursor / Composer** | 接近上下文上限；手动 `/summarize` | 训练期 **self-summarization**（模型自摘要进 RL）；产品侧仍有 harness 摘要 | 摘要 ~1k tokens + conversation state（plan/剩余任务等）；rules 仍在 system，但压缩后遵从度下降 | `/summarize`；社区建议 60–70% 主动摘要；用 `TASK.md` 等文件扛状态 | 规则/需求在摘要后「行为漂移」；自动压缩偶发过晚 | 高（官方博客）+ 论坛 |
| **Claude Code** | 近窗口自动；`/compact [instructions]`；`/autocompact <tokens>` | LLM 结构化摘要 + **磁盘再注入** | 保留：system、CLAUDE.md、auto memory、plan、最多 5 个最近读写文件（过大则路径指针）、技能（有 token 帽）；对话历史被摘要 | 焦点指令、提前阈值、rewind+summarize、可关 `autoCompactEnabled` | 路径作用域规则被摘要掉；摘要丢细节 | 高（官方 docs） |
| **Anthropic API Compaction** | on-demand 或 input_tokens 阈值（≥50k） | 服务端摘要 → `compaction` block；另有 **context editing**（清旧 tool/thinking，不摘要） | 可保留最近 turns；tool 结果可规则清空 | 自定义 `instructions`；`pause_after_compaction` | 依赖服务端；与 LightAgent `:free` 路径无关 | 高 |
| **OpenAI Codex CLI** | `auto_compact_limit`；手动 `/compact` | Codex 模型走 `/responses/compact`（加密 blob）；非 Codex 模型本地 LLM 摘要 + handoff 前缀 | 摘要替换 `input`；保留最近用户消息（源码路径）；加密路径不透明 | `/compact` | 重复 compact 精度下降；加密摘要不可审 | 中高（工程博客 + 源码/逆向文） |
| **Aider** | `done_messages` 超 `max_chat_history_tokens`（约 max_input/16，夹在 1024–8192） | **异步** LLM 摘要 head + 保留 tail；可选 double-buffer（60% 预摘要 / 85% 换入）；另有 **repo-map** 图排序占预算 | ChatChunks：system/examples/repo/files/cur 分段；done 可摘要 | `--map-tokens`、`--double-buffer` 等 | 摘要丢早期决策；repo-map 过大时禁用 | 高（源码+文档） |
| **OpenHands** | 事件数 > `max_size`（默认约 100–120） | **Condenser**：head + LLM 摘要 middle + tail；`Condensation` 事件记 `forgotten_event_ids`；可 Pipeline | 保留前 `keep_first`（默认 1–4）与近期事件；中间遗忘 | 配置 condenser 类型；可手动 CondensationRequest | 多一轮成本与缓存命中下降；摘要质量依赖 prompt | 高（官方 docs/blog） |
| **Cline** | 近上下文上限 | **Auto Compact**：LLM 全面摘要替换历史；不支持时回退规则截断 | 强调保留技术决策/文件变更；结构化任务列表跨窗口 | 检查点可回滚到摘要前 | 烧 token；截断回退丢上下文 | 中（产品 docs + prompt 源码） |
| **Roo Code** | condense / 滑动窗口 | **Fresh Start**：摘要为 user 消息；原文 `condenseParent` 标记隐藏，非删除 | API 只见摘要；UI/rewind 可恢复；可保 slash command、折叠文件上下文 | 自定义 condensing prompt | 摘要漂移；实现复杂 | 中（PR/源码） |
| **Continue** | 超窗 / autocompact | 修剪旧消息 + 工具输出截断；近期有 prune/fallback PR | 保留 system/tools/最近交换；Bash 等大输出截断 | 相对少公开「用户指令型 compact」 | 公开文档偏碎片 | 低–中 |
| **Goose (Block)** | 默认约 0.8 上下文占用 | 双受众：原文对用户可见、对 agent 标记不可见 + 注入摘要；另有增量 tool-pair 摘要 | 用户仍见全文；agent 见压缩视图 | 阈值可配 | 第三方解读为主；主仓 fetch 空 | 中（二级解读） |
| **Amp** | （已弃用 compact） | **Handoff**：按下一目标抽取消息/工具/文件 → **新线程草稿**供用户编辑 | 鼓励短线程；不堆叠摘要 | `/handoff <goal>`；草稿可改 | 需用户养成换线程习惯 | 高（官方） |

**MemGPT/Letta / LangGraph：** 与「coding agent 会话 compact」相关度中等（分层记忆 / 图节点摘要），本调研不展开实现细节，仅作「状态外置」思想参考。

---

## 4. 机制拆解（按策略类型）

### 4.1 滑动窗口 / 硬裁剪

- **做法：** 丢最旧，留 system + 最近 N 条。  
- **代表：** LightAgent 默认；Continue 修剪；早期 Cline 截断。  
- **成本：** 零 LLM。  
- **代价：** 丢决策与约束；易出现悬空 tool（LightAgent 已做简单修复）。

### 4.2 工具结果剪枝 / 外溢（Tool prune & spill）

- **做法：** 大 tool 输出截断、换成指针、或服务端 clear。  
- **代表：** LightAgent spill；Anthropic context editing `clear_tool_uses`；Continue 截断工具输出。  
- **对 `:free`：** **最高优先**，几乎不烧摘要额度。

### 4.3 LLM 对话摘要（lossy summary）

- **做法：** 中间或全部历史 → 结构化摘要消息，替换送模历史。  
- **代表：** Claude Code `/compact`；Cline Auto Compact；OpenHands Condenser；Aider ChatSummary；Codex 本地路径。  
- **变体：**  
  - **Head+Tail+Middle 摘要**（OpenHands）  
  - **只摘要 done，cur 原样**（Aider）  
  - **Fresh start 仅摘要**（Roo）  
  - **训练内 self-summary**（Composer，不可直接抄到 LightAgent）

### 4.4 分层 / 双缓冲 / 后台摘要

- **做法：** 未满窗时后台预摘要，阈值到达只换入（Aider double-buffer）；或 Amp 式「别在原线程无限 compact」。  
- **价值：** 降停顿、提高摘要时注意力；仍费 LLM。

### 4.5 权威状态外置（文件 / 元数据再注入）

- **做法：** 任务清单、规则、身份、打开文件存磁盘；compact 后从权威源再加载，不依赖摘要。  
- **代表：** Claude Code 再读 CLAUDE.md/plan/文件；Cursor 社区 `TASK.md`；Amp Handoff 列相关文件；LightAgent identity + memory pack（已具备雏形）。  
- **这是生活助手最该强化的层。**

### 4.6 服务端潜伏压缩（encrypted / API compaction）

- **代表：** Codex `/responses/compact`；Anthropic server compaction。  
- **对 LightAgent：** 走 OpenRouter `:free` 时通常不可用；仅作对照。

### 4.7 非破坏性标记（tag, don’t delete）

- **代表：** Roo `condenseParent` / truncation marker；Goose 双受众可见性。  
- **价值：** 可审可逆；UI 仍可展示全文。  
- **LightAgent：** 已有 Session 事件日志，`context.compacted` 记结果，但投影层尚未「有效历史 vs 全量历史」分离。

---

## 5. 对 LightAgent 的优化探索（先不改代码）

约束重申：仅 `:free`；压缩本身少烧 token；可审可逆；**禁止**把 ephemeral 身份/记忆 pack 压进摘要当事实。

### P0 — 启发式优先、接线与安全边界（建议优先验证）

| 项 | 说明 |
| --- | --- |
| **P0-a 默认启用「仅 spill + 温和滑动」** | TUI/助手路径配置保守 `ContextBudget`（按模型窗口估算，预留输出与 pack）；`summarizer=None`。长工具结果先指针化。 |
| **P0-b Compact 前剥离 ephemeral** | 压缩输入必须先 `_strip_ephemeral_memory` / 等价逻辑；摘要（若有）不得包含 `<identity>`/`<memory-context>`/`<persona>` 正文。压缩后 **下一轮照常再注入** 权威 identity + pack。 |
| **P0-c 保留「用户原话尾部」策略** | 裁剪时优先保住最近 K 条 **user** 与其配对 assistant；避免只剩 tool。可扩展现有「开头不能是 tool」规则。 |
| **P0-d TUI 可见性** | 状态栏显示估 token / 是否将 compact；手动「压缩上下文」调用现有 `compact_session`，展示 removed_count 与预览。 |
| **P0-e Spill 可取回（最小）** | `context.compacted.spilled` 已存全文：提供只读查看/按需「展开一条 tool 结果」进下一轮，避免摘要幻觉补全。 |

### P1 — 可选 LLM 摘要（旗帜关闭、廉价模型）

| 项 | 说明 |
| --- | --- |
| **P1-a `--llm-compact` / 设置项默认关** | 仅当启发式仍超预算或用户手动「智能压缩」时调用；强制 `:free` 或本地小模型；失败则回退纯裁剪。 |
| **P1-b 结构化摘要模板（生活助手向）** | 段落：当前目标、已确认偏好（**仅引用已确认 learnings id，不抄 ephemeral**）、未决问题、近期承诺、禁止事项。要求 verbatim 引用最近用户原话关键句。 |
| **P1-c Head 任务 + Tail 原话** | 学 OpenHands/Aider：保留会话最初用户目标与最近 N 轮原文，只摘要中间。 |
| **P1-d 非破坏投影** | 学 Roo：Session 保留全事件；送模用「有效视图」；UI 可 rewind 到 compact 前。 |
| **P1-e 用户焦点指令** | 学 Claude：`压缩并聚焦：下周旅行预算`；写入 summarizer prompt，不改用户消息历史语义。 |

### P2 — 产品形态与高级策略

| 项 | 说明 |
| --- | --- |
| **P2-a Handoff 式新会话** | 学 Amp：长线程鼓励「交接」——生成新会话草稿（目标 + 相关记忆 id + 最近原话），用户确认后开新线程，而非无限堆摘要。 |
| **P2-b 双缓冲预摘要** | 学 Aider：达 60% 后台用 `:free` 预摘要，85% 换入；注意额度与竞态。 |
| **P2-c 中文友好 token 估计** | 校准 `chars_per_token`（中文常 ~1.5–2 字/token），或对 OpenRouter usage 回写修正，减少误触发。 |
| **P2-d 与协作编排交互** | 子 Bot 上下文各自 compact；父 transcript 不吸入子 ephemeral（已有约束，压缩时勿打破）。 |
| **P2-e DAG / 工具链** | 大检索结果走 DAGContextBudget 思路：合同不可裁、检索可裁；对话层只留指针。 |

### 明确不建议（在当前约束下）

- 默认每轮 LLM 摘要（烧光 `:free`，且漂移）。  
- 依赖 Anthropic/OpenAI 服务端 compaction API（不在 OpenRouter 免费路径）。  
- 把 Composer 式「训练内 self-summary」当作可移植特性。  
- 将 identity/画像摘要进「用户长期事实」而不经确认写入 Profile。

---

## 6. 先不改代码的验证建议

1. **基线测量（mock）**  
   - 构造 50+/100+ 轮含大 tool 输出的会话，跑 `ContextCompactor.compact_to_budget`，记录：kept 条数、spilled 字节、estimate tokens、是否出现悬空 tool。  
   - 断言：无 summarizer 时零外部 LLM 调用。

2. **Ephemeral 安全用例**  
   - system 含 `<identity>`/`<memory-context>` → compact 输入剥离后，摘要（若手动挂假 summarizer）不得出现这些标签正文。  
   - compact 后下一轮 `prepare_turn` 仍能注入同一 identity。

3. **预算灵敏度**  
   - 中英混合长消息下，比较 `chars_per_token=4` 与更紧估计的触发早晚；记录误触发率。

4. **手动 compact 可逆性（设计验收）**  
   - `compact_session` 后 Session 事件是否仍含完整 `message.received`；UI 若只展示 compacted 视图，rewind 是否可恢复（当前：事件在，投影逻辑需确认）。

5. **TUI 手感脚本（ux_probe / shot）**  
   - 未接线前：只验证「若接线」的文案与确认流（预览 removed_count → 用户确认）。  
   - 不调用 OpenRouter。

6. **对照黄金集（离线）**  
   - 选 5 段真实生活助手对话（作息、采购、旅行）人工标「压缩后必须保留的事实」；对纯裁剪 vs 假摘要（规则拼接）打分，再决定是否打开 P1。

7. **回归**  
   - 现有 `tests/test_v010_session.py`、`test_v010_core_integration.py` compact 用例保持绿；新增用例列入计划但不在本调研实现。

---

## 7. 参考链接

### LightAgent 本地锚点

- `LightAgent/session.py` — `ContextProjector` / `ContextBudget` / `ContextCompactor` / `CompactionResult`
- `LightAgent/core.py` — `_compact_model_context` / `compact_session` / `_strip_ephemeral_memory`
- `LightAgent/dag/context.py` — `DAGContextBudget`
- `local/memory/pack.py` / `local/memory/inject.py` — pack 预算与 ephemeral 注入
- `tests/test_v010_session.py`、`tests/test_v010_core_integration.py`

### 外部（优先一手）

- Cursor Composer self-summarization：https://cursor.com/blog/self-summarization  
- Cursor 论坛（规则不经压缩存活 / 压缩过晚 / 自定义摘要）：https://forum.cursor.com/t/critical-rules-do-not-survive-context-compression-events/157249 、https://forum.cursor.com/t/compaction-not-happening-soon-enough/149490 、https://forum.cursor.com/t/customizing-how-cursor-summarizes-context/160865  
- Claude Code 上下文窗口与 compact：https://code.claude.com/docs/en/context-window.md  
- Claude Code 设置（autoCompact*）：https://code.claude.com/docs/en/settings-reference  
- Anthropic Compaction 总览：https://platform.claude.com/docs/en/build-with-claude/compaction  
- Anthropic 阈值压缩：https://platform.claude.com/docs/en/build-with-claude/compaction-threshold  
- Anthropic Context editing（清 tool/thinking）：https://platform.claude.com/docs/en/build-with-claude/context-editing  
- OpenAI Codex agent loop（含 compact）：https://openai.com/index/unrolling-the-codex-agent-loop/  
- Codex compact 源码：https://github.com/openai/codex/blob/main/codex-rs/core/src/compact.rs  
- Codex compact 逆向笔记（二级，需谨慎）：https://yuanchang.org/en/posts/investigating-codex-context-compaction/  
- Aider repo map：https://aider.chat/docs/repomap.html  
- Aider history 摘要源码：https://github.com/Aider-AI/aider/blob/main/aider/history.py  
- Aider double-buffer PR：https://github.com/Aider-AI/aider/pull/4858  
- OpenHands Condenser：https://docs.openhands.dev/sdk/arch/condenser  
- OpenHands Context Condenser 指南：https://docs.openhands.dev/sdk/guides/context-condenser  
- OpenHands 博客：https://www.openhands.dev/blog/openhands-context-condensensation-for-more-efficient-ai-agents  
- Cline Auto Compact：https://docs.cline.bot/features/auto-compact  
- Cline 摘要 prompt：https://github.com/cline/cline/blob/main/src/core/prompts/contextManagement.ts  
- Roo condense / Fresh Start：https://github.com/RooCodeInc/Roo-Code/blob/main/src/core/condense/index.ts 、https://github.com/RooCodeInc/Roo-Code/pull/10873  
- Amp Handoff（取代 compact）：https://ampcode.com/news/handoff  
- Amp 上下文管理指南：https://ampcode.com/guides/context-management  
- Goose context_mgmt（主仓文件；本环境 WebFetch 空，依赖社区解读）：https://github.com/block/goose/blob/main/crates/goose/src/context_mgmt/mod.rs  

### 信息缺口 / 阻断

- **Cursor** 产品侧自动压缩的精确阈值与提示词未完全公开（训练博客 ≠ IDE 行为全文）。  
- **Codex** 加密 compact blob 内部不可审；依赖工程博客 + 社区逆向。  
- **Goose** 官方模块页 fetch 失败/空文件，细节以二级解读为准。  
- **Continue** 公开「Auto Compact」产品文档弱于 Cline/Roo，多依赖 PR。  
- **Amp** 已战略放弃 compact，对照价值在「别无限摘要」而非算法移植。  
- 未使用任何付费/登录墙后的私有文档；未调用 OpenRouter。

---

*本文件为调研与探索，不包含实现补丁。*
