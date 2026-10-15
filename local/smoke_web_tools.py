"""Smoke-test web_search / web_fetch without OpenRouter.

Usage (from repo root):
  PYTHONPATH=. poetry run python -m local.smoke_web_tools
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    from local.tui.tools import TOOLS
    from local.tools.web import web_fetch, web_search

    names = [
        (t.tool_info.get("tool_name") if getattr(t, "tool_info", None) else t.__name__)
        for t in TOOLS
    ]
    assert "web_search" in names and "web_fetch" in names, names
    assert web_search in TOOLS and web_fetch in TOOLS

    # SSRF should fail closed
    blocked = json.loads(web_fetch("http://127.0.0.1/"))
    assert "error" in blocked and "SSRF" in blocked["error"], blocked
    print("ssrf_block_ok:", blocked["error"][:80])

    search_raw = web_search("LightAgent github")
    search = json.loads(search_raw)
    assert not search.get("error"), search
    assert search.get("results"), search
    assert any(r.get("url") for r in search["results"]), search
    print(
        "web_search_ok:",
        f"provider={search.get('provider')} count={search.get('count')} "
        f"first={search['results'][0].get('title', '')[:60]!r}",
    )

    fetch_raw = web_fetch("https://example.com")
    fetch = json.loads(fetch_raw)
    assert not fetch.get("error"), fetch
    text = fetch.get("text") or ""
    assert text.strip(), fetch
    assert "Example Domain" in text or "example" in text.lower(), text[:200]
    print(
        "web_fetch_ok:",
        f"status={fetch.get('status_code')} chars={fetch.get('chars')} "
        f"preview={text[:80]!r}",
    )
    print("SMOKE_PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("SMOKE_FAIL:", e, file=sys.stderr)
        raise
