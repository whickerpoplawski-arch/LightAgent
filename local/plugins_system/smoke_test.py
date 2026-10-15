"""Unit-ish smoke: install / list / enable / load tools — zero OpenRouter calls."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# repo root on path
REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def main() -> int:
    from local.plugins_system.manager import (
        PLUGINS_DIR,
        disable,
        enable,
        install,
        list_plugins,
        load_enabled_plugins,
        uninstall,
    )

    example = REPO / "local" / "plugins_system" / "examples" / "hello_plugin"
    assert example.is_dir(), example

    # isolate: use a temp plugins dir by monkeypatching? keep simple — install to real local/plugins
    # uninstall first if leftover
    try:
        uninstall("hello_plugin")
    except Exception:
        pass

    m = install(example, symlink=True, enable_after=True)
    assert m.name == "hello_plugin", m
    rows = list_plugins()
    names = {r["name"] for r in rows}
    assert "hello_plugin" in names, rows
    row = next(r for r in rows if r["name"] == "hello_plugin")
    assert row["enabled"] is True
    assert row["has_tools"] is True
    assert row["has_skills"] is True

    loaded = load_enabled_plugins()
    assert not loaded.errors, loaded.errors
    tool_names = {
        t.tool_info["tool_name"] for t in loaded.tools if getattr(t, "tool_info", None)
    }
    assert "hello" in tool_names, tool_names
    assert "echo_text" in tool_names, tool_names
    assert any("hello" in Path(d).as_posix() for d in loaded.skills_directories), loaded.skills_directories

    # call tools directly — no LLM
    hello = next(t for t in loaded.tools if t.tool_info["tool_name"] == "hello")
    echo = next(t for t in loaded.tools if t.tool_info["tool_name"] == "echo_text")
    assert "hello, LightAgent" in hello("LightAgent")
    assert echo("ping") == "ping"

    disable("hello_plugin")
    loaded2 = load_enabled_plugins()
    assert "hello_plugin" not in {p.name for p in loaded2.plugins}

    enable("hello_plugin")
    loaded3 = load_enabled_plugins()
    assert "hello_plugin" in {p.name for p in loaded3.plugins}

    # agent_kwargs shape (do not construct LightAgent with API)
    kw = loaded3.agent_kwargs()
    assert "tools" in kw and "skills_directories" in kw

    print("SMOKE OK")
    print(f"  plugins_dir={PLUGINS_DIR}")
    print(f"  tools={sorted(tool_names)}")
    print(f"  skills_directories={loaded.skills_directories}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
