# OpenHuman 记忆机制源码精读对照笔记（指导 LightAgent 自实现）

> 仓库：`/workspace/openhuman`（shallow clone）· commit **`bf3cf35`**  
> TinyMemory submodule：`/workspace/openhuman/vendor/tinymemory` · commit **`29c268c`**  
> 日期：2026-10-12（America/Martinique / AST）  
> **未**改 LightAgent 业务代码 · **未**调用 OpenRouter · **不**把 OpenHuman 代码抄进 LightAgent

---

## 0. 读源结论（给实现者）

### 0.1 真实组件边界

OpenHuman 记忆栈是 **三层**，不是一个「记忆模块」糊在一起：

| 层 | 位置 | 职责 |
| --- | --- | --- |
| **Host（OpenHuman）** | `crates/openhuman-core/src/memory/` | 绑引擎、身份/scope、围绕 turn 调生命周期、后台 job 队列、RPC/`memory` tool、scrub、consent 导入/删除、计费门控 |
| **TinyMemory Tools** | `vendor/tinymemory/crates/tinymemory-tools` | `AgentMemory` 生命周期、`MemoryLayout`、holistic recall → `ContextPack`、Brain、`BackgroundJob`、工具 schema |
| **TinyMemory API + Engine** | `tinymemory-api` + `tinymemory-integrations`（CortexDB / tinyhumans） | `MemoryEngine` 契约：store/fetch/recall/forget/list/consolidate/beliefs；具体持久化与信念构建 |

再加两条 **非 memory 目录、但强相关** 的边界：

| 边界 | 位置 | 说明 |
| --- | --- | --- |
| **Turn 注入** | `agent/tinyagents/middleware/memory_pack.rs` + `session_host/.../memory_ingest.rs` | pack **ephemeral** 注入；聊天线程持久化在 `threads/`，**不是** memory |
| **Persona** | `agent/prompts/{SOUL,IDENTITY,ROLE,STYLE,USER}.md` + `config/workspace` + `channels/system_prompt.rs` | 助手人格/角色文件，**与用户 learnings 分栏**；进 system prompt，不进 memory engine |

**Personalization 产品面**（`gitbooks/features/personalization.md`）在源码里 = **Learnings + Memory pack + Persona 文件**。  
没有独立的 `personalization/` crate，也没有名为「两车道 preference / ambient personalization cache / Dreaming」的实现模块（见 §0.4 与 §5）。

### 0.2 自实现必须对齐的不变量（硬规则）

1. **Pack 永不写回聊天 / transcript**  
   OpenHuman：`push_ephemeral_instruction`；`<memory-context>...</memory-context>` 只活在当次 model request。  
   LightAgent 应对齐：**检索结果不得拼进用户提问再整句 store**（当前 `core._add_memory_context` 违反此条）。

2. **Persona ≠ User memory**  
   `SOUL.md` / `IDENTITY.md` / `ROLE.md` 是可编辑人格文件；Learnings 是 engine 里的 durable statements。两套路径、两套编辑入口。

3. **身份由 host 决定，模型参数改不了 namespace/reach**  
   `CallFacts` / `confine` 覆盖模型传入的 `reach`；`learn` 的 workspace/thread/agent/tool_call/namespace 由 host stamp。

4. **Live turn 不 await 远程记忆 I/O**  
   pre-turn 只取 **已完成** 的 cached pack；冷缓存 → 无 pack；日志/召回在后台 scoped worker。显式 `recall`/`fetch` 才同步等引擎（有 tool budget）。

5. **拒绝 ≠ 空记忆**  
   `INSUFFICIENT_CREDITS` / `UNAUTHORIZED` / `UNAVAILABLE` → pack 是「memory unavailable」notice，禁止模型说「我什么都不记得」。

6. **写入一律 scrub（secrets + PII）**  
   `ScrubbingEngine` 包住引擎；任何路径（turn log、learn、brain ingest）都经 scrub。

7. **Belief / consolidate 是离线 BackgroundJob，不阻塞 turn**  
   `post_turn` 返回 job；host 持久化到 `jobs.json`，cron 延迟执行（`build_delay_secs`）。

