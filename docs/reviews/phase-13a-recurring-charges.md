# Review: Phase 13a

- Verdict: PASS
- Passed: 2490
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2490 passed`, `All checks passed.` (N + 33 = 2482; 8 more are the coder's)
- Given tests: `33 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists exactly the guide's paths, plus this review
- Given files: `tests/unit/test_recurring.py` and `tests/e2e/test_cli_recurring.py` are identical to the spec's blocks

## Requirement checklist

- R1 to R4, R6, R7: the given tests pass.
- R5: `tests/integration/test_recurring_report.py` covers each item of "Tests to write": a pending charge, a paired transfer, a charge with an income category, and a refund left out; charges after `as_of` ignored; a charge at zero or above inside a merchant's charges ignored; `fin recurring` without `--as-of` uses today.
- R1: `monthly_cost` is `(2 * amount * numerator + denominator) // (2 * denominator)`: integers only, half up.
- R5: `recurring_charges` keeps the `SPENDING` flows of Phase 12a's `load_flows` from `date.min` to `as_of`; spending is not defined again.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the tests run, and the code restored.

1. A year needs 3 charges: `test_each_cadence_and_its_monthly_cost` fails.
2. The split by amount is tried even when the whole is a series: 13 tests fail, among them `test_a_monthly_subscription` and `test_the_active_subscriptions`.
3. `active` uses the next charge day instead of the band's top: `test_active_until_the_latest_a_next_charge_could_come[as_of0-True]` fails.
4. The monthly cost rounds down: three cases of `test_monthly_cost_rounds_half_up` (1001 week, 1001 quarter, 1002 year) fail.
5. Transfers are counted as charges: `test_all_includes_the_ones_that_stopped` and `test_a_paired_transfer_is_left_out` fail.

## Out of scope

Absent: a migration; a web page; a stored list of subscriptions; findings.
