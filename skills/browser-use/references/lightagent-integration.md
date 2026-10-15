# LightAgent ↔ browser-use

Source of truth for the in-repo pattern: `example/08.browser_use.py`.

- Import: `from browser_use import Agent`
- LLM: `langchain_openai.ChatOpenAI` with `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `BROWSER_USE_MODEL`
- Helper: `ensure_browser_use_provider(llm)` sets `llm.provider` for browser-use 0.11+
- Tool surface when registered: `browser_data_fetcher(task_description: str)`
- Prefer `web_search` / `web_fetch` (in `local/tools/web.py`) before escalating to browser-use

Upstream: https://github.com/browser-use/browser-use