8. **Turn 索引稳定可重放**  
   user=`2n`，reply=`2n+1`（相对已提交 turn 数）；同输入重试 = replay，非重复写入。

9. **Pack 排除「仍在 prompt 里的窗口」**  
   `in_prompt_from` / `exclude_thread`：已 verbatim 在对话里的 turns 不再进 pack，避免重复与污染 prefix cache。

10. **Learnings 共享在 layout root；conversation 按 agent 节点隔离；brain 无 agent_id**  
    布局不变量：`root` learnings + `agent:<id>` turns + `source:<kind>` documents。

### 0.3 参考思路 / 不要抄的实现细节

| 参考思路（对齐语义） | 不要抄（实现细节/依赖） |
| --- | --- |
| 分层：Learnings / Conversations / Brain + Belief 巩固 | Rust crate 拆分、CortexDB wire、TinyHumans 凭证动态解析 |
| 每轮 token-budgeted pack + 分节优先级 + 从尾修剪 | `CHARS_PER_TOKEN=4`、默认 1200 tokens、具体 limit 数字可自定 |
| ephemeral 注入（system/instruction 车道，不进 user 持久历史） | `tinyagents` middleware / `push_ephemeral_instruction` API |
| host stamp meta + confine reach | OpenHuman task-local `MemoryIdentity`、RPC 全套 |
| learn/forget 异步出盒 + 「queued; not yet saved」语义 | `tool_writes` 256 条 / 2MiB 分区实现细节 |
| Persona 文件常驻 system；与 memory 分栏 | 强制 `SOUL.md` 文件名；可改成 LightAgent 的 profile YAML/MD |
| Background belief build + delay | CortexDB `v1/beliefs/build`、hosted `Scheduled` 语义 |
| Explore Facet = **元数据浏览维度** | 勿把 Facet 当成「用户偏好类别 taxonomy」 |

### 0.4 先前调研需纠偏（文档/印象 vs 本仓库源码）

| 说法 | 源码真相 |
| --- | --- |
| 「Dreaming」巩固 | **无** Dreaming 模块；对应物是 **belief build / `consolidate` + `BackgroundJob`** |
| general / situational **两车道偏好** | **无** 该命名与分流注入实现；只有 `LearningKind::{Preference,Fact,Procedure,Correction,Other}` + pack Learnings 节 |
| Facet = 偏好类别（style/health…） | Facet = explore 元数据：`Kind/Source/Workspace/Thread/Tag/...` |
| tool-scoped memory（critical/high/normal + prompt pin） | **记忆栈内无** 该子系统；tool 侧有 budget/出盒，不是 priority pin 规则引擎 |
| ROLE.md 始终注入 | `ROLE.md` 主要给 orchestrator；非 orchestrator 默认 **skip**（`sections.rs`） |
| Personalization = 独立引擎 | 产品文档三件套：Learnings + pack + Persona 文件 |

自实现「全方位生活助手」时，**两车道 / Dreaming / Space** 可作为 **LightAgent 产品加厚**，但不要谎称「OpenHuman 已有同名源码」。

---

## 1. 仓库地图

### 1.1 顶层

```text
openhuman/
├── crates/openhuman-core/src/memory/     # Host 记忆层（本文主战场）
├── crates/openhuman-core/src/agent/      # Turn 钩子、pack middleware、Persona prompts
├── vendor/tinymemory/                    # 引擎契约 + AgentMemory + Cortex 集成
├── docs/specs/memory-v2.md               # Host 规格（accepted）
├── gitbooks/features/memory.md           # 产品
├── gitbooks/features/personalization.md  # Learnings+pack+Persona
└── gitbooks/features/native-tools/memory-tools.md
```

### 1.2 Host：`crates/openhuman-core/src/memory/`

