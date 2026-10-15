# 个人生活助手：上下文压缩（Compact）业内调研与 LightAgent 二开方向

> 定位：全方位个人生活助手（非 coding agent 复刻）  
> 约束：OpenRouter `:free` 额度敏感；压缩本身少烧 LLM；与记忆层严格分工  
> 前序：`coding_agent_compact_survey_zh.md`、`selective_context_compact_community_zh.md`、`personal_life_assistant_memory_zh.md`、`openhuman_memory_source_notes_zh.md`  
> 日期：2026-10-12（America/Martinique / AST）  
> 范围：只读调研 + 公开文档/源码/X；**未改**业务代码；**未调** OpenRouter

---

## 1. 目标与约束

### 1.1 产品目标

生活助手的上下文系统要同时满足：

1. **跨天跨会话仍懂你**：偏好、忌口、时区、待办承诺、人际备忘——不应靠「把整段聊天一直塞进窗口」实现。  
2. **单会话不爆窗**：web_search / browser 大结果、长闲聊、多轮工具链要压得住。  
3. **身份与画像不被压掉**：persona / identity / memory pack 是 ephemeral 权威注入，压缩不得把它们当「用户说过的话」写进摘要。  
4. **可审可逆**：用户能 pin、能预览、能 rewind；默认路径零/极低 token。  
5. **免费可续跑**：`:free` 下压缩默认不调 LLM；可选摘要必须旗帜关闭、失败可回退。

### 1.2 与记忆层的边界（硬规则）

业界共识（Mem0 官方文、OpenClaw、OpenHuman、ChatGPT Dreaming）可压成一句话：

> **压缩管「本会话还看得见什么」；记忆管「跨会话还知道什么」。二者都要，且写记忆必须在压上下文之前。**

| 该进 Memory（权威外置） | 该留在对话上下文再压 | 不该进摘要也不该进 Memory |
| --- | --- | --- |
| 硬偏好 Always/Never、过敏忌口、称呼时区 | 本轮未决问题、刚确认的三条待办原文 | ephemeral `<identity>`/`<persona>`/`<memory-context>` 正文 |
| 用户显式「记住」的事实 | 最近 K 轮 user 原话与拍板 | 网页/工具 untrusted 原文（可 spill，不晋升） |
| 日程承诺、例程、Space 级项目进度 | 当次 tool 结果（可指针化后按需取回） | 密钥、卡号、政府证件号 |
| 沟通风格 facet（经 Admission） | 会话内临时假设（未确认） | 把 pack 误写成「用户事实」 |

**写前再压（write-before-compaction）**：OpenClaw `memoryFlush`、Mem0「extract after every turn, not at compression time」、OpenHuman compaction 时用缓存 recall 丰富 checkpoint——都指向同一模式。LightAgent 已有 Admission / Promotion / ephemeral pack；压缩层应 **调用** 它们，而不是自己发明第二套「长期记忆」。

### 1.3 LightAgent 现状（对照锚点，不重复前序全文）

| 组件 | 行为 | 生活助手缺口 |
| --- | --- | --- |
| `ContextCompactor` | spill 大 tool + 尾部裁剪；`summarizer` 默认关 | 无按内容类策略；无压前 memory flush |
| `ContextBudget` | 字符启发式估 token；自动压需注入 | TUI/助手路径默认未接线 |
| ephemeral pack | 每轮注入、落盘剥离 | 压缩器不认识 ephemeral（摘要路径潜伏风险） |
| P0 画像记忆 | 已落地 | 与 compact 的「压前写入」未编排 |
| Session 事件 | `context.compacted` 可持久 | spill 无可取回工具；无 pin；无有效视图/全量视图分离 |

---

## 2. 业内机制地图（按范式）

星数取自 2026-10-12 GitHub API（无认证公开字段）。Coding agent 细表见前序调研；本节偏 **生活助手可迁移** 与 **长期记忆+压缩**。

### 2.1 范式总表

