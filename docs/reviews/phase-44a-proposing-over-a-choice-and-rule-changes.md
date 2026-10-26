# Review: Phase 44a

- Verdict: PASS
- Passed: 4190
- Findings: 0
- Approved deviations: helpers moved out of `proposals.py` to stay within 400 lines; extra tests for field checks, a deleted rule, UTC stamp, and `decided_by_a_person`
- For the architect: None

## Findings

None

Parts that needed a repair: the include report first missed `decided_by_a_person` after `propose_category` stopped calling it; an extra test of that public function closed the gap.

Built beyond the spec: extra tests for a long pattern, an invalid match, a deleted rule, unpatched `_now`, and `decided_by_a_person` for a hand-set, split, and transfer transaction.

## Gates

- `scripts/check.py --first migrations,core,mcp,cli,web`: last line `All checks passed.`; summary lists `tests (migrations,core,mcp,cli,web): passed` then `tests: passed`; 4190 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table
- Given tests: `17 passed`
- Coverage include report: `TOTAL 1153 0 236 0 100%`
- `git diff --stat HEAD -- tests`: `tests/support.py` and the twelve files of the given diff, no other
- `git grep -n -e "edit_rule" -e "delete_rule" -- src/finances/mcp_server`: no output

`git status --short` lists the spec's Scope paths, `categories.py` and `chains.py` (private helpers moved out of `proposals.py`), this review, and local `.vscode/` (not part of the phase). The migration, the given test files, and the thirteen-file test diff match the spec.

## Requirement checklist

- R1: gate 2 (`test_0024_follows_0023`, `test_the_columns_come_and_go_and_the_rows_stay`)
- R2: gate 1 (`test_the_lists_and_limits`, `test_the_kinds`); `test_history_records_the_edit_and_the_delete`
- R3: gate 2 (`test_a_persons_choice_can_be_proposed_over`, `test_the_category_it_has_is_refused`); gate 1 (`test_proposals.py`, `test_splits_stored.py`); `test_a_split_and_a_transfer_are_still_refused`
- R4: gate 2 (`test_a_person_changing_it_since_puts_it_out_of_date`); `test_a_choice_stays_open_until_a_person_changes_the_name`; `test_a_proposal_with_before_none_goes_out_of_date_when_set_by_hand`
- R5: gate 2 (`test_the_agent_proposes_changing_a_rule`, `test_a_refused_rule_change`, `test_one_open_change_for_a_rule`, `test_a_declined_change_is_not_proposed_again`); `test_a_duplicate_pattern_and_match_is_refused`
- R6: gate 2 (the edit and delete accept tests, `test_a_rule_edited_since_puts_it_out_of_date`)
- R7: gate 2 (the review rows); `test_the_review_page_lists_and_accepts_a_rule_change`
- R8: gate 1 (`test_mcp_more.py`, `test_mcp_accounts.py`, `test_mcp_proposals.py`); gate 2; gate 5
- R9: gate 4; only those files

## Tests to write

- a category proposal over a person's choice (`before` Groceries): `test_a_choice_stays_open_until_a_person_changes_the_name`
- a category proposal with `before` None: `test_a_proposal_with_before_none_goes_out_of_date_when_set_by_hand`
- a split and a transfer still refused: `test_a_split_and_a_transfer_are_still_refused`
- duplicate pattern, and match-only duplicate: `test_a_duplicate_pattern_and_match_is_refused`
- a delete proposal's stored fields: `test_a_delete_stores_the_rules_current_fields`
- History `proposal_accepted` with `rule 1: …` and `delete rule 1`: `test_history_records_the_edit_and_the_delete`
- Review page lists and accepts a rule change: `test_the_review_page_lists_and_accepts_a_rule_change`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/fin-44a-spots/copies/`, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. `propose_category`: a person's choice still refused | `test_a_persons_choice_can_be_proposed_over` | failed |
| 2. `propose_category`: the current category not checked | `test_the_category_it_has_is_refused` | failed |
| 3. out of date: today's rule (set by hand) kept | `test_a_persons_choice_can_be_proposed_over` | failed |
| 4. out of date: `before` ignored, never out of date | `test_a_person_changing_it_since_puts_it_out_of_date` | failed |
| 5. `propose_rule_change`: no sameness check | `test_a_refused_rule_change` (`category: dining`) | failed |
| 6. `propose_rule_change`: fields allowed with delete | the same test (`CHANGE` with `delete`) | failed |
| 7. a rule change's out of date not checked | `test_a_rule_edited_since_puts_it_out_of_date` | failed |
| 8. `accept_proposals`: no categorize after a rule change | `test_the_agent_proposes_changing_a_rule` | failed |
| 9. the declined check without the values | `test_a_declined_change_is_not_proposed_again` (priority 6) | failed |
| 10. `review_items`: the rule's id read as a transaction's | `test_the_agent_proposes_changing_a_rule` | failed |

## Out of scope

Absent: renaming or deleting a category or group; a rule change into a proposed category; a split or transfer given one category by a proposal.

## Probe

None.
