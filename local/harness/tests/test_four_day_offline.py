"""L-P1-4: the 4-day script is offline and green. Live stays off."""

from __future__ import annotations

from local.harness.four_day import main, run_four_day
from local.openrouter_config import NETWORK_CALLS


def test_offline_four_day_script_is_green():
    before = NETWORK_CALLS
    rows = run_four_day()
    assert len(rows) == 40
    failed = [row for row in rows if row[1] != "PASS"]
    assert failed == []
    assert NETWORK_CALLS == before


def test_live_switch_is_off_unless_the_env_is_set(monkeypatch):
    monkeypatch.delenv("LIGHTAGENT_4DAY_LIVE", raising=False)
    before = NETWORK_CALLS
    assert main(["--live"]) == 2
    assert NETWORK_CALLS == before


def test_live_switch_does_not_call_a_model(monkeypatch):
    monkeypatch.setenv("LIGHTAGENT_4DAY_LIVE", "1")
    before = NETWORK_CALLS
    assert main(["--live"]) == 0
    assert NETWORK_CALLS == before
