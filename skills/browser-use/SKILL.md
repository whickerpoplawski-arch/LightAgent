---
name: browser-use
description: Use this skill when the user needs real browser automation — JS-rendered pages, multi-step UI flows, forms, logins, CAPTCHAs-hard sites, file downloads, or anything web_search/web_fetch cannot do with a static HTTP GET. Wraps the open-source browser-use library (https://github.com/browser-use/browser-use) the same way LightAgent example/08.browser_use.py does. Do NOT use this skill for simple search or static page fetch; prefer web_search and web_fetch tools first.
license: MIT-oriented guidance; browser-use itself is MIT (see upstream)
---

# browser-use (real browser agent)

Upstream project: **[browser-use/browser-use](https://github.com/browser-use/browser-use)** — open-source Python library that lets an LLM drive a real Chromium browser (click, type, navigate, extract). Docs: https://docs.browser-use.com · llms.txt: https://docs.browser-use.com/llms.txt

LightAgent already ships a reference integration: `example/08.browser_use.py` (`browser_data_fetcher` tool using `browser_use.Agent` + `langchain_openai.ChatOpenAI`).

## When to activate

Activate this skill **only** if at least one is true:

- Page is JS-rendered / SPA and `web_fetch` returns empty or useless HTML shell
- Task needs clicks, typing, multi-step navigation, menus, modals
- Login / authenticated session / cookie-backed flow
- User explicitly asks for browser automation / Playwright-style control

**Do not** activate for:

- Keyword web search → use tool `web_search`
- Fetch a public static URL → use tool `web_fetch`
- Simple API/JSON endpoints

Those two tools are **first-class LightAgent tools** (`local/tools/web.py`), not skills.

## Cost / free-tier warning

- The **library** is free (MIT). Chromium must be installed.
- The **LLM that steers the browser** is not free unless you point it at a free/local model. Prefer the same OpenRouter `:free` models / local Ollama when possible; avoid paid Browser Use Cloud (`BROWSER_USE_API_KEY`, `ChatBrowserUse`, `Browser(use_cloud=True)`) unless the user opts in.
- Browser loops burn many LLM turns — keep tasks short.

## Install (host env)

```bash
# Python >= 3.11
uv add browser-use
# or: poetry run pip install browser-use
# first run may need: playwright install chromium   (depends on browser-use version)
```

Env (align with `example/08.browser_use.py`):

```bash
export OPENAI_API_KEY=...          # or OpenRouter key
export OPENAI_BASE_URL=https://openrouter.ai/api/v1   # if using OpenRouter
export BROWSER_USE_MODEL=nvidia/nemotron-3-super-120b-a12b:free   # must stay :free if using free guard
```

## How to call (LightAgent pattern)

Pattern from `example/08.browser_use.py`:

1. Build an OpenAI-compatible chat model (`ChatOpenAI` or browser-use's `ChatOpenAI`).
2. For browser-use ≥0.11, ensure `llm.provider` is set (helper `ensure_browser_use_provider` in the example).
3. `agent = browser_use.Agent(task=..., llm=llm, use_vision=False)`
4. `result = await agent.run()` then `result.final_result()`

Optional thin sync wrapper in this skill:

```bash
PYTHONPATH=. poetry run python skills/browser-use/scripts/run_task.py "Open example.com and report the H1"
```

Or register the example's `fetch_data_with_browser` as a LightAgent tool (`tool_name=browser_data_fetcher`) when the session truly needs a browser.

Modern upstream quickstart (library API evolves — prefer current docs):

```python
import asyncio
from browser_use import Agent, ChatOpenAI  # see upstream README for ChatBrowserUse / Browser

async def main():
    llm = ChatOpenAI(model="gpt-4.1-mini")  # swap to your free OpenRouter model id
    agent = Agent(task="Find the star count of browser-use/browser-use", llm=llm)
    history = await agent.run()
    print(history.final_result())

asyncio.run(main())
```

## Decision tree

```
Need public facts from the web?
  ├─ search / snippets     → tool web_search
  ├─ one static URL body   → tool web_fetch
  └─ JS UI / form / login  → activate this skill → browser-use Agent
```

## References

- Upstream README: https://github.com/browser-use/browser-use
- LightAgent example: `example/08.browser_use.py`
- Optional notes: `references/lightagent-integration.md`
