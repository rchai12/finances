# Review: Phase 28d

- Verdict: PASS
- Passed: 3605
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3605 passed`, `All checks passed.` (N + 19 = 3593; extra 12 from extra tests and the HOMES area pin)
- Given tests: `19 passed`
- Coverage of `domain.splits` by `tests/unit/test_splits.py`: `Required test coverage of 100% reached`
- Coverage of domain.splits, domain.audit, db.repositories, categorize.service, analysis.spending: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: the four files of the given diff
- `git grep -n "domain/splits.py" -- scripts/critical_modules.txt docs/testing.md`: one line in each
- `git grep -n "TransactionSplitRow" -- src/finances/analysis src/finances/categorize src/finances/cli src/finances/web`: no output
- Given migration and given tests match the spec blocks

## Requirement checklist

- R1: `test_0019_follows_0018`; `test_the_table_and_its_row_class`; `test_down_and_up_again`
- R2: `test_the_constants_and_a_part`; `test_a_split_that_adds_up`; `test_a_split_that_is_refused`; critical list in `scripts/critical_modules.txt`, `docs/testing.md`, `tests/unit/test_check_script.py`
- R3: `test_the_lists`; `test_an_unknown_action`
- R4: `test_set_split_stores_parts_and_removes_the_own_category`; `test_set_split_refusals_store_nothing`; `set_split` refuses not-found, pending, transfer, `check_split`, then `_leaf_category`
- R5: `test_clear_split_removes_the_parts`
- R6: `test_categorize_skips_a_split_transaction`; `test_by_hand_refuses_a_split_and_changes_none`; the four by-hand functions refuse after existence checks
- R7: `test_a_split_is_decided_and_an_earlier_proposal_is_out_of_date`; `test_uncategorized_leaves_a_split_out`
- R8: `test_a_split_is_never_a_transfer`; `_check_transfer` refuses a split after its three earlier checks
- R9: `test_feed_delete_and_amount_change_look_after_parts`; `test_delete_category_counts_and_moves_parts`; `update_feed_transaction` clears only when the amount changes, `who` `system`
- R10: `test_load_flows_labels_a_split`; `flows_for` uses `SPLIT`; only `analysis/spending.py` changed under `analysis`
- R11: `git diff --stat HEAD -- tests` lists the four given-diff files

## Tests to write

- `set_split` stores parts and records names: `test_set_split_stores_parts_and_removes_the_own_category`
- each R4 refusal once, pending before the sum: `test_set_split_refusals_store_nothing`
- `clear_split` and not-split: `test_clear_split_removes_the_parts`
- `categorize` skips a split: `test_categorize_skips_a_split_transaction`
- by-hand all or none: `test_by_hand_refuses_a_split_and_changes_none`
- decided and out of date: `test_a_split_is_decided_and_an_earlier_proposal_is_out_of_date`
- uncategorized leaves a split out: `test_uncategorized_leaves_a_split_out`
- transfers leave a split out: `test_a_split_is_never_a_transfer`
- feed delete and amount change: `test_feed_delete_and_amount_change_look_after_parts`
- delete category counts and moves parts: `test_delete_category_counts_and_moves_parts`
- `load_flows` labels Split: `test_load_flows_labels_a_split`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy.

1. `check_split` no sign check: `test_a_split_that_is_refused[-2000-[-2100, 100]]` failed
2. count check after the sign check: `test_a_split_that_is_refused[-2000-[100]]` failed
3. `MAX_PARTS` exclusive: `test_a_split_that_adds_up` ten parts of -100 failed
4. `check_split` before pending: `test_set_split_refusals_store_nothing` failed
5. keep the own category: `test_set_split_stores_parts_and_removes_the_own_category` failed
6. `categorize` no skip: `test_categorize_skips_a_split_transaction` failed
7. `set_categories_by_hand` check as each id is set: `test_by_hand_refuses_a_split_and_changes_none` failed
8. `decided_by_a_person` ignore a split: `test_a_split_is_decided_and_an_earlier_proposal_is_out_of_date` failed
9. `list_transfer_movements` keep split transactions: `test_a_split_is_never_a_transfer` failed
10. `update_feed_transaction` clear on every update: `test_feed_delete_and_amount_change_look_after_parts` failed
11. `delete_category` count assignments only: `test_delete_category_counts_and_moves_parts` failed
12. `flows_for` no Split label: `test_load_flows_labels_a_split` failed

## Out of scope

No command, page, or MCP tool splits or shows parts. Reports still label the whole transaction `Split`. A pending transaction and a transfer cannot be split. A feed update that changes the amount clears the split.

## Progress log

`docs/progress.md` has the Phase 28d entry in the required form. Deviations: None.
