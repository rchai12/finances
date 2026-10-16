# Verify Phase 31: tidy

Spec: `docs/phases/phase-31-tidy.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder made every page and command read today's local date through `finances.clock.today()` (the Sync routes keep the UTC date), and removed four duplications. `clock.py`, one test file, and a change to `test_list_backups` were given; no migration.

These are correct and must not be reported: `print_rows` taking any iterable of dataclasses; the web's `_today` kept as a one-line wrapper.

## 1. Gates

N is `2887` when Phase 26b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 8 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_one_today.py --no-cov` | exactly `8 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.clock --cov=finances.cli --cov=finances.web --cov=finances.domain.budgets --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n -E "date\.today\(\)" -- src/finances` | only `src/finances/clock.py` |
| `git grep -n -E "def _print_rows|def _statement_cells|def _taken" -- src/finances/cli` | no output |
| `git grep -n "a budget must be an amount" -- src` | only `src/finances/domain/budgets.py` |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/cli/backup.py
 M src/finances/cli/budgets.py
 M src/finances/cli/categories.py
 M src/finances/cli/common.py
 M src/finances/cli/health.py
 M src/finances/cli/listing.py
 M src/finances/cli/reports.py
 M src/finances/cli/transfers.py
 M src/finances/db/repositories.py
 M src/finances/domain/budgets.py
 M src/finances/web/app.py
 M tests/e2e/test_cli_backup.py
?? src/finances/clock.py
?? tests/integration/test_one_today.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2; gate 4 | passes; only `clock.py` |
| R2 | `git diff HEAD -- src/finances/web/app.py` | the Sync routes call `_utc_today()`, which returns the UTC date as before |
| R3 to R6 | gate 1 (the earlier tests pin every output); gates 5 and 6 | pass; as expected |
| test change | `git diff HEAD -- tests/e2e/test_cli_backup.py` | exactly the spec's diff |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the place and the given input that decides it. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `fin budgets list` keeps `date.today()` | `clock.today` set to 25 May 2026 | `Budgets for 2026-05.` | the real month |
| 2. The web's `_today` keeps the UTC date | the same | `Today is 2026-05-25.` | the real date |
| 3. `fin health` keeps `date.today()` | a backup taken 24 May | `No problems found.` | a backup problem |
| 4. `from finances.clock import today` in `cli/reports.py` | the same, `fin months` | `Months from 2025-12 to 2026-05.` | the real months |
| 5. `fin backup list` keeps two columns | two empty backup files | a `Size` column, `0 B` | two columns |

## 6. Out of scope

Each must be absent: a change to `sync/`, to stored timestamps, or to any other output; the split of `web/app.py`.
