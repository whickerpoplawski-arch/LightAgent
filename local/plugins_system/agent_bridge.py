"""Wrap local.openrouter_config.make_agent so enabled plugins inject tools/skills."""

from __future__ import annotations

from typing import Any

from .manager import load_enabled_plugins


def make_agent_with_plugins(**kwargs: Any):
    """Like openrouter_config.make_agent, plus enabled local plugins.

    Caller kwargs win on conflicts for tools/skills_directories (merged, not replaced):
    - tools: plugin tools first, then caller tools
    - skills_directories: plugin dirs + caller dirs + default 'skills'
    """
    from local.openrouter_config import make_agent

    loaded = load_enabled_plugins()
    if loaded.errors:
        for err in loaded.errors:
            print(f"[plugins] load warning: {err}")

    tools = list(loaded.tools)
    caller_tools = kwargs.pop("tools", None) or []
    tools.extend(caller_tools)

    skill_dirs = list(loaded.skills_directories)
    caller_dirs = kwargs.pop("skills_directories", None) or []
    for d in caller_dirs:
        if d not in skill_dirs:
            skill_dirs.append(d)
    if "skills" not in skill_dirs:
        skill_dirs.append("skills")

    auto = kwargs.pop("auto_discover_skills", True if skill_dirs else kwargs.get("auto_discover_skills", True))

    agent_kwargs = dict(kwargs)
    if tools:
        agent_kwargs["tools"] = tools
    if skill_dirs:
        agent_kwargs["skills_directories"] = skill_dirs
        agent_kwargs["auto_discover_skills"] = auto

    agent = make_agent(**agent_kwargs)
    # stash for callers that want MCP later
    agent._local_plugin_mcp = dict(loaded.mcp_servers)  # type: ignore[attr-defined]
    agent._local_plugins = list(loaded.plugins)  # type: ignore[attr-defined]
    return agent
