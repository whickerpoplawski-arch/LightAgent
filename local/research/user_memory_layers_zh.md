# 「越用越懂用户」记忆分层调研

> 范围：OpenHuman、Mem0、Letta/MemGPT、Claude/ChatGPT Memory、OpenClaw（及 ClawMem 插件）  
> 对照：LightAgent `MemoryProtocol` / `MemoryPolicy` / Admission / Promotion / `SharedMemoryPool`  
> 日期：2026-10-12 · 未消耗 OpenRouter 额度

---

## 1. 结论先看

「越用越懂用户」几乎从不靠「把整段聊天塞进上下文」，而是靠：

1. **可编辑的用户画像 / 偏好层**（常驻或高优先级注入）  
2. **从对话中抽取 → 准入 → 晋升** 到长期语义/画像  
3. **按需检索** 情景记忆（会话/日笔记/历史聊天）  
4. **遗忘与覆盖**（supersede、forget、衰减、用户可删）

强相关层：**Profile / Preference（画像与偏好）> Semantic/User memory（长期事实）> Episodic（情景）**。  
Working / Session 主要保连贯，对「跨天越用越懂」贡献弱；Procedural（怎么做事）偏工作流复用，间接相关。

---

## 2. 通用记忆分层（对照表）

| 层 | 含义 | 写入 | 检索/注入 | 晋升/遗忘 | 与「懂用户」相关度 |
| --- | --- | --- | --- | --- | --- |
| Working | 当前轮上下文、工具中间态 | 自动进 prompt | 本轮可见 | 轮结束丢弃 | 弱 |
| Session | 当前任务/频道内短期事实 | 会话内 store | 按 session/run_id 过滤 | 会话结束清理或晋升 | 中（任务内） |
| Episodic | 「某次发生了什么」 | 日笔记、transcript、摘要 | 搜索/召回，通常不自动全量注入 | 反复有用 → 晋升为语义/画像 | 中（证据源） |
| Semantic / User | 长期事实、偏好、实体关系 | 抽取/learn/add | 向量+关键词+实体；部分常驻 | 去重、冲突解决、过期 | **强** |
| Profile | 结构化「你是谁/怎么对你」 | 显式偏好、facet 稳定分、USER.md | 常驻 system 或每轮小包 | pin/衰减/supersede | **最强** |
| Procedural | 习惯流程、工具用法 | learn procedure / skill 沉淀 | 任务匹配时注入 | 版本化、纠正覆盖 | 中偏强（风格与习惯） |

---

## 3. 各项目怎么做

### 3.1 OpenHuman（tinyhumansai/openhuman）— 最贴近「越用越懂」

