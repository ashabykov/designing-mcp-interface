"""Thin GitPython adapter used by the analysis layer.

Exposes the same shape as :class:`mock_git_utils.MockGitRepository` so tools
can swap between real and mock backends without branching.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

try:
    from git import Repo  # type: ignore
except Exception:  # pragma: no cover - gitpython may not be importable at test time
    Repo = None  # type: ignore


@dataclass
class Author:
    email: str


@dataclass
class Commit:
    author: Author
    changed_files: list[str]
    committed_datetime: datetime


class GitRepository:
    """Read commits from a local `.git` directory via GitPython."""

    def __init__(self, path: str):
        if Repo is None:
            raise RuntimeError("gitpython is not available")
        self.path = path
        self._repo = Repo(path)

    def get_commits(self, days: int, branch: str | None = None) -> list[Commit]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rev = branch or self._repo.head.ref.name
        out: list[Commit] = []
        for c in self._repo.iter_commits(rev):
            when = c.committed_datetime
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when < since:
                continue
            files = list(c.stats.files.keys()) if c.parents else []
            out.append(
                Commit(
                    author=Author(email=c.author.email or "unknown"),
                    changed_files=files,
                    committed_datetime=when,
                )
            )
        return out

    def get_changed_files(self, commit: Commit) -> list[str]:
        return list(commit.changed_files)


def iter_authors(commits: Iterable[Commit]) -> list[str]:
    seen: list[str] = []
    for c in commits:
        if c.author.email not in seen:
            seen.append(c.author.email)
    return seen