| 路径 | 一句话职责 |
| --- | --- |
| `README.md` | Host 设计总览（强烈建议实现者通读） |
| `engine.rs` | 解析/缓存 bound engine；`tinyhumans` / `cortexdb` / host install |
| `guard.rs` | `ScrubbingEngine`：写路径 scrub + timing |
| `scope.rs` / `user_scope.rs` / `local_root.rs` | 谁在行动；layout v3 用户根；signed-out install id |
| `lifecycle/mod.rs` | 为 identity 构建 `AgentMemory` + RecallPolicy |
| `lifecycle/hooks.rs` | `TurnPack` / `MemoryTurn`；pre/post/compaction 操作 |
| `lifecycle/prefetch.rs` | **不阻塞 turn** 的缓存 pack + 后台刷新 |
| `lifecycle/jobs.rs` | `jobs.json` 后台 belief/ingest 队列 |
| `lifecycle/views.rs` | UI：policy / pack preview / agents / jobs |
| `lifecycle/date_hint.rs` | 可选「用户说的是哪几天」小模型提示 |
| `lifecycle/sender.rs` | channel 发送者 → `observed_actor` |
| `tools.rs` | 唯一 agent tool：`recall|fetch|learn|forget` |
| `tool_budget.rs` / `tool_writes.rs` | 读超时预算；learn/forget 本地出盒异步投递 |
| `confine.rs` | RPC/tool 强制 reach ⊆ identity 子树 |
| `ops.rs` / `explore.rs` / `brain.rs` / `sources/` | 引擎 ops、facet 浏览、brain、同步源 |
| `deletion.rs` / `backfill.rs` / `import*.rs` / `layout_migration/` | 删除队列、历史回填、v1 导入、布局迁移 |
| `billing.rs` / `bus.rs` / `schemas*` / `types.rs` / `error.rs` | 免费期、cron 订阅、RPC、错误码 |

### 1.3 TinyMemory

| Crate | 职责 |
| --- | --- |
| `tinymemory-api` | `MemoryEngine`、`StoreItem`、`MemoryMeta`、`LearningKind`、`consolidate`/`beliefs`、`Facet` explore |
| `tinymemory-tools` | `AgentMemory`、`HolisticRecall`/`ContextPack`、`Brain`、`BackgroundJob`、memory tools |
| `tinymemory-integrations` | CortexDB 引擎、scrub、document convert、source readers、v1 import |

### 1.4 Agent harness 关键入口

| 文件 | 角色 |
| --- | --- |
| `agent/session_host/runtime_session/memory_ingest.rs` | pre-turn / post-turn 挂到 session |
| `agent/tinyagents/middleware/memory_pack.rs` | 每请求 ephemeral 注入 pack |
| `agent/tinyagents/memory_summarizer.rs` | compaction 时 recall |
| `agent/prompts/sections.rs` + `render_helpers/workspace_files.rs` | 加载 SOUL/IDENTITY/ROLE |
| `channels/system_prompt.rs` | channel 侧 identity 文件热刷新 |

### 1.5 规格 / 文档入口

- `docs/specs/memory-v2.md`
- `vendor/tinymemory/docs/specs/agent-memory.md`
- `crates/openhuman-core/src/memory/README.md`
- `docs/gitbooks/en/developing/architecture/memory.md`

---

## 2. 生命周期（按 turn）

编号步骤 ↔ 源码：

1. **Session / identity 就绪**  
   Host 用 `scope::within_agent` / `within` 设 task-local `MemoryIdentity` → `ResolvedIdentity`（root + memory agent id）。  
   文件：`memory/scope.rs`；ingest：`memory_ingest.rs`。

2. **Pre-turn（before_turn）**  
   `OpenHumanTurnPrelude::memory_pre_turn` → `lifecycle::prefetch::pre_turn`：  
   - **同步**：取已完成 cached `TurnPack`（或 none / refusal notice）  
   - **异步队列**：`AgentMemory::pre_turn`（或 resumed 后 `start_session`/`pre_turn_resumed`）：`WaitFor::Accepted` 记用户 turn + holistic fetch  
   文件：`memory_ingest.rs`、`lifecycle/prefetch.rs`、`lifecycle/hooks.rs`、`tinymemory-tools/.../lifecycle/mod.rs`。

