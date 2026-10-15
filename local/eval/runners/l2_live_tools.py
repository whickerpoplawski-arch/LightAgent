"""L2/L3 live_agent runner via make_agent + TOOLS (MX / OpenAI-compatible).

Usage:
  source local/env_mx.sh
  PYTHONPATH=. /workspace/la-venv/bin/python -m local.eval.runners.l2_live_tools --tier l2
"""
from __future__ import annotations

import argparse
import os
import shutil
import time
import traceback

from local.eval.runners.common import (
    CaseResult,
    SPACE_ID,
    apply_setup,
    bind_workspace,
    cases_for_tier,
    load_cases_file,
    check_tools,
    fresh_workspace,
    merge_status,
    redact,
    run_invariants,
    run_store_checks,
    tool_names_from_result,
    write_report,
)
from local.eval.runners.l0_store import run_case as run_store_case

LIFE_INSTRUCTIONS = (
    "你是个人生活助手。需要实时天气时调用 get_weather；"
    "需要联网资料时调用 web_search / web_fetch。"
    "闲聊时不要调用工具，也不要无故 memory_learn。"
    "用户有忌口时必须遵守，不要推荐违禁食物。"
)


def _prepare_env_for_live() -> None:
    # Default MX; mx path uses MX_BASE_URL only (openrouter_config).
    os.environ.pop("LIGHTAGENT_FORBID_OPENROUTER", None)
    os.environ["LIGHTAGENT_PROVIDER"] = "mx"
    os.environ.setdefault("MX_BASE_URL", "https://mxzzz.xyz/v1")
    # Drop leftover ScienceEdu / openai base so it cannot override mx.
    os.environ.pop("LIGHTAGENT_BASE_URL", None)
    os.environ.setdefault("LIGHTAGENT_MODEL", "deepseek-v4.1-flash")
    os.environ.setdefault("MX_MODEL", "deepseek-v4.1-flash")
    os.environ.setdefault("LIGHTAGENT_REASONING_EFFORT", "medium")


