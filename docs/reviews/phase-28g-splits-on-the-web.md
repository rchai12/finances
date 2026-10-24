# Review: Phase 28g

- Verdict: PASS
- Passed: 3678
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: the account page unpack, after the spec added `account.html` to the given diff.

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3678 passed`, `All checks passed.` (N + 13 = 3670; extra 8 from extra tests)
- Given tests: `13 passed`
- Coverage of domain.splits, analysis.search, views.transactions, web.routes.transactions: `Required test coverage of 100% reached`
- `git diff --stat 092b179 -- tests`: `tests/unit/test_web_split.py` and the three new test files only
- `git grep -n "splitlines\\|parse_part(" -- src/finances/web`: no output
- Given tests match the spec blocks; `account.html` unpacks five values and shows no part badge

## Requirement checklist

- R1: `test_a_split_transactions_page`; `test_a_page_that_is_not_split`; `test_a_refused_split_on_a_split_transaction_keeps_the_parts`
- R2: `test_splitting_on_the_page`; `test_a_refused_split_keeps_what_was_typed`; `test_splitting_a_pending_transaction_is_refused`; `test_a_part_of_size_zero_is_refused`
- R3: `test_removing_the_split`; `test_a_refused_form`; `test_removing_a_split_puts_the_rule_category_back`
- R4: `test_get_on_the_new_paths_is_405` (two paths)
- R5: `test_splitting_on_the_page`; `test_removing_the_split`; `NOTICES` are `Split saved.` and `Split removed, and the rules were run again.`
- R6: `tests/unit/test_split_lines.py`; check.py critical coverage of `domain/splits.py`
- R7: `test_parts_on_the_transactions_page`; `test_search_gives_part_numbers_on_a_split`; account page tests pass with five values unpacked and no badge
- R8: `git diff --stat 092b179 -- tests` lists only the given-diff earlier file and the three new test files

## Tests to write

- GET on each of the two new paths is 405: `test_get_on_the_new_paths_is_405`
- a refused split on an already-split transaction keeps the parts table: `test_a_refused_split_on_a_split_transaction_keeps_the_parts`
- pending split and a size of 0: `test_splitting_a_pending_transaction_is_refused`; `test_a_part_of_size_zero_is_refused`
- removing a split whose merchant a rule matches puts the rule category back: `test_removing_a_split_puts_the_rule_category_back`
- `search_transactions` part 1 and 2, else None: `test_search_gives_part_numbers_on_a_split`
- a form without a valid token is 403: `test_a_form_without_a_valid_token_is_refused`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. `parse_parts` blank lines not skipped: `test_one_part_per_line` failed (size-and-category message on `"\n  12.00 Groceries  \r\n\n 8 Dining\n"`)
2. `search_transactions` parts numbered from 0: `test_parts_on_the_transactions_page` failed (`Dining` without `part 1`)
3. `found_rows` the part left out: `test_parts_on_the_transactions_page` failed (unpack error)
7. `account.html` four values unpacked: `tests/integration/test_web_account_page.py` failed (too many values to unpack)
4. `_transaction_page` `parts` left empty: `test_a_split_transactions_page` failed (no parts table)
5. the split route 400 without the typed text: `test_a_refused_split_keeps_what_was_typed` failed (empty box)
6. the clear route no categorize run: `test_removing_a_split_puts_the_rule_category_back` failed (no Coffee & Dessert)

## Probe

On a temporary `FIN_DATA_DIR` (never the owner's `data/`): one -$20.00 FOOBAR GROCERY purchase on 2026-05-01; `fin web` on port 18766; split on the page into `12.00 Groceries` and `8.00 Dining`; Parts card with no Set the category card; Transactions page showed `part 1` and `part 2`; Remove the split restored the Split card. `FAILURES 0`.

## Out of scope

Absent: editing one part in place; a category select per part; splits in the bulk form or an MCP tool; a change to the detail table at the top of a transaction's page; a part badge anywhere but the Transactions page.

## Progress log

`docs/progress.md` has the Phase 28g entry in the required form. Deviations: None.