| 范式 | 一句话 | 代表 | 适合生活助手？ | `:free` 成本 |
| --- | --- | --- | --- | --- |
| A. Spill / 外溢指针 | 大 tool 出窗，留 handle | LightAgent spill；Haystack prune；Anthropic `clear_tool_uses`；OpenHands ObservationMasking | **优先** | 零 LLM |
| B. 角色/分层裁剪 | 保 system + 尾部；中间丢或摘要 | LightAgent 默认；Letta sliding_window；LangMem SummarizationNode | **优先（无 LLM 版）** | 零 / 可选 LLM |
| C. 会话摘要（lossy） | 旧轮 → 摘要消息 | Letta compact；OpenClaw compaction；Cline/Claude Code | **opt-in** | 烧额度 |
| D. 锚定增量摘要 | 持久结构化文档，按驱逐段追加 | Mem0 引用 Factory anchored summarization | P1–P2 | 中 |
| E. 检索式遗忘 | 历史进向量/图，按需召回 | Mem0；Zep Context Block；LlamaIndex VectorMemoryBlock | **跨会话主力** | 抽取可批量化 |
| F. 编辑式 context editing | 只清 tool/thinking，不摘要 | Anthropic context editing | 有 API 时好；`:free` 常不可用 | 通常零摘要 |
| G. 双层 working + long-term | 短窗 + 外置记忆 pack | OpenClaw USER/MEMORY/daily；OpenHuman pack；ChatGPT Dreaming；Claude Project memory | **产品核心** | pack 本地；巩固可离线 |
| H. 压前 Memory Flush | 压前静默写入权威记忆 | OpenClaw `memoryFlush`；Mem0 write-before-compaction | **P0 必做** | 可规则/本地小模型 |
| I. Handoff / 新线程 | 不无限堆摘要，开新会话草稿 | Amp Handoff | P2 产品形态 | 低 |
| J. 非破坏标记 | UI 全量，送模有效视图 | Roo condenseParent；LangGraph 分 key | P1 | 零 |

### 2.2 个人 / 陪伴 / 生活向产品

#### OpenClaw（~391.8k★）— 生活助手压缩+记忆的「教科书」

- **定位：** 个人助手 runtime；Markdown 工作区记忆 + 会话 compaction。  
- **压缩：** 旧轮摘要 + 保留近期；保 tool_call/toolResult 配对；可 `/compact Focus on …`；另有 **session pruning**（只剪 tool，不摘要）。  
- **与记忆边界：** **压前 `memoryFlush`**（默认开）静默提醒 agent 把重要上下文写入工作区记忆文件；失败不阻断 compaction。Dreaming（light→REM→deep）后台把短期信号晋升到 `MEMORY.md`，可审（`DREAMS.md`）。  
- **权威文件：** `USER.md`（偏好指令）/ `MEMORY.md`（长期事实）/ `memory/YYYY-MM-DD.md`（日笔记）— bootstrap 注入有预算，过大截断注入而非毁盘。  
- **证据：** https://docs.openclaw.ai/concepts/compaction · https://docs.openclaw.ai/concepts/memory · https://docs.openclaw.ai/concepts/dreaming · https://github.com/openclaw/openclaw  
- **对 LightAgent：** **最高优先级对标**——压前 flush + 文件/画像权威再注入 + tool prune 与会话摘要分离。

#### Mem0（~67.0k★）— 「压缩 ≠ 记忆」的理论与 Tier-3 实现

- **定位：** Agent 外置记忆层（跨会话事实抽取 + 检索）。  
- **关键主张：** Context compression 只是「忘得更慢」；生产要 **三层**：① 本会话无损 working；② 会话内锚定摘要；③ 外置持久记忆。**每轮抽取，不要等压缩触发再抽。**  
- **压缩本身：** Mem0 不做会话 compact；负责 Tier 3。  
- **证据：** https://mem0.ai/blog/context-compression-vs-memory-in-ai-agents · https://github.com/mem0ai/mem0  
- **对 LightAgent：** 用其边界定义指导分工；不必绑 Mem0 云，可自实现 Profile/Semantic + 可选适配器。

#### Zep / Graphiti（zep ~5.0k★；graphiti ~31.7k★）— 检索式 Context Block

- **定位：** 时序知识图 + 每轮组装紧凑 Context Block（facts/entities/episodes/thread summaries/user summary）。  
- **压缩观：** 「少塞历史、多检索」；thread summary 增量更新，非手动 `/compact`。  
- **证据：** https://help.getzep.com/context-types.md · https://help.getzep.com/thread-summaries.md · https://www.getzep.com/ai-agents/persistent-memory-for-ai-agents/  
- **对 LightAgent：** 强化「pack = 检索结果，不写回 transcript」；结构化生活事实（日程/人际）可走图或 facet，而不是塞进会话摘要。

