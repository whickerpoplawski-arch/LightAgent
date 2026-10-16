# LightAgent 能力测评（意图 / 拆解 / 工具 / 多轮 / JD 尺子）

分层：L0 库探针 + L2/L3 live + **jd_bar（实习 JD A–E）**。

## 当前供应商

| 项 | 值 |
| --- | --- |
| Provider | `mx`（默认） |
| Base URL | `https://mxzzz.xyz/v1`（`MX_BASE_URL`） |
| Model | `deepseek-v4.1-flash` |
| Effort | `medium`（`LIGHTAGENT_REASONING_EFFORT`） |
| Key | `MX_API_KEY` → `LIGHTAGENT_API_KEY` → `OPENAI_API_KEY`（勿打印） |

推荐：`source local/env_mx.sh` 后再跑 live。额度不敏感时可 `LIGHTAGENT_DAILY_LIMIT=500`。

> 裸 urllib 会被 Cloudflare 1010；必须走 OpenAI SDK / `local.openrouter_config.make_agent`。

## 目录

```
local/eval/
  cases/l2_smoke.yaml      # 8 条冒烟
  cases/l3_core.yaml       # 24 条核心
  cases/jd_bar.yaml        # 34 条 JD A–E 尺子（v1）
  cases/jd_bar_v2.yaml     # 52 条：v1+社区扩面（多约束/飞轮边界/单层Swarm/多store）
  cases/life_heuristics.yaml  # 生活向 27 题：卡 grounded / 别记别搜别改忌口 / 多约束
  runners/l0_store.py      # mode=store
  runners/l2_live_tools.py # mode=live_agent（亦可跑 store）
  reports/                 # md+json + *_latest.*
  schema.md
```

## 怎么跑

仓库根目录，解释器建议 `/workspace/la-venv/bin/python`：

```bash
# L0：全部 store（l2+l3+jd，0 token）
PYTHONPATH=. /workspace/la-venv/bin/python -m local.eval.runners.l0_store --tier all

# 仅 jd_bar 的 store
PYTHONPATH=. /workspace/la-venv/bin/python -m local.eval.runners.l0_store --file jd_bar

# L3 全量（store+live）
source local/env_mx.sh
PYTHONPATH=. /workspace/la-venv/bin/python -m local.eval.runners.l2_live_tools --tier l3

# JD 尺子全量（34：store+live）
PYTHONPATH=. /workspace/la-venv/bin/python -m local.eval.runners.l2_live_tools --file jd_bar --tier all

# JD v2 扩面（52：store+live，effort=medium）
PYTHONPATH=. /workspace/la-venv/bin/python -m local.eval.runners.l2_live_tools --file jd_bar_v2 --tier all

# 单条 / 按 bar
PYTHONPATH=. /workspace/la-venv/bin/python -m local.eval.runners.l2_live_tools --file jd_bar --id JD-A03
PYTHONPATH=. /workspace/la-venv/bin/python -m local.eval.runners.l0_store --file jd_bar --bar D

# 生活启发式（store，0 token；失败即非 0。不是 JD，不上 FACTS/RAGAS；无 live 题）
PYTHONPATH=. python -m local.eval.runners.l0_store --file life_heuristics
```

报告：`local/eval/reports/l0_store_latest.md`、`l2_live_l3_latest.md`、`jd_bar_live_latest.md`。

## JD 标签（bar）

| bar | 含义 |
| --- | --- |
| A | 事实错误 / 遗漏 / 工具 / 指令 / 任务完成 |
| B | Context 飞轮 / 自进化 |
| C | 规划 · Tool-use · 记忆 · Reasoning |
| D | Multi-Agent 编排 |
| E | Long-horizon · 多级存储 · 评测/生产力 |

总评（达标与否）：`local/research/jd_capability_bar_verdict_zh.md`  
调研：`local/research/jd_capability_bar_survey_zh.md`

## 设计依据

- `local/research/agent_capability_eval_design_zh.md`
- `local/research/agent_capability_eval_survey_zh.md`
- `local/research/jd_capability_bar_survey_zh.md`
- `local/research/long_horizon_4day_dialogue_script_zh.md`

## 最近再测（2026-10-15）

- 供应商：MX `https://mxzzz.xyz/v1` · `deepseek-v4.1-flash` · effort=medium  
- `jd_bar_v2`：**52/52 PASS**（报告 `reports/jd_bar_v2_live_latest.md`）  
- 总评仍「JD 不够格」：见 `local/research/jd_capability_bar_verdict_zh.md`  
- 社区扩搜：`jd_bar_community_eval_survey_zh.md` · 生产缺口：`jd_bar_prod_impl_gap_zh.md`
