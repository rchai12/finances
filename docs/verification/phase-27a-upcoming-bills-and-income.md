# Verify Phase 27a: upcoming bills and recurring income

Spec: `docs/phases/phase-27a-upcoming-bills-and-income.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a two-week band for income, recurring income, the expected bills and income of the next N days, `fin upcoming`, and `fin recurring --income`. Two test files were given; no migration.

These are correct and must not be reported: the band tables extended with `two_weeks` entries; one private series builder shared by charges and income.

## 1. Gates

N is `2932` when Phase 33 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 17 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_upcoming.py tests/e2e/test_cli_upcoming.py --no-cov` | exactly `17 passed` |
| `.venv/bin/python -m pytest tests/unit/test_recurring.py tests/e2e/test_cli_recurring.py tests/unit/test_insights.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.recurring --cov=finances.domain.upcoming --cov=finances.analysis.recurring --cov=finances.analysis.upcoming --cov=finances.views.recurring --cov=finances.views.upcoming --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(|timedelta" -- src/finances/cli/reports.py` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/analysis/recurring.py
 M src/finances/cli/main.py
 M src/finances/cli/reports.py
 M src/finances/domain/recurring.py
 M src/finances/views/recurring.py
?? src/finances/analysis/upcoming.py
?? src/finances/domain/upcoming.py
?? src/finances/views/upcoming.py
?? tests/e2e/test_cli_upcoming.py
?? tests/integration/test_upcoming_more.py
?? tests/unit/test_upcoming.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R8 | gates 2 and 3 | pass |
| R5, R6 (edges) | the coder's `tests/integration/test_upcoming_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the function and the given input that decides it. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `find_recurring` also tries the two-week band | ACME CLEANING charges 14 days apart | no series | a two-week series |
| 2. `expected` includes inactive series | OLD GYM (inactive) | absent | a June bill |
| 3. `expected` drops a series whose `next_day` is past | LATE BILL (next 20 May, window from 25 May) | a bill on 20 June | absent |
| 4. `recurring_income` counts refunds | FOOBAR GROCERY +$5.99 each month | no FOOBAR row | a FOOBAR income row |
| 5. The window leaves today out | `days` 1, a bill due today | the bill | nothing |

## 6. Out of scope

Each must be absent: a forecast; a web page; a migration; a two-week band for charges.