#### Letta / MemGPT（~25.1k★）— 有状态 agent：窗口 compact + 分层记忆

- **定位：** 长期运行 stateful agent。  
- **压缩：** `compaction_settings`：默认 `sliding_window`（摘要约 30%、保留约 70%，可步进加大）；可用更便宜 summarizer；`self_compact_*` 为 prompt cache。保留 system；从 index 1 驱逐到 assistant 边界。Issue #3270 警示滑动窗口写错会全擦。  
- **证据：** https://docs.letta.com/v1-sdk/messages/compaction/ · https://github.com/letta-ai/letta  
- **对 LightAgent：** 可选 LLM 摘要学「便宜模型 + sliding + 保 system」；默认仍关；实现要有失败回退，忌静默全擦。

#### OpenHuman / TinyMemory（本地精读，见 `openhuman_memory_source_notes_zh.md`）

- **定位：** 个人化 host + 记忆引擎。  
- **压缩相关：** compaction 时 `MemoryRecallSummarizer` 用 **已完成缓存 pack** 丰富 checkpoint，**不**让引擎 I/O 拖住 summarizer；pack 永不写回聊天。  
- **对 LightAgent：** 压时只读缓存 pack；摘要不得抄 ephemeral 标签正文。

#### ChatGPT Memory + Dreaming（闭源，公开产品行为）

- **Saved memories** → **Dreaming 后台合成** profile（2026 Dreaming V3）：跨会话偏好/项目/约束；强调 **时效**（「下周去新加坡」会过期）。可审、可改、可关；Temporary chat 不写入。  
- **证据：** https://openai.com/index/chatgpt-memory-dreaming/ · https://help.openai.com/en/articles/8590148-memory-in-chatgpt  
- **对 LightAgent：** 「越用越懂」靠后台巩固 + 用户可审，不靠会话无限摘要；生活域事实要有时间有效性。

#### Claude Memory / Projects（闭源，公开 Help）

- **聊天记忆**按 topic 保存；**Project memory** 与全局隔离；另有 **chat search（RAG）** 跨会话取原文。敏感类默认不存，需用户打开。  
- **证据：** https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context · https://support.claude.com/en/articles/9517075-what-are-projects  
- **对 LightAgent：** Space/Project 隔离压缩与记忆；「搜旧对话」可作 P2 补充，不能替代 Profile。

#### Gemini Gems / Personal Intelligence（公开 Help，摘要级）

- Gems：指令 + 知识文件，**不**自动吃全量聊天记忆。Personal Intelligence：账户级个性化（可连 Google 应用），与 Gem 正交。  
- **证据：** https://support.google.com/gemini/answer/15146780 · https://support.google.com/gemini/answer/16598469  
- **对 LightAgent：** 「Persona 文件 + 可选知识」与「全局个性化」分栏——对齐已有 persona ≠ user memory。

### 2.3 Agent 框架：长期记忆 + 压缩

| 项目 | 星数 | 机制 | 生活助手可学点 | 暂缓/不做 |
| --- | --- | --- | --- | --- |
| **LangGraph + LangMem** | LangGraph ~43.1k | `SummarizationNode`：超阈值摘要旧消息；**UI 全量 messages ≠ 送模 summarized_messages**；RunningSummary 增量 | 双 key 视图；摘要用便宜模型 | 默认每轮摘要 |
| **LlamaIndex Memory** | ~52.5k | 短窗 token_limit；溢出 flush 到 FactExtraction / Vector / Static blocks | 「短窗满 → 抽事实进长期」= write-before-forget | 每条都 LLM 抽（额度） |
| **Haystack** | ~26.7k | `ToolResultPruningCompactor`：只剪 tool；`min_keep_steps`/`min_tokens`/`skip_meta_keys`；`CompactionHook` 阈值 | **升级 spill 为预算型 tool prune** | 会话语义摘要非其长项 |
| **CrewAI** | ~59.6k | `respect_context_window` 溢出时摘要；另有 Memory() 任务前召回 | 有「窗满再摘要」开关思想 | 多智能体编排非本产品主线 |
| **AutoGen** | ~61.4k | 有 compressible / summary context 社区探索；与 SK 合流 Agent Framework | 仅作「需显式 context transform」对照 | 无成熟生活助手 compact 子系统可抄 |
| **Semantic Kernel** | ~28.7k | 偏企业 RAG/插件记忆 | 弱相关 | 不做主对标 |

