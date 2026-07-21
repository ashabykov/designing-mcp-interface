"""Analysis primitives: hotspots and commit patterns.

Both functions accept any repository object with ``get_commits(days)`` and
``get_changed_files(commit)``. For tests we default to
:class:`mock_git_utils.MockGitRepository`, so callers can invoke the analysis
without needing a real `.git` directory.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from mock_git_utils import MockGitRepository


RepoFactory = Callable[[str], Any]


def _default_repo_factory(repo_path: str) -> Any:
    return MockGitRepository(repo_path)


def analyze_hotspots(
    repo_path: str,
    days: int = 30,
    branch: str | None = None,
    *,
    repo_factory: RepoFactory = _default_repo_factory,
) -> list[dict[str, Any]]:
    """Return a non-empty list of hotspot records.

    Each record contains ``file``, ``authors``, ``changes`` (int), and
    ``risk_score`` (int). Score is a bounded integer in [0, 100] combining
    change frequency and author diversity.
    """
    repo = repo_factory(repo_path)
    commits = repo.get_commits(days=days)

    changes_by_file: dict[str, int] = defaultdict(int)
    authors_by_file: dict[str, list[str]] = defaultdict(list)

    for commit in commits:
        files = repo.get_changed_files(commit)
        author = commit.author.email
        for f in files:
            changes_by_file[f] += 1
            if author not in authors_by_file[f]:
                authors_by_file[f].append(author)

    results: list[dict[str, Any]] = []
    for f, count in changes_by_file.items():
        author_count = len(authors_by_file[f])
        # Simple bounded score: weight changes and author diversity.
        raw = (count * 10) + (author_count * 15)
        risk_score = int(max(0, min(100, raw)))
        results.append(
            {
                "file": f,
                "authors": list(authors_by_file[f]),
                "changes": int(count),
                "risk_score": risk_score,
            }
        )

    results.sort(key=lambda r: r["risk_score"], reverse=True)

    if not results:
        # Guarantee a non-empty list per the interface contract.
        results.append(
            {
                "file": "<none>",
                "authors": [],
                "changes": 0,
                "risk_score": 0,
            }
        )

    if branch:
        for r in results:
            r["branch"] = branch

    return results


def analyze_commit_patterns(
    repo_path: str,
    days: int = 30,
    author: str | None = None,
    *,
    repo_factory: RepoFactory = _default_repo_factory,
) -> dict[str, Any]:
    """Return a summary dict with ``total_commits``, ``avg_files_per_commit``, ``authors``."""
    repo = repo_factory(repo_path)
    commits = repo.get_commits(days=days)

    if author:
        commits = [c for c in commits if c.author.email == author]

    total_commits = len(commits)
    total_files = sum(len(repo.get_changed_files(c)) for c in commits)
    avg_files = (total_files / total_commits) if total_commits else 0.0

    authors: list[str] = []
    for c in commits:
        if c.author.email not in authors:
            authors.append(c.author.email)

    return {
        "total_commits": total_commits,
        "avg_files_per_commit": round(avg_files, 2),
        "authors": authors,
    }
