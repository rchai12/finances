# Review: Phase 12b

- Verdict: PASS
- Passed: 2433
- Findings: 0
- Approved deviations: None
- For the architect: the spec does not say what `fin months` prints with no active account; it prints the months, each covered, since no account is uncovered.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2433 passed`, `All checks passed.` (N + 17 = 2420; 13 more are the coder's)
- Given tests: `17 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists exactly the guide's paths, plus this review
- Given files: `tests/unit/test_periods.py` and `tests/e2e/test_cli_balances_months.py` are identical to the spec's blocks

## Requirement checklist

- R1, R2, R6 to R9: the given tests pass.
- R3 to R5, R9 (no `--to`): `tests/integration/test_balances_months.py` covers each item of "Tests to write": no data; statements only; a day bought before its statement starts; a pending transaction left out; a feed pull later than every transaction; an inactive account left out of balances; the newest of two snapshots; an inactive account never uncovered; an account with no data uncovered every month; `fin months` without `--to` names this month.
- R3: `account_data_span` takes the min and max of statement periods, of `coalesce(transaction_date, posted_date)` over non-pending transactions, and of feed pull dates (in UTC through `to_feed_pull`); no dialect-specific SQL.
- R5: `month_report` takes spent and income from `summarize(load_flows(...))` of Phase 12a.
- R10: `cli/reports.py` has no sums, date arithmetic, or coverage checks; each command opens one session.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the tests run, and the code restored.

1. `account_data_span` ignores feed pulls: `test_a_feed_pull_after_every_transaction_ends_the_span` and `test_feed_pulls_alone_give_the_span` fail.
2. Net worth leaves out credit cards: `test_balances_and_net_worth`, `test_an_account_without_a_balance`, and `test_the_newest_of_two_snapshots_is_the_balance` fail.
3. The change is the previous month minus this one: `test_three_months` fails.
4. An account with no data covers every month: `test_uncovered_names_the_accounts_missing_part_of_the_range` and `test_an_account_with_no_data_is_uncovered_every_month` fail.
5. `balance_report` includes inactive accounts: `test_an_inactive_account_is_left_out_of_balances` fails.

## Out of scope

Absent: a migration (newest is still `0009`); balances worked forward from transactions; a web page; checks for gaps between statements.
