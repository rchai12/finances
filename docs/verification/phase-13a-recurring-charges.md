# Verify Phase 13a: recurring charges

Spec: `docs/phases/phase-13a-recurring-charges.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added the rules that find regular charges (pure), a loader in `analysis`, rows in `views`, and `fin recurring`. Two test files were given; no migration.

These are correct and must not be reported: `Fraction` or integer arithmetic for the monthly cost; a table of bands as a dictionary or a tuple; the day clipping done with `calendar.monthrange`.

## 1. Gates

N is `2449` when Phase 12c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 33 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_recurring.py tests/e2e/test_cli_recurring.py --no-cov` | exactly `33 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.recurring --cov=finances.analysis.recurring --cov=finances.views.recurring --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(|timedelta|find_recurring\(" -- src/finances/cli/reports.py` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/cli/main.py
 M src/finances/cli/reports.py
?? src/finances/analysis/recurring.py
?? src/finances/domain/recurring.py
?? src/finances/views/recurring.py
?? tests/e2e/test_cli_recurring.py
?? tests/integration/test_recurring_report.py
?? tests/unit/test_recurring.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R4, R6, R7 | gate 2 | passes |
| R5 | the coder's `tests/integration/test_recurring_report.py` | each item of the spec's "Tests to write" has a test |
| R1 | read `monthly_cost` | no `float`, no `/` on floats; half-up rounding |
| R5 | read `recurring_charges` | flows come from Phase 12a's `load_flows`; no second definition of spending |

## 4. Probe

None: the given tests cover every cadence, the split by amount, and the cut-off day. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. A year needs 3 charges, like the others.
2. The split by amount is tried even when the merchant's charges together are a series.
3. `active` uses the nominal step (the next charge day) instead of the band's top.
4. The monthly cost rounds down.
5. Transfers are counted as charges.

## 6. Out of scope

Each must be absent: a migration; a web page; a stored list of subscriptions; findings.