3. **Pack 组成（TinyMemory）**  
   `HolisticRecall` 分节（优先级从前到后，预算从**最后一节**修剪）：  
   1. **Learnings**（含 engine beliefs，tag `belief`）  
   2. CoreScope 节（默认空；仅 host `promote` 可写）  
   3. **Brain**（最多 `BRAIN_SCOPES_PER_TURN=4` 个 source scopes）  
   4. **This agent's history**  
   5. **Team conversations**（同 root 其他 agent；`team_limit=0` 则关闭）  
   排除：当前正在 log 的 turn；`in_prompt_from` 之后仍在 prompt 的 turns。  
   文件：`tinymemory-tools/src/lifecycle/mod.rs`、`recall/{gather,render,types}.rs`。

4. **注入点（system / instruction 车道，非 user 持久消息）**  
   `MemoryPackMiddleware::before_model` → `TurnPack::injection()` →  
   `format!("<memory-context>\n{markdown}\n</memory-context>")` →  
   `push_ephemeral_instruction(...)`（尾 system，或对 hoist system 的模型挂到尾 user/tool）。  
   **不**写入 transcript / provider cached prefix。  
   文件：`middleware/memory_pack.rs`、`lifecycle/hooks.rs`（`OPEN_TAG`/`CLOSE_TAG`）。

5. **Model + tools 运行**  
   可选显式 `memory` tool：`recall`/`fetch`（同步、有 budget）；`learn`/`forget`（校验+scrub → 本地 outbox → 后台投递）。  
   文件：`memory/tools.rs`、`tool_budget.rs`、`tool_writes.rs`、`confine.rs`。

6. **Turn log（post-turn，durable commit 之后）**  
   `memory_post_turn` → 后台 `AgentMemory::post_turn`：记 assistant turn（含 tool call 摘要）→ 可能返回 `BuildBeliefs` job。  
   文件：`memory_ingest.rs`、`lifecycle/hooks.rs`、`lifecycle/jobs.rs`。

7. **Background belief / consolidate**  
   Job 入 `workspace/memory/jobs.json`，去重；`memory_background` cron（约 5 min）在 `build_delay_secs`（默认 300）后 `run_due`。  
   Engine：`consolidate` / 或 `Scheduled`/`Automatic` 自建信念；读：`beliefs()` → Learning hits + `BELIEF_TAG`。  
   文件：`lifecycle/jobs.rs`、`bus.rs`、`tinymemory-api/src/consolidate/mod.rs`。

8. **Compaction 时 recall**  
   `MemoryRecallSummarizer`：用 **已完成缓存** 丰富 checkpoint；队列 `recall_for_compaction`（answered summary + 标准节）；**不**让引擎 I/O 拖住 summarizer。  
   文件：`agent/tinyagents/memory_summarizer.rs`、`lifecycle/prefetch.rs`。

默认 `RecallPolicy`（`tinymemory-tools/.../lifecycle/types.rs`）：`budget_tokens=1200`，learnings/brain/history/team = 8/6/6/3，`build_beliefs_every=Some(10)`。

---

## 3. 数据结构（字段级摘要）

### 3.1 Learning（`StoreItem::Learning`）

```text
Learning {
  text: String,                 # 一句 durable 陈述
  kind: LearningKind,           # preference | fact | procedure | correction | other
  confidence: f32,              # 0.0..=1.0
  evidence: Option<String>,
  meta: MemoryMeta,
}
```

Host `learn` 强制 stamp 的 meta（模型不可选）：`namespace=learnings节点`、`workspace`、`thread_id`、`agent_id`、`tool_call={name:memory,id}`、`source.kind=agent`。

### 3.2 Belief

- **不是**可 list/fetch/forget-by-id 的普通 item（Cortex 层）。  
- `MemoryEngine::beliefs` → Learning 形态 hits，tag **`belief`**（`BELIEF_TAG`）。  
- 删 sources 则信念随之消失。  
- Pack 的 Learnings 节：stored learnings 与 beliefs **按秩交错，stored 优先**。

### 3.3 Memory pack / ContextPack / TurnPack

