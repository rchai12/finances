# Verify Phase 16e: find and drill down

Spec: `docs/phases/phase-16e-find-and-drill-down.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a transaction search built on Phase 12a's flows, new filters and a Category column on the Transactions page, and links from the Reports and Insights pages to the transactions behind each line. Three templates, one test file, and a change to `tests/integration/test_web_pages.py` were given; no migration.

These are correct and must not be reported: filtering in Python after one query; the `kind` and person checks living in `analysis/search.py`; `flows_for` taking a list.

## 1. Gates

N is `2533` when Phase 13c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 28 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_search.py --no-cov` | exactly `28 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_pages.py tests/integration/test_web_reports.py tests/integration/test_web_insights.py tests/e2e/test_cli_spending.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.analysis --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|casefold|flow_kind|clean_merchant" -- src/finances/web` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/analysis/spending.py
 M src/finances/db/repositories.py
 M src/finances/domain/spending.py
 M src/finances/views/transactions.py
 M src/finances/web/app.py
 M src/finances/web/templates/insights.html
 M src/finances/web/templates/reports.html
 M src/finances/web/templates/transactions.html
 M tests/integration/test_web_pages.py
?? src/finances/analysis/search.py
?? tests/integration/test_transaction_search.py
?? tests/integration/test_web_search.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1, R4 to R9 | gates 2 and 3 | pass |
| R2, R3, R4 (messages and order) | the coder's `tests/integration/test_transaction_search.py` | each item of the spec's "Tests to write" has a test |
| R3 | read `load_flows` and `flows_for` | one place builds a `Flow`; `load_flows` calls it |
| test change | `git diff HEAD -- tests/integration/test_web_pages.py` | exactly the spec's diff |

## 4. Probe

None: `test_every_line_opens_exactly_its_transactions` drives every grouping through the real pages. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. From and To compare the posted date again.
2. Pending transactions get the kind `spending` in the search.
3. The `merchant` filter matches part of the merchant instead of all of it.
4. A link filter (`group`) is dropped from the form after Show.
5. `fin transactions list` gains the Category column.

## 6. Out of scope

Each must be absent: a change to `cli/`; a migration; JavaScript; a change to how any report counts.
