# P0 实现 Plan：用户画像记忆地基（LightAgent 二开）

> 定位：全方位个人生活助手（长久日用）  
> 实现策略：**按 OpenHuman 思路自研**，不照搬代码；落在 `local/`，复用内核 Admission/Promotion/Protocol  
> 依据：`personal_life_assistant_memory_zh.md` + `openhuman_memory_source_notes_zh.md`  
> 日期：2026-10-12 · 免费额度约束：实现与单测**不要**默认调用 OpenRouter

---

## 0. 目标与非目标

### 目标（P0 做完应有）
1. **可编辑 User Profile**（结构化偏好/事实：identity、style、veto、goal、tooling 等 facets）
2. **learn / forget / pin / edit** API + 对应 agent tools（或 hook 入口）
3. **每轮 memory pack**：token 预算内组装；**ephemeral 注入**当次请求，**绝不**拼进用户提问再 `store`
4. **两车道偏好**：`general` 常驻（session/system 侧）；`situational` 按主题相似度每轮召回
5. **写前 scrub**（密钥/明显 PII 模式）；敏感类可标 `needs_confirm`
6. **TUI 可编辑入口**（记忆/画像面板：列表、编辑、forget、pin）——若本轮时间紧，至少 CLI/`local` API + 最小 Textual 面板
7. **复用**现有 `MemoryPolicy` / Admission / Promotion 门闩思路；Profile 持久化用本地 SQLite 或 JSONL（`local/memory/store/`）

### 非目标（P0 不做）
- Dreaming / 全量实体图 / provenance 产品化（P2）
- Routines 主动提醒（P3）
- 照搬 OpenHuman/TinyMemory/CortexDB
- 默认 ToT / 多 Agent
- 改坏现有 OpenRouter `run_free` 额度逻辑

---

## 1. 必须对齐的不变量（来自 OpenHuman 源码精读）

1. Pack **永不写回**聊天 / transcript  
2. Persona（助手是谁）≠ User Profile（用户是谁）——分文件/分 store  
3. 写入 namespace / user_id 由 **host stamp**，模型参数改不了权限边界  
4. Live turn：**优先用缓存 pack**；不要为召回阻塞整轮（显式 recall tool 可同步）  
5. 拒绝/不可用 ≠「我什么都不记得」——要有 unavailable notice  
6. 写入一律 scrub  
7. Belief/consolidate 后台化（P0 可只留 job stub / 队列接口，真正巩固可空实现）  
8. Pack 排除已在 prompt 窗口里的原文，避免重复污染 cache  

**对照现状必改**：`core._add_memory_context`（或等价路径）把检索拼进用户提问并整句 store —— P0 必须改为 ephemeral pack 注入，且**不得**把 pack 内容当作用户消息持久化。

---

## 2. 建议目录（自研）

```
local/memory/
  __init__.py
  types.py          # Learning, PreferenceLane, Facet, MemoryPack, ScrubResult
  scrub.py          # secrets/PII 规则
  store.py          # SQLite/JSONL：learnings + profile facets
  pack.py           # 预算组装、优先级、裁剪
  inject.py         # ephemeral 注入适配 LightAgent（不改用户消息持久化）
  tools.py          # learn / forget / recall / pin 工具函数
  host.py           # stamp user_id/session、confine reach
  tui_panel.py      # 或对接现有 TUI 的记忆面板
  tests/            # 纯本地单测，无网络
```

Persona 文件建议：`local/persona/SOUL.md`（可空模板），与 profile store 分离。

---

## 3. 接入点（假设，实现时自行核实）

- 对话入口：`local/` 下现有 TUI / `run_free` / agent 构造处  
- 内核记忆：搜索 `_add_memory_context`、`MemoryProtocol`、`self_learning` —— **Profile ≠ self_learning**  
- 工具注册：与 `local/tools/web.py` 同级，把 `memory_learn` / `memory_forget` / `memory_recall` 挂进 agent tools 列表  
- 配置：`local/openrouter_config.py` 保持 free-only；记忆抽取若需 LLM，必须走 `run_free` 且可关闭（P0 默认规则/显式 learn，少自动抽取）

---

## 4. 验收标准

- [ ] 单测：learn → pack 含该条；forget 后消失；pin 优先生效；scrub 拒写假密钥  
- [ ] 集成：一轮对话里 pack 出现在**模型请求的 ephemeral/system 侧**，会话历史里**没有** pack 原文被当成 user  
- [ ] general 偏好在新 session 仍在；situational 仅相关主题召回  
- [ ] TUI 或 CLI 能列出/编辑/删除一条 learning  
- [ ] `pytest`（或仓库现有测试命令）对 `local/memory/tests` 全绿；**不**消耗 OpenRouter  
- [ ] 文档：`local/memory/README.md` 说明用法与不变量  

---

## 5. 实现顺序

1. types + store + scrub + 单测  
2. pack + inject（先修「拼进用户提问」路径）  
3. tools learn/forget/recall/pin + host stamp  
4. 挂到 agent / TUI  
5. README + 冒烟脚本（可 mock LLM）  

---

## 6. 约束写给 Cursor 云端

- 在 **LightAgent** 仓库实现；优先新增 `local/memory/**`，尽量少改上游内核；若必须改 `_add_memory_context`，改动要小、可回滚，并注释为何对齐 ephemeral pack  
- 参考附件中的调研笔记，**参考思路不抄 Rust/CortexDB**  
- 中文注释可适度；用户可见 README 用中文  
- 不要提交真实 API key；不要在测试里打外网  
