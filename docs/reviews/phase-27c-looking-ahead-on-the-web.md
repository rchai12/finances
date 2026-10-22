# Review: Phase 27c

- Verdict: PASS
- Passed: 2997
- Findings: 0
- Approved deviations: `_days` uses `str.isdigit`; wrapped a 130-character line in `template_check.py` left by the 27c spec commit so ruff could pass
- For the architect: wrap that `template_check.py` line in the spec tree so later phases do not have to touch it

## Findings

None

Parts that needed a repair: a 130-character line in `.claude/skills/phase-architect/template_check.py` (from the 27c spec commit) split so `ruff` stays at 100 characters

Built beyond the spec: that one-line wrap; seven extra tests in `tests/integration/test_web_ahead_more.py`

## Gates

- `scripts/check.py`: `2997 passed`, `All checks passed.` (N + 14 = 2990; extra 7 coder tests)
- Given tests: `30 passed`
- Dashboard, budgets, and one-today: `35 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Thin-route search on `reports.py` and `home.py`: no output
- `git diff --stat HEAD -- tests`: only `tests/unit/test_web_split.py`, 1 line added
- Given files match the spec blocks (`ahead.html`, `test_web_ahead.py`, the three given diffs)

## Requirement checklist

- R1: `test_coming_up_on_the_dashboard`; `test_the_dashboard_window_is_seven_days`
- R2: `test_coming_up_on_the_dashboard`; `test_nothing_coming_up_on_the_dashboard`
- R3: `test_not_migrated`; `test_every_account_and_what_is_expected`
- R4: `test_refused_days`; `test_leading_zero_days_is_seven`; `test_days_are_checked_before_account`
- R5: `test_every_account_and_what_is_expected`; `test_a_shorter_window`; `test_nothing_yet`; `test_spaces_only_account_shows_every_account`
- R6: `test_one_account_day_by_day`; `test_refused_account`; `test_one_account_with_nothing_expected`; `test_an_inactive_account_is_found_through_its_link`
- R7: `test_every_account_and_what_is_expected`; `test_one_account_day_by_day`; `test_a_shorter_window`
- R4, R6 (edges): all seven tests in `tests/integration/test_web_ahead_more.py`

## Probe

None, as the guide says.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `ahead` uses `date.today()`: lowest-on is 2026-10-22, not 2026-05-25.
2. `routes/reports.py` imports `_today` by name: the same test fails (the fixture replaces `finances.web.app._today` after the app is created).
3. Expected rows come from forecast steps: PAYMENT rows appear and the Expected table no longer matches.
4. `upcoming_report` always gets 30: Bills/Income stay `-$183.99` / `$6,001.00` on `days=7`.
5. `_days` uses `int(float(...))`: `days=1.5` returns 200.
6. Account `ValueError` renders 400: both refused-account cases fail.
7. `detail.account` is the typed query: hidden field is `test checking`.
8. Dashboard `upcoming_report` uses 30: rows continue past INTEREST PAID on 2026-05-30.

## Out of scope

Absent: a chart or net worth over time; a new router module; a change to `analysis/forecast.py`, `analysis/upcoming.py`, or their views; a migration.
