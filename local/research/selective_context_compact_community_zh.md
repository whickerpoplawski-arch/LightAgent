# 单对话选择性上下文压缩：高星项目与社区调研

> 聚焦：同一会话内能否**按内容类型**差异化压缩（非跨会话记忆）  
> 前序总览：`coding_agent_compact_survey_zh.md`（不重复改写）  
> 渠道：GitHub 源码/文档、Reddit 线程、X（本轮 429 未取到帖）  
> 日期：2026-10-12（America/Martinique / AST）  
> 约束：只读调研；未改 LightAgent 产品代码；未调 OpenRouter

---

## 1. 结论先行

**能否选择性压缩？业界答案：partial（部分常见，完整「按五类内容各一套策略」仍偏少）。**

| 问题 | 业界常见答案 |
| --- | --- |
| 工具结果 vs 对话文字能否不同策略？ | **常见。** 多数成熟 agent 先剪/清/外溢 tool output，对话轮次另做窗口或摘要。 |
| system / 身份 / 规则能否「永不摘要」？ | **常见约定。** 用 head 保留、外置文件再注入、或压缩前剥离 ephemeral；真正「按标签永不动」的元数据策略较少写成通用框架。 |
| 代码块 / 错误 / 用户决策能否单独规则？ | **部分。** 多靠摘要 prompt「保留决策与错误」、用户 `/compact` 焦点指令、或「先写文件再压」；少见独立 score 引擎。 |
| 单对话 live array vs 磁盘指针？ | **常见二分。** live：占位符/摘要/投影视图；磁盘：原文事件、spill、tool offload、session JSONL。 |
| 手动 vs 自动？ | **社区强烈偏好：自动只做廉价层；语义摘要尽量手动带指令。** |

**对 LightAgent：** 现有 `ContextCompactor` 已是「工具 spill（按大小）+ 统一尾部裁剪」的弱选择性；用户要的「按内容类可配置」在业界有清晰对标，P0 不必上 LLM。

**选择性-by-content 流行度判定：partial。**

---

## 2. 内容类型 × 压缩策略矩阵

| 内容类 | 推荐强度 | 常见机制 | 留在 live messages？ | 原文去哪？ |
| --- | --- | --- | --- | --- |
| **工具结果**（读文件、搜索、命令输出） | **最激进** | 截断 / placeholder / spill 指针 / `clear_tool_uses` / ObservationMasking / tool-pair 摘要 | 短占位或最近 N 步全文 | 事件库、offload 存储、`spilled[]` |
| **对话轮次**（user/assistant 文本） | **中等** | head+tail 窗口；中间 LLM 摘要；topic 簇摘要后可 drop | 最近 N 轮全文 + 可选摘要消息 | 被标记 hidden / forgotten_ids；UI 可 rewind |
| **代码块**（assistant 贴出的大段代码） | **软压或外置** | 摘要里写路径+符号；folded file context；repo-map 另注入 | 最近编辑相关片段 | 磁盘文件为权威；摘要只留路径 |
| **系统与身份**（system、CLAUDE.md、identity/persona） | **几乎不压** | `keep_first`；每轮重新注入；compact 前剥离 ephemeral | 1 条 system 或每轮重建 | 配置/身份元数据，不进 summary 正文 |
| **错误与决策**（失败栈、用户拍板） | **优先保留** | 摘要 prompt 硬性要求；用户 `/compact keep …`；错误 tool 可 `exclude` 或延后 prune | 决策原文尽量留尾部；错误可摘要但不可丢「已否决方案」 | 任务文件 / handoff.md |

**机制维度对照（回答「怎么选」）：**

| 机制 | 代表 | 选择性粒度 |
| --- | --- | --- |
| **角色 / 事件类型** | OpenHands ObservationMasking、BrowserOutput；Anthropic `clear_tool_uses` / `clear_thinking` | 按 observation / tool / thinking |
| **年龄 + 窗口** | OpenHands head/tail；Haystack `min_keep_steps`；Letta sliding_window | 旧中间压，头尾保 |
| **大小阈值** | LightAgent spill；Claude Code budget reduction；Haystack `min_tokens` | 只动「大」的 tool |
| **元数据保护** | Haystack `skip_meta_keys`（offloaded）；Roo `condenseParent` | 指针/已压消息跳过 |
| **重要性 / 注意力** | OpenHands `LLMAttentionCondenser`（按事件打分留 top-N） | 有，但烧 LLM |
| **用户钉选 / 指令** | Claude `/compact <focus>`；Aider `/drop-topic`（PR）；Reddit 焦点指令 | 手动选择性 |
| **Middle-out** | OpenHands rolling；Aider head 摘要 + tail 保留 | 中间压两端留 |
| **双视图** | Goose 用户见全文 / agent 见压缩；Roo 存储全量 + API 有效历史 | UI≠送模 |

