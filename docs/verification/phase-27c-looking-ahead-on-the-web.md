# Verify Phase 27c: looking ahead on the web

Spec: `docs/phases/phase-27c-looking-ahead-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a read-only page `/ahead` (27b's forecast and 27a's expected items, or one account day by day) in `routes/reports.py`, and a "Coming up" block on the dashboard. The page template and a diff (dashboard, menu, the route list in `tests/unit/test_web_split.py`) were given; no migration.

These are correct and must not be reported: a private helper in `routes/reports.py` that reads `days`; checking the digits with `str.isdigit` or a regular expression, as long as R4's five refused values are refused; `upcoming` placed before `budgets` in `Dashboard`.

## 1. Gates

N is `2976` when Phase 27b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 14 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_ahead.py tests/unit/test_web_split.py --no-cov` | exactly `30 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_dashboard.py tests/integration/test_dashboard_more.py tests/integration/test_web_budgets.py tests/integration/test_web_budgets_more.py tests/integration/test_one_today.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.dashboard --cov=finances.web.routes.reports --cov=finances.web.routes.home --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "sum\(|sorted\(|timedelta|select\(|session\.(add|execute|delete)" -- src/finances/web/routes/reports.py src/finances/web/routes/home.py` | no output |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_web_split.py`, 1 line added |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/analysis/dashboard.py
 M src/finances/web/routes/home.py
 M src/finances/web/routes/reports.py
 M src/finances/web/templates/dashboard.html
 M src/finances/web/templates/layout.html
 M tests/unit/test_web_split.py
?? src/finances/web/templates/ahead.html
?? tests/integration/test_web_ahead.py
?? tests/integration/test_web_ahead_more.py
```

`ahead.html`, the two template changes, and the test changes match the spec's blocks exactly.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R7 | gates 2 and 3 | pass |
| R4, R6 (edges) | the coder's `tests/integration/test_web_ahead_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the function and the given input that decides it. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `ahead` calls `clock.today()` or `date.today()` instead of `web_app._today()` | `test_every_account_and_what_is_expected` | `Forecast from 2026-05-25 to 2026-06-23.` | today's real date |
| 2. `routes/reports.py` imports `_today` by name from `finances.web.app` | the same (the fixture replaces `_today` after creating the app) | 2026-05-25 | today's real date |
| 3. `ahead` builds the Expected table from the forecast's steps, not `upcoming_report` | the same | no PAYMENT rows; `Bills: -$183.99. Income: $6,001.00.` | PAYMENT TO TEST CARD and PAYMENT THANK YOU rows |
| 4. `ahead` passes 30 to `upcoming_report` whatever `days` is | `test_a_shorter_window` | `Bills: -$132.00. Income: $3,001.00.` | `Bills: -$183.99. Income: $6,001.00.` |
| 5. `ahead` reads `days` with `float` or `int` of a number with a point | `test_refused_days[1.5]` | 400 | 200 |
| 6. `ahead` renders the account's `ValueError` with 400 | `test_refused_account` | 404 | 400 |
| 7. `ahead` puts the account name as typed in `detail.account` | `test_one_account_day_by_day` (`test checking`) | hidden field `Test Checking` | `test checking` |
| 8. `dashboard` passes 30 days to `upcoming_report` | `test_coming_up_on_the_dashboard` | last row INTEREST PAID on 2026-05-30 | rows on to 2026-06-19 |

## 6. Out of scope

Each must be absent: a chart or net worth over time; a new router module; a change to `analysis/forecast.py`, `analysis/upcoming.py`, or their views; a migration.