证据链接：  
- LangMem：https://langchain-ai.github.io/langmem/guides/summarization/  
- LlamaIndex：https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/memory/  
- Haystack：https://docs.haystack.deepset.ai/docs/tool-result-pruning-compactor  
- CrewAI Memory：https://docs.crewai.com/edge/en/concepts/memory  

### 2.4 Coding agent：只列可迁移点（不重写）

详见 `coding_agent_compact_survey_zh.md` / `selective_context_compact_community_zh.md`。生活助手应带走的：

1. **先剪 tool，再动对话**（OpenHands / Haystack / Anthropic editing / LightAgent spill）。  
2. **System/身份外置再注入**（Claude Code / OpenClaw / LightAgent ephemeral）。  
3. **送模视图 ≠ 持久原文**（Roo / LangGraph / OpenHands View）。  
4. **自动只做廉价层；语义摘要手动+焦点指令**（Reddit/X 社区共识）。  
5. **不要默认每条 tool 再调一次 LLM 压**（`:free` 会刷爆且碎 cache）。

---

## 3. 生活助手特有压力点（对照 coding agent）

| 维度 | Coding agent | 生活助手 | 对压缩的含义 |
| --- | --- | --- | --- |
| 成功标准 | 改对文件、测试绿 | 隔天仍知偏好；提醒不漏；不串 Space | 偏好/承诺必须进 Memory，不能赌摘要 |
| 上下文膨胀主犯 | 文件内容、命令日志、MCP | web_search/browser、闲聊、重复确认 | tool spill + 闲聊尾部窗口；搜索结果可取回 |
| 「丢了就坏」的内容 | 路径、错误栈、任务清单 | 用药边界、忌口、否决项、约会时间 | pin + never-compact 元数据；veto 进 Profile |
| 时间 | 单会话任务为主 | 跨天/跨周；事实会过期 | Memory 要有有效期/supersede；摘要勿写死过时地点 |
| 身份 | CLAUDE.md / rules | persona + 多对话 identity | compact 前 strip ephemeral；压后照常再注入 |
| 用户主权 | rewind / handoff | pin、forget、可审巩固 | 压缩可预览；晋升可审（已有愿景） |
| 额度 | 常付费模型 | `:free` | 默认零 LLM 压缩；flush 优先规则 |
| 多会话 | 短线程+handoff | 家/工作/学习 Space | 按 Space 隔离 pack；压缩不跨 Space 串摘要 |

**结构化事实 vs 闲聊：**

- 日程、待办、健康忌口、购物偏好 → **结构化写入 Profile/Semantic/例程**，上下文只留「本轮相关切片」。  
- 闲聊、情绪倾诉 → 可尾部保留近期；旧的可丢或进日笔记（Episodic），**不要**整段塞进「用户长期事实」。  
- Tool 结果 → spill/prune；需要时按 sha 取回，禁止靠模型「回忆」网页原文。

---

## 4. LightAgent 二开方向（推荐 / 暂缓 / 不做）

### 4.1 一句话策略

> **默认：压前 memory flush（规则优先）→ strip ephemeral → 激进 tool spill/prune → 温和保尾部 user 轮 →（可选）结构化中间摘要。权威身份与画像每轮再注入；跨天事实走 Memory，不走 compact。**

### 4.2 与现有组件怎么接

```text
prepare_model_request
  │
  ├─► [P0] memory_flush_hook（候选/日笔记/显式 learn；不阻塞过久）
  ├─► 组装 ephemeral pack（identity/persona/profile）——独立预算
  ├─► 投影 Session → messages
  ├─► [P0] strip_ephemeral 副本专供 compact 输入
  ├─► ContextCompactor:
  │     ① tool_prune（增强 spill）
  │     ② orphan tool 修复
  │     ③ turn_window（保 head system + tail user 轮）
  │     ④ [P1 opt-in] summarizer(middle) —— 禁止含 ephemeral 正文
  ├─► 把「本轮」ephemeral 装回送模 messages（权威再注入）
  └─► 落盘时继续剥离 ephemeral
```

