"""Discover / install / enable / disable / load local plugins."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .manifest import PluginManifest, find_manifest_file, load_manifest

_HERE = Path(__file__).resolve().parent
# installed plugins live next to plugins_system/
PLUGINS_DIR = (_HERE.parent / "plugins").resolve()
ENABLED_FILE = PLUGINS_DIR / "enabled.json"
# never treat these as plugins
_SKIP_NAMES = {"__pycache__", ".git", "enabled.json"}


@dataclass
class LoadedPlugins:
    """Result of load_enabled_plugins() — ready to pass into LightAgent."""

    tools: list[Callable[..., Any]] = field(default_factory=list)
    skills_directories: list[str] = field(default_factory=list)
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)
    plugins: list[PluginManifest] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def agent_kwargs(self) -> dict[str, Any]:
        """Kwargs suitable for LightAgent / make_agent (MCP left to caller)."""
        kw: dict[str, Any] = {}
        if self.tools:
            kw["tools"] = list(self.tools)
        if self.skills_directories:
            kw["skills_directories"] = list(self.skills_directories)
            kw["auto_discover_skills"] = True
        return kw


def ensure_plugins_dir() -> Path:
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    if not ENABLED_FILE.exists():
        ENABLED_FILE.write_text("{}", encoding="utf-8")
    return PLUGINS_DIR


def _read_enabled() -> dict[str, bool]:
    ensure_plugins_dir()
    try:
        data = json.loads(ENABLED_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {str(k): bool(v) for k, v in data.items()}


def _write_enabled(state: dict[str, bool]) -> None:
    ensure_plugins_dir()
    ENABLED_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def discover(plugins_dir: Path | None = None) -> list[PluginManifest]:
    """List installed plugin folders that have a valid manifest."""
    root = Path(plugins_dir or PLUGINS_DIR).resolve()
    ensure_plugins_dir()
    found: list[PluginManifest] = []
    if not root.is_dir():
        return found
    for child in sorted(root.iterdir()):
        if child.name in _SKIP_NAMES or child.name.startswith("."):
            continue
        if not child.is_dir():
            continue
        if find_manifest_file(child) is None:
            continue
        try:
            found.append(load_manifest(child))
        except Exception:
            continue
    return found


def list_plugins(plugins_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return list of {name, version, description, enabled, path}."""
    enabled = _read_enabled()
    rows = []
    for m in discover(plugins_dir):
        rows.append(
            {
                "name": m.name,
                "version": m.version,
                "description": m.description,
                "enabled": bool(enabled.get(m.name, False)),
                "path": str(m.root) if m.root else "",
                "has_tools": m.tools_path is not None,
                "has_skills": m.skills_path is not None,
                "has_mcp": m.mcp_path is not None,
            }
        )
    return rows


def install(
    source: str | Path,
    *,
    symlink: bool = False,
    enable_after: bool = True,
    name: str | None = None,
) -> PluginManifest:
    """Copy or symlink a plugin folder into local/plugins/.

    Does NOT download remote code. Source must be a local directory with a manifest.
    """
    src = Path(source).expanduser().resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"source not a directory: {src}")
    manifest = load_manifest(src)
    plugin_name = name or manifest.name
    # re-validate folder name safety
    if "/" in plugin_name or "\\" in plugin_name or plugin_name in {".", ".."}:
        raise ValueError(f"unsafe plugin name: {plugin_name}")

    ensure_plugins_dir()
    dest = PLUGINS_DIR / plugin_name
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)

    if symlink:
        dest.symlink_to(src, target_is_directory=True)
    else:
        shutil.copytree(src, dest)

    installed = load_manifest(dest)
    if enable_after:
        enable(installed.name)
    return installed


def uninstall(name: str) -> None:
    ensure_plugins_dir()
    dest = PLUGINS_DIR / name
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)
    state = _read_enabled()
    state.pop(name, None)
    _write_enabled(state)


def enable(name: str) -> None:
    # must be installed
    names = {m.name for m in discover()}
    if name not in names:
        raise KeyError(f"plugin not installed: {name}")
    state = _read_enabled()
    state[name] = True
    _write_enabled(state)