```text
ContextPack { markdown, tokens, refs: [ItemId], sections, skipped, engine }

TurnPack {  # Host 包装
  markdown, tokens, refs: [String], engine,
  citations,                 # UI chips
  refusal: Option<code>,     # 账户拒绝时的 notice
}
injection() => "<memory-context>\n{markdown}\n</memory-context>"
```

### 3.4 Preference「车道」

源码 **无** general/situational 双车道结构。最接近的分类是：

```text
LearningKind = Preference | Fact | Procedure | Correction | Other
```

产品层「偏好」= kind=preference 的 Learning，经 Learnings 节进 pack。

### 3.5 Facet（explore，非偏好 taxonomy）

```text
Facet = Kind | Source | SourceId | Workspace | Folder | FilePath
      | Language | Repo | Url | Thread | Agent | ToolCall | Tag | Namespace
```

用途：UI/CLI 按元数据下钻计数（`explore` → narrow → 再 explore）。

### 3.6 ToolMemoryRule

**本仓库记忆栈不存在** `ToolMemoryRule` / critical-pin 类型。  
相近机制：

- agent `memory` tool 的 **budget + writebox**  
- CoreScope + `AgentMemory::promote`（**仅 host**，模型工具不能选 core 节点）

### 3.7 Persona 文件

| 文件 | 加载 | 备注 |
| --- | --- | --- |
| `SOUL.md` | system / channel prompt 常驻 | 行为与语气 |
| `IDENTITY.md` | 同上 | 使命/价值观 |
| `ROLE.md` | orchestrator 注入；普通 agent 默认 skip | 角色 brief |
| `STYLE.md` / `USER.md` | prompts 包内 | 风格与「记住/忘记边界」指导（USER.md 是 **提示词**，不是用户 Profile store） |

Workspace RPC allowlist 主要暴露 `SOUL.md`/`IDENTITY.md` 编辑；`ROLE.md` 由 agent prompt 渲染路径加载。

### 3.8 MemoryMeta（摘要）

`namespace, workspace, folder, file_path, language, repo, commit, url, thread_id, turns, agent_id, tool_call, source, tags, observed_at, derive, observed_actor`。

---

## 4. 工具面

单一工具名：`memory`（`MEMORY_TOOL_NAME`），仅 memory on 时注册。

| action | 行为 | 同步性 | 权限/边界 |
| --- | --- | --- | --- |
| `recall` | 问答式召回 + citations | 同步（≤ tool budget） | reach 被 confine 为 identity 子树；模型 filter.reach 被覆盖 |
| `fetch` | 原始 hybrid 检索 + MetaFilter | 同步 | 同上 |
| `learn` | 存一条 Learning | **本地出盒确认** → 后台投递 | host stamp meta；scrub；默认 learnings 节点 |
| `forget` | 按 id（或 filter）删除 | 出盒异步 | 只能删 reach 内 id |

预算（host）：单次约 15s、aggregate 约 30s、每 run ≤8 次；超时后告知模型勿在本 run 重试。

语义字符串：

- 读成功 / 写排队：文档写明 learn/forget 为「queued; not yet saved/removed」——**确认的是本地准入，不是远端已索引**。  
- （`tools.rs` 另有历史 `LEARN_STATUS = "saved; searchable in recall shortly"` 常量；以 README/`memory-tools.md` 的 queued 语义为准做产品对齐。）

PII/secret：所有 store 经 `ScrubbingEngine` / `scrub_item_with(host_policy)`。

MCP：`memory.recall|fetch|list|learn|forget` 走同一 confine。

---

## 5. Personalization 源码细节

### 5.1 产品定义（文档）

`gitbooks/features/personalization.md`：

1. Learnings（preference/fact/procedure/correction）  
2. 每轮 memory pack（不进聊天）  
3. Persona 文件（SOUL/IDENTITY/ROLE）

### 5.2 Facets「类别」

**不是** style/health/finance 偏好面。  
Explore `Facet` = 存储元数据维度（见 §3.5）。

### 5.3 稳定性 / 半衰期 / 冲突解决

