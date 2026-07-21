"""MCP server entry point.

Registers the resources (static/read-only data addressable by ``git-activity://``
URIs), imports :mod:`tools` for its side-effect registrations, and starts the
FastMCP transport.

Auth note (SSE):
    FastMCP's default transport for local use is stdio, which is authenticated
    by the OS process boundary. If this server is later exposed over SSE, add
    an API key / JWT check in front of the SSE endpoint. See the TODO block
    inside ``_sse_auth_placeholder`` below.
"""
from __future__ import annotations

import json
import os
from typing import Any

from app import server
from mock_git_utils import MOCK_CODEOWNERS, MOCK_REPO_SUMMARY, MOCK_TEAMS

# Import tool/prompt registrations for their side effects.
import tools  # noqa: F401


@server.resource(
    "git-activity://summary/{repo_path}",
    description="High-level repo summary: commits, contributors, top-changed files, date range.",
)
def repo_summary(repo_path: str) -> str:
    payload: dict[str, Any] = dict(MOCK_REPO_SUMMARY)
    payload["repo_path"] = repo_path
    return json.dumps(payload, indent=2)


@server.resource(
    "git-activity://teams/backend",
    description="Roster and roles for the backend team.",
)
def team_backend() -> str:
    return json.dumps(MOCK_TEAMS, indent=2)


@server.resource(
    "git-activity://ownership/CODEOWNERS",
    description="Parsed CODEOWNERS mapping: path glob → owners.",
)
def ownership_codeowners() -> str:
    return json.dumps(MOCK_CODEOWNERS, indent=2)


def _sse_auth_placeholder(headers: dict[str, str]) -> None:
    """Auth check for SSE transport.

    TODO: When enabling SSE, wire this into the FastMCP SSE middleware. Accept
    a bearer token via the ``Authorization`` header or an API key via
    ``X-API-Key`` and reject requests that fail validation. Example sketch::

        expected = os.environ.get("GIT_ACTIVITY_API_KEY")
        provided = headers.get("x-api-key") or headers.get("X-API-Key")
        if not expected or provided != expected:
            raise PermissionError("invalid api key / jwt")

    For now this is a documented no-op so the stdio path stays unauthenticated
    by intent (OS-level trust boundary).
    """
    _ = os.environ.get("GIT_ACTIVITY_API_KEY")
    _ = headers  # unused until SSE is enabled


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