### 4.3 P0 — 推荐立即做（零/极低 LLM）

| ID | 方向 | 接法 | 验收 |
| --- | --- | --- | --- |
| **P0-1 压前 Memory Flush** | 对齐 OpenClaw：接近预算或手动 compact 前，把「未决承诺/用户说记住/硬偏好变更」写入候选或日笔记；规则模板优先，失败不阻断 compact | 新 hook：`local/memory/flush.py` → 调既有 Admission；TUI/core 在 `_compact_model_context` / `compact_session` 前调用 | 压后隔天仍能从 Profile/日笔记读到「记住我素食」 |
| **P0-2 Compact 输入 strip ephemeral** | 压缩/摘要输入必须先 `_strip_ephemeral_memory`；摘要模板禁止抄标签正文 | `ContextCompactor.compact` 入口或 core 包装 | 假 summarizer 输出不含 `<identity>`/`<memory-context>` |
| **P0-3 启用保守 ContextBudget（无 summarizer）** | 助手路径注入 `ContextBudget`；`summarizer=None`；预留 output + pack 预算 | TUI/agent 工厂配置 | 长大 tool 会话触发 spill+裁剪；零外部 LLM |
| **P0-4 Tool prune 增强** | 在 spill 上加：`min_keep_tool_steps`、错误结果延后剪、已 spill 元数据跳过（Haystack 对齐） | 扩展 `ContextCompactor._spill_tool_results` | 最近 1–2 步 tool 全文；更旧大结果变指针 |
| **P0-5 Spill 可取回** | `spilled[]` 已有全文：只读工具 `recall_spilled(ref)` 或 TUI「展开」 | core tool / TUI | 压后能取回某次 web_fetch 原文片段 |
| **P0-6 保尾部用户原话** | 裁剪优先保留最近 K 条 **user** 及其配对 assistant | `compact` 选择 kept 策略 | 压后仍见用户最近拍板句 |

### 4.4 P1 — 推荐下一阶段（可控 LLM / UX）

| ID | 方向 | 说明 |
| --- | --- | --- |
| **P1-1 手动智能压缩 + 焦点指令** | 默认关；用户「压缩并聚焦：下周旅行」才调 `:free` 摘要；失败回退纯裁剪 | 对齐 Claude `/compact`、OpenClaw focus |
| **P1-2 结构化生活摘要模板** | 字段：当前目标、已确认偏好（**只引 learning id**）、未决问题、近期承诺、禁止事项；要求 verbatim 引用关键 user 句 | 禁止把 ephemeral 当事实 |
| **P1-3 Pin / never-compact 元数据** | `metadata.compact="never"` 或消息标记；决策块、用户钉选 | 对齐 Haystack skip_meta + 社区诉求 |
| **P1-4 有效视图 vs 全量历史** | Session 事件全留；送模用投影；UI rewind 到 compact 前 | 对齐 Roo / LangGraph |
| **P1-5 选择性管道配置** | `pipeline: strip → tool_prune → turn_window → [summarize]` 可配 | 对齐 OpenHands Pipeline |
| **P1-6 中文 token 估计校准** | `chars_per_token` 分中英或 usage 回写 | 减少误触发 |

### 4.5 P2 — 产品形态（可排期）

| ID | 方向 | 说明 |
| --- | --- | --- |
| **P2-1 Handoff 新会话** | 长线程生成「交接草稿」（目标+记忆 id+最近原话）用户确认后新开 | Amp；减轻无限摘要 |
| **P2-2 锚定增量会话摘要** | 持久 `session_summary.md` 按驱逐段追加，非整段重生 | Mem0/Factory 主张 |
| **P2-3 与 Dreaming/巩固编排** | 日终巩固读日笔记+compact 边界；晋升可审 | OpenClaw Dreaming；ChatGPT 时效 |
| **P2-4 跨会话检索工具** | 「上次我们说的相机」→ search episodic（Claude chat search 思路） | 补充 pack，不替代 Profile |
| **P2-5 双缓冲预摘要** | 60% 后台预摘要 / 85% 换入 | Aider；注意 `:free` 竞态，默认关 |

