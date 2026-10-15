"""Shared first-class tools for LightAgent local forks (not plugins)."""

from local.memory.tools import MEMORY_TOOLS
from .web import web_fetch, web_search

__all__ = ["MEMORY_TOOLS", "web_search", "web_fetch"]
