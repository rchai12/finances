# Review: Phase 28e

- Verdict: PASS
- Passed: 3640
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3640 passed`, `All checks passed.` (N + 24 = 3629; extra 11 from extra tests)
- Given tests: `24 passed`
- Coverage of domain.splits, db.repositories, analysis.spending, months, budgets, account_page, insights, search, views.transactions, mcp_server, cli.splits: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: only `tests/unit/test_repositories_split.py`
- `git grep -n "parts=True"` on recurring, forecast, names, refunds, views, cli, web, mcp_server: no output
- Given tests match the spec blocks; HOMES given diff applied

## Requirement checklist

- R1: `test_flows_whole_and_in_parts`; `test_month_report_counts_spent_without_the_transfer_part`
- R2: `test_spending_counts_the_parts`; `test_month_report_counts_spent_without_the_transfer_part`; `test_a_groceries_budget_counts_the_part`; `test_the_account_page_spending_shows_the_parts`; `test_spikes_see_a_groceries_part`
- R3: `git diff` of recurring, forecast, names, refunds empty; `test_recurring_charges_keep_the_whole_streamflix_amount`; `test_merchant_stats_count_a_split_purchase_once`; `insights_report` gives whole flows to every finding but spikes and over_budget, and to merchant_stats
- R4: `test_a_drill_down_finds_the_part`; `test_search_matches_a_part_kind_and_limit_counts_parts`
- R5: `test_the_transactions_page_shows_the_parts_amounts`; `test_list_transactions_gives_each_part_amount`
- R6: `test_split_parts.py`; critical coverage of `domain.splits`
- R7: `test_split_by_sizes_refuses_not_found_before_a_size`; `test_split_by_sizes_refuses_pending_before_the_sum`; `split_by_sizes` requires the transaction, then signs, then `set_split`
- R8: `test_splitting`; `test_refused`
- R9: `test_unsplitting`
- R10: `test_splitting`; `test_unsplitting`; `test_refused`
- R11: `git diff --stat HEAD -- tests` lists only the given-diff file

## Tests to write

- month_report spent without a Transfer part, transfer kind: `test_month_report_counts_spent_without_the_transfer_part`
- Groceries budget counts the -$12.00 part: `test_a_groceries_budget_counts_the_part`
- account page spending shows the parts: `test_the_account_page_spending_shows_the_parts`
- spikes see Groceries only from parts: `test_spikes_see_a_groceries_part`
- STREAMFLIX split in month four stays one $15 series: `test_recurring_charges_keep_the_whole_streamflix_amount`
- merchant_stats visits 1: `test_merchant_stats_count_a_split_purchase_once`
- search kind=transfer and limit=2 of three parts: `test_search_matches_a_part_kind_and_limit_counts_parts`
- MCP list_transactions two items, same id, part amounts: `test_list_transactions_gives_each_part_amount`
- Transactions page part amounts: `test_the_transactions_page_shows_the_parts_amounts`
- split_by_sizes id 9 with size 0: `test_split_by_sizes_refuses_not_found_before_a_size`
- pending sizes that do not add up: `test_split_by_sizes_refuses_pending_before_the_sum`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. `flows_for` a part takes the first part's group: `test_flows_whole_and_in_parts` failed (`Food` for Home & Garden)
2. `search_transactions` whole flows: `test_a_drill_down_finds_the_part` failed (nothing found for groceries)
3. `spending_report` whole flows: `test_spending_counts_the_parts` failed (`Split` 2000 and Dining)
4. `recurring_charges` flows in parts: `test_recurring_charges_keep_the_whole_streamflix_amount` failed (series broken)
5. `found_rows` the transaction's amount: `test_the_transactions_page_shows_the_parts_amounts` failed (`-$20.00` twice)
6. `signed_parts` negative for a zero amount: `test_sizes_take_the_transaction_sign` failed (`[-100, -100]`)
7. `parse_part` split on every space: `test_a_part_as_typed` failed (`Home` instead of `Home & Garden`)
8. `fin transactions unsplit` no categorize run: `test_unsplitting` failed (one line)
9. `split_by_sizes` sizes before the transaction: `test_split_by_sizes_refuses_not_found_before_a_size` failed (the size message)
10. `merchant_stats` flows in parts: `test_merchant_stats_count_a_split_purchase_once` failed (visits 2)
11. `_transaction_item` the transaction's amount: `test_list_transactions_gives_each_part_amount` failed (`-2000` twice)

## Probe

On a temporary `FIN_DATA_DIR` (never the owner's `data/`): one -$20.00 purchase on 2026-10-23; `fin transactions split --id 1 --part "12.00 Groceries" --part "8.00 Dining"` printed `Transaction 1: split into 2 parts.`; `fin spending --month 2026-10` showed Groceries $12.00 and Dining $8.00. `FAILURES 0`.

## Out of scope

Absent: a page or form for splits; a mark or column saying a row is a part; any change to `recurring.py`, `forecast.py`, `names.py`, or `refunds.py`.

## Progress log

`docs/progress.md` has the Phase 28e entry in the required form. Deviations: None.
