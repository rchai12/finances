# Verify Phase 14b: the agent's transaction and spending tools

Spec: `docs/phases/phase-14b-transactions-and-spending-tools.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added three read-only MCP tools (`list_transactions`, `get_spending`, `month_over_month`), each wrapping one existing function, and their descriptions. One test file and a diff to two earlier test files were given; no migration.

These are correct and must not be reported: a private helper that turns one found transaction into a dict; the account names read once per call; the `by` choices written as a `Literal` alias.

## 1. Gates

N is `3145` when Phase 35b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 27 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_mcp_spending.py --no-cov` | exactly `27 passed` |
| `.venv/bin/python -m pytest tests/integration/test_mcp_accounts.py tests/integration/test_mcp_more.py tests/e2e/test_cli_mcp.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(views|web|cli)" -- src/finances/mcp_server` | no output |
| `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py` | no output |
| `git diff --stat HEAD -- tests` | the two files of the given diff |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/mcp_server/server.py
 M src/finances/mcp_server/tools.py
 M tests/integration/test_mcp_accounts.py
 M tests/integration/test_mcp_more.py
?? tests/integration/test_mcp_spending.py
?? tests/integration/test_mcp_spending_more.py
```

The diff of the two earlier test files equals the spec's; the three descriptions equal the spec's text.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R6 | gates 1 to 7 | pass |
| R1 to R4 (edges) | the coder's `tests/integration/test_mcp_spending_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

Run Phase 14a's stdio probe (its guide, section 4) unchanged, except that its tool list check now expects six names; report the line it prints. Expected otherwise: the three other checks `ok`.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `next_offset` set whenever the page is full, not when more were found | `test_pages`, last page (limit 3, offset 6: exactly the last three) | `None` | 9 |
| 2. `refund` from the sign alone (any money in) | `test_every_transaction_latest_first` | only id 2 | ids 9, 6, 4, 2 |
| 3. `get_spending`'s `spent_cents` is the net | `test_spending_this_month_by_category` | 2599 | 2000 |
| 4. `get_spending` defaults to `date.today()`'s month | the same | `2026-05-01` | the real month |
| 5. `month_over_month` ignores `month` and ends this month | `test_month_over_month_ends_with_the_month_given` | 2026-03, 2026-04 | 2026-04, 2026-05 |
| 6. `list_transactions` checks `start` after `end` only inside the search | `test_refusals` (start after end) | the fixed message | no error (the search returns nothing) |

## 6. Out of scope

Each must be absent: a findings, budget, or coverage tool; a change to `analysis`, `views`, `web`, or `cli`; a write of any kind.
