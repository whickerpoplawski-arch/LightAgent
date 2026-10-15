# First-class web tools (not a plugin)

`web_search` and `web_fetch` live here and are imported into `local/tui/tools.py` → `TOOLS`.
OpenRouterBackend / `_merged_tools()` pass them to `LightAgent.run(..., tools=...)`.

| Tool | Default | Optional paid/free-key providers |
|---|---|---|
| `web_search` | **ddgs** (DuckDuckGo, $0, no key) | `TAVILY_API_KEY` → Tavily; else `BRAVE_API_KEY` → Brave |
| `web_fetch` | **httpx** + html2text/trafilatura/readability fallback | SSRF: blocks localhost / private IPs; truncates body |

**Not** packaged as `web_tools` plugin. Do not install them via `plugins_system`.

Browser automation is a separate **Skill**: `skills/browser-use/` → real [browser-use/browser-use](https://github.com/browser-use/browser-use), same spirit as `example/08.browser_use.py`.

## Smoke (0 OpenRouter)

```bash
cd /workspace/LightAgent
uv tool run --from poetry==2.4.1 poetry run pip install ddgs html2text   # once
PYTHONPATH=. uv tool run --from poetry==2.4.1 poetry run python -m local.smoke_web_tools
```

## Env knobs

- `WEB_SEARCH_MAX_RESULTS` (default 5)
- `WEB_FETCH_MAX_CHARS` (default 12000)
- `WEB_FETCH_TIMEOUT` (default 20)
- `TAVILY_API_KEY` / `BRAVE_API_KEY` — optional; only if you have free-tier keys
