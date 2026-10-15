# Review: Phase 16e

- Verdict: PASS
- Passed: 2578
- Findings: 0
- Approved deviations: None
- For the architect: `docs/roadmap.md` was already modified in the working tree before this phase (Phases 24 to 30, 16i, and 13d added to the build order); it is not part of this phase and was left as it is.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2578 passed`, `All checks passed.` (N + 28 = 2561; 17 more are the coder's)
- Given tests: `tests/integration/test_web_search.py` `28 passed`
- `test_web_pages.py`, `test_web_reports.py`, `test_web_insights.py`, `test_cli_spending.py`: all passed (with the given tests, 107 passed)
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists exactly the guide's 13 paths, plus `docs/roadmap.md` (the architect's, present before the phase) and this review
- Given files: `transactions.html`, `reports.html`, `insights.html`, and `tests/integration/test_web_search.py` are identical to the spec's blocks; `git diff HEAD -- tests/integration/test_web_pages.py` is exactly the spec's diff (applied with `git apply`)

## Requirement checklist

- R1: `domain/spending.py` adds `PENDING = "pending"` and `KINDS = (SPENDING, INCOME, TRANSFER, UNSORTED_IN, PENDING)`.
- R2: `db/repositories.py:305` `list_transactions_by_day` filters on the day bought, else posted, with optional bounds, includes pending, and orders by posted date then id, both descending. Tests: `test_by_day_with_no_bounds_lists_everything_latest_posted_first`, `test_by_day_with_one_bound_uses_the_day_bought`, `test_by_day_includes_pending`.
- R3: `analysis/spending.py:43` `flows_for` is the one place that builds a `Flow`; `load_flows` (line 78) returns `flows_for(session, list_transactions_between(...))`. Tests: `test_flows_for_marks_a_pending_transaction_pending`, `test_load_flows_over_a_month_is_unchanged` (a transfer pair, income, spending, and a pending charge left out).
- R4: `analysis/search.py` checks messages 4 to 6 in order, then filters the flows. Tests: `test_refusals_come_in_order` (six cases, including `SPENDING `), `test_fields_with_surrounding_spaces_still_match`, `test_joint_unassigned_and_a_name_in_another_case`, `test_an_account_in_another_case`, `test_every_label_compares_whole`, `test_the_limit_cuts_after_the_filters`, `test_pending_is_a_kind_of_its_own`.
- R5 to R9: the given tests pass. `found_rows` is at `views/transactions.py:35`; the route builds its query in `_search_query` (`web/app.py:277`), which checks messages 1 to 3 in order and calls `search_transactions` once; Reports and Insights pass `start` and `end` as ISO dates.
- Thin: search 1 prints nothing.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the tests run, and the code restored.

1. From and To compare the posted date: `test_by_day_with_one_bound_uses_the_day_bought`, two cases of `test_filters`, `test_a_spending_line_opens_its_transactions`, and three cases of `test_every_line_opens_exactly_its_transactions` fail.
2. Pending transactions get the kind `spending`: `test_flows_for_marks_a_pending_transaction_pending`, `test_pending_is_a_kind_of_its_own`, `test_filters[kind=pending]`, `test_a_spending_line_opens_its_transactions`, and six cases of `test_every_line_opens_exactly_its_transactions` fail.
3. The `merchant` filter matches part of the merchant: `test_every_label_compares_whole` and `test_filters[merchant=acme]` fail.
4. `group` is dropped from the form after Show: `test_link_filters_are_kept_and_named` fails.
5. `fin transactions list` gains the Category column: seven tests in `tests/e2e/test_cli_listing.py` fail, starting with `test_transactions_list_newest_first`.

## Out of scope

Absent: a change to `cli/`; a migration; JavaScript (search 2 prints nothing); a change to how any report counts (`load_flows` gives the same flows, and the Reports, Insights, and spending tests pass unchanged).
