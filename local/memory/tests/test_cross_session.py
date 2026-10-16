"""L-P0-3: diet card, pin, and the open goal survive a new process.

A bot with share_user_profile off does not receive that hard-fact block.
The room digest stays a short ephemeral-stripped note, not a shared knowledge base.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from local.constraints.card import ConstraintStore
from local.conversations.collaborate import DelegateQuota, run_delegation
from local.conversations.models import BotIdentity, ConversationMeta
from local.goals.store import create_goal
from local.memory.host import MemoryHost
from local.memory.inject import prepare_turn
from local.rooms.digest import MAX_DIGEST_CHARS, build_room_digest
from local.rooms.types import GroupRoom, RoomMessage
from local.rooms.utterance import run_room_utterance

_ROOT = Path(__file__).resolve().parents[3]
_FACTS = ("忌口：海鲜", "叫我小Q")


def _reopen_script(path: Path) -> None:
    path.write_text(
        """
import json
import os
from pathlib import Path

from local.constraints.card import ConstraintStore
from local.goals.store import GoalStore
from local.memory.store import ProfileStore

root = Path(os.environ["LIFE_WS"])
store = ProfileStore(os.environ["LIFE_DB"])
pins = [
    row.text
    for row in store.list_learnings(user_id="alice", namespace="profile")
    if row.pinned and row.status == "active"
]
steps = []
for goal in GoalStore(root).list_goals():
    for step in goal.steps:
        if step.status == "in_progress":
            steps.append({"goal_id": goal.goal_id, "title": step.title, "objective": goal.objective})
print(json.dumps({
    "card": ConstraintStore(root).active_texts(),
    "pins": pins,
    "steps": steps,
}, ensure_ascii=False))
""".lstrip(),
        encoding="utf-8",
    )


def test_new_process_reopens_diet_pin_and_goal(env, tmp_path):
    ConstraintStore(tmp_path).remember("忌口：海鲜")
    saved = env.learn("叫我小Q", user_id="alice", namespace="profile", lane="general", facet="identity")
    env.pin(saved.learning.id, user_id="alice", namespace="profile", pinned=True)
    goal = create_goal(tmp_path, space_id="home", objective="本周健身和饮食")
    in_progress = next(step.title for step in goal.steps if step.status == "in_progress")

    script = tmp_path / "reopen_life_store.py"
    _reopen_script(script)
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = str(_ROOT)
    child_env["LIFE_WS"] = str(tmp_path)
    child_env["LIFE_DB"] = str(env.path)
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(_ROOT),
        env=child_env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["card"] == ["忌口：海鲜"]
    assert payload["pins"] == ["叫我小Q"]
    assert payload["steps"] == [{
        "goal_id": goal.goal_id,
        "title": in_progress,
        "objective": "本周健身和饮食",
    }]


def test_private_bot_system_omits_hard_facts(env, tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_WORKSPACE", str(tmp_path))
    ConstraintStore(tmp_path).remember("忌口：海鲜")
    saved = env.learn("叫我小Q", user_id="alice", namespace="profile", lane="general", facet="identity")
    env.pin(saved.learning.id, user_id="alice", namespace="profile", pinned=True)
    create_goal(tmp_path, space_id="home", objective="本周健身和饮食")
    host = MemoryHost(user_id="alice", namespace="profile", space_id="home")

    hidden = prepare_turn(
        system="base",
        history=[],
        user_text="今天记一笔",
        store=env,
        host=host,
        persona_text="",
        identity_block="",
        share_user_profile=False,
    )
    private_system = hidden.messages[0]["content"]
    for fact in (*_FACTS, "本周健身和饮食"):
        assert fact not in private_system
    assert "<memory-context>" not in private_system

    shared = prepare_turn(
        system="base",
        history=[],
        user_text="今天记一笔",
        store=env,
        host=host,
        persona_text="",
        identity_block="",
        share_user_profile=True,
    )
    shared_system = shared.messages[0]["content"]
    for fact in (*_FACTS, "本周健身和饮食"):
        assert fact in shared_system

    private = ConversationMeta(
        id="priv",
        title="家庭账本",
        identity=BotIdentity(role_title="家庭账本官", job_description="只记猫粮。"),
        share_user_profile=False,
        agent_id="bot-priv",
    )
    block = "<memory-context>\n叫我小Q\n忌口：海鲜\n</memory-context>"
    outcome = run_delegation(
        roster=[private],
        bot_id="priv",
        task="今天记一笔",
        profile_block=block,
        mode="mock",
    )
    for fact in _FACTS:
        assert fact not in outcome.child_system

    captured: dict[str, str] = {}

    def spy(*args, **kwargs):
        result = run_delegation(*args, **kwargs)
        captured["system"] = result.child_system
        return result

    monkeypatch.setattr("local.rooms.utterance.run_delegation", spy)
    room = GroupRoom(id="r1", title="健康日常", member_bot_ids=["priv"])
    run_room_utterance(
        room,
        "priv",
        "今天记一笔",
        "",
        [private],
        DelegateQuota(),
        turn_id="t1",
        profile_block=block,
    )
    for fact in _FACTS:
        assert fact not in captured["system"]


def test_digest_stays_short_and_drops_hard_facts():
    secret = "<memory-context>\n忌口：海鲜\n叫我小Q\n</memory-context>"
    messages = [
        RoomMessage(
            id=str(index),
            role="assistant",
            speaker="bot:c1",
            speaker_label="习惯教练",
            content=secret + ("普通一句。" * 50),
            ts=float(index),
            kind="chat",
        )
        for index in range(12)
    ]
    digest = build_room_digest(messages)
    assert len(digest) <= MAX_DIGEST_CHARS == 480
    assert "<memory-context>" not in digest
    for fact in _FACTS:
        assert fact not in digest
