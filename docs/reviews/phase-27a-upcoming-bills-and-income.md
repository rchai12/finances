# Review: Phase 27a

- Verdict: PASS
- Passed: 2954
- Findings: 0
- Approved deviations: charges and income share `_find` / `_series`; `two_weeks` lives in the shared band tables
- For the architect: none

## Findings

None

Parts that needed a repair: `find_recurring_income` docstring shortened by one word so the line stays at 100 characters

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2954 passed`, `All checks passed.` (N + 17 = 2949; extra 5 coder tests)
- Given tests: `17 passed`
- Phase 13a and insights: all passed
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Domain import search: no output
- Thin-CLI search on `reports.py`: no output
- Given files match the spec blocks

## Requirement checklist

- R1: `test_income_has_a_two_week_band`; `test_income_ignores_money_out_and_charges_ignore_the_new_band`; 13a tests still pass
- R2: `test_a_paycheck_every_two_weeks`; `test_pay_on_the_15th_and_the_last_day_counts_as_every_two_weeks`
- R3: `test_income_has_a_two_week_band`
- R4: `test_expected_bills_and_income_in_a_window`; `test_the_window_counts_today_as_its_first_day`; `test_nothing_expected`
- R5: `test_recurring_income`; `test_uncategorized_income_is_counted`; `test_a_paired_transfer_is_not_income`
- R6: `test_the_next_30_days`; `test_a_quarterly_bill_in_the_window`
- R7: `test_the_next_30_days`; `test_nothing_expected`; `test_recurring_income`
- R8: `test_the_next_30_days`; `test_a_window_out_of_range`; `test_upcoming_without_as_of_uses_today`; `test_stopped_income_is_listed_only_with_all`
- R5, R6 (edges): all five tests in `tests/integration/test_upcoming_more.py`

## Probe

None, as the guide says.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `find_recurring` also tries the two-week band: ACME CLEANING 14 days apart becomes a `two_weeks` series.
2. `expected` includes inactive series: OLD GYM appears as a 1 June bill.
3. `expected` drops a series whose `next_day` is past: LATE BILL on 20 June is absent.
4. `recurring_income` counts refunds: FOOBAR GROCERY is an income row.
5. The window leaves today out: days 1, a bill due today, yields nothing.

## Out of scope

Absent: a forecast; a web page; a migration; a two-week band for charges (`CADENCES` is still week, month, quarter, year).
