#!/usr/bin/env python3
"""Thin sync wrapper around browser-use Agent (same spirit as example/08.browser_use.py).

Does NOT call OpenRouter unless you configure keys. Requires optional dep: browser-use.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys


def ensure_browser_use_provider(llm, provider: str = "openai"):
    if hasattr(llm, "provider"):
        return llm
    try:
        setattr(llm, "provider", provider)
    except Exception:
        object.__setattr__(llm, "provider", provider)
    return llm


async def _run(task: str) -> str:
    try:
        from browser_use import Agent
    except ImportError as e:
        raise SystemExit(
            "browser-use not installed. Install: poetry run pip install browser-use\n"
            "Upstream: https://github.com/browser-use/browser-use"
        ) from e

    # Prefer browser-use's ChatOpenAI if present; else langchain_openai (example/08).
    llm = None
    try:
        from browser_use import ChatOpenAI as BUChat

        llm = BUChat(model=os.getenv("BROWSER_USE_MODEL", "gpt-4.1-mini"))
    except Exception:
        from langchain_openai import ChatOpenAI

        llm = ensure_browser_use_provider(
            ChatOpenAI(
                base_url=os.getenv("OPENAI_BASE_URL"),
                model=os.getenv("BROWSER_USE_MODEL", "gpt-4.1-mini"),
                api_key=os.getenv("OPENAI_API_KEY"),
            )
        )

    agent = Agent(task=task, llm=llm, use_vision=False)
    result = await agent.run()
    final = result.final_result() if hasattr(result, "final_result") else str(result)
    return final or ""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run a browser-use task (optional; needs Chromium + LLM key)")
    p.add_argument("task", help="Natural-language browser task")
    args = p.parse_args(argv)
    print(asyncio.run(_run(args.task)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
