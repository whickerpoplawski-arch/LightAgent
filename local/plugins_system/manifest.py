"""PluginManifest: folder with manifest.yaml (+ optional tools.py / skills / mcp.json)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_MANIFEST_NAMES = ("manifest.yaml", "manifest.yml", "plugin.yaml", "plugin.yml", "plugin.json")


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    description: str = ""
    # relative paths inside the plugin root
    tools_module: str = "tools.py"
    skills_dir: str = "skills"
    mcp_file: str = "mcp.json"
    # optional explicit entrypoints declared in manifest
    entrypoints: dict[str, str] = field(default_factory=dict)
    root: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def tools_path(self) -> Path | None:
        if not self.root:
            return None
        # entrypoints.tools overrides default
        rel = self.entrypoints.get("tools") or self.tools_module
        path = (self.root / rel).resolve()
        return path if path.is_file() else None

    @property
    def skills_path(self) -> Path | None:
        if not self.root:
            return None
        rel = self.entrypoints.get("skills") or self.skills_dir
        path = (self.root / rel).resolve()
        return path if path.is_dir() else None

    @property
    def mcp_path(self) -> Path | None:
        if not self.root:
            return None
        rel = self.entrypoints.get("mcp") or self.mcp_file
        path = (self.root / rel).resolve()
        return path if path.is_file() else None


def find_manifest_file(plugin_dir: Path) -> Path | None:
    for name in _MANIFEST_NAMES:
        candidate = plugin_dir / name
        if candidate.is_file():
            return candidate
    return None


def load_manifest(plugin_dir: str | Path) -> PluginManifest:
    root = Path(plugin_dir).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"plugin directory not found: {root}")
    manifest_file = find_manifest_file(root)
    if manifest_file is None:
        raise FileNotFoundError(
            f"no manifest.yaml/plugin.yaml in {root} "
            f"(looked for {_MANIFEST_NAMES})"
        )
    text = manifest_file.read_text(encoding="utf-8")
    if manifest_file.suffix == ".json":
        import json

        data = json.loads(text)
    else:
        data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"manifest must be a mapping: {manifest_file}")

    name = str(data.get("name") or root.name).strip()
    version = str(data.get("version") or "0.0.0").strip()
    description = str(data.get("description") or "").strip()
    entrypoints = data.get("entrypoints") or {}
    if not isinstance(entrypoints, dict):
        raise ValueError("entrypoints must be a mapping")
    entrypoints = {str(k): str(v) for k, v in entrypoints.items()}

    return PluginManifest(
        name=name,
        version=version,
        description=description,
        tools_module=str(data.get("tools_module") or entrypoints.get("tools") or "tools.py"),
        skills_dir=str(data.get("skills_dir") or entrypoints.get("skills") or "skills"),
        mcp_file=str(data.get("mcp_file") or entrypoints.get("mcp") or "mcp.json"),
        entrypoints=entrypoints,
        root=root,
        raw=data,
    )
