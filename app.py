"""FastMCP server initialization.

Kept intentionally tiny so ``tools.py`` can ``from app import server`` without
triggering circular imports. All resource/tool/prompt registrations live in
``server.py`` and ``tools.py``.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

server = FastMCP("git-activity-analyzer")
