# Review: Phase 27b

- Verdict: PASS
- Passed: 2976
- Findings: 0
- Approved deviations: `walk` totals in and out with two independent sign checks; a private helper picks one account's charges and credits from the loaded flows
- For the architect: none

## Findings

None

Parts that needed a repair: an `if`/`elif` on the item's sign left a zero-amount branch uncovered; two independent checks reach 100% with the given bills and paychecks

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2976 passed`, `All checks passed.` (N + 16 = 2970; extra 6 coder tests)
- Given tests: `16 passed`
- Phase 27a and recurring: `25 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Domain import search: no output
- Thin-CLI search on `reports.py`: no output
- Given files match the spec blocks

## Requirement checklist

- R1: `test_a_dip_before_payday`; `test_the_start_is_the_lowest_when_nothing_dips`; `test_a_tie_keeps_the_earliest_day`; `test_nothing_expected`
- R2: `test_every_account`; `test_one_account_day_by_day`; `test_a_recurring_refund_is_not_income`; `test_a_pending_charge_is_left_out`
- R3: `test_a_balance_after_the_start_is_not_used`; `test_a_refused_account`
- R4: `test_every_account`; `test_two_accounts_without_a_balance_are_named_in_order`
- R5: `test_one_account_day_by_day`; `test_a_refused_account`; `test_an_inactive_account_is_left_out_of_the_summary_but_found_by_name`
- R6: `test_every_account`; `test_one_account_with_nothing_expected`
- R7: `test_every_account`; `test_nothing_to_forecast`; `test_forecast_without_as_of_uses_today`
- R8: `test_one_account_day_by_day`; `test_a_refused_account`; `test_a_window_out_of_range`
- R4, R5 (edges): all six tests in `tests/integration/test_forecast_more.py`

## Probe

None, as the guide says.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Bills take `SPENDING` only: Checking out is `-$120.00`.
2. Income leaves out `TRANSFER`: Card in is `$0.00`.
3. Series found over every account's flows: BAZ BOX appears in the checking detail.
4. The lowest point starts from the first step: Test Savings lowest is `$1,001.00` on 2026-05-30.
5. `walk` replaces the lowest on a tie (`<=`): 2026-05-28.
6. `latest_balance` used for the start: Savings shows `$2,000.00`.
7. An account without a balance forecast from 0: a Test Brokerage row.

## Out of scope

Absent: a web page or chart; a migration; a household total; a change to `fin upcoming`.