- Learning 有 `confidence`；**无** half-life / stability 字段或衰减调度器。  
- Belief 由 engine consolidate 产生；冲突解决在 **engine 侧**（Cortex），host 只排队 job。  
- 用户可在 UI Learnings 删除，或 tool `forget`。

### 5.4 general vs situational 两车道

**源码未实现分流注入。**  
对齐建议（LightAgent 自研）：用 `LearningKind` + 自有 `lane`/`space`/`topic` 标签扩展 Profile，**不要**假装从 OpenHuman 抄了两车道模块。

### 5.5 USER.md

是 bundled **adaptation 提示**（记住什么/忘记什么/隐私规则），**不是**运行时用户画像数据库。

---

## 6. Tool-scoped memory

### 6.1 OpenHuman 实际有什么

- **全局** `memory` tool（非 per-tool memory 规则表）  
- **CoreScope + promote**：跨 agent 共享的「核心」层，仅 host 写入  
- Turn log 可带 **tool_calls 摘要**（名称/id/一行结果）进 conversation item  
- `meta.derive=false` 可禁止 engine 从 runtime/tool 输出派生信念

### 6.2 没有什么

- `priority: critical|high|normal`  
- `prompt_pin` 规则对象  
- per-tool capture hook 专用 memory schema  

若 LightAgent 需要「critical 规则钉进 system」，应作为 **自研 Profile/Policy pin**，参考的是 Persona 常驻 + Learnings 高优先级节，而不是 OpenHuman 的 tool_memory 子系统（不存在）。

---

## 7. 与 LightAgent 对照（防错乱）

### 7.1 已知偏差

| LightAgent 现状 | OpenHuman 做法 | 应对齐 |
| --- | --- | --- |
| `core._add_memory_context`：检索拼进 query，再 `return f"{context}\n##用户提问：\n{query}"`，且 **把拼接前/后的用户话 store** | pack → ephemeral instruction；**不改**用户消息；turn log 是独立 conversation item | **拆开**：Retrieve→Pack（独立车道）；Store 只存原始 user text / 抽取后的 Learning，绝不存「带记忆前缀的提问」 |
| `self_learning=True`：用 **agent name** 当另一 user_id 存同一 query | Agent 侧是 conversation 节点 + 可选 reflection **不等于** 用户 Profile；Learnings 在共享 root | `self_learning` ≠ User Profile；新建真正的 Profile/Learnings store |
| `SharedMemoryPool` 进程内 append-only 原型 | Engine 持久化 + layout namespaces + scrub + deletion 队列 | Pool 可做开发期；产品态要对齐「持久 + scrub + forget + scope」 |
| Admission/Promotion 门闩已有 | confine + host stamp + CoreScope.promote + scrub | **复用** LightAgent Admission/Promotion；对应 OpenHuman 的「谁可写 / 谁可升 / 谁可进 pack」 |

### 7.2 自实现模块草图：`local/memory/`

| 建议文件 | 对齐 OpenHuman 哪条机制（语义，非抄路径） |
| --- | --- |
| `layout.py` | MemoryLayout：learnings / agent turns / brain|docs / space 根 |
| `types.py` | Learning（含 kind/confidence）、Episode、ProfileEntry、PackSection |
| `store.py` | MemoryEngine 抽象：store/fetch/forget/list；（可 SQLite 先） |
| `scrub.py` | ScrubbingEngine：写前 secrets/PII |
| `pack.py` | HolisticRecall + token budget + 分节优先级 + trim from end |
| `inject.py` | **ephemeral** 注入（system/开发者消息）；**禁止**改写 user query 再入库 |
| `lifecycle.py` | pre_turn / post_turn / compaction hooks；稳定 turn index |
| `prefetch.py` | 短 TTL 缓存 pack；live turn 不阻塞远程 I/O |
| `tools.py` | `memory` recall/fetch/learn/forget；host stamp + confine |
| `jobs.py` | BackgroundJob：consolidate/belief 或自研 Dreaming |
| `persona.py` | 加载/编辑 SOUL·IDENTITY·ROLE（或等价）；与 Profile 分栏 |
| `profile.py` | **自研** 常驻画像 +（可选）general/situational 两车道 — OpenHuman 无现成模块 |
| `space.py` | **自研** 生活域隔离 — 可对标 layout root / namespace |
| `tui_panel.py` | Learnings/Profile 可编辑；对标 Memory UI views |