### 4.6 明确暂缓

- 默认自动 LLM 摘要（烧额度 + 社区反感自动压时机）。  
- 每条 tool 结果再调一次 LLM 压缩。  
- 依赖 Anthropic/OpenAI **服务端** compaction（不在 OpenRouter `:free` 路径）。  
- 把 Mem0/Zep 云当硬依赖（可适配器，本地优先）。  
- AutoGen/CrewAI 多智能体 compact 子系统深挖。

### 4.7 明确不做

- 把 identity/persona/pack **摘要进用户长期事实**而不经 Admission。  
- untrusted 网页/工具结果自动晋升 curated。  
- 压缩时物理删除 Session 事件（只改送模投影）。  
- 「更大的 context window」替代记忆层。

---

## 5. 风险与验收要点

### 5.1 风险

| 风险 | 缓解 |
| --- | --- |
| 摘要漂移，丢掉忌口/否决 | P0 flush + pin + 摘要只引 learning id |
| ephemeral 污染摘要 | P0-2 strip；测试锁 |
| 滑动窗口写错全擦（Letta #3270） | 单元测试边界；失败保留原历史 |
| 压缩刷爆 `:free` | 默认无 summarizer；摘要限次/日；flush 规则优先 |
| 双视图不一致 | UI 标明「模型上下文已压缩」；rewind |
| 过时事实（人已回国仍推新加坡外卖） | Memory 时效/supersede（巩固层）；摘要避免写死绝对地点无日期 |
| Space 串味 | pack 按 space；压缩摘要带 space_id，禁跨 Space 合并 |

### 5.2 可测场景（建议写入验收）

1. **跨天偏好不丢：** 今日「我素食」→ flush/Admission → compact 裁掉原话 → 新会话仅靠 pack 仍给素食方案。  
2. **Tool 可取回：** 大 `web_fetch` spill 后，`recall_spilled` 能还原；模型不被要求「背」全文。  
3. **Identity 不被压掉：** system 含 `<identity>` → compact 输入剥离 → 下一轮仍注入同一人设。  
4. **Pin 存活：** 钉选「用药提醒边界」消息，激进 `max_messages` 仍保留。  
5. **额度：** 100 轮含大 tool 的 mock 会话，自动路径 LLM 调用次数 = 0；手动智能压缩 ≤ 1 次/触发。  
6. **否决保留：** 用户否决方案 A 后 compact，尾部或 pin 仍含否决；不推荐 A。  
7. **Space 隔离：** 工作 Space 摘要/pack 不出现在「家」对话注入。

### 5.3 成功标准（对照任务书）

- [x] 文档落盘且有可执行 P0/P1/P2  
- [x] 关键主张有来源（repo/docs/X）  
- [x] 明确：生活助手优先 **flush + tool prune + 尾部保留 + 权威再注入**；与 memory 分工写清  
- [x] X ≤25/min（本轮检索见附录）

---

## 6. 附录：检索日志

### 6.1 已读本地前序

- `local/research/coding_agent_compact_survey_zh.md`  
- `local/research/selective_context_compact_community_zh.md`  
- `local/research/personal_life_assistant_memory_zh.md`  
- `local/research/openhuman_memory_source_notes_zh.md`  
- 代码锚点：`LightAgent/session.py`（ContextCompactor）、`LightAgent/core.py`（`_strip_ephemeral_memory`）

### 6.2 Web / 文档（代表性）

| 主题 | URL |
| --- | --- |
| Mem0 压缩 vs 记忆 | https://mem0.ai/blog/context-compression-vs-memory-in-ai-agents |
| Letta compaction | https://docs.letta.com/v1-sdk/messages/compaction/ |
| OpenClaw compaction / memory / dreaming | https://docs.openclaw.ai/concepts/compaction · …/memory · …/dreaming |
| Zep context types / thread summaries | https://help.getzep.com/context-types.md · …/thread-summaries.md |
| ChatGPT Dreaming | https://openai.com/index/chatgpt-memory-dreaming/ |
| ChatGPT Memory FAQ | https://help.openai.com/en/articles/8590148-memory-in-chatgpt |
| Claude memory / chat search | https://support.claude.com/en/articles/11817273-… |
| LangMem summarization | https://langchain-ai.github.io/langmem/guides/summarization/ |
| LlamaIndex agent memory | https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/memory/ |
| Haystack tool pruning | https://docs.haystack.deepset.ai/docs/tool-result-pruning-compactor |
| Gemini Gems / personalization | https://support.google.com/gemini/answer/15146780 · …/16598469 |

