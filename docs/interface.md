# Git Activity Analyzer — MCP Interface Design

This document is the design source of truth for the `git-activity-analyzer` MCP server.
It defines the host questions the server must answer, the underlying data sources,
and the mapping of each capability onto an MCP primitive (Resource, Tool, or Prompt).

---

## 1. Host questions

Questions a coding agent (host) should be able to answer through this server,
along with the minimum data required to answer each one.

| # | Question                                                        | Minimum required data                                                           |
|---|-----------------------------------------------------------------|---------------------------------------------------------------------------------|
| 1 | Which files are risky to change?                                | Per-file change count, distinct author count, and recent churn from the git log |
| 2 | What's the repository's ownership schema?                       | `CODEOWNERS` file (or equivalent) mapping path globs → owning teams/users       |
| 3 | What changed most in the last 30 days?                          | Commit log for the last N days, with file paths and change counts               |
| 4 | Who are the top contributors, and to which areas?               | Commits per author, files touched per author, lines added/deleted               |
| 5 | What are the recent commit patterns (frequency, size, authors)? | Commit timestamps, files-per-commit, author identities over a time window       |
| 6 | Which teams own the code that's changing most?                  | Hotspot list + CODEOWNERS mapping + team roster                                 |
| 7 | How healthy is the main branch (CI pass rate, failing stages)?  | CI/CD run history: run id, branch, stage results, timestamps                    |
| 8 | Which recent deploys touched a given service or path?           | Deployment history: environment, version, timestamp, commit SHA                 |

---

## 2. Data sources

The server draws on the following data sources. Data can come from `.git` locally
(via GitPython) or from external APIs; sensitive values may be mocked with placeholders.

- **Git commit logs** — authors, timestamps, messages, diffs (via GitPython on `.git`)
- **File change history** — frequency and recency of modifications per path
- **Author contributions** — lines added/deleted, files touched, commit counts per author
- **CI/CD build history** — pipeline runs, stages, pass/fail status (GitHub Actions / GitLab CI / internal)
- **Team structure** — team roster, roles, membership (placeholder / internal directory)
- **Repository ownership** — `CODEOWNERS` file, review policies
- **Deployment history** — environment, version, timestamp, commit SHA (internal dashboard placeholder)

For the reference implementation, git-derived data uses GitPython against a local
clone; team, CI, and deployment data are served from mock fixtures
(`mock_git_utils.py`, `SAMPLE_COMMITS`) to avoid exposing sensitive info.

---

## 3. Capability → MCP primitive mapping

Each capability is mapped to exactly one MCP primitive:

- **Resource** → static/read-only data addressable by a stable URI
- **Tool** → parameterized operation that computes or returns results
- **Prompt** → guided workflow that orchestrates one or more tools

### 3.1 Resources (≥ 3)

Stable URIs use the `git-activity://` scheme.

| URI                                   | Description                                                                          | Backing data           |
|---------------------------------------|--------------------------------------------------------------------------------------|------------------------|
| `git-activity://summary/{repo_path}`  | High-level repo summary: commit count, active authors, top-changed files, date range | Git commit log         |
| `git-activity://teams/backend`        | Roster and roles for the `backend` team                                              | Team structure fixture |
| `git-activity://ownership/CODEOWNERS` | Parsed CODEOWNERS mapping: path glob → owners                                        | `CODEOWNERS` file      |

### 3.2 Tools (≥ 2, both required)

Both tools accept `repo_path` and validate it via `security.validate_repo_path`.

#### `analyze_hotspots(repo_path, days=30, branch=None)`

Identifies files that change often and are touched by many authors — candidates
for refactoring or extra review scrutiny.

**Input schema (JSON Schema):**

```json
{
  "name": "analyze_hotspots",
  "description": "Identify risky/hotspot files based on change frequency and author diversity.",
  "parameters": {
    "type": "object",
    "properties": {
      "repo_path": {
        "type": "string",
        "description": "Absolute path to a Git repository (must be in allowed_repos.json)."
      },
      "days": {
        "type": "integer",
        "description": "Look-back window in days.",
        "default": 30,
        "minimum": 1
      },
      "branch": {
        "type": ["string", "null"],
        "description": "Branch to analyze. Defaults to the repo's default branch.",
        "default": null
      }
    },
    "required": ["repo_path"]
  }
}
```

**Output contract:** non-empty `list` of records:

```json
[
  {
    "file": "src/api/users.py",
    "authors": ["alice", "bob", "carol"],
    "changes": 27,
    "risk_score": 84
  }
]
```

- `file` — string, path relative to the repo root
- `authors` — list of author identifiers who changed the file in the window
- `changes` — integer, number of commits touching the file
- `risk_score` — **integer** in `[0, 100]`, derived from change count × author diversity × recency

#### `analyze_commit_patterns(repo_path, days=30, author=None)`

Aggregates commit behavior over a time window — useful for spotting churn spikes,
solo-author risk, or oversized commits.

**Input schema (JSON Schema):**

```json
{
  "name": "analyze_commit_patterns",
  "description": "Summarize commit patterns (volume, size, authorship) over a time window.",
  "parameters": {
    "type": "object",
    "properties": {
      "repo_path": {
        "type": "string",
        "description": "Absolute path to a Git repository (must be in allowed_repos.json)."
      },
      "days": {
        "type": "integer",
        "description": "Look-back window in days.",
        "default": 30,
        "minimum": 1
      },
      "author": {
        "type": ["string", "null"],
        "description": "Optional filter — restrict analysis to a single author.",
        "default": null
      }
    },
    "required": ["repo_path"]
  }
}
```

**Output contract:** `dict` with:

- `total_commits` — integer, number of commits in the window (matches `SAMPLE_COMMITS` fixture, expected `== 4`)
- `avg_files_per_commit` — number, mean files touched per commit
- `authors` — list of unique author identifiers seen in the window

Example:

```json
{
  "total_commits": 4,
  "avg_files_per_commit": 2.5,
  "authors": ["alice", "bob", "carol"]
}
```

#### Extra tool (optional): `list_recent_deploys(repo_path, env=None, limit=10)`

Returns recent deployment records `{ env, version, commit_sha, timestamp }` for
cross-referencing hotspots with production changes.

### 3.3 Prompt template (≥ 1)

#### `repo_health_review`

A guided workflow the host can invoke to produce a repository health report.
It orchestrates the mandatory tools and the CODEOWNERS resource.

**Workflow steps:**

1. Read `git-activity://summary/{repo_path}` for baseline stats.
2. Call `analyze_hotspots(repo_path, days=30)` to identify risky files.
3. Call `analyze_commit_patterns(repo_path, days=30)` to characterize recent activity.
4. Read `git-activity://ownership/CODEOWNERS` and join owners onto each hotspot.
5. Produce a prioritized recommendation list: files to refactor, teams to notify,
   and any solo-author risks.

**Arguments:** `repo_path` (required), `days` (optional, default 30).

---

## 4. Security & access control

- `config/allowed_repos.json` lists absolute paths that may be analyzed.
- `security.validate_repo_path(path)` rejects any repo not covered by that list
  with an error message containing `"not inside any allowed"`.
- `security.validate_file_path(repo, relpath)` blocks `../` traversal
  (error message contains `"traversal"`) and returns the joined `repo/relpath`
  when safe.
- SSE transport (if enabled) must enforce an API key / JWT header, or carry a
  documented `TODO` in the middleware for auth.
