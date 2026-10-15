# LightAgent 记忆机制验收方案（P0）

> 对照：`p0_memory_impl_plan_zh.md` + OpenHuman 不变量  
> 定位：长久日用个人生活助手的 **P0 画像地基**  
> 原则：能离线的全离线；涉及 LLM 的用例可 mock，真连 OpenRouter 仅作可选冒烟且必须 `:free`

---

## 1. 预期能力（验收尺子）

| ID | 预期能力 | 优先级 | 说明 |
| --- | --- | --- | --- |
| E1 | Ephemeral pack | P0 必须 | pack 进 system/instruction，**不**写入用户消息 / transcript store |
| E2 | learn 持久化 | P0 必须 | CLI/tool learn 后跨进程仍在 |
| E3 | forget 真删 | P0 必须 | forget 后 list/pack 不再出现 |
| E4 | pin 优先 | P0 必须 | 预算裁剪时 pin/veto 保留 |
| E5 | general 车道 | P0 必须 | 新 session 仍注入 general |
| E6 | situational 车道 | P0 必须 | 仅主题相关时进入 pack |
| E7 | Persona ≠ Profile | P0 必须 | persona 文件与 profile store 分离 |
| E8 | host stamp | P0 必须 | tool 无法改写到他人 user_id/namespace |
| E9 | scrub | P0 必须 | 假密钥拒写；邮箱/电话脱敏或拒写 |
| E10 | 敏感待确认 | P0 必须 | 健康/薪资类未 confirm 不进 pack |
| E11 | unavailable ≠ 失忆 | P0 必须 | store 失败时 notice，不说「什么都不记得」 |
| E12 | 工具面齐全 | P0 必须 | learn/forget/recall/pin/edit/list 可调用 |
| E13 | 可编辑入口 | P0 必须 | CLI 与/或 TUI 记忆面板能列出编辑 |
| E14 | 免费额度安全 | P0 必须 | 单测零外网；不破坏 run_free |
| E15 | self_learning 隔离 | P0 必须 | agent reflection 不写入 User Profile |
| E16 | Dreaming/例程 | 非 P0 | 本轮不验收通过；标「未交付」即可 |

---

## 2. 测试层次

### L0 静态/结构
- `local/memory/`、`local/persona/` 存在；README 写明不变量
- 导入不拉 OpenRouter

### L1 单元（pytest，离线）
覆盖 store/scrub/pack/inject/host；对应 E1–E11、E15

### L2 集成（离线 mock LLM）
- 构造一轮：learn → 新 LightAgent/run 路径 → 检查发给模型的 messages：system 含 pack，user 为原文
- 确认 session/history 持久化内容不含 `<memory-context>` / pack 原文

### L3 CLI / TUI 冒烟（离线）
- `python -m local.memory.cli learn/list/forget/pin`
- TUI 记忆 tab 可 import / 或 `tui_panel` 可启动（能起就算，不强制截图）

### L4 可选真模型（`:free`，可跳过）
- 一句「记住我叫小Q」→ 下轮问「我叫什么」有记忆痕迹  
- **额度门控**：失败不挡 P0 结论

---

## 3. 用例脚本（执行清单）

### A. 自动化（必须）
```bash
cd <repo>
python -m pytest local/memory/tests -q
# 若有额外验收脚本：
python -m local.memory.tests.acceptance_runner   # 若无则本方案下新建
```

### B. 手工/脚本断言（必须）
1. **E1 注入形态**：调用 inject/pack API，断言返回的 system 增量含记忆、user 字符串不变；再 store 后读回无 pack  
2. **E2/E3**：learn → 新 Store 实例 list 有；forget → 无  
3. **E5/E6**：写入 general + 无关 situational；新 session pack 只有 general；相关 query 才带 situational  
4. **E4**：塞满超预算 + 一条 pin；裁剪后 pin 仍在  
5. **E8**：tool 带异 user_id 被 stamp 覆盖或拒绝  
6. **E9/E10**：`sk-`/`api_key=` 拒写；含「过敏」未 confirm 不进 pack  
7. **E11**：人为关掉 DB/坏路径 → pack 为 unavailable notice  
8. **E12**：tools 注册表含 memory_*  
9. **E15**：触发/模拟 self_learning 输出，断言 profile store 行数不变  

### C. 回归
- 上游 `pytest`（或项目惯用单测）不因 P0 大面积失败  
- `local/openrouter_config.py` 仍只允许 `:free`

---

## 4. 通过标准

| 等级 | 条件 |
| --- | --- |
| **达标（P0 PASS）** | E1–E15 全部 PASS；L1 全绿；L2 至少 E1 集成断言通过 |
| **基本可用（PARTIAL）** | E1–E3、E7、E9、E12、E14 PASS，其余有缺口但有文档 |
| **未达标（FAIL）** | E1 失败（仍把 pack 拼进用户提问并 store），或无持久化，或单测大量红 |

P0 **不要求** E16。相对「全方位生活助手最终态」，本轮只判定 **P0 地基是否达到预期**，并列出距最终态缺口。

---

## 5. 输出物
1. 本方案文档  
2. 验收报告：`local/research/memory_acceptance_report_zh.md`（逐条 E* 结果 + 证据 + 总评）  
3. 若缺自动化用例，补 `local/memory/tests/test_acceptance_invariants.py`
