# Review: Phase 35a

- Verdict: PASS
- Passed: 3111
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3111 passed`, `All checks passed.` (N + 14 = 3107; extra 4)
- Given tests: `14 passed`
- Earlier spending, reports, account, search, cards, and bulk tests: `133 passed`
- Coverage of `domain.spending`, `views.spending`, `views.format`, `views.months`, `views.budgets`, `views.account_page`, `cli.reports`: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: exactly the six files of the given diff
- Given files match the spec blocks; the six earlier-test files match the given diff

## Requirement checklist

- R1: `test_a_tie_goes_by_name_ignoring_case_and_a_refund_can_win`; `test_purchases_are_net_spending_plus_refunds`
- R2: `test_summarize`; `test_a_month_by_category`
- R3: `test_net_spending_never_shows_a_minus`
- R4: `test_money_back_reads_as_a_gain`; `test_the_reports_page`
- R5: `test_a_month_where_refunds_win`; `test_the_account_page`
- R6: `test_a_month_where_refunds_win`; `test_the_reports_page`
- R7: `test_the_months_table_says_back`
- R8: `test_a_budget_with_money_back_is_not_below_zero_used`
- R9: `test_the_reports_page`; `test_the_account_page`; `test_a_month_where_refunds_win`
- R10: given diff applied; `git diff --stat HEAD -- tests` lists those six files
- R5 to R8 edges: `tests/integration/test_refunds_more.py` (merchant and card, dashboard months, a Food group budget, one category back with net spending still out)

## Probe

None.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `spending_lines` adds every `SPENDING` flow's amount to refunds, of either sign: `test_a_tie_goes_by_name_ignoring_case_and_a_refund_can_win` fails (`refunds_cents=500`).
2. `summarize` counts money in without a category as refunds: `test_a_month_by_category` fails (`Refunds: $30.99.`).
3. `spending_rows` puts the net in Spent: the same, Groceries `$20.00` instead of `$25.99`.
4. `net_text` writes a minus: `test_net_spending_never_shows_a_minus[-599-$5.99 back]` fails (`-$5.99`).
5. `amount_class` leaves `back` plain: `test_the_reports_page` finds no green `$5.99 back` cells.
6. `month_rows` keeps `format_cents`: `test_the_months_table_says_back` fails (`-$5.99`).
7. `budget_rows` shows the used percentage below zero: `test_a_budget_with_money_back_is_not_below_zero_used` fails (`-6%`).

## Out of scope

Absent: a refund label or filter on transactions; matching refunds to purchases; any change to a total, budget left, the Change column, insights, or the pie chart.
