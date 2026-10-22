# Review: Phase 36b

- Verdict: PASS
- Passed: 3286
- Findings: 0
- Approved deviations: none
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3286 passed`, `All checks passed.` (N + 8 = 3281; extra 5)
- Given tests plus earlier view tests: all passed
- Page and command tests: all passed
- Coverage of listings, analysis.categories, and the four views: `Required test coverage of 100% reached`
- `git grep` of db/sync/sqlalchemy/keyring in the four views: no output
- `git diff --stat HEAD -- tests`: the two files of the given diff
- Given files match the spec blocks; no template changes

## Requirement checklist

- R1: `test_account_rows`; `test_people_rows`; `test_account_listing_includes_closed_when_asked`; `test_people_listing_with_no_people`
- R2: `test_groups_and_their_categories_in_name_order`; `test_uncategorized_items_on_a_closed_account`; `test_transaction_facts_for_a_rule_category`; `test_card_credit_count_on_an_empty_list`
- R3: `test_account_rows_from_a_listing`; `test_people_rows_from_a_listing`
- R4: `test_the_category_tree_as_lines_and_choices`; `test_uncategorized_lines_and_the_card_note`
- R5: `test_the_refund_sections`
- R6: page and command tests unchanged
- R7: `test_only_the_frozen_views_still_load_data`
- R8: given earlier-test diffs applied
- R1, R2 edges: `tests/integration/test_listings_more.py`

## Probe

None. The earlier page and command tests pin every output these views make.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `card_credit_count` counts money in on any account: `test_uncategorized_lines_and_the_card_note` fails (`2`).
2. `views/categories.py` imports `list_categories` again: `test_only_the_frozen_views_still_load_data` fails.
3. `refund_view` returns a view for a purchase: `test_the_refund_sections` fails (`RefundView` instead of `None`).
4. `account_rows` shows `None` for no owner: `test_account_rows_from_a_listing` fails (`"None"`).

## Out of scope

Absent: a change to `views/sync.py`, `views/transfers.py`, `views/backups.py`, `analysis/people.py`, or any template; a change to output.
