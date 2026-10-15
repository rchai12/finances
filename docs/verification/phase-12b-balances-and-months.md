# Verify Phase 12b: balances and months

Spec: `docs/phases/phase-12b-balances-and-months.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added month periods and coverage (pure), `account_data_span`, a balance report and a month report in `analysis`, their rows in `views`, and `fin balances` and `fin months`. Two test files were given; no migration.

These are correct and must not be reported: `account_data_span` as several queries or one; `month_report` loading flows once per month; the change computed in `views`.

## 1. Gates

N is `2403` when Phase 12a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 17 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_periods.py tests/e2e/test_cli_balances_months.py --no-cov` | exactly `17 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.periods --cov=finances.analysis.balances --cov=finances.analysis.months --cov=finances.views.balances --cov=finances.views.months --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(|timedelta|uncovered\(" -- src/finances/cli/reports.py` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/cli/main.py
 M src/finances/cli/reports.py
 M src/finances/db/repositories.py
?? src/finances/analysis/balances.py
?? src/finances/analysis/months.py
?? src/finances/domain/periods.py
?? src/finances/views/balances.py
?? src/finances/views/months.py
?? tests/e2e/test_cli_balances_months.py
?? tests/integration/test_balances_months.py
?? tests/unit/test_periods.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1, R2, R6 to R9 | gate 2 | passes |
| R3 to R5, R9 (no `--to`) | the coder's `tests/integration/test_balances_months.py` | each item of the spec's "Tests to write" has a test |
| R3 | read `account_data_span` | statement periods, non-pending transaction days (`coalesce`), and pull dates; no dialect-specific SQL |
| R5 | read `month_report` | spent and income come from Phase 12a's `summarize` and `load_flows`, not a second definition |
| R10 | read `cli/reports.py` | no sums, date arithmetic, or coverage checks |

## 4. Probe

None: the given end-to-end tests run both reports through the real database. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. `account_data_span` ignores feed pulls.
2. Net worth leaves out credit cards.
3. The change is the previous month minus this one.
4. An account with no data is treated as covering every month.
5. `balance_report` includes inactive accounts.

## 6. Out of scope

Each must be absent: a migration; balances worked forward from transactions; a web page; checks for gaps between statements.
