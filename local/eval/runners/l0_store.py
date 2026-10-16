"""L0 store probes — no API calls.

Usage (repo root):
  PYTHONPATH=. /workspace/la-venv/bin/python -m local.eval.runners.l0_store
  PYTHONPATH=. /workspace/la-venv/bin/python -m local.eval.runners.l0_store --tier l3
"""
from __future__ import annotations

import argparse
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
    dispatch_store_action,
    fresh_workspace,
    merge_status,
    redact,
    run_invariants,
    run_store_checks,
    write_report,
)


def run_case(case: dict) -> CaseResult:
    t0 = time.time()
    ws = fresh_workspace(prefix=f"la_eval_{case['id']}_")
    try:
        bind_workspace(ws)
        bag = apply_setup(ws, case.get("setup"))
        # snapshot steps if goal exists (for unchanged checks)
        from local.goals.store import get_active_goal

        g = get_active_goal(ws, SPACE_ID)
        if g is not None:
            bag.setdefault("steps_before", [s.status for s in g.steps])
            bag.setdefault("goal_id", g.goal_id)
        bag = dispatch_store_action(ws, case, bag)
        last = bag.get("last_text") or ""
        st_status, st_msg = run_store_checks(ws, case, bag, last)
        inv_status, inv_msg = run_invariants(ws, case, reply="")
        status, detail = merge_status((st_status, st_msg), (inv_status, inv_msg))
        return CaseResult(
            id=case["id"],
            dim=case.get("dim", ""),
            tier=case.get("tier", ""),
            title=case.get("title", ""),
            mode="store",
            bar=str(case.get("bar") or ""),
            status=status,
            detail=redact(detail),
            elapsed_ms=int((time.time() - t0) * 1000),
        )
    except Exception as exc:
        return CaseResult(
            id=case.get("id", "?"),
            dim=case.get("dim", ""),
            tier=case.get("tier", ""),
            title=case.get("title", ""),
            mode="store",
            bar=str(case.get("bar") or ""),
            status="ERROR",
            detail=redact(f"{exc}\n{traceback.format_exc()[-400:]}"),
            elapsed_ms=int((time.time() - t0) * 1000),
        )
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L0 store eval (no API)")
    parser.add_argument("--tier", default="all", help="l2 | l3 | jd | all (store cases only)")
    parser.add_argument("--file", default="", help="optional cases yaml stem, e.g. jd_bar")
    parser.add_argument("--bar", default="", help="optional A|B|C|D|E filter")
    args = parser.parse_args(argv)

    cases = []
    if args.file:
        raw = load_cases_file(args.file, tier=None if args.tier == "all" else args.tier, bar=args.bar or None)
        cases = [c for c in raw if c.get("mode") == "store"]
    else:
        tiers = ["l2", "l3", "jd"] if args.tier == "all" else [args.tier]
        for tier in tiers:
            for case in cases_for_tier(tier):
                if case.get("mode") != "store":
                    continue
                if args.bar and str(case.get("bar") or "").upper() != args.bar.upper():
                    continue
                cases.append(case)

    results = [run_case(c) for c in cases]
    if args.file in ("life_heuristics", "life_heuristics.yaml"):
        report_name = "life_heuristics"
    elif args.file == "jd_bar" or args.tier == "jd":
        report_name = "l0_store_jd"
    else:
        report_name = "l0_store"
    jpath, mpath = write_report(
        report_name,
        results,
        meta={"tier": args.tier, "file": args.file, "bar": args.bar, "mode": "store", "provider": "none"},
    )
    summary = {k: sum(1 for r in results if r.status == k) for k in ("PASS", "PARTIAL", "FAIL", "ERROR")}
    print(f"L0 store done: {summary}")
    print(f"report: {mpath}")
    print(f"json: {jpath}")
    for r in results:
        print(f"  {r.status:7} {r.id}  {r.detail[:100]}")
    return 0 if summary.get("FAIL", 0) == 0 and summary.get("ERROR", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
