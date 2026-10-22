# Review: Phase 27d

- Verdict: PASS
- Passed: 3014
- Findings: 0
- Approved deviations: `point_days` uses `months_ending` then replaces this month with today; `_days` refuses non-ASCII with `str.isascii`
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: five extra tests in `tests/integration/test_networth_more.py`

## Gates

- `scripts/check.py`: `3014 passed`, `All checks passed.` (N + 12 = 3009; extra 5 coder tests; one earlier parametrized case removed)
- Given tests: `13 passed`
- Reports, charts, ahead, and one-today: `47 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Domain import search: no output
- Thin-route search on `reports.py`: no output
- `git diff --stat HEAD -- tests`: only `tests/integration/test_web_reports.py` and `tests/integration/test_web_charts.py`, as in the given diff
- Given files match the spec blocks

## Requirement checklist

- R1: `test_days_take_only_the_digits_0_to_9`; `test_leading_zero_days_is_still_seven`
- R2: `test_one_day_a_month_ending_today`; `test_twelve_months_from_january_start_in_the_year_before`
- R3: `test_each_account_counts_its_newest_balance_on_or_before_the_day`; `test_two_balances_on_one_day_take_the_first_listed`; `test_nothing_before_the_first_balance`
- R4: `test_net_worth_over_time`; `test_a_balance_after_today_is_not_counted`; `test_two_snapshots_on_one_date_take_the_later_added`
- R5: `test_rows_and_chart`
- R6: `test_rows_and_chart`; `test_net_worth_over_time`; `test_no_balances_yet`
- R7: `test_net_worth_over_time`; `test_the_months_follow_today_not_the_month_shown`; `test_no_balances_yet`
- R2 to R4 (edges): all five tests in `tests/integration/test_networth_more.py`
- Known limit: recorded in the progress entry

## Probe

None, as the guide says.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `_days` uses `str.isdigit` alone: `٣` returns 200; `²` shows Python's invalid-literal message.
2. `point_days` keeps this month's last day: 2026-05-31, not 2026-05-25.
3. Snapshots dated on the day are skipped (`<`): April 30 no longer matches the April 30 balances.
4. The last entry on a shared date is taken: 300000, not 310000.
5. Days with nothing counted stay: a point of 0 from 0 accounts.
6. Inactive accounts are loaded: Test Old raises the May count to 4 accounts.
7. The page uses the month shown: last row 2026-03-31.
8. `json.dumps` of `None`: the chart scripts load on a page with no balances.

## Out of scope

Absent: a `fin` command for net worth over time; a dashboard block; a change to `charts.js`; a migration.
