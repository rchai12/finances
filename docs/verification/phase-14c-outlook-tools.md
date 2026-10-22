# Verify Phase 14c: the agent's outlook tools

Spec: `docs/phases/phase-14c-outlook-tools.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added five read-only MCP tools (`get_insights`, `get_recurring`, `get_upcoming`, `get_forecast`, `get_budgets`), each wrapping one existing report, and their descriptions. One test file and a diff to three earlier test files were given; no migration.

These are correct and must not be reported: a private helper that reads the `month` argument; the sign written as a multiplier; the tools in a different order in `tools.py` as long as they register after 14b's.

## 1. Gates

N is `3182` when Phase 14b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 16 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_mcp_outlook.py --no-cov` | exactly `16 passed` |
| `.venv/bin/python -m pytest tests/integration/test_mcp_accounts.py tests/integration/test_mcp_more.py tests/integration/test_mcp_spending.py tests/e2e/test_cli_mcp.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(views|web|cli)" -- src/finances/mcp_server` | no output |
| `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py` | no output |
| `git diff --stat HEAD -- tests` | the three files of the given diff |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/mcp_server/server.py
 M src/finances/mcp_server/tools.py
 M tests/integration/test_mcp_accounts.py
 M tests/integration/test_mcp_more.py
 M tests/integration/test_mcp_spending.py
?? tests/integration/test_mcp_outlook.py
?? tests/integration/test_mcp_outlook_more.py
```

The diff of the three earlier test files equals the spec's; the five descriptions equal the spec's text.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R7 | gates 1 to 7 | pass |
| R1 to R5 (edges) | the coder's `tests/integration/test_mcp_outlook_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `get_recurring` keeps every series | `test_stopped_charges_only_when_asked`, first call | `[]` | OLD GYM |
| 2. `get_recurring` ignores `include_inactive` | the same, second call | OLD GYM | `[]` |
| 3. `get_recurring` leaves charges unsigned | `test_recurring_charges_are_negative` | -12000 | 12000 |
| 4. `get_recurring` signs income negative too | `test_recurring_income_is_positive` | 300000 | -300000 |
| 5. `get_insights` keeps an empty subject as `""` | `test_insights` (interest) | `None` | `""` |
| 6. `get_forecast` drops the `account` argument | `test_one_account_forecast` | one account | three |
| 7. `get_upcoming` uses `date.today()` | `test_upcoming` | starts 2026-05-25 | the real day |
| 8. `get_forecast` lets the `ValueError` through | `test_refusals[get_forecast-...Nope...]` | `...: account not found` | `Error executing tool get_forecast` |

## 6. Out of scope

Each must be absent: a data coverage or `find_merchants` tool; a work-queue tool; a change to `analysis`, `views`, `web`, or `cli`; a write.
