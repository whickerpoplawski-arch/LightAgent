"""Gaps left by the earlier P0 suite: cross-process persistence, phone
redaction, salary confirm-gate, and the edit/list tool names.

No OpenRouter. Subprocess checks talk to a temp sqlite file only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from local.memory.host import MemoryHost
from local.memory.pack import build_for_turn
from local.memory.scrub import scrub_text
from local.memory.store import ProfileStore
from local.openrouter_config import FREE_MODELS, run_free


def _cli(db: str, args: list[str]) -> str:
    env = os.environ.copy()
    env["LIGHTAGENT_PROFILE_DB"] = db
    env["LIGHTAGENT_USER_ID"] = "alice"
    env.pop("OPENROUTER_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-m", "local.memory.cli", *args],
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_learn_and_forget_cross_process(tmp_path):
    db = str(tmp_path / "profile.sqlite")
    created = json.loads(_cli(db, ["learn", "以后简称我小Q", "--lane", "general", "--facet", "identity"]))
    learning_id = created["learning"]["id"]

    reopened = ProfileStore(db)
    rows = reopened.list_learnings(user_id="alice", namespace="profile")
    assert [row.text for row in rows] == ["以后简称我小Q"]

    listed = json.loads(_cli(db, ["list"]))
    assert listed[0]["text"] == "以后简称我小Q"

    forgotten = json.loads(_cli(db, ["forget", learning_id]))
    assert learning_id in forgotten["forgotten"]
    assert json.loads(_cli(db, ["list"])) == []
    assert ProfileStore(db).list_learnings(user_id="alice", namespace="profile") == []


def test_phone_is_redacted_and_salary_stays_out_of_the_pack(env):
    phone = scrub_text("手机 13800138000 ，以后简称我小Q")
    assert phone.allowed is True
    assert "13800138000" not in phone.text
    assert "[redacted-phone]" in phone.text
    assert "小Q" in phone.text

    pending = env.learn("月薪是 20000", user_id="alice", namespace="profile", lane="general", facet="life")
    assert pending.status == "needs_confirm"
    assert pending.learning.injectable is False
    pack = build_for_turn(env, MemoryHost(user_id="alice"), query="工资")
    assert "20000" not in pack.markdown
    assert "月薪" not in pack.markdown


def test_edit_and_list_tools_are_registered():
    from local.tui.tools import TOOLS

    names = [tool.tool_info["tool_name"] for tool in TOOLS]
    for name in (
        "memory_learn",
        "memory_forget",
        "memory_recall",
        "memory_pin",
        "memory_edit",
        "memory_list",
    ):
        assert name in names


def test_run_free_catalog_is_free_only_and_is_not_called():
    from local import openrouter_config as orc

    assert FREE_MODELS
    assert "openai/gpt-4o" not in FREE_MODELS
    if orc.REQUIRE_FREE_SUFFIX:
        assert all(model.endswith(":free") for model in FREE_MODELS)
    else:
        assert orc.DEFAULT_MODEL == FREE_MODELS[0]
        assert "deepseek" in orc.DEFAULT_MODEL or orc.PROVIDER == "mx"
    # Touching the function object must not open a socket.
    assert callable(run_free)