# 当前供应商（已切换）

- Provider: `openai`（OpenAI 兼容）
- Base: `https://api.scienceedu.me/v1`
- Model: `deepseek-v4.1-flash`
- Effort: `medium`
- Key: `LIGHTAGENT_API_KEY`（Secret 卡片注入，不进聊天）

启动：`./local/run_tui.sh`  
冒烟：2026-10-15 `run_free` →「通了」OK。  
注意：裸 `urllib` 会被 Cloudflare 1010；走 OpenAI SDK / LightAgent 正常。