**明确不要做的 vibecoding：**

- 把 pack markdown 拼进 `messages[-1].content` 再交给现有 `memory.add(query)`  
- 用 `self_learning` 开关冒充用户画像  
- 把 explore Facet 枚举当成偏好类目写死进 Profile  
- Fork / 拷贝 `vendor/tinymemory` Rust 进 Python 树

---

## 8. 给用户看的摘要

1. OpenHuman 记忆 = **Host 绑生命周期** + **TinyMemory 引擎/召回**；聊天记录另存，不是 memory。  
2. 每轮有一个 **token 预算 memory pack**（Learnings/信念、Brain、本 agent 历史、可选 team）。  
3. Pack 用 `<memory-context>` **临时**塞进模型请求，**绝不写进聊天记录**。  
4. 「越用越懂」主要靠 **Learnings**（偏好/事实/流程/纠正）+ 引擎 **belief 巩固**，不是堆原文。  
5. 助手性格在 **SOUL/IDENTITY/ROLE** 文件里，和用户记忆分开。  
6. 模型不能自己指定「写到谁的记忆」：host 盖章 namespace，并限制可读范围。  
7. 写入前会 **去掉密钥和个人标识**；删聊天会排队真正忘掉对应记忆。  
8. Live 对话 **不等** 远程记忆返回；没缓存就本轮无 pack，需要时再显式 recall。  
9. 源码里 **没有** 名叫 Dreaming / 两车道偏好 / tool critical-pin 的现成模块——那些是我们生活助手方案的加厚，不是照搬点。  
10. LightAgent 当前把记忆拼进用户提问再存储，和 OpenHuman **相反**，自实现时这条必须先改掉。  
11. 我们按同一思路在 `local/memory/` 自研，复用已有 Admission/Promotion，不拷贝 OpenHuman/TinyMemory 代码。

---

## 附录 A. 最关键源码文件（精读清单）

1. `crates/openhuman-core/src/memory/README.md`  
2. `docs/specs/memory-v2.md`  
3. `vendor/tinymemory/docs/specs/agent-memory.md`  
4. `vendor/tinymemory/crates/tinymemory-tools/src/lifecycle/mod.rs`  
5. `vendor/tinymemory/crates/tinymemory-tools/src/lifecycle/types.rs`  
6. `vendor/tinymemory/crates/tinymemory-tools/src/recall/{types,render,gather}.rs`  
7. `crates/openhuman-core/src/memory/lifecycle/hooks.rs`  
8. `crates/openhuman-core/src/memory/lifecycle/prefetch.rs`  
9. `crates/openhuman-core/src/agent/tinyagents/middleware/memory_pack.rs`  
10. `crates/openhuman-core/src/agent/session_host/runtime_session/memory_ingest.rs`  
11. `crates/openhuman-core/src/memory/tools.rs`  
12. `crates/openhuman-core/src/memory/guard.rs`  
13. `vendor/tinymemory/crates/tinymemory-api/src/item/mod.rs`  
14. `vendor/tinymemory/crates/tinymemory-api/src/consolidate/mod.rs`  
15. `gitbooks/features/personalization.md`

## 附录 B. 文档 vs 源码差异速查

| 点 | 说明 |
| --- | --- |
| personalization.md 写 ROLE.md | 渲染路径对非 orchestrator **默认跳过 ROLE.md** |
| 早期调研「两车道/Dreaming/tool_memory」 | **文档产品愿景/跨项目类比**，非本 commit 源码模块 |
| `LEARN_STATUS` 常量 vs memory-tools「queued」文案 | 实现与文档措辞需以 README queued 语义做产品对齐 |
| Facet 一词多义 | API=元数据浏览；生活助手文档里的「facet」是自研偏好面，勿混用 |