文档：[Personalization](https://tinyhumans.gitbook.io/openhuman/features/personalization)、[Memory Tools](https://tinyhumans.gitbook.io/openhuman/features/native-tools/memory-tools)

**机制三件套**

1. **Learnings**：一条可持久陈述（偏好 / 事实 / 流程 / 纠正），经 `memory` 工具的 `learn` 写入；可 UI 编辑、可 `forget`；跨同 memory root 的 agent 共享；写前 scrub 密钥/标识。  
2. **Memory pack（每轮召回包）**：token 预算内拼相关 learnings、beliefs、brain 文档、本 agent 历史、短暂其他 agent 回合 → **只进当轮请求，不写回聊天**（保护 prompt cache）。  
3. **Persona 文件**：`SOUL.md` / `IDENTITY.md` / `ROLE.md` — 管「agent 是谁」，与用户记忆分离。

**进阶（PR / 源码）**

- **Ambient personalization cache**：6 类 facet（style / identity / tooling / veto / goal / channel）→ `user_profile_facets`；稳定性打分 + 类半衰期（identity ~90d → channel ~7d）；冲突 `argmax(stability)`；prompt 上限约 25 条；可 pin/forget/rebuild。  
- **两车道偏好**：`save_preference`  
  - **general**：线程开始常驻 system  
  - **situational**：按主题语义相似度每轮召回进 user lane  
- 工具：`recall` / `fetch` / `learn` / `forget`；另有指令偏置「涉人/项目/历史决策先 `memory_recall`」。

**分层映射**：Working=当轮；Episodic≈历史对话片段进 pack；Semantic=learnings；Profile=facets + general prefs；Procedural=procedure 类 learning。

**强相关**：Learnings + Profile facets + two-lane preferences + 每轮 memory pack。

---

### 3.2 Mem0

文档：[Memory types](https://docs.mem0.ai/core-concepts/memory-types)、[Architecture skill](https://github.com/mem0ai/mem0/blob/HEAD/skills/mem0/references/architecture.md)、[Graph Memory](https://docs.mem0.ai/platform/features/graph-memory)

**生命周期层**：Conversation（轮内）→ Session（`run_id`）→ User（`user_id`）→ Org（共享）。  
**认知类型**：Factual / Episodic / Semantic（含实体图共现增强检索）。

**写**：`add(messages, user_id, run_id)` → 服务端抽取、去重、冲突处理；ADD-only 保留时间线。  
**读**：语义 + BM25 + 实体 boost + 时间意图；用户层优先。  
**晋升**：重复情景记忆可 consolidate 成更稳的语义事实。  
**强相关**：User-scoped factual/preference memories + graph 实体关联；Session 只保证任务连贯。

---

### 3.3 Letta / MemGPT

文档：[Stateful agents](https://docs.letta.com/guides/core-concepts/stateful-agents)、[Memory blocks](https://docs.letta.com/guides/core-concepts/memory/memory-blocks)、[Archival](https://docs.letta.com/v1-sdk/memory/archival-memory/)

| 层 | 实现 | 注入 |
| --- | --- | --- |
| Core（Working+Profile 混合） | Memory blocks（推荐 `human` + `persona`） | **始终在上下文**，agent 用 memory 工具改写 |
| Recall / Episodic | 全量消息落库 | conversation search 按需 |
| Archival / Semantic | 无限语义库 | `archival_memory_insert/search` 按需 |

**晋升**：无自动「做梦」；靠 agent **主动**把重要事实写进 block 或 archival。  
**强相关**：`human` block（用户画像常驻）+ 共享 blocks；archival 是知识库，次之。

---

### 3.4 Claude Memory / ChatGPT Memory（产品形态）

| | Claude | ChatGPT |
| --- | --- | --- |
| 自动记忆 | 聊天中抽取 topic 条目；可「记住这个」 | Saved memories + 可选 Reference chat history |
| 常驻规则 | **User Preferences**（always 指令） | Custom Instructions |
| 范围 | 全局池 + **按 Project 隔离**；incognito 不记 | 偏全局；临时聊天可绕过 |
| 检索 | Chat search（历史 RAG）+ memory 相关性加权 | 历史参考 + 显式记忆 |
| 用户控制 | 查看/编辑/暂停/重置 | 单条删、清空、开关 |

**强相关**：Preferences/Custom Instructions（硬规则）+ 自动记忆条目（软画像）。  
与开源 agent 差异：产品侧抽取与注入黑盒，但「硬偏好 vs 软记忆」分层与 OpenHuman 两车道同构。

---

### 3.5 OpenClaw（+ ClawMem）

文档：[Memory architecture](https://docs.openclaw.ai/concepts/memory-architecture)、[Dreaming](https://docs.openclaw.ai/concepts/dreaming)

**Tier 模型（文件 + SQLite）**

| Tier | 表面 | 自动注入 |
| --- | --- | --- |
| Instructions | `AGENTS.md` 等 | 会话开始始终 |
| Curated core | `MEMORY.md`、**`USER.md`** | 会话开始预算内（仅可信 provenance） |
| Episodic | `memory/YYYY-MM-DD.md`、transcript | **否**；仅 search / Active Memory |
| Prospective | standing intents / cron | 触发时 |
| Review | `DREAMS.md` | 否（给人看） |

**写路径**：交互中写日笔记 → flush/ingestion → **Dreaming**（Light/REM 暂存；Deep = 确定性门控 + 模型合并进 MEMORY/USER）→ supersede / 预算 / 哈希乐观并发。  
**读路径**：Lane1 零模型（bootstrap + hybrid search + trigger 注入≤3）；Lane2 贵（召回子 agent，仅有意图且 Lane1 弱命中时）。  
**安全**：provenance（owner/agent/untrusted/system）；untrusted **永不能**晋升 curated / 自动注入；网络工具结果 taint 当轮。  
**USER.md 契约**：祈使句偏好（Always/Never/Prefer），原地 supersede，避免追加矛盾导致模型读旧值（PrefEval）。

ClawMem：SQLite vault（BM25+向量+关系图），作 OpenClaw `kind: memory` 插件；钩子做注入与 turn 后抽取。

**强相关**：`USER.md` 用户模型 + Dreaming 晋升 + trigger 自动注入；日笔记是证据不是画像。

---

## 4. 对照 LightAgent（/workspace/LightAgent）

| 概念 | LightAgent 现状 | 与「懂用户」缺口 |
| --- | --- | --- |
| `MemoryProtocol` | `store(data, user_id)` / `retrieve(query, user_id)` — 极简适配器口 | 无原生 Profile/facet/类型字段 |
| `MemoryScope` | source=`user`\|`reflection`，scope=`user`\|`agent` + provenance 元数据 | 有溯源骨架，缺偏好 taxonomy |
| `MemoryPolicy` | 命名空间、来源/范围白名单、写限流、去重、模式拒绝、`expires_at` | **准入/安全强**，产品化画像弱 |
| Admission | `memory_write_admission`；可 `require_write_admission` fail-closed | 适合挡毒/控额度，不负责「学到什么」 |
| Promotion | 内部证据默认非 injectable；`approve/reject/rewrite/keep`；可后审 `promote_memory_candidate` | 接近 OpenClaw「候选→晋升」，但无 Dreaming/稳定性打分 |
| `SharedMemoryPool` | 内存 append-only 原型，满足 Protocol | 实验用，非持久用户画像 |
| `self_learning` | core 开关，reflection 类写入走 Promotion | 开启后若不接 Promotion 审核会积「候选」而非可用画像 |
| 生态适配 | 示例：Mem0、vector、memcode、clawmem adapter | **可外挂** Mem0/ClawMem，内核不强制分层 |

**一句话**：LightAgent 已具备「可插拔存储 + 写准入 + 内部记忆晋升门闩 + 共享池原型」，偏 **安全与边界**；缺 OpenHuman/OpenClaw 那种 **Profile 常驻 + 每轮 memory pack + 偏好两车道 + 后台巩固**。二开应落在 `local/`：User Profile store + 每轮注入预算 + 把 user 显式偏好与 episodic 检索分开，复用现有 Admission/Promotion。

---

## 5. 对 LightAgent 二开的轻量建议（不实施，仅方向）

按投入从小到大：

1. **User Profile 文件/表**（类 `USER.md` / general prefs）：可编辑条目，每轮预算注入 system；不耗搜索。  
2. **显式 learn/forget 工具** + Admission（scrub、拒密钥、限写）。  
3. **每轮 retrieve 包**（类 memory pack）：user 层优先，token 封顶；勿写回聊天历史。  
4. **Episodic → Profile 晋升**：复用 `MemoryCandidate` + Promotion；可用「重复出现 / 用户说记住 / 稳定性」规则，后台批处理以免烧免费额度。  
5. 需要图/混合检索时再挂 Mem0 或 ClawMem adapter，而不是先造重存储。

**务必强相关的最小集**：Profile（常驻）+ User semantic（检索）+ Promotion 门闩；Session/Working 沿用现有对话即可。

---

## 6. 参考链接

- OpenHuman Personalization / Memory Tools（tinyhumans.gitbook.io）  
- Mem0 Memory types / Graph Memory / architecture skill  
- Letta Stateful agents / Memory blocks / Archival  
- Claude Help：chat search and memory；OpenAI：Memory FAQ  
- OpenClaw Memory architecture / Dreaming；ClawMem architecture  
- LightAgent：`LightAgent/protocol.py`，`docs/memory_admission.md`，`docs/shared_memory_pool.md`
