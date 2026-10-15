"""CLI: python -m local.plugins_system <install|list|enable|disable|uninstall|load>"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m local.plugins_system",
        description="LightAgent 本地插件（无 marketplace，仅目录复制/软链）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_install = sub.add_parser("install", help="从本地路径 / GitHub URL / owner/repo 安装到 local/plugins/")
    p_install.add_argument("source", help="本地目录、https://github.com/… 或 owner/repo")
    p_install.add_argument("--symlink", action="store_true", help="软链而不是复制")
    p_install.add_argument("--no-enable", action="store_true", help="安装后不自动启用")
    p_install.add_argument("--name", help="覆盖安装名（默认用 manifest.name）")

    sub.add_parser("list", help="列出已安装插件")

    p_enable = sub.add_parser("enable", help="启用插件")
    p_enable.add_argument("name")

    p_disable = sub.add_parser("disable", help="禁用插件")
    p_disable.add_argument("name")

    p_uninstall = sub.add_parser("uninstall", help="卸载插件")
    p_uninstall.add_argument("name")

    p_load = sub.add_parser("load", help="加载已启用插件（打印 tools/skills，不调 API）")
    p_load.add_argument("--json", action="store_true", help="JSON 输出")

    args = parser.parse_args(argv)

    # ensure local package importable when run as module from repo root
    repo = Path(__file__).resolve().parents[2]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    from local.plugins_system.manager import (
        disable,
        enable,
        install,
        install_from_spec,
        list_plugins,
        load_enabled_plugins,
        uninstall,
    )

    if args.cmd == "install":
        # --name only applies to pure local install(); git/spec uses manifest name
        if args.name and Path(args.source).expanduser().exists():
            m = install(args.source, symlink=args.symlink, enable_after=not args.no_enable, name=args.name)
        else:
            m = install_from_spec(args.source, symlink=args.symlink, enable_after=not args.no_enable)
        print(f"installed: {m.name}@{m.version} -> {m.root}")
        print(f"enabled: {not args.no_enable}")
        return 0

    if args.cmd == "list":
        rows = list_plugins()
        if not rows:
            print("(no plugins installed)")
            return 0
        for row in rows:
            flag = "ON " if row["enabled"] else "off"
            bits = []
            if row["has_tools"]:
                bits.append("tools")
            if row["has_skills"]:
                bits.append("skills")
            if row["has_mcp"]:
                bits.append("mcp")
            extra = ",".join(bits) or "-"
            print(f"[{flag}] {row['name']}@{row['version']}  ({extra})  {row['description']}")
        return 0

    if args.cmd == "enable":
        enable(args.name)
        print(f"enabled: {args.name}")
        return 0

    if args.cmd == "disable":
        disable(args.name)
        print(f"disabled: {args.name}")
        return 0

    if args.cmd == "uninstall":
        uninstall(args.name)
        print(f"uninstalled: {args.name}")
        return 0

    if args.cmd == "load":
        loaded = load_enabled_plugins()
        payload = {
            "plugins": [p.name for p in loaded.plugins],
            "tools": [
                getattr(getattr(t, "tool_info", {}), "get", lambda *_: None)("tool_name")
                if hasattr(getattr(t, "tool_info", None), "get")
                else (t.tool_info.get("tool_name") if getattr(t, "tool_info", None) else getattr(t, "__name__", "?"))
                for t in loaded.tools
            ],
            "skills_directories": loaded.skills_directories,
            "mcp_servers": list(loaded.mcp_servers.keys()),
            "errors": loaded.errors,
        }
        # fix tool names more simply
        payload["tools"] = [
            (t.tool_info.get("tool_name") if getattr(t, "tool_info", None) else getattr(t, "__name__", "?"))
            for t in loaded.tools
        ]
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"plugins: {', '.join(payload['plugins']) or '(none)'}")
            print(f"tools: {', '.join(payload['tools']) or '(none)'}")
            print(f"skills_directories: {payload['skills_directories'] or '(none)'}")
            print(f"mcp_servers: {payload['mcp_servers'] or '(none)'}")
            if payload["errors"]:
                print("errors:")
                for e in payload["errors"]:
                    print(f"  - {e}")
        return 1 if loaded.errors else 0

    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
