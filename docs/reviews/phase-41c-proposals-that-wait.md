# Review: Phase 41c

- Verdict: PASS
- Passed: 4136
- Findings: 0
- Approved deviations: extra tests for the spec's extra cases; removed a cycle guard, a default `_target_exists` for other kinds, and a cascade skip the OPEN filter already makes unreachable
- For the architect: None

## Findings

None

Parts that needed a repair: the include report first missed a cycle guard, a default `_target_exists` branch, a parent-status check redundant with `waits_for`, and a cascade skip for children the OPEN query never returns; those lines were removed because the spec does not need them.

Built beyond the spec: extra tests for `[3, 9, 1, 2]` and `[9, 2]`, a parent declined by `decline_proposal` alone, a decided transaction, `open_suggestions`, decline refusals and a closed id in the middle of a CLI list, a child named before its parent, and `propose_category` after an accepted or declined name.

## Gates

- `scripts/check.py --first core,mcp,cli,web`: last line `All checks passed.`; summary lists `tests (core,mcp,cli,web): passed` then `tests: passed`; 4136 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table
- Given tests: `12 passed`
- Coverage include report: `TOTAL 1000 0 282 0 100%`
- `git diff --stat HEAD -- tests`: only the seven files of the given diff
- `git grep -n --untracked "decline_proposal(" -- src/finances`: `chains.py` (the two calls) and `proposals.py` (the definition)

`git status --short` lists the spec's Scope paths, this review, and local `.vscode/` (not part of the phase). Given tests, template, and the seven-file diff match the spec.

## Requirement checklist

- R1: gate 2 (`test_each_proposal_names_what_it_waits_for`, `test_made_by_hand_the_proposals_stop_waiting`); `test_a_parent_declined_alone_makes_the_child_out_of_date`
- R2: gate 2 (`test_each_proposal_names_what_it_waits_for`, `test_an_unknown_name_is_still_refused`); `test_propose_category_needs_an_open_new_category_or_a_real_one`
- R3: gate 2 (`test_made_by_hand_the_proposals_stop_waiting`); `test_a_parent_declined_alone_makes_the_child_out_of_date`; `test_a_waiting_proposal_whose_transaction_was_decided_is_out_of_date`
- R4: gate 2 (`test_a_waiting_proposal_is_not_accepted_alone`)
- R5: gate 2 (`test_a_chain_accepted_together_goes_parents_first`); `test_accepting_order_parents_first_then_ids_as_given`
- R6: gate 2 (the two CLI declines and the two web declines); gate 5; `test_decline_proposals_refuses_an_already_declined_id`
- R7: gate 2 (`test_the_list_shows_what_waits`, `test_the_review_page_shows_what_waits`); `test_open_suggestions_leave_out_a_waiting_proposal`
- R8: gate 2 (the decline lines; `test_declining_a_parent_says_what_else_was_declined`, `test_declining_with_nothing_waiting_keeps_the_old_notice`)
- R9: gate 1 (`test_mcp_more.py`, the given diff's item tests); gate 2
- R10: gate 4; only those seven files in `git diff --stat HEAD -- tests`

## Tests to write

- `accepting_order` for `[3, 9, 1, 2]` and `[9, 2]`: `test_accepting_order_parents_first_then_ids_as_given`
- parent declined by `decline_proposal` alone: `test_a_parent_declined_alone_makes_the_child_out_of_date`
- waiting category whose transaction was decided: `test_a_waiting_proposal_whose_transaction_was_decided_is_out_of_date`
- `open_suggestions` leaves out a waiting proposal: `test_open_suggestions_leave_out_a_waiting_proposal`
- already declined, and a closed id in the middle of a list: `test_decline_proposals_refuses_an_already_declined_id`
- accepted or declined name, no category: `test_propose_category_needs_an_open_new_category_or_a_real_one`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/fin-41c-spots/`, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. `waits_for`: the target's existence not checked | `test_made_by_hand_the_proposals_stop_waiting` | failed |
| 2. `accept_proposal`: a waiting one accepted | `test_a_waiting_proposal_is_not_accepted_alone` | failed |
| 3. `accepting_order`: the ids as given | `test_a_chain_accepted_together_goes_parents_first` | failed |
| 4. `decline_proposals`: no cascade | `test_declining_a_parent_declines_what_waits_on_it` | failed |
| 5. `decline_proposals`: one level only | the same test | failed |
| 6. `decline_proposals`: an id the cascade declined declined again | `test_a_parent_and_its_child_declined_together` | failed |
| 7. the cascade without the target check | `test_made_by_hand_the_proposals_stop_waiting` | failed |
| 8. `propose_new_category`: the group as given | `test_each_proposal_names_what_it_waits_for` | failed |
| 9. the web: the old notice always | `test_declining_a_parent_says_what_else_was_declined` | failed |

## Out of scope

Absent: a confirmation page before a cascading decline; grouping or indenting a chain; accepting a parent for a dependent; a chain through a transfer or an alias; a migration.

## Probe

Temporary `FIN_DATA_DIR=/tmp/fin-41c-probe/data`, in-memory keyring, TestClient on `127.0.0.1:8765`. Group Pets, category Dog Food waiting for it, transaction proposal waiting for Dog Food: Review showed `waits for #1` and `waits for #2`. Declining the group redirected to `proposals-declined-waiting` with an empty list. Script deleted afterwards. FAILURES 0.