def _require_key() -> None:
    if not (
        os.environ.get("LIGHTAGENT_API_KEY")
        or os.environ.get("MX_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    ):
        raise RuntimeError("MX_API_KEY / LIGHTAGENT_API_KEY missing — refuse to run live eval")


def run_live_case(case: dict) -> CaseResult:
    t0 = time.time()
    ws = fresh_workspace(prefix=f"la_eval_{case['id']}_")
    try:
        bind_workspace(ws)
        bag = apply_setup(ws, case.get("setup"))
        # product-like: also absorb/open on setup-less turns before agent
        from local.constraints.extract import absorb_user_text
        from local.goals.advance import maybe_advance_goal
        from local.goals.store import maybe_open_goal
        from local.openrouter_config import (
            BASE_URL,
            DEFAULT_MODEL,
            PROVIDER,
            _check_and_count,
            make_agent,
            usage_today,
        )
        from local.tui.tools import TOOLS

        history: list[dict] = []
        all_tools: list[str] = []
        last_reply = ""
        for turn in case.get("turns") or []:
            if turn.get("role") != "user":
                continue
            text = turn.get("text") or ""
            absorb_user_text(ws, text)
            maybe_open_goal(ws, SPACE_ID, text)
            maybe_advance_goal(ws, SPACE_ID, text)
            _check_and_count()
            agent = make_agent(
                model=DEFAULT_MODEL,
                instructions=LIFE_INSTRUCTIONS,
                tree_of_thought=False,
                session_id=f"eval-{case['id']}",
                agent_id="eval-bot",
                space_id=SPACE_ID,
            )
            res = agent.run(
                text,
                tools=TOOLS,
                history=list(history),
                user_id="local-user",
                result_format="object",
                max_retry=4,
            )
            content = getattr(res, "content", None) or getattr(res, "error", None) or str(res)
            last_reply = str(content or "")
            names = tool_names_from_result(res)
            all_tools.extend(names)
            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": last_reply})

        tool_status, tool_msg = check_tools(all_tools, (case.get("expect") or {}).get("tools"))
        st_status, st_msg = run_store_checks(ws, case, bag, (case.get("turns") or [{}])[-1].get("text", ""))
        inv_status, inv_msg = run_invariants(ws, case, reply=last_reply)
        status, detail = merge_status((tool_status, tool_msg), (st_status, st_msg), (inv_status, inv_msg))
        return CaseResult(
            id=case["id"],
            dim=case.get("dim", ""),
            tier=case.get("tier", ""),
            title=case.get("title", ""),
            mode="live_agent",
            bar=str(case.get("bar") or ""),
            status=status,
            detail=redact(detail),
            tools_seen=all_tools,
            reply_snip=redact(last_reply)[:240],
            elapsed_ms=int((time.time() - t0) * 1000),
        )
    except Exception as exc:
        return CaseResult(
            id=case.get("id", "?"),
            dim=case.get("dim", ""),
            tier=case.get("tier", ""),
            title=case.get("title", ""),
            mode="live_agent",
            bar=str(case.get("bar") or ""),
            status="ERROR",
            detail=redact(f"{exc}\n{traceback.format_exc()[-500:]}"),
            elapsed_ms=int((time.time() - t0) * 1000),
        )
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live tool/context eval")
    parser.add_argument("--tier", default="l2", help="l2 | l3 | jd | all")
    parser.add_argument("--file", default="", help="optional cases yaml stem, e.g. jd_bar")
    parser.add_argument("--bar", default="", help="optional A|B|C|D|E filter")
    parser.add_argument("--id", default="", help="run a single case id")
    args = parser.parse_args(argv)

    _prepare_env_for_live()
    _require_key()

    # Re-import config after env prep so module-level PROVIDER matches
    import importlib

    import local.openrouter_config as orc

    importlib.reload(orc)

    from local.openrouter_config import BASE_URL, DAILY_LIMIT, DEFAULT_MODEL, PROVIDER, usage_today

    print(f"live eval provider={PROVIDER} model={DEFAULT_MODEL} base={BASE_URL} used={usage_today()}/{DAILY_LIMIT}")

    cases = []
    if args.file:
        cases = load_cases_file(args.file, tier=None if args.tier == "all" else args.tier, bar=args.bar or None)
    else:
        tiers = ["l2", "l3", "jd"] if args.tier == "all" else [args.tier]
        for tier in tiers:
            for case in cases_for_tier(tier):
                if args.bar and str(case.get("bar") or "").upper() != args.bar.upper():
                    continue
                cases.append(case)
    if args.id:
        cases = [c for c in cases if c.get("id") == args.id]

    if not cases:
        print("no cases matched")
        return 2

    results = []
    for case in cases:
        mode = case.get("mode")
        print(f"→ {case['id']} [{mode}] {case.get('title', '')[:40]} …")
        if mode == "store":
            r = run_store_case(case)
        elif mode == "live_agent":
            r = run_live_case(case)
        else:
            r = CaseResult(
                id=case.get("id", "?"),
                dim=case.get("dim", ""),
                tier=case.get("tier", ""),
                title=case.get("title", ""),
                mode=str(mode),
                bar=str(case.get("bar") or ""),
                status="SKIP",
                detail=f"unknown mode {mode}",
            )
        print(f"  {r.status} tools={r.tools_seen} {r.detail[:120]}")
        results.append(r)

    if args.file in ("jd_bar", "jd_bar_v2") or args.tier == "jd":
        report_name = "jd_bar_v2_live" if args.file == "jd_bar_v2" else "jd_bar_live"
    else:
        report_name = f"l2_live_{args.tier}"
    jpath, mpath = write_report(
        report_name,
        results,
        meta={
            "tier": args.tier,
            "file": args.file,
            "bar": args.bar,
            "provider": PROVIDER,
            "model": DEFAULT_MODEL,
            "base_url": BASE_URL,
            "usage_today": usage_today(),
            "daily_limit": DAILY_LIMIT,
        },
    )
    summary = {k: sum(1 for r in results if r.status == k) for k in ("PASS", "PARTIAL", "FAIL", "ERROR", "SKIP")}
    print(f"live done: {summary}")
    print(f"report: {mpath}")
    print(f"json: {jpath}")
    # connectivity gate: any ERROR on transport is red; PARTIAL ok
    hard = summary.get("FAIL", 0) + summary.get("ERROR", 0)
    return 0 if hard == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
