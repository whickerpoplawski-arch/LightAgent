"""Mock probe for the six acceptance scenes plus S7–S9. No network."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("LIGHTAGENT_FORBID_OPENROUTER", "1")

from local.checkpoints.store import latest_checkpoint, record_run_event, resume
from local.constraints.card import ConstraintStore, active_texts
from local.constraints.extract import absorb_user_text
from local.goals.advance import maybe_advance_goal
from local.goals.detect import should_create_goal
from local.goals.store import get_active_goal, maybe_open_goal
from local.harness.ephemeral import assert_transcript_clean, clean_persisted_text, sanitize_transcript
from local.openrouter_config import NETWORK_CALLS
from local.rooms.digest import prepare_room_transcript
from local.rooms.host_summary import render_host_summary
from local.rooms.types import RoomMessage
from local.routines.detect import parse_routine
from local.routines.due import confirm_routine
from local.routines.store import RoutineStore
from local.tui.backend import MockBackend, TurnContext


def _user(index: int, content: str) -> RoomMessage:
    return RoomMessage(
        id=f"u{index}", role="user", speaker="user", speaker_label="用户", content=content, ts=index,
    )


def _bot(index: int, content: str) -> RoomMessage:
    return RoomMessage(
        id=f"b{index}", role="assistant", speaker="bot:c1", speaker_label="习惯教练", content=content, ts=index,
    )


def main() -> int:
    rows: list[tuple[str, str, str]] = []
    before = NETWORK_CALLS

    def check(name: str, ok: bool, detail: str) -> None:
        rows.append((name, "PASS" if ok else "FAIL", detail))

    # S1 explicit goal snapshots a remembered diet card.
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        ConstraintStore(root).remember("忌口：海鲜")
        goal = maybe_open_goal(root, "life", "帮我制定一周健身与饮食计划")
        ok = (
            goal is not None
            and any("海鲜" in text for text in goal.constraints_ref)
            and sum(step.status == "in_progress" for step in goal.steps) == 1
        )
        check("S1", ok, f"constraints_ref={None if goal is None else goal.constraints_ref}")

    # S2 short question does not create a goal.
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        before_files = list((root / "goals").glob("*.json")) if (root / "goals").exists() else []
        opened = maybe_open_goal(root, "life", "今天吃什么")
        after = list((root / "goals").glob("*.json")) if (root / "goals").exists() else []
        check("S2", should_create_goal("今天吃什么") is False and opened is None and after == before_files, "no goal file")

    # S3 cancel writes a checkpoint; 继续 keeps the same goal.
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        os.environ["LIGHTAGENT_WORKSPACE"] = str(root)
        goal = maybe_open_goal(root, "life", "帮我制定一周健身与饮食计划")
        record_run_event("life", "user_cancel", detail="已展示三分训练草案")
        paused = get_active_goal(root, "life")
        checkpoint = latest_checkpoint(root, goal.goal_id if goal else "")
        plan = resume(root, "life")
        restored = get_active_goal(root, "life")
        ok = (
            paused is not None and paused.status == "paused" and paused.goal_id == goal.goal_id
            and checkpoint is not None and checkpoint.reason == "user_cancel"
            and plan is not None and plan.goal_id == goal.goal_id and "半执行" in plan.notice
            and restored is not None and restored.goal_id == goal.goal_id
        )
        check("S3", ok, f"goal={None if goal is None else goal.goal_id}")

    # S4 host lines and compact keep the diet sentence. 109 messages → 41.
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        messages = [_user(0, "忌口：海鲜")]
        messages.extend(_bot(index + 1, f"闲聊 {index}") for index in range(108))
        saved = prepare_room_transcript(messages, workspace=root, room_id="r1", keep=40)
        summary = render_host_summary(
            [item for item in saved if item.speaker.startswith("bot:")][:1] or [_bot(1, "少油")],
            constraints=ConstraintStore(root).active_texts(),
            next_step="定训练日",
        )
        ok = (
            len(messages) == 109
            and len(saved) == 41
            and any("海鲜" in item.content for item in saved)
            and summary.splitlines()[0].startswith("动作：")
            and "忌口：" in summary
            and summary.splitlines()[-1].startswith("下一步：")
        )
        check("S4", ok, f"{len(messages)}→{len(saved)}")

    # S5 create does not run a model; confirm passes the budget and token.
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        calls = {"n": 0}

        def runner(instruction, *, budget_limits, cancellation_token):
            calls["n"] += 1
            calls["budget"] = budget_limits
            calls["token"] = cancellation_token
            return instruction

        parsed = parse_routine("每周一提醒我称重")
        routine = RoutineStore(root).create(
            title=parsed["title"],
            instruction=parsed["instruction"],
            cadence=parsed["cadence"],
            owner_space="life",
            timezone_name=parsed["timezone"],
            now=datetime(2026, 10, 14, 12, tzinfo=timezone.utc),
        )
        assert calls["n"] == 0
        RoutineStore(root).set_next_due(routine.id, datetime(2026, 10, 1, tzinfo=timezone.utc))
        result = confirm_routine(root, routine.id, runner=runner, now=datetime(2026, 10, 14, 15, tzinfo=timezone.utc))
        ok = (
            parsed is not None
            and calls["n"] == 1
            and calls["budget"].model_calls == 8
            and calls["budget"].seconds == 120
            and calls["token"] is result["token"]
        )
        check("S5", ok, f"runner_calls={calls['n']}")

    # S6 persisted transcript has no memory-context tag.
    with tempfile.TemporaryDirectory() as raw:
        backend = MockBackend(delay=0)
        turn = TurnContext(session_id="s", space_id="life", collaboration_enabled=False)
        reply = backend.chat([], "帮我制定一周健身与饮食计划", turn=turn)
        history = sanitize_transcript([
            {"role": "user", "content": clean_persisted_text("帮我制定一周健身与饮食计划 <memory-context>secret</memory-context>")},
            {"role": "assistant", "content": clean_persisted_text(reply.content)},
        ])
        try:
            assert_transcript_clean(history)
            ok = True
        except AssertionError:
            ok = False
        check("S6", ok, "transcript clean")

    # S7 1:1 absorb then open goal.
    net = NETWORK_CALLS
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        absorb_user_text(root, "忌口：海鲜")
        goal = maybe_open_goal(root, "life", "帮我制定一周健身与饮食计划")
        ok = goal is not None and any("海鲜" in text for text in goal.constraints_ref) and NETWORK_CALLS == net
        check("S7", ok, f"ref={None if goal is None else goal.constraints_ref}")

    # S8 spoken step advance.
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        maybe_open_goal(root, "life", "帮我制定一周健身与饮食计划")
        updated = maybe_advance_goal(root, "life", "训练日定好了")
        by_id = {} if updated is None else {step.id: step.status for step in updated.steps}
        ok = by_id.get("s1") == "completed" and by_id.get("s2") == "in_progress"
        check("S8", ok, str(by_id))

    # S9 wider phrases, still no model.
    net = NETWORK_CALLS
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        absorb_user_text(root, "别再给我海鲜")
        parsed = parse_routine("每周一叫我称重")
        created = None
        if parsed is not None:
            created = RoutineStore(root).create(
                title=parsed["title"],
                instruction=parsed["instruction"],
                cadence=parsed["cadence"],
                owner_space="life",
                timezone_name=parsed["timezone"],
                now=datetime.now(timezone.utc) - timedelta(days=1),
            )
        texts = active_texts(ConstraintStore(root).load())
        ok = any("别再给我海鲜" in text for text in texts) and created is not None and created.cadence == "weekly" and NETWORK_CALLS == net
        check("S9", ok, f"active={texts} cadence={None if created is None else created.cadence}")

    check("NET", NETWORK_CALLS == before, f"NETWORK_CALLS {before}→{NETWORK_CALLS}")
    for name, status, detail in rows:
        print(f"{status} {name} {detail}")
    failed = [name for name, status, _detail in rows if status != "PASS"]
    print(f"{len(rows) - len(failed)} PASS / {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