def disable(name: str) -> None:
    state = _read_enabled()
    state[name] = False
    _write_enabled(state)


def _load_tools_from_module(path: Path, plugin_name: str) -> list[Callable[..., Any]]:
    """Import tools.py and collect callables that have tool_info."""
    module_name = f"lightagent_plugin_{plugin_name}".replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load tools module: {path}")
    module = importlib.util.module_from_spec(spec)
    # allow relative imports inside the plugin folder
    sys.modules[module_name] = module
    plugin_root = str(path.parent)
    inserted = False
    if plugin_root not in sys.path:
        sys.path.insert(0, plugin_root)
        inserted = True
    try:
        spec.loader.exec_module(module)
    finally:
        if inserted:
            try:
                sys.path.remove(plugin_root)
            except ValueError:
                pass

    tools: list[Callable[..., Any]] = []
    # prefer TOOLS list if provided
    declared = getattr(module, "TOOLS", None)
    if isinstance(declared, (list, tuple)):
        for item in declared:
            if callable(item) and getattr(item, "tool_info", None):
                tools.append(item)
        if tools:
            return tools

    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue
        obj = getattr(module, attr_name)
        if callable(obj) and getattr(obj, "tool_info", None):
            tools.append(obj)
    return tools


def _load_mcp(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    servers = data.get("mcpServers") or data
    if not isinstance(servers, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, val in servers.items():
        if isinstance(val, dict):
            out[str(key)] = dict(val)
    return out


def load_enabled_plugins(plugins_dir: Path | None = None) -> LoadedPlugins:
    """Load tools + skills dirs (+ mcp config) from enabled plugins. No API calls."""
    result = LoadedPlugins()
    enabled = _read_enabled()
    for manifest in discover(plugins_dir):
        if not enabled.get(manifest.name, False):
            continue
        result.plugins.append(manifest)
        if manifest.tools_path is not None:
            try:
                result.tools.extend(_load_tools_from_module(manifest.tools_path, manifest.name))
            except Exception as exc:
                result.errors.append(f"{manifest.name}/tools: {exc}")
        if manifest.skills_path is not None:
            result.skills_directories.append(str(manifest.skills_path))
        if manifest.mcp_path is not None:
            try:
                result.mcp_servers.update(_load_mcp(manifest.mcp_path))
            except Exception as exc:
                result.errors.append(f"{manifest.name}/mcp: {exc}")
    return result


def _looks_like_github(spec: str) -> bool:
    import re

    s = spec.strip()
    if s.startswith(("https://github.com/", "http://github.com/", "git@github.com:")):
        return True
    # bare owner/repo (not a relative path like ./foo or local/bar)
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", s):
        return True
    return False


def _github_clone_url(spec: str) -> str:
    s = spec.strip().rstrip("/")
    if s.startswith("git@"):
        return s
    if s.startswith("http://") or s.startswith("https://"):
        if s.endswith(".git"):
            return s
        return s + ".git"
    return f"https://github.com/{s}.git"


def _skill_tree_dir(root: Path) -> Path | None:
    """Return skills/ if it contains at least one */SKILL.md child."""
    skills = Path(root) / "skills"
    if not skills.is_dir():
        return None
    try:
        for child in skills.iterdir():
            if child.is_dir() and (child / "SKILL.md").is_file():
                return skills
    except OSError:
        return None
    return None


def _read_external_plugin_meta(repo: Path) -> dict[str, Any]:
    """Best-effort metadata from Cursor/Claude/npm plugin descriptors."""
    import json

    for rel in (
        Path(".cursor-plugin") / "plugin.json",
        Path(".claude-plugin") / "plugin.json",
        Path(".codex-plugin") / "plugin.json",
        Path("package.json"),
    ):
        path = repo / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        # marketplace index: {plugins: [...]} without top-level version
        if "plugins" in data and "version" not in data:
            continue
        name = str(data.get("name") or data.get("displayName") or "").strip()
        if not name:
            continue
        if name.endswith("-dev"):
            name = name[: -len("-dev")]
        version = str(data.get("version") or "0.0.0").strip() or "0.0.0"
        description = str(data.get("description") or data.get("displayName") or "").strip()
        return {
            "name": name.replace("@", "").replace("/", "-"),
            "version": version,
            "description": description,
            "source_meta": str(rel),
        }
    return {
        "name": repo.name,
        "version": "0.0.0",
        "description": f"Adapted skills plugin from {repo.name}",
        "source_meta": "",
    }


def yaml_dump(data: dict[str, Any]) -> str:
    import yaml

    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def adapt_external_skills_repo(
    repo: Path,
    *,
    wrapper_parent: Path | None = None,
    origin_url: str | None = None,
) -> Path:
    """Build a LightAgent wrapper around an upstream skills repo (no upstream mutation).

    Creates a sibling wrapper with manifest.yaml + skills symlink to upstream skills/.
    install() then copytree-follows the symlink into local/plugins/<name>/skills.
    """
    repo = Path(repo).resolve()
    skills = _skill_tree_dir(repo)
    if skills is None:
        raise FileNotFoundError(
            f"no LightAgent manifest.yaml and no skills/*/SKILL.md under {repo}"
        )
    meta = _read_external_plugin_meta(repo)
    name = meta["name"] or "skills_plugin"
    if name in {"superpowers-dev"}:
        name = "superpowers"
    parent = Path(wrapper_parent or repo.parent).resolve()
    wrapper = parent / f"la-wrapper-{name}"
    if wrapper.exists():
        shutil.rmtree(wrapper)
    wrapper.mkdir(parents=True)
    manifest = {
        "name": name,
        "version": meta["version"],
        "description": meta["description"]
        or "Adapted Cursor/Claude skills plugin (skills only)",
        "entrypoints": {"skills": "skills"},
        "adapter": "external-skills-wrapper",
        "upstream": origin_url or str(repo.name),
    }
    if meta.get("source_meta"):
        manifest["upstream_meta"] = meta["source_meta"]
    (wrapper / "manifest.yaml").write_text(yaml_dump(manifest), encoding="utf-8")
    (wrapper / "skills").symlink_to(skills.resolve(), target_is_directory=True)
    origin_line = origin_url or str(repo)
    (wrapper / "ORIGIN.txt").write_text(
        f"Adapted from {origin_line}\nskills -> {skills.resolve()}\n",
        encoding="utf-8",
    )
    return wrapper


def install_from_git(url: str, *, enable_after: bool = True) -> PluginManifest:
    """Shallow-clone a git URL into a temp dir, then install() into local/plugins/.

    If the clone has no LightAgent manifest but exposes skills/*/SKILL.md
    (Cursor/Claude Superpowers-style), auto-wrap it with a generated manifest.
    """
    import subprocess
    import tempfile

    ensure_plugins_dir()
    tmp = Path(tempfile.mkdtemp(prefix="la-plugin-"))
    repo = tmp / "repo"
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(repo)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            raise RuntimeError(f"git clone failed: {err}")
        target: Path | None = repo if find_manifest_file(repo) else None
        if target is None:
            for child in sorted(repo.iterdir()):
                if child.is_dir() and not child.name.startswith(".") and find_manifest_file(child):
                    target = child
                    break
        if target is None:
            # Cursor / Claude skills pack (e.g. obra/superpowers)
            try:
                target = adapt_external_skills_repo(repo, wrapper_parent=tmp, origin_url=url)
            except FileNotFoundError as exc:
                raise FileNotFoundError(
                    f"cloned repo has no manifest.yaml and no adaptable skills/: {url} ({exc})"
                ) from exc
        return install(target, symlink=False, enable_after=enable_after)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install_from_spec(
    spec: str,
    *,
    enable_after: bool = True,
    symlink: bool = False,
) -> PluginManifest:
    """Install from a local path, GitHub URL, or owner/repo.

    Local path always preferred when it exists (mock-friendly, no network).
    """
    raw = (spec or "").strip()
    if not raw:
        raise ValueError("empty install source")
    path = Path(raw).expanduser()
    if path.exists() and path.is_dir():
        return install(path, symlink=symlink, enable_after=enable_after)
    if _looks_like_github(raw):
        return install_from_git(_github_clone_url(raw), enable_after=enable_after)
    # fall through for clearer FileNotFoundError
    return install(path, symlink=symlink, enable_after=enable_after)
