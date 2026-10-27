# Review: Phase 44b

- Verdict: PASS
- Passed: 4218
- Findings: 0
- Approved deviations: pair out-of-date moved into `chains.py` so `proposals.py` stays within 400 lines; accepting a CATEGORY proposal into a deleted name still raises `category not found` because an earlier test pins that message; extra tests for a deleted category by id, unpatched `_now`, a waiting category, and a gone rule
- For the architect: None

## Findings

None

Parts that needed a repair: `CategoryExistsError` imported from `categories` rather than the facade so `FROM_REPOSITORIES` stays exact; accepting a CATEGORY proposal into a deleted name still calls `set_category_by_hand` so the earlier `category not found` test passes while the list shows out of date.

Built beyond the spec: extra tests for History after a refused delete, a deleted category by id, unpatched `_now`, a rule already gone when a rename is accepted, and a waiting category after a delete.

## Gates

- `scripts/check.py --first core,mcp,cli,web`: last line `All checks passed.`; summary lists `tests (core,mcp,cli,web): passed` then `tests: passed`; 4218 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table
- Given tests: `18 passed`
- Coverage include report: `TOTAL 1031 0 336 0 100%`
- `git diff --stat HEAD -- tests`: `tests/support.py` and the eleven files of the given diff, no other
- `git grep -n -e "rename_category" -e "delete_category" -- src/finances/mcp_server`: no output

`git status --short` lists the spec's Scope paths, `docs/reviews/phase-44b-category-changes.md`, and local `.vscode/` (not part of the phase). The given test file and the twelve-file test diff match the spec.

## Requirement checklist

- R1: gate 1 (`test_proposal_rules.py`, `test_rule_proposal_rules.py`); `test_a_refused_delete_then_a_rename_leave_only_the_accepted_history`
- R2: gate 2 (`test_a_refused_change`, `test_one_open_change_for_a_category`, `test_a_declined_change_is_not_proposed_again`); `test_a_refused_delete_then_a_rename_leave_only_the_accepted_history`
- R3: gate 2 (the rename, delete, and empty-group tests)
- R4: gate 2 (`test_a_category_renamed_by_hand_since_puts_it_out_of_date`, `test_a_delete_puts_the_agents_other_proposals_out_of_date`); `test_a_delete_whose_move_to_was_removed_is_out_of_date`; `test_a_rename_whose_new_name_was_taken_is_out_of_date`
- R5: gate 2 (`test_a_rename_carries_the_agents_other_proposals`); `test_renaming_a_group_carries_an_open_new_category`; `test_a_rule_change_stays_usable_after_a_rename`
- R6: gate 2 (the review rows); `test_the_review_page_lists_and_accepts_a_category_change`
- R7: gate 1 (`test_mcp_more.py`, `test_mcp_accounts.py`, `test_mcp_proposals.py`); gate 2; gate 5
- R8: gate 4; only those files

## Tests to write

- the dry run leaves nothing behind: `test_a_refused_delete_then_a_rename_leave_only_the_accepted_history`
- renaming a group carries an open NEW_CATEGORY: `test_renaming_a_group_carries_an_open_new_category`
- a rule-change on a rule into Dining stays usable; one already out of date stays out of date: `test_a_rule_change_stays_usable_after_a_rename`
- a waiting category proposal stays waiting after a delete of Dining; a RULE_EDIT into Dining is out of date: `test_a_waiting_category_stays_waiting_after_a_delete`
- a delete whose move_to was removed is out of date: `test_a_delete_whose_move_to_was_removed_is_out_of_date`
- a rename whose new name was taken is out of date: `test_a_rename_whose_new_name_was_taken_is_out_of_date`
- the Review page lists and accepts a category change: `test_the_review_page_lists_and_accepts_a_category_change`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/fin-44b-spots/copies/`, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. the dry run not rolled back | `test_one_open_change_for_a_category` | failed |
| 2. no dry run: only the name checked | `test_a_refused_change` (Dining delete without `move_to`) | failed |
| 3. no sameness check | the same test (`rename_to: Dining`) | failed |
| 4. out of date by id only, the name not compared | `test_a_category_renamed_by_hand_since_puts_it_out_of_date` | failed |
| 5. a rename leaves the other proposals as they were | `test_a_rename_carries_the_agents_other_proposals` | failed |
| 6. a CATEGORY proposal into a deleted category not out of date | `test_a_delete_puts_the_agents_other_proposals_out_of_date` | failed |
| 7. `move_to` stored as given | `test_the_agent_proposes_deleting_a_category` (`coffee & dessert`) | failed |
| 8. `review_items`: the category's id read as a transaction's | `test_the_agent_proposes_renaming_a_category` | failed |

## Out of scope

Absent: moving a category to another group; changing a group's flags; a `move_to` still only proposed.

## Probe

None.
