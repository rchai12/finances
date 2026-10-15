# Verify Phase 12a: spending

Spec: `docs/phases/phase-12a-spending.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added the spending rules (pure), a loader and report in `analysis`, rows in `views`, and `fin spending`. Two test files were given; no migration.

These are correct and must not be reported: loading categories, pairs, and accounts with several queries; a dictionary or `Counter` for grouping; reading `--month` as text and parsing it in `domain`.

## 1. Gates

N is `2342` when Phase 11d was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 43 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_spending.py tests/e2e/test_cli_spending.py --no-cov` | exactly `43 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.spending --cov=finances.analysis.spending --cov=finances.views.spending --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|flow_kind|spending_lines|summarize|sum\(|sorted\(" -- src/finances/cli/reports.py` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/cli/main.py
 M src/finances/db/repositories.py
?? src/finances/analysis/spending.py
?? src/finances/cli/reports.py
?? src/finances/domain/spending.py
?? src/finances/views/spending.py
?? tests/e2e/test_cli_spending.py
?? tests/integration/test_spending_report.py
?? tests/unit/test_spending.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R5, R9 to R11 | gate 2 | passes |
| R6 to R8, R10 (no options) | the coder's `tests/integration/test_spending_report.py` | each item of the spec's "Tests to write" has a test |
| R6 | read `list_transactions_between` | `coalesce` of the two dates, pending left out, no dialect-specific SQL |
| R12 | read `cli/reports.py` | no sums, sorting, or kind checks |

## 4. Probe

None: the given end-to-end tests run every rule through the real database. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. Paired transactions count as spending.
2. Refunds are left out instead of netted.
3. The month is decided by the posted date.
4. Pending transactions are counted.
5. A tie between two lines keeps the order the flows came in.

## 6. Out of scope

Each must be absent: a migration; balances or net worth; a web page; a change to categories, rules, or pairs.
