# Verify Phase 27d: net worth over time

Spec: `docs/phases/phase-27d-net-worth-over-time.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder fixed the Ahead page's days check (ASCII digits only) and added net worth over time: pure month-end days and points, a loader, rows, a line chart, and a section on the Reports page. The page change and two earlier test changes were given as a diff; no migration.

These are correct and must not be reported: a regular expression or a character check for R1; `net_worth_chart` beside the other charts in `views/charts.py`; the 12 written as a default of `net_worth_over_time` rather than at the route.

## 1. Gates

N is `2997` when Phase 27c was the last phase built. The given diff removes one parametrized case, so the suite grows by at least 12.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 12 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_networth.py tests/integration/test_web_net_worth.py --no-cov` | exactly `13 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_reports.py tests/integration/test_web_charts.py tests/integration/test_web_ahead.py tests/integration/test_one_today.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.networth --cov=finances.analysis.networth --cov=finances.views.networth --cov=finances.views.charts --cov=finances.web.routes.reports --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "sum\(|sorted\(|timedelta|select\(|session\.(add|execute|delete)" -- src/finances/web/routes/reports.py` | no output |
| `git diff --stat HEAD -- tests` | only `tests/integration/test_web_reports.py` and `tests/integration/test_web_charts.py`, as in the given diff |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/views/charts.py
 M src/finances/web/routes/reports.py
 M src/finances/web/templates/reports.html
 M tests/integration/test_web_charts.py
 M tests/integration/test_web_reports.py
?? src/finances/analysis/networth.py
?? src/finances/domain/networth.py
?? src/finances/views/networth.py
?? tests/integration/test_networth_more.py
?? tests/integration/test_web_net_worth.py
?? tests/unit/test_networth.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R7 | gates 2 and 3 | pass |
| R2 to R4 (edges) | the coder's `tests/integration/test_networth_more.py` | each item of the spec's "Tests to write" has a test |
| Known limit | the progress entry | recorded |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the function and the given input that decides it. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `_days` back to `str.isdigit` alone | `test_days_take_only_the_digits_0_to_9` | 400 and the days message | 200 for `٣`; Python's message for `²` |
| 2. `point_days` gives this month's last day, not today | `test_one_day_a_month_ending_today[...2026-05-25...]` | last day 2026-05-25 | 2026-05-31 |
| 3. `net_worth_points` counts entries dated strictly before the day (`<`) | `test_each_account_counts_its_newest_balance_on_or_before_the_day` | 2026-04-30: 220000 from 2 accounts | 200000 from 1 |
| 4. `net_worth_points` takes the last entry on a shared date | `test_two_balances_on_one_day_take_the_first_listed` | 310000 | 300000 |
| 5. `net_worth_points` keeps days with nothing counted | `test_nothing_before_the_first_balance` | `[]` | a point of 0 from 0 accounts |
| 6. `net_worth_over_time` reads inactive accounts too | `test_net_worth_over_time` (Test Old, closed, $5,000.00 from 2026-01-31) | first row 2026-03-31, $2,000.00, 1 | rows from 2026-01-31 |
| 7. The page takes its days from the month shown | `test_the_months_follow_today_not_the_month_shown` | last row 2026-05-25 | 2026-03-31 |
| 8. The route passes `json.dumps(net_worth_chart(...))` always, so no points give the text `null` | `test_no_balances_yet` | no `<script` | the scripts |

## 6. Out of scope

Each must be absent: a `fin` command for net worth; a dashboard block; a change to `charts.js`; a migration.
