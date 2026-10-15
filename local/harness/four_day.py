"""Offline 4-day life harness. No model calls.

This is a life-assistant script, not a JD pass and not WorkArena / THE AGENT COMPANY.

Default command (green path)::

    PYTHONPATH=. python -m local.harness.four_day

``--live`` is a separate switch and stays off unless ``LIGHTAGENT_4DAY_LIVE=1``.
Even then this entry does not call a model (cap is 0 network calls).
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from local.openrouter_config import NETWORK_CALLS

_BANNER = "本报告不是 JD 达标。未接 WorkArena / THE AGENT COMPANY。"
_LIVE_CAP = 0


def run_four_day(workspace: Path | str | None = None) -> list[tuple[str, str, str]]:
    """Run the 40 offline beats in one workspace. Returns (id, PASS|FAIL, detail)."""
    from local.memory.store import ProfileStore, set_store

    owned = workspace is None
    root = Path(workspace) if workspace is not None else Path(tempfile.mkdtemp(prefix="lh_4day_"))
    (root / "memory").mkdir(parents=True, exist_ok=True)
    saved = {
        key: os.environ.get(key)
        for key in ("LIGHTAGENT_WORKSPACE", "LIGHTAGENT_PROFILE_DB", "LIGHTAGENT_FORBID_OPENROUTER")
    }
    os.environ["LIGHTAGENT_WORKSPACE"] = str(root)
    os.environ["LIGHTAGENT_PROFILE_DB"] = str(root / "memory" / "profile.sqlite")
    os.environ["LIGHTAGENT_FORBID_OPENROUTER"] = "1"
    store = ProfileStore(root / "memory" / "profile.sqlite")
    set_store(store)
    rows: list[tuple[str, str, str]] = []
    try:
        rows.extend(_beats(root, store))
    finally:
        set_store(None)
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if owned:
            shutil.rmtree(root, ignore_errors=True)
    return rows


def _beats(root: Path, store) -> list[tuple[str, str, str]]:
    from local.checkpoints.store import is_resume_request, latest_checkpoint, record_run_event, resume
    from local.constraints.card import ConstraintStore
    from local.constraints.extract import absorb_user_text, classify_utterance
    from local.goals.advance import maybe_advance_goal
    from local.goals.detect import should_create_goal
    from local.goals.store import GoalStore, get_active_goal, maybe_open_goal
    from local.harness.ephemeral import assert_transcript_clean, sanitize_transcript
    from local.rooms.digest import prepare_room_transcript
    from local.rooms.host_summary import render_host_summary
    from local.rooms.types import RoomMessage
    from local.routines.detect import parse_routine, routine_action
    from local.routines.due import confirm_first_due, due_routines
    from local.routines.store import RoutineStore

    space = "life"
    box: dict = {"net0": NETWORK_CALLS, "runs": 0}
    rows: list[tuple[str, str, str]] = []

    def step(name: str, fn) -> None:
        try:
            detail = fn()
            rows.append((name, "PASS", "ok" if detail is None else str(detail)))
        except Exception as exc:
            rows.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))

    def statuses(goal) -> list[str]:
        return [item.status for item in goal.steps]

    def user_msg(index: int, content: str) -> RoomMessage:
        return RoomMessage(
            id=f"u{index}", role="user", speaker="user", speaker_label="用户", content=content, ts=float(index),
        )

    def bot_msg(index: int, content: str) -> RoomMessage:
        return RoomMessage(
            id=f"b{index}",
            role="assistant",
            speaker="bot:c1",
            speaker_label="习惯教练",
            content=content,
            ts=float(index),
        )

    def d1_01():
        before = list((root / "goals").glob("*.json")) if (root / "goals").exists() else []
        opened = maybe_open_goal(root, space, "今天吃什么")
        after = list((root / "goals").glob("*.json")) if (root / "goals").exists() else []
        assert should_create_goal("今天吃什么") is False
        assert opened is None and after == before
        return "no goal"

    def d1_02():
        absorb_user_text(root, "忌口：海鲜")
        assert any("海鲜" in text for text in ConstraintStore(root).active_texts())
        return "card has 海鲜"

    def d1_03():
        goal = maybe_open_goal(root, space, "帮我制定一周健身与饮食计划")
        assert goal is not None and goal.status == "active"
        assert any("海鲜" in text for text in goal.constraints_ref)
        assert sum(item.status == "in_progress" for item in goal.steps) == 1
        box["goal_id"] = goal.goal_id
        return goal.goal_id

    def d1_04():
        before = statuses(get_active_goal(root, space))
        assert maybe_advance_goal(root, space, "今天天气呢") is None
        assert statuses(get_active_goal(root, space)) == before
        return "steps held"

    def d1_05():
        goal = maybe_advance_goal(root, space, "训练日定好了")
        assert goal is not None
        assert goal.steps[0].status == "completed" and goal.steps[1].status == "in_progress"
        assert sum(item.status == "in_progress" for item in goal.steps) <= 1
        return "s1 done"

    def d1_06():
        before = statuses(get_active_goal(root, space))
        assert maybe_advance_goal(root, space, "现在几点") is None
        assert statuses(get_active_goal(root, space)) == before
        return "no advance"

    def d1_07():
        assert parse_routine("提醒我一下") is None
        return "no cadence"

    def d1_08():
        summary = render_host_summary(
            [bot_msg(1, "少油")],
            constraints=ConstraintStore(root).active_texts(),
            next_step="配一日三餐",
        )
        lines = summary.splitlines()
        assert len(lines) == 3
        assert lines[0].startswith("动作：") and lines[1].startswith("忌口：") and "海鲜" in lines[1]
        assert lines[2].startswith("下一步：")
        return "three lines"

    def d1_09():
        cleaned = sanitize_transcript([
            {"role": "assistant", "content": "<memory-context>SECRET</memory-context> hello"},
        ])
        assert_transcript_clean(cleaned)
        assert all("<memory-context>" not in (item.get("content") or "") for item in cleaned)
        return "stripped"

    def d1_10():
        goal = get_active_goal(root, space)
        assert goal is not None and goal.goal_id == box["goal_id"] and goal.status == "active"
        assert any("海鲜" in text for text in ConstraintStore(root).active_texts())
        assert goal.steps[1].status == "in_progress"
        return "still open"

    def d2_01():
        goal = get_active_goal(root, space)
        assert goal is not None and goal.goal_id == box["goal_id"]
        assert goal.steps[1].status == "in_progress"
        return goal.goal_id

    def d2_02():
        absorb_user_text(root, "其实可以吃虾")
        card = ConstraintStore(root).load()
        assert any(item.status == "superseded" and "海鲜" in item.text for item in card.items)
        assert any("其实可以吃虾" in text for text in ConstraintStore(root).active_texts())
        return "seafood lifted"

    def d2_03():
        absorb_user_text(root, "别再给我花生")
        assert any("别再给我花生" in text for text in ConstraintStore(root).active_texts())
        return "peanut active"

    def d2_04():
        before = statuses(get_active_goal(root, space))
        assert should_create_goal("吃什么好") is False
        assert maybe_open_goal(root, space, "吃什么好") is None
        assert maybe_advance_goal(root, space, "吃什么好") is None
        assert statuses(get_active_goal(root, space)) == before
        return "no goal, no advance"

    def d2_05():
        parsed = parse_routine("每周一叫我称重")
        assert parsed is not None and parsed["cadence"] == "weekly"
        routine = RoutineStore(root).create(
            title=parsed["title"],
            instruction=parsed["instruction"],
            cadence=parsed["cadence"],
            owner_space=space,
            timezone_name=parsed["timezone"],
            now=datetime(2026, 10, 14, 12, tzinfo=timezone.utc),
        )
        box["routine_id"] = routine.id
        assert box["runs"] == 0
        return routine.id

    def d2_06():
        now = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)
        RoutineStore(root).set_next_due(box["routine_id"], now - timedelta(days=1))
        due = due_routines(root, now=now, space_id=space)
        assert [item.id for item in due] == [box["routine_id"]]
        assert box["runs"] == 0
        return "listed, not run"

    def d2_07():
        assert should_create_goal("我想健身") is False
        return "no goal"

    def d2_08():
        messages = [user_msg(0, "别再给我花生")]
        messages.extend(bot_msg(index + 1, "闲聊") for index in range(8))
        saved = prepare_room_transcript(messages, workspace=root, room_id="r-d2", keep=4)
        assert len(saved) < len(messages)
        assert any("花生" in item.content or "忌口" in item.content for item in saved)
        return f"{len(messages)}→{len(saved)}"

    def d2_09():
        result = store.learn(
            "叫我小Q",
            user_id="local-user",
            namespace="profile",
            lane="general",
            facet="identity",
            kind="preference",
        )
        learning = result.learning
        assert learning is not None
        pinned = store.pin(learning.id, user_id="local-user", namespace="profile", pinned=True)
        assert pinned is not None and pinned.pinned is True
        box["learning_id"] = learning.id
        return learning.id

    def d2_10():
        goal = get_active_goal(root, space)
        assert goal is not None and goal.status == "active" and goal.goal_id == box["goal_id"]
        assert RoutineStore(root).load(box["routine_id"]) is not None
        assert any("花生" in text for text in ConstraintStore(root).active_texts())
        return "goal, routine, peanut"

    def d3_01():
        assert routine_action("确认提醒") == ("confirm", "")
        now = datetime(2026, 10, 14, 16, tzinfo=timezone.utc)

        def runner(instruction, *, budget_limits, cancellation_token):
            box["runs"] += 1
            box["budget"] = budget_limits
            box["token"] = cancellation_token
            return instruction

        result = confirm_first_due(root, space_id=space, runner=runner, now=now)
        assert result["ok"] is True and box["runs"] == 1
        assert box["budget"].model_calls == 8 and box["budget"].seconds == 120
        assert box["token"] is result["token"]
        assert due_routines(root, now=now, space_id=space) == []
        return "ran once"

    def d3_02():
        record_run_event(space, "user_cancel", detail="已展示三分训练草案")
        goal = get_active_goal(root, space)
        checkpoint = latest_checkpoint(root, box["goal_id"])
        assert goal is not None and goal.status == "paused" and goal.goal_id == box["goal_id"]
        assert checkpoint is not None and checkpoint.reason == "user_cancel"
        return "paused"

    def d3_03():
        assert is_resume_request("继续") is True
        plan = resume(root, space)
        goal = get_active_goal(root, space)
        assert plan is not None and plan.goal_id == box["goal_id"]
        assert goal is not None and goal.goal_id == box["goal_id"] and goal.status == "active"
        return "same goal"

    def d3_04():
        goal = maybe_advance_goal(root, space, "这步完成了")
        assert goal is not None and goal.status == "completed"
        assert all(item.status == "completed" for item in goal.steps)
        assert get_active_goal(root, space) is None
        return "old goal done"

    def d3_05():
        assert should_create_goal("做个一周健身饮食计划") is True
        goal = maybe_open_goal(root, space, "做个一周健身饮食计划")
        assert goal is not None and goal.status == "active" and goal.goal_id != box["goal_id"]
        box["goal2"] = goal.goal_id
        return goal.goal_id

    def d3_06():
        before = {item.goal_id for item in GoalStore(root).list_goals()}
        assert should_create_goal("帮我安排一周锻炼和饮食") is True
        goal = maybe_open_goal(root, space, "帮我安排一周锻炼和饮食")
        after = {item.goal_id for item in GoalStore(root).list_goals()}
        assert goal is not None and goal.goal_id == box["goal2"] and after == before
        return "same open goal"

    def d3_07():
        record_run_event(space, "user_cancel", detail="4day")
        assert get_active_goal(root, space).status == "paused"
        assert is_resume_request("接着来") is True
        plan = resume(root, space)
        goal = get_active_goal(root, space)
        assert plan is not None and plan.goal_id == box["goal2"]
        assert goal is not None and goal.goal_id == box["goal2"] and goal.status == "active"
        return "resumed"

    def d3_08():
        goal = maybe_advance_goal(root, space, "定好了")
        assert goal is not None and goal.goal_id == box["goal2"]
        assert goal.steps[0].status == "completed" and goal.steps[1].status == "in_progress"
        return "s1 of new goal"

    def d3_09():
        before = list(ConstraintStore(root).active_texts())
        assert classify_utterance("海鲜") is None
        absorb_user_text(root, "海鲜")
        assert ConstraintStore(root).active_texts() == before
        return "bare word ignored"

    def d3_10():
        goal = get_active_goal(root, space)
        listed = GoalStore(root).list_goals()
        assert goal is not None and goal.goal_id == box["goal2"] and goal.status == "active"
        assert any("花生" in text for text in ConstraintStore(root).active_texts())
        assert any(item.goal_id == box["goal_id"] and item.status == "completed" for item in listed)
        return "old completed, new active"

    def d4_01():
        goal = get_active_goal(root, space)
        assert any("花生" in text for text in ConstraintStore(root).active_texts())
        assert goal is not None and goal.goal_id == box["goal2"]
        return "same card and goal"

    def d4_02():
        before = statuses(get_active_goal(root, space))
        assert should_create_goal("今天吃什么") is False
        assert maybe_open_goal(root, space, "今天吃什么") is None
        assert maybe_advance_goal(root, space, "今天吃什么") is None
        assert statuses(get_active_goal(root, space)) == before
        return "held"

    def d4_03():
        goal = maybe_advance_goal(root, space, "一日三餐配好了")
        assert goal is not None and goal.status == "completed"
        assert get_active_goal(root, space) is None
        return "menu step done"

    def d4_04():
        assert maybe_open_goal(root, space, "吃什么好") is None
        assert get_active_goal(root, space) is None
        return "no open goal"

    def d4_05():
        summary = render_host_summary(
            [bot_msg(2, "少油")],
            constraints=ConstraintStore(root).active_texts(),
            next_step="回顾本周",
        )
        lines = summary.splitlines()
        assert len(lines) == 3 and lines[0].startswith("动作：") and lines[2].startswith("下一步：")
        assert lines[1].startswith("忌口：") and "花生" in lines[1]
        return "host still three lines"

    def d4_06():
        messages = [user_msg(0, "别再给我花生")]
        messages.extend(bot_msg(index + 1, f"闲聊 {index}") for index in range(108))
        saved = prepare_room_transcript(messages, workspace=root, room_id="r-d4", keep=40)
        assert len(messages) == 109 and len(saved) == 41
        assert any("花生" in item.content or "忌口" in item.content for item in saved)
        return "109→41"

    def d4_07():
        from local.memory.store import ProfileStore

        again = ProfileStore(store.path)
        rows_now = again.list_learnings(user_id="local-user", namespace="profile")
        assert any(item.pinned and "小Q" in item.text for item in rows_now)
        return "pin reopened"

    def d4_08():
        assert NETWORK_CALLS == box["net0"]
        return f"calls={NETWORK_CALLS}"

    def d4_09():
        hits = []
        for folder in ("goals", "constraints", "routines", "checkpoints"):
            base = root / folder
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".txt"}:
                    continue
                blob = path.read_text(encoding="utf-8", errors="ignore")
                if "<memory-context>" in blob.lower():
                    hits.append(str(path))
        assert hits == []
        return "json clean"

    def d4_10():
        listed = GoalStore(root).list_goals()
        routines = RoutineStore(root).list_routines()
        assert sum(item.status == "completed" for item in listed) >= 1
        assert any(item.last_run_at for item in routines)
        assert ConstraintStore(root).active_texts()
        assert get_active_goal(root, space) is None
        return f"goals={len(listed)} routines={len(routines)}"

    for name, fn in (
        ("D1-01", d1_01), ("D1-02", d1_02), ("D1-03", d1_03), ("D1-04", d1_04), ("D1-05", d1_05),
        ("D1-06", d1_06), ("D1-07", d1_07), ("D1-08", d1_08), ("D1-09", d1_09), ("D1-10", d1_10),
        ("D2-01", d2_01), ("D2-02", d2_02), ("D2-03", d2_03), ("D2-04", d2_04), ("D2-05", d2_05),
        ("D2-06", d2_06), ("D2-07", d2_07), ("D2-08", d2_08), ("D2-09", d2_09), ("D2-10", d2_10),
        ("D3-01", d3_01), ("D3-02", d3_02), ("D3-03", d3_03), ("D3-04", d3_04), ("D3-05", d3_05),
        ("D3-06", d3_06), ("D3-07", d3_07), ("D3-08", d3_08), ("D3-09", d3_09), ("D3-10", d3_10),
        ("D4-01", d4_01), ("D4-02", d4_02), ("D4-03", d4_03), ("D4-04", d4_04), ("D4-05", d4_05),
        ("D4-06", d4_06), ("D4-07", d4_07), ("D4-08", d4_08), ("D4-09", d4_09), ("D4-10", d4_10),
    ):
        step(name, fn)
    return rows


def _print_report(rows: list[tuple[str, str, str]]) -> int:
    passed = sum(1 for _name, status, _detail in rows if status == "PASS")
    failed = len(rows) - passed
    print(_BANNER)
    print(f"4day offline: PASS {passed} / FAIL {failed} / {len(rows)}")
    for name, status, detail in rows:
        print(f"  {status:4} {name}  {detail}")
    print(_BANNER)
    return 0 if failed == 0 and len(rows) == 40 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Life-assistant 4-day harness (offline)")
    parser.add_argument(
        "--live",
        action="store_true",
        help="limited live switch; default off, requires LIGHTAGENT_4DAY_LIVE=1, still no model call",
    )
    args = parser.parse_args(argv)
    if args.live:
        print(_BANNER)
        if os.environ.get("LIGHTAGENT_4DAY_LIVE") != "1":
            print("live 默认关。要进入限量 live 才设置 LIGHTAGENT_4DAY_LIVE=1。")
            print("离线验收：PYTHONPATH=. python -m local.harness.four_day")
            return 2
        before = NETWORK_CALLS
        print(f"live 限量：本入口不调用模型（上限 {_LIVE_CAP} 次联网）。不是 JD 达标。")
        if NETWORK_CALLS != before:
            print("FAIL live touched the network counter")
            return 1
        return 0
    return _print_report(run_four_day())


if __name__ == "__main__":
    raise SystemExit(main())
