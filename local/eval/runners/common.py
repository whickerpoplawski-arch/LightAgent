"""Shared helpers for LightAgent capability eval runners."""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

EVAL_ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = EVAL_ROOT / "cases"
REPORTS_DIR = EVAL_ROOT / "reports"
SPACE_ID = "eval-life"

_REDACT = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}"
)
_SEAFOOD_REFUSE = ("忌口", "不能", "不要", "别点", "避免", "不建议", "过敏", "海鲜忌", "不推荐海鲜")


@dataclass
class CaseResult:
    id: str
    dim: str
    tier: str
    title: str
    mode: str
    status: str  # PASS | PARTIAL | FAIL | SKIP | ERROR
    bar: str = ""
    detail: str = ""
    tools_seen: list[str] = field(default_factory=list)
    reply_snip: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def redact(text: str | None) -> str:
    raw = "" if text is None else str(text)
    return _REDACT.sub(r"\1=***REDACTED***", raw)


def load_cases(path: Path | str, *, tier: str | None = None, dim: str | None = None, bar: str | None = None) -> list[dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cases = list(data.get("cases") or [])
    out = []
    for case in cases:
        if tier and str(case.get("tier", "")).lower() != tier.lower():
            continue
        if dim and str(case.get("dim", "")).lower() != dim.lower():
            continue
        if bar and str(case.get("bar", "")).upper() != bar.upper():
            continue
        out.append(case)
    return out


def cases_for_tier(tier: str) -> list[dict]:
    """Load all yaml cases filtering by tier (l2|l3|jd|...)."""
    found: list[dict] = []
    for path in sorted(CASES_DIR.glob("*.yaml")):
        found.extend(load_cases(path, tier=tier))
    return found


def load_cases_file(name: str, *, tier: str | None = None, bar: str | None = None) -> list[dict]:
    """Load one file under cases/ by stem or filename."""
    path = Path(name)
    if not path.is_absolute():
        path = CASES_DIR / (name if name.endswith(".yaml") else f"{name}.yaml")
    return load_cases(path, tier=tier, bar=bar)


def fresh_workspace(prefix: str = "la_eval_ws_") -> Path:
    root = Path(tempfile.mkdtemp(prefix=prefix, dir="/tmp"))
    (root / "goals").mkdir(parents=True, exist_ok=True)
    (root / "constraints").mkdir(parents=True, exist_ok=True)
    (root / "routines").mkdir(parents=True, exist_ok=True)
    (root / "checkpoints").mkdir(parents=True, exist_ok=True)
    (root / "memory").mkdir(parents=True, exist_ok=True)
    return root


def bind_workspace(workspace: Path) -> None:
    """Point store + profile db at this workspace; clear ProfileStore singleton."""
    os.environ["LIGHTAGENT_WORKSPACE"] = str(workspace)
    os.environ["LIGHTAGENT_PROFILE_DB"] = str(workspace / "memory" / "profile.sqlite")
    from local.memory.store import ProfileStore, set_store

    set_store(ProfileStore(workspace / "memory" / "profile.sqlite"))


def apply_setup(workspace: Path, setup: list[dict] | None) -> dict[str, Any]:
    """Run declarative setup ops. Returns bag of created ids."""
    bag: dict[str, Any] = {}
    if not setup:
        return bag
    from local.constraints.extract import absorb_user_text
    from local.goals.store import maybe_open_goal
    from local.memory.store import get_store
    from local.routines.detect import parse_routine
    from local.routines.store import RoutineStore

    for step in setup:
        if not isinstance(step, dict):
            continue
        if "absorb" in step:
            absorb_user_text(workspace, str(step["absorb"]))
        elif "open_goal" in step:
            goal = maybe_open_goal(workspace, SPACE_ID, str(step["open_goal"]))
            bag["goal_id"] = getattr(goal, "goal_id", None)
            bag["goal"] = goal
        elif "create_routine" in step:
            text = str(step["create_routine"])
            parsed = parse_routine(text)
            if parsed:
                r = RoutineStore(workspace).create(
                    title=parsed["title"],
                    instruction=parsed["instruction"],
                    cadence=parsed["cadence"],
                    owner_space=SPACE_ID,
                    timezone_name=parsed.get("timezone") or "America/Martinique",
                )
                bag["routine_id"] = r.id
                bag["routine"] = r
        elif "memory_learn_pin" in step:
            store = get_store()
            result = store.learn(
                str(step["memory_learn_pin"]),
                user_id="local-user",
                namespace="profile",
                lane="general",
                facet="identity",
                kind="preference",
                pinned=False,
            )
            lid = getattr(getattr(result, "learning", None), "id", None) or getattr(result, "id", None)
            if lid:
                store.pin(lid, user_id="local-user", namespace="profile", pinned=True)
                bag["learning_id"] = lid
        elif "cancel_goal" in step:
            from local.checkpoints.store import record_run_event
            from local.goals.store import apply_run_event

            apply_run_event(workspace, SPACE_ID, "user_cancel")
            record_run_event(SPACE_ID, "user_cancel", detail="eval")
    return bag


def tool_names_from_result(res: Any) -> list[str]:
    names: list[str] = []
    calls = getattr(res, "tool_calls", None) or []
    for c in calls:
        if isinstance(c, dict):
            name = c.get("name") or c.get("tool_name") or ""
        else:
            name = str(c).split("(", 1)[0]
        if name:
            names.append(str(name))
    return names


def check_tools(seen: list[str], expect_tools: dict | None) -> tuple[str, str]:
    """Return (PASS|PARTIAL|FAIL, detail)."""
    if not expect_tools:
        return "PASS", "no tool expect"
    must = list(expect_tools.get("must") or [])
    forbid = list(expect_tools.get("forbid") or [])
    extra = str(expect_tools.get("extra") or "allow").lower()
    missing = [t for t in must if t not in seen]
    forbidden_hit = [t for t in forbid if t in seen]
    extras = [t for t in seen if t not in must and t not in forbid]
    if missing or forbidden_hit:
        return "FAIL", f"missing={missing} forbidden_hit={forbidden_hit} seen={seen}"
    if extra == "forbid" and extras:
        return "PARTIAL", f"unexpected extras={extras} seen={seen}"
    return "PASS", f"seen={seen}"


def _active_texts(workspace: Path) -> list[str]:
    from local.constraints.card import ConstraintStore

    return ConstraintStore(workspace).active_texts()


def _active_goal(workspace: Path):
    from local.goals.store import get_active_goal

    return get_active_goal(workspace, SPACE_ID)


def run_store_checks(workspace: Path, case: dict, bag: dict[str, Any], last_text: str) -> tuple[str, str]:
    """Execute expect.stores predicates. Returns worst status + joined details."""
    expects = list((case.get("expect") or {}).get("stores") or [])
    if not expects:
        return "PASS", "no store expect"
    statuses: list[str] = []
    details: list[str] = []
    for item in expects:
        if isinstance(item, str):
            name, args = item, {}
        else:
            name = str(item.get("check") or item.get("name") or "")
            args = dict(item.get("args") or {})
        ok, msg = _STORE_CHECKS[name](workspace, case, bag, last_text, args) if name in _STORE_CHECKS else (False, f"unknown check {name}")
        statuses.append("PASS" if ok else "FAIL")
        details.append(f"{name}: {msg}")
    if any(s == "FAIL" for s in statuses):
        return "FAIL", "; ".join(details)
    return "PASS", "; ".join(details)


def run_invariants(workspace: Path, case: dict, reply: str = "") -> tuple[str, str]:
    invs = list((case.get("expect") or {}).get("invariants") or [])
    if not invs:
        return "PASS", "no invariants"
    details = []
    for inv in invs:
        name = inv if isinstance(inv, str) else str(inv.get("name") or "")
        if name == "no_memory_context_leak":
            hits = []
            for path in workspace.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in {".json", ".md", ".txt", ".sqlite"}:
                    # still scan json-like
                    if path.suffix.lower() not in {".json", ".md", ".txt"}:
                        continue
                try:
                    blob = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if "<memory-context>" in blob.lower():
                    hits.append(str(path))
            if hits:
                return "FAIL", f"memory-context in {hits[:5]}"
            details.append("no_memory_context_leak ok")
        elif name == "no_new_goal":
            goal = _active_goal(workspace)
            if goal is not None and goal.source != "eval_seed":
                # allow pre-existing from setup; check count didn't grow past setup
                from local.goals.store import GoalStore

                n = len(GoalStore(workspace).list_goals())
                setup_opened = any("open_goal" in (s or {}) for s in (case.get("setup") or []) if isinstance(s, dict))
                if not setup_opened and n > 0:
                    return "FAIL", f"unexpected goals={n}"
            details.append("no_new_goal ok")
        elif name == "routine_not_run":
            from local.routines.store import RoutineStore

            for r in RoutineStore(workspace).list_routines():
                if r.last_run_at:
                    return "FAIL", f"routine {r.id} ran at {r.last_run_at}"
            details.append("routine_not_run ok")
        elif name == "reply_avoid_seafood_primary":
            soft = _soft_seafood_reply(reply)
            if soft == "FAIL":
                return "PARTIAL", "reply seems to recommend seafood without refuse cue"
            details.append(f"reply_avoid_seafood_primary={soft}")
        else:
            details.append(f"skip unknown invariant {name}")
    return "PASS", "; ".join(details)


def _soft_seafood_reply(reply: str) -> str:
    text = reply or ""
    if "海鲜" not in text:
        return "PASS"
    if any(w in text for w in _SEAFOOD_REFUSE):
        return "PASS"
    # mentions 海鲜 alongside a recommendation tone
    if any(w in text for w in ("推荐", "火锅", "可以试试", "建议", "点个")):
        return "FAIL"
    return "PASS"


def merge_status(*parts: tuple[str, str]) -> tuple[str, str]:
    rank = {"PASS": 0, "PARTIAL": 1, "SKIP": 1, "FAIL": 2, "ERROR": 3}
    worst = "PASS"
    msgs = []
    for status, msg in parts:
        if rank.get(status, 0) > rank.get(worst, 0):
            worst = status
        if msg:
            msgs.append(f"[{status}] {msg}")
    return worst, " | ".join(msgs)


def write_report(name: str, results: list[CaseResult], meta: dict | None = None) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{name}_{stamp}"
    payload = {
        "meta": meta or {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": _summary(results),
        "results": [r.to_dict() for r in results],
    }
    jpath = REPORTS_DIR / f"{base}.json"
    mpath = REPORTS_DIR / f"{base}.md"
    jpath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# Eval report: {name}",
        "",
        f"- generated: {payload['generated_at']}",
        f"- provider: {redact(str((meta or {}).get('provider', '')))}",
        f"- model: {(meta or {}).get('model', '')}",
        f"- summary: {payload['summary']}",
        "",
        "| id | bar | dim | status | detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        detail = redact(r.detail).replace("|", "\\|")[:160]
        lines.append(f"| {r.id} | {r.bar or '-'} | {r.dim} | **{r.status}** | {detail} |")
    mpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # also write latest symlinks-ish copies
    (REPORTS_DIR / f"{name}_latest.json").write_text(jpath.read_text(encoding="utf-8"), encoding="utf-8")
    (REPORTS_DIR / f"{name}_latest.md").write_text(mpath.read_text(encoding="utf-8"), encoding="utf-8")
    return jpath, mpath


def _summary(results: list[CaseResult]) -> dict:
    counts = {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts


# ---- store check implementations ----

def _chk_should_not_create(workspace, case, bag, last_text, args):
    from local.goals.detect import should_create_goal
    from local.goals.store import maybe_open_goal

    text = args.get("text") or last_text
    if should_create_goal(text):
        return False, f"should_create_goal True for {text!r}"
    before = len(list((workspace / "goals").glob("*.json"))) if (workspace / "goals").exists() else 0
    g = maybe_open_goal(workspace, SPACE_ID, text)
    after = len(list((workspace / "goals").glob("*.json")))
    if g is not None and after > before:
        return False, "maybe_open_goal created a file"
    return True, "no goal"


def _chk_should_create(workspace, case, bag, last_text, args):
    from local.goals.detect import should_create_goal

    text = args.get("text") or last_text
    return (should_create_goal(text), f"should_create_goal={should_create_goal(text)}")


def _chk_constraint_contains(workspace, case, bag, last_text, args):
    needle = str(args.get("needle") or "海鲜")
    texts = _active_texts(workspace)
    ok = any(needle in t for t in texts)
    return ok, f"active={texts}"


def _chk_constraint_superseded(workspace, case, bag, last_text, args):
    from local.constraints.card import ConstraintStore

    card = ConstraintStore(workspace).load()
    old = str(args.get("old_needle") or "海鲜")
    active = [i for i in card.items if getattr(i, "status", "") == "active" or not getattr(i, "superseded_by", None)]
    # ConstraintItem may use different fields — fall back to active_texts + any superseded flag
    texts = _active_texts(workspace)
    has_lift = any(any(k in t for k in ("可以吃", "其实可以", "虾")) for t in texts)
    # old seafood remember should not be the sole active if superseded
    from local.constraints.card import active_texts as at

    # Prefer: at least one item marked superseded OR active texts reflect lift
    superseded = [i for i in card.items if getattr(i, "status", "") == "superseded"]
    ok = bool(superseded) or has_lift
    return ok, f"active={texts} superseded_n={len(superseded)}"


def _chk_goal_one_in_progress(workspace, case, bag, last_text, args):
    goal = _active_goal(workspace)
    if goal is None:
        return False, "no active goal"
    n = sum(1 for s in goal.steps if s.status == "in_progress")
    return n == 1, f"in_progress={n} status={goal.status} steps={[s.status for s in goal.steps]}"


def _chk_goal_advanced(workspace, case, bag, last_text, args):
    goal = _active_goal(workspace)
    if goal is None:
        return False, "no active goal"
    if not goal.steps:
        return False, "no steps"
    s1 = goal.steps[0]
    ok = s1.status == "completed"
    if len(goal.steps) > 1:
        ok = ok and goal.steps[1].status == "in_progress"
    n_ip = sum(1 for s in goal.steps if s.status == "in_progress")
    return ok and n_ip <= 1, f"steps={[s.status for s in goal.steps]}"


def _chk_goal_unchanged_steps(workspace, case, bag, last_text, args):
    goal = _active_goal(workspace)
    if goal is None:
        return True, "no goal (ok)"
    before = bag.get("steps_before")
    if before is None:
        return True, "no baseline"
    now = [s.status for s in goal.steps]
    return now == before, f"before={before} now={now}"


def _chk_no_active_goal(workspace, case, bag, last_text, args):
    return _active_goal(workspace) is None, f"goal={_active_goal(workspace)}"


def _chk_parse_routine_none(workspace, case, bag, last_text, args):
    from local.routines.detect import parse_routine

    text = args.get("text") or last_text
    parsed = parse_routine(text)
    return parsed is None, f"parsed={parsed}"


def _chk_parse_routine_weekly(workspace, case, bag, last_text, args):
    from local.routines.detect import parse_routine

    text = args.get("text") or last_text
    parsed = parse_routine(text)
    ok = parsed is not None and parsed.get("cadence") == "weekly"
    return ok, f"parsed={parsed}"


def _chk_classify_none(workspace, case, bag, last_text, args):
    from local.constraints.extract import classify_utterance

    text = args.get("text") or last_text
    kind = classify_utterance(text)
    return kind is None, f"kind={kind}"


def _chk_resume_same_goal(workspace, case, bag, last_text, args):
    from local.checkpoints.store import is_resume_request, resume

    text = args.get("text") or last_text or "继续"
    if not is_resume_request(text):
        return False, f"not resume request: {text!r}"
    plan = resume(workspace, SPACE_ID)
    if plan is None:
        return False, "resume returned None"
    want = bag.get("goal_id")
    ok = want is None or plan.goal_id == want
    return ok, f"plan.goal_id={plan.goal_id} want={want}"


def _chk_goal_paused(workspace, case, bag, last_text, args):
    from local.goals.store import GoalStore

    gid = bag.get("goal_id")
    if not gid:
        g = _active_goal(workspace)
        # after cancel, active may be paused
        from local.goals.store import get_active_goal

        # paused is still "open"
        g = get_active_goal(workspace, SPACE_ID)
        if g is None:
            return False, "no goal"
        return g.status == "paused", f"status={g.status}"
    g = GoalStore(workspace).load(gid)
    if g is None:
        return False, "missing"
    return g.status == "paused", f"status={g.status}"


def _chk_sanitize_clean(workspace, case, bag, last_text, args):
    from local.harness.ephemeral import assert_transcript_clean, sanitize_transcript

    dirty = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "<memory-context>secret</memory-context> hello"},
    ]
    cleaned = sanitize_transcript(dirty)
    try:
        assert_transcript_clean(cleaned)
    except AssertionError as e:
        return False, str(e)
    ok = all("<memory-context>" not in (m.get("content") or "").lower() for m in cleaned)
    return ok, "sanitized"


def _chk_memory_pinned_contains(workspace, case, bag, last_text, args):
    from local.memory.store import get_store

    needle = str(args.get("needle") or "小Q")
    store = get_store()
    rows = store.list_learnings(user_id="local-user", namespace="profile")
    texts = []
    pinned = False
    for row in rows or []:
        text = getattr(row, "text", "") or ""
        is_pin = bool(getattr(row, "pinned", False))
        texts.append(str(text))
        if needle in str(text) and is_pin:
            pinned = True
    return pinned, f"pinned_hit={pinned} texts={texts[:5]}"


def _chk_routine_created_not_run(workspace, case, bag, last_text, args):
    from local.routines.store import RoutineStore

    items = RoutineStore(workspace).list_routines()
    if not items:
        return False, "no routines"
    if any(r.last_run_at for r in items):
        return False, "ran unexpectedly"
    return True, f"n={len(items)}"


_STORE_CHECKS = {
    "should_not_create_goal": _chk_should_not_create,
    "should_create_goal": _chk_should_create,
    "constraint_contains": _chk_constraint_contains,
    "constraint_superseded": _chk_constraint_superseded,
    "goal_one_in_progress": _chk_goal_one_in_progress,
    "goal_advanced": _chk_goal_advanced,
    "goal_unchanged_steps": _chk_goal_unchanged_steps,
    "no_active_goal": _chk_no_active_goal,
    "parse_routine_none": _chk_parse_routine_none,
    "parse_routine_weekly": _chk_parse_routine_weekly,
    "classify_none": _chk_classify_none,
    "resume_same_goal": _chk_resume_same_goal,
    "goal_paused": _chk_goal_paused,
    "sanitize_clean": _chk_sanitize_clean,
    "memory_pinned_contains": _chk_memory_pinned_contains,
    "routine_created_not_run": _chk_routine_created_not_run,
}


def dispatch_store_action(workspace: Path, case: dict, bag: dict[str, Any]) -> dict[str, Any]:
    """Apply the case's store_action using the last user turn text."""
    turns = case.get("turns") or []
    text = ""
    for t in turns:
        if t.get("role") == "user":
            text = t.get("text") or ""
    action = str(case.get("store_action") or "auto")
    from local.constraints.extract import absorb_user_text, classify_utterance
    from local.goals.advance import maybe_advance_goal
    from local.goals.detect import should_create_goal
    from local.goals.store import maybe_open_goal
    from local.routines.detect import parse_routine
    from local.routines.store import RoutineStore

    if action in ("auto", "absorb") and ("忌口" in text or "可以吃" in text or "别再" in text or "忘掉" in text):
        absorb_user_text(workspace, text)
    if action in ("auto", "maybe_open_goal", "detect_goal"):
        if should_create_goal(text):
            g = maybe_open_goal(workspace, SPACE_ID, text)
            if g:
                bag["goal_id"] = g.goal_id
                bag["goal"] = g
    if action in ("auto", "maybe_advance_goal", "advance"):
        g = _active_goal(workspace)
        if g:
            bag["steps_before"] = [s.status for s in g.steps]
        maybe_advance_goal(workspace, SPACE_ID, text)
    if action in ("auto", "parse_routine"):
        parsed = parse_routine(text)
        bag["parsed_routine"] = parsed
        if parsed and case.get("create_if_parsed"):
            r = RoutineStore(workspace).create(
                title=parsed["title"],
                instruction=parsed["instruction"],
                cadence=parsed["cadence"],
                owner_space=SPACE_ID,
                timezone_name=parsed.get("timezone") or "America/Martinique",
            )
            bag["routine_id"] = r.id
    if action == "classify":
        bag["classify"] = classify_utterance(text)
    if action == "cancel":
        from local.checkpoints.store import record_run_event
        from local.goals.store import apply_run_event

        apply_run_event(workspace, SPACE_ID, "user_cancel")
        record_run_event(SPACE_ID, "user_cancel", detail="eval")
    if action == "resume":
        from local.checkpoints.store import resume

        plan = resume(workspace, SPACE_ID)
        bag["resume_plan"] = plan
    if action == "sanitize":
        pass  # check-only
    if action == "confirm_routine":
        from datetime import datetime, timedelta, timezone as tz

        from local.routines.due import confirm_first_due
        from local.routines.store import RoutineStore as RS

        runs = {"n": 0}

        def _runner(instruction, **kwargs):
            runs["n"] += 1
            return {"ok": True, "instruction": instruction}

        for r in RS(workspace).list_routines():
            RS(workspace).set_next_due(r.id, datetime.now(tz.utc) - timedelta(hours=1))
        confirm_first_due(workspace, space_id=SPACE_ID, runner=_runner)
        bag["routine_runs"] = runs["n"]
    bag["last_text"] = text
    return bag


def _chk_routine_ran_once(workspace, case, bag, last_text, args):
    n = bag.get("routine_runs")
    return n == 1, f"routine_runs={n}"


_STORE_CHECKS["routine_ran_once"] = _chk_routine_ran_once


def _eval_room_fixture():
    from local.conversations.models import BotIdentity, ConversationMeta
    from local.rooms.types import GroupRoom

    coach = ConversationMeta(
        id="c1",
        title="习惯教练",
        identity=BotIdentity(
            display_name="习惯教练",
            role_title="习惯教练",
            job_description="陪用户看运动习惯",
            template_id="habit_coach",
        ),
        agent_id="bot-c1",
    )
    diet = ConversationMeta(
        id="d1",
        title="饮食顾问",
        identity=BotIdentity(
            display_name="饮食顾问",
            role_title="饮食顾问",
            job_description="按忌口给配餐建议",
            template_id="nutrition_advisor",
        ),
        agent_id="bot-d1",
    )
    room = GroupRoom(id="r1", title="健康日常", member_bot_ids=["c1", "d1"], created_at=1, updated_at=1)
    return room, [coach, diet]


def _chk_room_plan_reason(workspace, case, bag, last_text, args):
    plan = bag.get("room_plan")
    if plan is None:
        return False, "no room_plan"
    want = str(args.get("reason_prefix") or "")
    reason = str(getattr(plan, "reason", "") or "")
    ok = reason.startswith(want) if want else bool(reason)
    return ok, f"reason={reason} want_prefix={want}"


def _chk_host_summary_has_next(workspace, case, bag, last_text, args):
    text = str(bag.get("host_summary") or "")
    ok = "下一步" in text
    return ok, f"summary={text[:120]!r}"


def _chk_consolidate_job_queued_not_run(workspace, case, bag, last_text, args):
    from local.memory.jobs import run_due
    from local.memory.store import get_store

    store = get_store()
    job_id = bag.get("consolidate_job_id")
    due = run_due(store)
    # stub must return empty list (no real consolidate)
    if due:
        return False, f"run_due unexpectedly processed {due}"
    if not job_id:
        return False, "no job_id enqueued"
    return True, f"queued={job_id} run_due=[] (stub)"


_STORE_CHECKS["room_plan_reason"] = _chk_room_plan_reason
_STORE_CHECKS["host_summary_has_next"] = _chk_host_summary_has_next
_STORE_CHECKS["consolidate_job_queued_not_run"] = _chk_consolidate_job_queued_not_run


def _dispatch_room_and_jobs(workspace, case, bag, text, action):
    if action in ("room_plan", "room_plan_mention"):
        from local.rooms.plan import build_turn_plan

        room, roster = _eval_room_fixture()
        plan = build_turn_plan(text, room, roster)
        bag["room_plan"] = plan
    if action == "host_summary":
        from local.rooms.host_summary import render_host_summary
        from local.rooms.types import RoomMessage

        bubbles = [
            RoomMessage(
                id="m1",
                role="assistant",
                speaker="bot:c1",
                speaker_label="习惯教练",
                content="今晚做一组深蹲即可",
                ts=1.0,
                turn_id="t1",
                kind="chat",
            )
        ]
        bag["host_summary"] = render_host_summary(
            bubbles,
            user_text="今日健身和饮食",
            constraints=["海鲜"],
            next_step="明天再确认训练日",
        )
    if action == "enqueue_consolidate":
        from local.memory.jobs import enqueue
        from local.memory.store import get_store

        store = get_store()
        bag["consolidate_job_id"] = enqueue(store, kind="consolidate", payload={"src": "jd_eval"})


# Monkey-patch dispatch to call extra actions: wrap by extending at end of original function body.
_orig_dispatch = dispatch_store_action


def dispatch_store_action(workspace: Path, case: dict, bag: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
    turns = case.get("turns") or []
    text = ""
    for t in turns:
        if t.get("role") == "user":
            text = t.get("text") or ""
    action = str(case.get("store_action") or "auto")
    bag = _orig_dispatch(workspace, case, bag)
    _dispatch_room_and_jobs(workspace, case, bag, text, action)
    bag["last_text"] = text
    return bag


# --- jd_bar_v2 extra checks ---

def _chk_constraint_contains_all(workspace, case, bag, last_text, args):
    needles = args.get("needles") or []
    if isinstance(needles, str):
        needles = [needles]
    texts = _active_texts(workspace)
    missing = [n for n in needles if not any(str(n) in t for t in texts)]
    return (not missing), f"missing={missing} active={texts}"


def _chk_room_speakers_at_most(workspace, case, bag, last_text, args):
    plan = bag.get("room_plan")
    if plan is None:
        return False, "no room_plan"
    n = len(getattr(plan, "speakers", []) or [])
    cap = int(args.get("max") or 2)
    return n <= cap, f"speakers={n} cap={cap} reason={getattr(plan, 'reason', '')}"


def _chk_digest_no_ephemeral(workspace, case, bag, last_text, args):
    from local.rooms.digest import build_room_digest, strip_ephemeral
    from local.rooms.types import RoomMessage

    msgs = [
        RoomMessage(
            id="m1",
            role="assistant",
            speaker="bot:c1",
            speaker_label="习惯教练",
            content="<memory-context>SECRET_PIN</memory-context>今晚深蹲",
            ts=1.0,
            turn_id="t1",
            kind="chat",
        ),
        RoomMessage(
            id="m2",
            role="user",
            speaker="user",
            speaker_label="用户",
            content="忌口：海鲜",
            ts=2.0,
            turn_id="t1",
            kind="chat",
        ),
    ]
    dig = build_room_digest(msgs)
    bad = "<memory-context>" in dig.lower() or "SECRET_PIN" in dig
    clean = strip_ephemeral(msgs[0].content)
    ok = (not bad) and ("SECRET_PIN" not in clean) and ("深蹲" in dig or "深蹲" in clean)
    return ok, f"digest={dig!r} clean={clean!r}"


def _chk_no_recursive_swarm(workspace, case, bag, last_text, args):
    """Honest capability boundary: Hosted Room never spawns recursive child plans."""
    plan = bag.get("room_plan")
    if plan is None:
        return False, "no room_plan"
    # TurnPlan has no children / subplans by design
    has_children = hasattr(plan, "children") and bool(getattr(plan, "children"))
    has_sub = hasattr(plan, "sub_plans") and bool(getattr(plan, "sub_plans"))
    reason = str(getattr(plan, "reason", "") or "")
    # success = no recursive structure
    ok = (not has_children) and (not has_sub)
    return ok, f"reason={reason} children={has_children} sub_plans={has_sub}"


_STORE_CHECKS["constraint_contains_all"] = _chk_constraint_contains_all
_STORE_CHECKS["room_speakers_at_most"] = _chk_room_speakers_at_most
_STORE_CHECKS["digest_no_ephemeral"] = _chk_digest_no_ephemeral
_STORE_CHECKS["no_recursive_swarm"] = _chk_no_recursive_swarm
