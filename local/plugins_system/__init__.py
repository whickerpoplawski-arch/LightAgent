"""Lightweight local plugin system for LightAgent (no marketplace)."""

from .manifest import PluginManifest, load_manifest
from .manager import (
    PLUGINS_DIR,
    disable,
    enable,
    install,
    install_from_git,
    install_from_spec,
    list_plugins,
    load_enabled_plugins,
    uninstall,
)

__all__ = [
    "PluginManifest",
    "load_manifest",
    "PLUGINS_DIR",
    "install",
    "install_from_spec",
    "install_from_git",
    "uninstall",
    "list_plugins",
    "enable",
    "disable",
    "load_enabled_plugins",
]
