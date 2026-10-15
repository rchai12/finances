# Review: Phase 12a

- Verdict: PASS
- Passed: 2403
- Findings: 0
- Approved deviations: None
- For the architect: `domain.spending.check_by` is a public helper not in the design; `spending_lines` and `spending_report` share it so the `by` message lives in one place.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: `domain.spending.check_by` (recorded in the progress entry)

## Gates

- `scripts/check.py`: `2403 passed`, `All checks passed.` (N + 43 = 2385; 18 more are the coder's)
- Given tests: `43 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists exactly the guide's paths, plus this review
- Given files: `tests/unit/test_spending.py` and `tests/e2e/test_cli_spending.py` are identical to the spec's blocks

## Requirement checklist

- R1 to R5, R9 to R11: the given tests pass.
- R6 to R8, R10 (no options): `tests/integration/test_spending_report.py` covers each item of "Tests to write": the day bought decides, pending left out, both ends included, id order; a paired transaction, a transfer category, an income category, a category added to a group by hand, a cardholder mapped to a person, an account with no owner; both report messages in order; `fin spending` with no options names this month.
- R6: `list_transactions_between` filters on `func.coalesce(transaction_date, posted_date)`, leaves out pending, orders by id; no dialect-specific SQL.
- R12: `cli/reports.py` has no sums, sorting, or kind checks; it opens one session and only reads.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the tests run, and the code restored.

1. Paired transactions count as spending: `test_flow_kind[paired]`, `test_flow_kind[paired-wins]`, `test_a_month_by_category`, and `test_a_paired_transaction_is_a_transfer` fail (11 in all).
2. Refunds left out instead of netted: `test_refunds_net_and_the_largest_comes_first`, `test_a_range_where_refunds_win`, and `test_a_month_by_category` fail (10 in all).
3. The month decided by the posted date: `test_the_day_bought_decides_the_month`, `test_the_day_bought_decides_the_range`, and `test_a_month_by_category` fail (10 in all).
4. Pending transactions counted: `test_pending_transactions_are_left_out` and `test_a_month_by_category` fail (9 in all).
5. A tie keeps the input order: `test_a_tie_goes_by_name_ignoring_case_and_a_refund_can_win` fails.

## Out of scope

Absent: a migration (newest is still `0009`); balances or net worth; a web page; a change to categories, rules, or pairs (the only repository change adds `list_transactions_between`).
