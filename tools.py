"""MCP tool and prompt registrations.

Imports the FastMCP instance from ``app`` — this indirection keeps registration
side effects out of ``app.py`` and avoids the circular import that would occur
if ``app.py`` itself referenced tools/analysis.
"""
from __future__ import annotations

from typing import Any

from app import server
from analysis import analyze_commit_patterns as _analyze_commit_patterns
from analysis import analyze_hotspots as _analyze_hotspots
from security import validate_repo_path


@server.tool(
    description=(
        "Identify risky/hotspot files based on change frequency and author "
        "diversity. Returns a non-empty list of {file, authors, changes, risk_score}."
    ),
)
def analyze_hotspots(
    repo_path: str,
    days: int = 30,
    branch: str | None = None,
) -> list[dict[str, Any]]:
    validate_repo_path(repo_path)
    return _analyze_hotspots(repo_path, days=days, branch=branch)


@server.tool(
    description=(
        "Summarize commit patterns (volume, size, authorship) over a time window. "
        "Returns {total_commits, avg_files_per_commit, authors}."
    ),
)
def analyze_commit_patterns(
    repo_path: str,
    days: int = 30,
    author: str | None = None,
) -> dict[str, Any]:
    validate_repo_path(repo_path)
    return _analyze_commit_patterns(repo_path, days=days, author=author)


@server.tool(
    description=(
        "Extra tool: return recent (mock) deployment records for cross-referencing "
        "hotspots with production changes."
    ),
)
def list_recent_deploys(
    repo_path: str,
    env: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    validate_repo_path(repo_path)
    deploys = [
        {"env": "prod", "version": "v1.4.2", "commit_sha": "a1b2c3d", "timestamp": "2026-07-19T14:02:00Z"},
        {"env": "prod", "version": "v1.4.1", "commit_sha": "9f8e7d6", "timestamp": "2026-07-17T09:31:00Z"},
        {"env": "staging", "version": "v1.4.2-rc1", "commit_sha": "a1b2c3d", "timestamp": "2026-07-18T16:20:00Z"},
    ]
    if env:
        deploys = [d for d in deploys if d["env"] == env]
    return deploys[:limit]


@server.prompt(
    name="repo_health_review",
    description=(
        "Guided workflow: pull repo summary, run analyze_hotspots and "
        "analyze_commit_patterns, join CODEOWNERS, and produce a prioritized "
        "recommendation list."
    ),
)
def repo_health_review(repo_path: str, days: int = 30) -> str:
    return (
        "You are reviewing repository health for the given repo.\n\n"
        f"Repository: {repo_path}\n"
        f"Window: last {days} days\n\n"
        "Follow these steps in order:\n"
        f"1. Read resource `git-activity://summary/{repo_path}` for baseline stats.\n"
        f"2. Call tool `analyze_hotspots(repo_path={repo_path!r}, days={days})` "
        "to identify risky files.\n"
        f"3. Call tool `analyze_commit_patterns(repo_path={repo_path!r}, days={days})` "
        "to characterize recent activity.\n"
        "4. Read resource `git-activity://ownership/CODEOWNERS` and join owners "
        "onto each hotspot from step 2.\n"
        "5. Produce a prioritized recommendation list: files to refactor, teams "
        "to notify, and any solo-author risks (authors of length 1 in a hotspot)."
    )
