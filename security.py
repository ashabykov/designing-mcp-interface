"""Security helpers: repo allow-list and file-path traversal protection.

Enforced everywhere `repo_path` or `file_path` cross the MCP boundary. Kept
free of side effects so tools and tests can call them directly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

_CONFIG_PATH = Path(__file__).parent / "config" / "allowed_repos.json"


def _load_allowed_repos() -> list[str]:
    if not _CONFIG_PATH.exists():
        return []
    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("allowed_repos", []))


def _is_inside(child: str, parent: str) -> bool:
    try:
        child_abs = os.path.abspath(child)
        parent_abs = os.path.abspath(parent)
    except (TypeError, ValueError):
        return False
    if child_abs == parent_abs:
        return True
    return child_abs.startswith(parent_abs.rstrip(os.sep) + os.sep)


def validate_repo_path(repo_path: str, allowed: Iterable[str] | None = None) -> str:
    """Return the normalized repo_path if it lives inside an allowed root.

    Raises ValueError otherwise. The error message contains the substring
    ``"not inside any allowed"`` so callers can pattern-match on it.
    """
    if not isinstance(repo_path, str) or not repo_path:
        raise ValueError("repo_path must be a non-empty string")

    roots = list(allowed) if allowed is not None else _load_allowed_repos()
    for root in roots:
        if _is_inside(repo_path, root):
            return os.path.abspath(repo_path)

    raise ValueError(
        f"repo_path {repo_path!r} is not inside any allowed repository root"
    )


def validate_file_path(repo: str, file_path: str) -> str:
    """Join ``repo`` and ``file_path`` after blocking ``..`` traversal.

    Returns the joined path (as ``repo/file_path``-style string) when safe.
    Raises ValueError with a message containing ``"traversal"`` otherwise.
    """
    if not isinstance(repo, str) or not repo:
        raise ValueError("repo must be a non-empty string")
    if not isinstance(file_path, str):
        raise ValueError("file_path must be a string")

    if os.path.isabs(file_path):
        raise ValueError(
            f"path traversal blocked: absolute file_path {file_path!r} not allowed"
        )

    parts = file_path.replace("\\", "/").split("/")
    if any(part == ".." for part in parts):
        raise ValueError(
            f"path traversal blocked: {file_path!r} contains '..' segments"
        )

    repo_abs = os.path.abspath(repo)
    joined_abs = os.path.abspath(os.path.join(repo_abs, file_path))
    if not (joined_abs == repo_abs or joined_abs.startswith(repo_abs + os.sep)):
        raise ValueError(
            f"path traversal blocked: {file_path!r} escapes {repo!r}"
        )

    # Return in the "repo/relpath" shape the checklist expects
    # (e.g. validate_file_path("repo", "src/main.py") -> "repo/src/main.py").
    rel = file_path.lstrip("/")
    return f"{repo.rstrip('/')}/{rel}"
