# LightAgent 记忆机制验收报告（P0）

> 日期：2026-10-12（America/Martinique）  
> 方案：`local/research/memory_acceptance_plan_zh.md`  
> 执行环境：Cursor 云端 agent `bc-a76480d6`（含 P0 实现）  
> 命令：`python3 -m pytest local/memory/tests -q` → **31 passed** / 4.76s  
> **未**调用 OpenRouter  

## 总评：**P0 PASS**

对照方案 §4：E1–E15 全部 PASS；E16（Dreaming/例程）按非 P0 记为未交付，不计入失败。  
相对「全方位个人生活助手最终态」：P0 画像地基达标；日笔记/Space/Dreaming/主动提醒仍属 P1–P3。

| ID | 能力 | 结果 | 证据要点 |
| --- | --- | --- | --- |
| E1 | Ephemeral pack | **PASS** | pack 只在 system；user 原文不变；store 只收原问；session 会剥 `<memory-context>` |
| E2 | learn 持久化 | **PASS** | 跨进程 CLI learn → 新 ProfileStore / CLI list 可读 |
| E3 | forget 真删 | **PASS** | forget 后跨进程 list 为空；pack 不再含该条 |
| E4 | pin 优先 | **PASS** | 预算 24 token 裁剪后 pin 保留 |
| E5 | general 车道 | **PASS** | 新 session 晚饭问题仍含「小Q」 |
| E6 | situational | **PASS** | 无关主题不含「靠窗」；出差主题才召回 |
| E7 | Persona≠Profile | **PASS** | learn 不改 SOUL.md；人格块无用户学习内容 |
| E8 | host stamp | **PASS** | 工具传入 mallory/bob 仍写入 alice |
| E9 | scrub | **PASS** | 假 sk-/password/私钥拒写；邮箱手机打码 |
| E10 | 敏感确认 | **PASS** | 过敏/月薪未 confirm 不进 pack |
| E11 | unavailable | **PASS** | store 失败 → unavailable notice，禁止「什么都不记得」话术 |
| E12 | 工具面 | **PASS** | learn/forget/recall/pin/edit/list 均注册 |
| E13 | CLI/TUI | **PASS** | CLI 读写删；Textual MemoryApp 可学可忘 |
| E14 | 免费额度 | **PASS** | 31 项离线；FREE_MODELS 全 `:free`；付费模型被拒 |
| E15 | self_learning 隔离 | **PASS** | reflection 不进 profile |
| E16 | Dreaming/例程 | **未交付** | consolidate 仅为 queued stub（符合 P0） |

## 与预期能力的判断

1. **达到 P0 预期**：越用越懂的地基（可编辑画像、两车道、ephemeral pack、安全写入）已按 OpenHuman 不变量落地，且用自动化用例钉死，不是口头宣称。  
2. **未达最终态**（预期内）：无真正巩固、无 Space 隔离产品化、无主动例程/提醒、无跨周情景日笔记闭环。  
3. **本地同步**：云端 tarball 在对话里被拆段截断，箱内 `/workspace/LightAgent` 尚需补齐 `local/memory/` 源码；验收结论以云端绿测为准。

## 建议下一步
- 把 P0 源码可靠同步回 `/workspace/LightAgent` 后本地复跑 `pytest local/memory/tests -q`  
- 再开 P1：日笔记 + pack 完整化 + Space 隔离  