---

## 3. 高星项目拆解

星数来自 2026-10-12 GitHub API（无认证，公开字段）。

### 3.1 OpenHands（~90.7k★）— 选择性最清晰的「管道」

- **依据：** 高星 + 可插拔 Condenser；二级源码深潜 [gist](https://gist.github.com/sam-saffron-jarvis/0f5e9b76942678019f15bdd1bd60bbb6)；官方 [Condenser 架构](https://docs.openhands.dev/sdk/arch/condenser)、[使用指南](https://docs.openhands.dev/sdk/guides/context-condenser)。
- **选择性点：**
  - `ObservationMaskingCondenser`：attention_window 外的 **observation** 换成占位（每步、无 LLM）。
  - `BrowserOutputCondenser`：只保留最近浏览器输出，旧的改成 URL + omitted。
  - `LLMSummarizingCondenser`：head `keep_first` + 中间摘要 + tail；`forgotten_event_ids` 非物理删除。
  - `LLMAttentionCondenser`：按重要性留事件（无摘要文本）。
  - `PipelineCondenser`：可串联「先 mask 浏览器 → 再 LLM 摘要」。
- **源码锚点（主仓路径，SDK 另有平行实现）：**  
  `openhands/memory/condenser/impl/observation_masking_condenser.py`、`browser_output_condenser.py`、`llm_summarizing_condenser.py`、`pipeline.py`；配置 `openhands/core/config/condenser_config.py`。  
  SDK：`openhands-sdk/.../condenser/`、`event/condenser.py`（`forgotten_event_ids` + `summary_offset`）。
- **单对话语义：** 全量事件持久；**View** 是送模投影。
- **链接：** https://github.com/OpenHands/OpenHands · https://docs.openhands.dev/sdk/arch/condenser

### 3.2 Anthropic Context Editing + Claude Code 五层管道 — 「按块类型」官方化

- **依据：** 官方 API 文档（非开源 CLI，但选择性 API 最明确）；arxiv 源码级分析 [Dive into Claude Code](https://arxiv.org/html/2604.14228v1)。
- **选择性点（API）：**
  - `clear_tool_uses_20250919`：只清旧 tool result（可保留最近 N 次 tool_uses；`exclude_tools`；可选清 inputs）。
  - `clear_thinking_20251015`：只清旧 thinking；`keep` 最近 N turn 或 `all`。
  - 与整段 `compact` **正交**：编辑是选择性清空，compact 是语义摘要。
- **Claude Code（产品，源码分析可信度：中高，非官方架构文）：** 每轮模型调用前五层——budget（单条 tool 过大→引用）→ snip → microcompact → context collapse（只读投影）→ auto-compact（最后才 LLM）。**先按类型/廉价层，再语义。**
- **用户侧选择性：** `/compact <instructions>`；社区还用 `/rewind` 只压一侧、`/btw` 旁路、handoff 文件。
- **链接：** https://docs.anthropic.com/en/docs/build-with-claude/context-editing · https://code.claude.com/docs/en/how-claude-code-works · arxiv 上文

### 3.3 Haystack `ToolResultPruningCompactor`（~26.7k★）— 工具类选择性的教科书实现

- **依据：** 文档 + 源码可读、策略参数完整。
- **选择性点：** **只改 tool result 内容**，保留 call/result 配对；`min_keep_steps` 保护最近工具步；`min_tokens` 跳过小结果；`skip_meta_keys` 保护已 offload 指针；从旧到新直到 `target_tokens`。
- **源码锚点：** https://github.com/deepset-ai/haystack/blob/main/haystack/hooks/compaction/tool_result_pruning.py  
- **文档：** https://docs.haystack.deepset.ai/docs/next/tool-result-pruning-compactor  
- **与 LightAgent 关系：** 最接近「把 spill 从纯大小阈值升级为：大小 + 年龄步骤 + 元数据保护 + 预算目标」的设计。

### 3.4 Roo Code（~24.3k★）— 非破坏性 + 内容类保留钩子

- **依据：** 主仓 `src/core/condense/index.ts` 全文可读。
- **选择性点：**
  - 摘要为 **user** 消息（fresh start）；原文打 `condenseParent`，**UI/存储不删**，`getEffectiveApiHistory` 过滤送模视图。
  - 摘要时强制保留 `<command>` 工作流块；可选 **folded file context**（代码以折叠定义续命）。
  - 自动 vs 手动：自动才把 environmentDetails 塞进摘要。
  - 自定义 condensing prompt → 用户级内容偏好。
- **链接：** https://github.com/RooCodeInc/Roo-Code/blob/main/src/core/condense/index.ts

### 3.5 Aider（~49.5k★）— 对话分区 + 主题级选择（PR 中）

- **依据：** `aider/history.py`；ChatChunks（system / repo-map / files / cur / done）结构见前序调研；PR [#4940](https://github.com/Aider-AI/aider/pull/4940)、[#4941](https://github.com/Aider-AI/aider/pull/4941)。
- **选择性点：**
  - **默认：** `done_messages` 可摘要，`cur_messages` 近期不摘要；system/repo/files **分段外置**，不是整段 transcript 一锅炖。
  - **PR（opt-in，合并状态请以 GitHub 为准）：** union-find 主题簇 → `/topics` 查看 → `/drop-topic N` **按主题丢弃**——社区最接近「用户选择性」的 UX。
- **链接：** https://github.com/Aider-AI/aider/blob/main/aider/history.py

### 3.6 Letta / MemGPT（~25.1k★）— 会话窗口驱逐 + 系统消息保护

- **依据：** `summarizer_sliding_window.py`、`compact.py`；issue [#3270](https://github.com/letta-ai/letta/issues/3270)（滑动窗口误全量擦除，说明选择性实现脆弱）。
- **选择性点：** 保留 system；从 index 1 起驱逐到某 assistant 边界；摘要插入 in-context；全量消息仍可 recall 检索（跨本调研「单对话」边界，但「权威在磁盘、窗口是投影」一致）。
- **链接：** https://github.com/letta-ai/letta

### 3.7 Continue（~36.2k★）、Cline（~70.2k★）、Goose（~55.2k★）— 有压缩，选择性较弱或波动

| 项目 | 星数 | 选择性程度 | 锚点 / 备注 |
| --- | --- | --- | --- |
| Continue | ~36.2k | **弱–中**：按 index 摘要到某点；其后消息保留；有 prune/fallback PR（公开文档偏碎） | `core/util/conversationCompaction.ts` |
| Cline | ~70.2k | **中**：结构化任务列表跨窗；Auto Compact 偏整段摘要；检查点可回滚 | 路径多变，本次 raw 404；以产品 docs 为准 |
| Goose | ~55.2k | **中**：曾有 tool-pair 摘要（旧 tool 请求/响应对 agent 隐藏）；有稳定性问题，flag/PR 曾关再开 | `crates/goose/src/context_mgmt/mod.rs`；PR #7481 / #7938 |

### 3.8 明确弱相关 / 未深挖

- **CrewAI / AutoGen / MetaGPT：** 多为多智能体编排与记忆，**少见**「单对话 messages 按内容类 compact」的成熟子系统 → 不作为本议题首选对标。
- **SWE-agent：** 重环境/轨迹，上下文管理不如 OpenHands/Claude 管道清晰。
- **Codex CLI：** 加密 compact blob，公开选择性细节不足（见前序调研）。

---

## 4. GitHub / X / Reddit 社区共识与争议

### 4.1 GitHub（源码与 issue）

**共识：**

1. **工具输出是上下文膨胀主犯** → 应最先、最激进、最好零 LLM（OpenHands mask、Haystack prune、Anthropic clear_tool_uses、LightAgent spill）。
2. **送模视图 ≠ 持久原文**（View / effective history / server-side edit + 客户端全量）。
3. **分层**：廉价剪枝 → 窗口 → 才 LLM 摘要。
4. **System/任务合同外置再注入**，别指望摘要「记住规则」。

**争议 / 坑：**

- Letta sliding_window 曾静默 fallback 成全量擦除（#3270）→ **选择性策略写错 = 比不压缩更糟**。
- Goose tool-pair 隐藏消息与客户端状态不同步 → **双视图一致性**难。
- OpenHands 默认 Condenser 可能偏「请求才压」，配置不当等于没压。
- Aider topic drop 仍是 PR/opt-in，主线仍是整段 done 摘要。

### 4.2 Reddit（摘要自搜索结果；部分 `.json` fetch 超时）

| 线程 | 要点 |
| --- | --- |
| [r/ClaudeAI 关 autocompact](https://www.reddit.com/r/ClaudeAI/comments/1mdno8f/claude_code_pro_tip_disable_autocompact/) | 任务中途自动压容易跑偏；改手动 + 焦点指令 |
| [r/ClaudeCode 处理 autocompact](https://www.reddit.com/r/ClaudeCode/comments/1pwxy0f/how_do_you_handle_autocompact_in_claude_code/) | 关自动；`/compact` 带保留项；或 handoff + `/clear`；子 agent 隔离噪音 |
| [r/ClaudeCode 四种精细工具](https://www.reddit.com/r/ClaudeCode/comments/1tfjhgj/anthropic_shipped_4_context_tools_between_clear/) | `/btw`、`/rewind` 单侧摘要、`/compact focus`、CLAUDE.md 固定保留规则 —— **反对「只会 /compact 全压」** |
| [r/ClaudeCode compact 写什么](https://www.reddit.com/r/ClaudeCode/comments/1w1b7x5/what_do_you_write_in_compact_optional/) | 显式：`keep decisions/plans`；**`delete all tool outputs: grep/git/sed/cat`** —— 用户级内容类策略 |
| [r/LocalLLaMA tool output compression](https://www.reddit.com/r/LocalLLaMA/comments/1qbei13/tool_output_compression_for_agents_6070_token/) | 本地模型更依赖 **进模前压 tool**；保留 error/异常/相关行，忌盲截断 |
| Headroom 等帖 | 代理层压 MCP/tool，保持 tool-call 形状完整 |

**社区金句级共识（意译）：** 摘要丢的是「精确文件状态与约束」；重要状态应先落盘；自动语义 compact 常在错误时机触发。

### 4.3 X（Twitter）

**访问阻断：** 本回合 `search_posts_all` 连续 HTTP 429（共享额度限流），**未能引用具体帖文 URL**。  
间接：Reddit/文档中大量从业者实践与 X 讨论同构（关 autocompact、焦点 `/compact`、先清 tool）。若需补 X 原帖，应在限流缓解后重跑查询：`Claude Code /compact`、`context compaction coding agent`、`tool result pruning`。

---

## 5. 对 LightAgent 单对话的可选方案（策略草案，不写代码）

**现状钩子（对照）：**  
`ContextCompactor`：① 全体 `role=tool` 且超 `max_inline_tool_chars` → spill；② 最多 1 条 system + 尾部 N；③ 可选统一 summarizer。  
**缺口：** 无按工具名/错误/年龄步骤/钉选的差异；identity ephemeral 压缩器不认识；无「只剪 tool、不动对话」的独立旋钮。

### 建议 3–5 个策略旋钮（配置级，实现可后置）

1. **`tool_prune`（P0，零 LLM）**  
   - `max_inline_chars`（已有）  
   - `min_keep_tool_steps`（对齐 Haystack：最近 K 次工具步全文）  
   - `always_keep_if`：`is_error` / 工具名白名单（如 `delegate_to_bot` 结果）  
   - `spill_vs_placeholder`：外溢可取回 vs 仅「已移除，请重调」  
   → **只压缩工具类，对话轮次不动。**

2. **`turn_policy`（P0–P1）**  
   - `keep_tail_user_turns: N`（用户决策原文）  
   - `keep_head_system: 1` + **compact 前 `_strip_ephemeral`**（身份/画像永不进 removed→summary）  
   - `middle: drop | summarize`（默认 drop，摘要 opt-in）

3. **`protect_tags` / metadata（P1）**  
   - 消息 `metadata.compact = "never" | "soft" | "aggressive"`  
   - 或内容标签：`<decision>`、错误块、身份块 → never  
   - 对齐 Haystack `skip_meta_keys` + 用户钉选。

4. **`manual_focus`（P1，TUI）**  
   - 手动压缩指令：`保留：用药提醒边界、未完成三事；丢弃：旧搜索原文`  
   - 对齐 Claude `/compact` 与 Reddit 实践；自动路径仍只用 tool_prune。

5. **`pipeline_order`（P1 设计，P2 再做多插件）**  
   - 固定顺序：`strip_ephemeral → tool_prune → orphan_tool_fix → (optional) summarize_middle → tail_window`  
   - 对齐 OpenHands Pipeline / Claude 五层「先便宜后贵」。

**失败模式（选择性写错时）：**

| 错误策略 | 后果 |
| --- | --- |
| 把 system/identity 摘要进「对话事实」 | 人设漂移、记忆污染 |
| 剪掉最近未消化的 tool result | 模型重复调工具或幻觉结果 |
| 丢掉用户否决/错误栈 | 重复踩坑 |
| 只留摘要丢路径/约束 | 「行为漂移」（Cursor/Claude 用户报告） |
| 双视图不同步（UI 有、送模无或反之） | 用户以为还记得，模型已忘 |
| 滑动窗口算错 fallback 全擦 | Letta #3270 类事故 |

---

## 6. 参考链接（可点）

### 文档 / 论文
- https://docs.openhands.dev/sdk/arch/condenser  
- https://docs.openhands.dev/sdk/guides/context-condenser  
- https://www.openhands.dev/blog/openhands-context-condensensation-for-more-efficient-ai-agents  
- https://docs.anthropic.com/en/docs/build-with-claude/context-editing  
- https://docs.haystack.deepset.ai/docs/next/tool-result-pruning-compactor  
- https://arxiv.org/html/2604.14228v1  

### 源码
- https://github.com/deepset-ai/haystack/blob/main/haystack/hooks/compaction/tool_result_pruning.py  
- https://github.com/RooCodeInc/Roo-Code/blob/main/src/core/condense/index.ts  
- https://github.com/Aider-AI/aider/blob/main/aider/history.py  
- https://github.com/continuedev/continue/blob/main/core/util/conversationCompaction.ts  
- https://gist.github.com/sam-saffron-jarvis/0f5e9b76942678019f15bdd1bd60bbb6（OpenHands condensation 深潜）  
- https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/event/condenser.py  

### PR / Issue
- https://github.com/Aider-AI/aider/pull/4940 · https://github.com/Aider-AI/aider/pull/4941  
- https://github.com/letta-ai/letta/issues/3270  
- https://github.com/All-Hands-AI/OpenHands/pull/6578（BrowserOutput condenser）  

### Reddit
- https://www.reddit.com/r/ClaudeAI/comments/1mdno8f/claude_code_pro_tip_disable_autocompact/  
- https://www.reddit.com/r/ClaudeCode/comments/1pwxy0f/how_do_you_handle_autocompact_in_claude_code/  
- https://www.reddit.com/r/ClaudeCode/comments/1tfjhgj/anthropic_shipped_4_context_tools_between_clear/  
- https://www.reddit.com/r/ClaudeCode/comments/1w1b7x5/what_do_you_write_in_compact_optional/  
- https://www.reddit.com/r/LocalLLaMA/comments/1qbei13/tool_output_compression_for_agents_6070_token/  

### 本地
- `/workspace/LightAgent/local/research/coding_agent_compact_survey_zh.md`  
- `/workspace/LightAgent/LightAgent/session.py`（`ContextCompactor`）

### 稀疏 / 不确定标注
- Claude Code 五层管道细节来自第三方源码分析论文，**非 Anthropic 官方架构白皮书**。  
- Cline 具体 `ContextManager` 路径本次 404，实现细节标为中置信。  
- Goose tool-pair 开关随版本变化，以当前主仓 flag 为准。  
- X 帖文本轮 **未采集**（429）。  
- Aider `/drop-topic` 以 PR 描述为准，合并状态需复查。

---

*文档结束。*

---

## 附录 A · 补采（2026-10-12 09:43 AST）

> 说明：云电脑在美国。此前 X 失败是 **API 429 限流**，不是地理墙；本轮 X `search_posts_all` 已成功。Reddit 对本机 IP 返回 **HTTP 403 Blocked**（bot 防护），`old.reddit` / `.json` / WebFetch 均被拦；Reddit 内容仍来自搜索引擎可见摘要与标题页，非全文爬取。

### A.1 X 上与「选择性压缩」直接相关的共识

| 来源 | 要点 | 链接 |
| --- | --- | --- |
| @pixelsilicon 转述 NVIDIA SoL-Pi | **Online Context Compact**：计划步骤结束就压，不等窗口满；**ObservationPack**：大工具输出归档，上下文只留短 handle | https://x.com/pixelsilicon/status/2103862204940386433 |
| @omarsar0 等热帖（高赞） | SoL-Pi 自演化 harness：Action Fusion / Online Compact / ObservationPack / Evidence-Preserving Reducer，token 约减半 | https://x.com/omarsar0/status/2101074795643494546 |
| @akiraxtwo | 痛点：Playwright snapshot、Issues、日志整包进窗口 → 忘决策；本质是**未按内容类剪枝** | https://x.com/akiraxtwo/status/2106716892803342755 |
| @thegreatest_sv / @LaboNft | Claude Code 实操：`/context` 看占用；`/compact` 宜在约 60% 时早做；关无用 MCP；压短 CLAUDE.md | https://x.com/thegreatest_sv/status/2106352825789812919 |
| @Wilf_Lin | 提醒：部分客户端会把 compact **结果当作用户消息**注入（污染角色） | https://x.com/Wilf_Lin/status/2108257143875133713 |

**对 LightAgent 的启示（来自 X）：**  
1. 压缩触发可挂在「阶段结束」（任务/子目标完成），不只能挂 token 阈值。  
2. ObservationPack ≈ 已有 spill，但应「归档 + 可取回 handle」，不是只删。  
3. 摘要消息角色要小心（别冒充 user）。

### A.2 Reddit（搜索摘要；全文被 403）

| 帖子 | 选择性点 | 链接 |
| --- | --- | --- |
| r/ClaudeCode「为何 /compact 丢上下文」 | 批评「所有内容一视同仁摘要」；建议写盘 + 引用 + **可选择性恢复**；对比 Cursor 把长 tool 写文件再按需 fetch；Tokenring 把条目当 artifact 打标签跨 compact 可检索 | https://www.reddit.com/r/ClaudeCode/comments/1qcjwou/figured_out_why_compact_loses_so_much_useful/ |
| r/opencode「Magic Compact」 | **保留每条 user**；旧 assistant 变瘦摘要；大 tool I/O 进 cache，tool call 本身可见；反对整段换成单一 summary blob | https://www.reddit.com/r/opencode/comments/1uog5n3/magic_compact_replacing_opencodes_terrible/ |
| r/PiCodingAgent「cprune」 | off/safe/full；持久化时剪重复/过大 tool；保护 edits、失败 tool、有副作用命令；等价于「每轮只 prune tool，不动 user/assistant」 | https://www.reddit.com/r/PiCodingAgent/comments/1ujjoxn/i_built_cprune_a_small_pi_extension_for_pruning/ |
| r/PiCodingAgent「Compact Every Tool Response」 | 每条 tool 结果丢子 agent 压；评论警告 **打爆 prompt cache / 双倍费用**；替代：大结果写文件 + rg/RLM，主上下文永不进大输出 | https://www.reddit.com/r/PiCodingAgent/comments/1v08aok/compact_every_tool_response/ |
| r/LocalLLaMA「MCP compact proxy」 | **按工具规则**：token 预算、必留字段、可丢字段；DOM→可见文本+轻结构 | https://www.reddit.com/r/LocalLLaMA/comments/1p1s2go/compacting_mcp_tool_outputs_so_local_agents_dont/ |

**社区对「选择性」的几乎一致答案：**  
- 工具结果：可激进、可自动、最好外溢可取回。  
- 用户原话 / 拍板：尽量不丢。  
- 整段一锅粥 LLM 摘要：招骂最多。  
- 「每条 tool 都再调一次 LLM」：省窗口但贵且碎 cache，生活助手 `:free` 路径应避免。

### A.3 访问结论

| 渠道 | 本轮 | 原因 |
| --- | --- | --- |
| X API | 成功 | 美国节点 + 官方搜索；先前 429 为额度窗 |
| Reddit 直连 | 失败（403 Blocked） | 站点 bot 防护，与「是否在美国」无关 |
| Reddit 经搜索摘要 | 可用 | 已采入上表 |
