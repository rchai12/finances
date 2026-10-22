# Verify Phase 14d: the agent's work queues

Spec: `docs/phases/phase-14d-work-queues.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added five read-only MCP tools (`list_uncategorized`, `list_categories`, `list_rules`, `list_transfers`, `list_transfer_suggestions`) and their descriptions. One test file and a diff to four earlier test files were given; no migration.

These are correct and must not be reported: a private helper for the brief of a transaction; the account names read once per call; repository functions imported under other names.

## 1. Gates

N is `3203` when Phase 14c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 14 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_mcp_queues.py --no-cov` | exactly `14 passed` |
| `.venv/bin/python -m pytest tests/integration/test_mcp_accounts.py tests/integration/test_mcp_more.py tests/integration/test_mcp_spending.py tests/integration/test_mcp_outlook.py tests/e2e/test_cli_mcp.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(views|web|cli)" -- src/finances/mcp_server` | no output |
| `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py` | no output |
| `git diff --stat HEAD -- tests` | the four files of the given diff |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/mcp_server/server.py
 M src/finances/mcp_server/tools.py
 M tests/integration/test_mcp_accounts.py
 M tests/integration/test_mcp_more.py
 M tests/integration/test_mcp_outlook.py
 M tests/integration/test_mcp_spending.py
?? tests/integration/test_mcp_queues.py
?? tests/integration/test_mcp_queues_more.py
```

The diff of the four earlier test files equals the spec's; the five descriptions equal the spec's text.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R7 | gates 1 to 7 | pass |
| R1 to R5 (edges) | the coder's `tests/integration/test_mcp_queues_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `list_transfers` keeps the repository's order (oldest first) | `test_transfers_newest_pair_first`, second call | pair 2, then 1 | 1, then 2 |
| 2. `list_transfers` counts only the page in `total` | the same, `limit` 1 | `total` 2 | 1 |
| 3. `list_categories` lists the groups too | `test_categories` | 34 | 46 |
| 4. `list_uncategorized` reports the page's length as `total` | `test_uncategorized_latest_first_with_the_total` (`limit` 2) | 6 | 2 |
| 5. A tool reads with `get_engine()` instead of `reading()` | `test_a_database_that_is_not_migrated` | the fixed message | a SQL error |

## 6. Out of scope

Each must be absent: a write, a proposal, or a confirmation; a data coverage or `find_merchants` tool; a change to `analysis`, `categorize`, `views`, `web`, or `cli`.
