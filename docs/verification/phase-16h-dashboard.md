# Verify Phase 16h: dashboard

Spec: `docs/phases/phase-16h-dashboard.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder made `/` a read-only Home page built from the balances, months, findings, data health, and counts of Phases 12b, 13b, 25, and 11. Two templates, one test file, and the removal of one earlier test were given; no migration.

These are correct and must not be reported: `func.count()` over the same conditions as `list_uncategorized`; slicing the finding rows in the route.

## 1. Gates

N is `2791` when Phase 25 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 5 - 1 passed (one earlier test was removed), 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_dashboard.py --no-cov` | exactly `5 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_pages.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.analysis --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|timedelta|sum\(" -- src/finances/web` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/db/repositories.py
 M src/finances/web/app.py
 M src/finances/web/templates/layout.html
 M tests/integration/test_web_pages.py
?? src/finances/analysis/dashboard.py
?? src/finances/web/templates/dashboard.html
?? tests/integration/test_dashboard_more.py
?? tests/integration/test_web_dashboard.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R2 to R4 | gate 2 | passes |
| R1, R2 (January), links | the coder's `tests/integration/test_dashboard_more.py` | each item of the spec's "Tests to write" has a test |
| test change | `git diff HEAD -- tests/integration/test_web_pages.py` | exactly the spec's diff |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the given input that decides it: the correct code and the broken code give different results there. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. The page shows every finding, not the first three | May has four findings | three rows; `frequent_small` absent | four rows |
| 2. The uncategorized count includes paired transactions | the card payment pair (two uncategorized legs) | `6 transactions without a category.` | `8 ...` |
| 3. Transfers waiting counts pairs, not suggestions | one pair and two suggestions | `2 transfers waiting for review.` | `1 ...` |
| 4. The months end with last month | today is 25 May | April and May | March and April |
| 5. The health problems ignore the backup folder | a backup taken today | `No data problems found.` | the backup row |

## 6. Out of scope

Each must be absent: charts or JavaScript; a `POST` route; changes to reports, findings, or health.