### 6.3 GitHub 星数快照（2026-10-12 API）

| Repo | ★ |
| --- | --- |
| openclaw/openclaw | 391757 |
| OpenHands/OpenHands | 90699 |
| mem0ai/mem0 | 67036 |
| microsoft/autogen | 61370 |
| crewAIInc/crewAI | 59600 |
| run-llama/llama_index | 52469 |
| langchain-ai/langgraph | 43133 |
| getzep/graphiti | 31672 |
| microsoft/semantic-kernel | 28654 |
| deepset-ai/haystack | 26726 |
| letta-ai/letta | 25112 |
| getzep/zep | 4956 |

（cursor-github MCP 本环境未连接，星数改用 `api.github.com`。）

### 6.4 X（Twitter）检索

- **配额策略：** 先 `get_posts_counts_recent`，再分批 `search_posts_all`；本任务合计约 **6 次**读（counts×1 + search×5），远低于每分钟 25。  
- **查询主题：** personal assistant memory；Mem0/Zep/Letta；OpenClaw memory flush/dreaming；memory vs compression；ChatGPT Dreaming / project memory。  
- **有用信号：**  
  - @kingclaw_K：先 Memory Flush（约 77%）再 Compaction（约 85%）——与 OpenClaw 同构。  
  - @OpenClawLog：memory plugin 可拥有 pre-compaction flush。  
  - @KaelirRises：OpenClaw Dreaming 三阶段作个人陪伴记忆。  
  - @garrytan / 回复：个人 AI 要自有 skills + memory。  
  - @snwiki238337：工作记忆含滑动窗口等分层路线。  
  - @0xthe0 文题：把百万 token 会话压到 86k **不等于** memory。  
  - @stretchcloud 等：瓶颈从窗口转向跨会话记忆；无 LLM 的确定性归档（snapcompact）叙事。  
- **前序文档**已采 SoL-Pi Online Compact / ObservationPack 等（见 selective 附录 A）。

### 6.5 Reddit

- 直连 / `.json`：**超时或 403 Bot 防护**（与前序一致）。  
- 不死磕全文；选择性压缩社区结论沿用 `selective_context_compact_community_zh.md`（搜索引擎摘要 + 已引用线程）。

### 6.6 未做 / 限制

- 未改 LightAgent 业务代码、未调 OpenRouter。  
- 未深挖 AutoGen/SK 合流后的最新 Agent Framework compact API（公开生活助手案例少）。  
- ChatGPT/Claude/Gemini 内部实现不可见，仅公开产品行为。  
- ClawMem（~210★）为 OpenClaw 生态插件，未当独立 compact 引擎深读。

---

## 7. 核心结论（给决策者）

1. **生活助手的「记得」主要靠 Memory，不靠 Compact**；Compact 只负责本会话窗口卫生。  
2. **业界生产模式是三层**：working 原文 → 会话内廉价压缩 → 外置记忆检索；**写记忆必须在压缩前**（OpenClaw flush / Mem0）。  
3. **`:free` 下默认策略应是：flush（规则）+ strip ephemeral + tool spill/prune + 尾部 user 保留**；LLM 摘要仅手动 opt-in。  
4. **Identity/persona/pack 永不进摘要正文**；压后每轮从权威源再注入。  
5. **对标优先级：** OpenClaw（flush+文件记忆+compaction）> Mem0 边界论 > Haystack tool prune > Letta sliding（opt-in）> ChatGPT/Claude 产品行为（可审巩固与 Project 隔离）。

**推荐二开一句话：** 先做压前 memory flush 与增强 tool prune，并保证 ephemeral 剥离与权威再注入；LLM 会话摘要保持关闭，仅作带焦点指令的手动能力。

---

*本文件为调研与方向建议，不包含实现补丁。*
