# Review: Phase 41b

- Verdict: PASS
- Passed: 4116
- Findings: 0
- Approved deviations: extra tests so `new_categories._now`, `propose_group`'s empty reason, `group_kind_word(transfer=True)`, and new-category refusal and out-of-date branches stay at 100% on the include report
- For the architect: None

## Findings

None

Parts that needed a repair: the include report missed `_now`, an empty group reason, and the transfer kind word until extra tests covered them.

Built beyond the spec: extra tests for `kind=savings` and a 51-character name first, stored transfer flags and `home` stored as `Home`, declined group vs category vs open name, deleted group and a group name that is now a leaf, History `category_added` then `category_tax_set`, texts including `(income, sensitive)`, Review `POST /review`, plus the coverage extras above.

## Gates

- `scripts/check.py --first migrations,core,mcp,cli,web`: last line `All checks passed.`; summary lists `tests (migrations,core,mcp,cli,web): passed` then `tests: passed`; 4116 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table
- Given tests: `15 passed`
- Coverage include report: `TOTAL 1010 0 194 0 100%`
- `git diff --stat HEAD -- tests`: only the eleven files of the given diff
- `git grep -n -e "create_group" -e "create_category" -- src/finances/mcp_server`: no output

`git status --short` lists the spec's Scope paths, this review, and local `.vscode/` (not part of the phase). Given tests, migration, and the eleven-file diff match the spec.

## Requirement checklist

- R1: gate 2 (`test_migration_0022.py`)
- R2: gate 1 (`test_proposal_rules.py`, `test_rule_proposal_rules.py`); `test_the_texts_for_a_group_and_a_category`
- R3: gate 2 (`test_the_agent_proposes_a_group`, `test_a_refused_proposal`, `test_one_open_proposal_for_a_name`, `test_a_declined_name_is_not_proposed_again`); `test_kind_savings_is_refused_and_a_long_name_is_checked_first`; `test_a_stored_transfer_group_and_a_category_group_spelling`
- R4: gate 2 (`test_the_agent_proposes_a_category_in_a_group`, `test_a_refused_proposal`); `test_a_stored_transfer_group_and_a_category_group_spelling`; `test_a_declined_group_does_not_block_a_category_of_the_same_name`
- R5: gate 2 (`test_a_group_whose_name_was_taken_since_is_out_of_date`); `test_a_category_whose_group_was_deleted_is_out_of_date`
- R6: gate 2 (the two accept tests); `test_accepting_records_category_added_then_tax_when_proposed`
- R7: gate 2 (the two accept tests' rows and lines); `test_the_texts_for_a_group_and_a_category`
- R8: gate 1 (`test_mcp_more.py`, `test_mcp_accounts.py`, `test_mcp_proposals.py`); gate 2
- R9: gate 4; only those eleven files in `git diff --stat HEAD -- tests`

## Tests to write

- `kind="savings"` and 51-character name first: `test_kind_savings_is_refused_and_a_long_name_is_checked_first`
- stored transfer flags; `home` stored as `Home`: `test_a_stored_transfer_group_and_a_category_group_spelling`
- declined group `Pets` does not block category `Pets`; an open one does: `test_a_declined_group_does_not_block_a_category_of_the_same_name`
- deleted group is out of date: `test_a_category_whose_group_was_deleted_is_out_of_date`
- tax History `category_added` then `category_tax_set`; non-tax only `category_added`: `test_accepting_records_category_added_then_tax_when_proposed`
- texts for transfer, income and sensitive, and a non-tax category: `test_the_texts_for_a_group_and_a_category`
- Review page lists `a new group: Pets` and `POST /review` creates it: `test_the_review_page_lists_and_accepts_a_group`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/fin-41b-spots/`, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. `propose_group`: the name compared with case | `test_a_refused_proposal` (`food`) | failed |
| 2. `propose_group`: the name not stripped | `test_the_agent_proposes_a_group` | failed |
| 3. `propose_new_category`: a category accepted as the group | `test_a_refused_proposal` (group `Dining`) | failed |
| 4. `propose_new_category`: the group stored as given | `test_the_agent_proposes_a_category_in_a_group` | failed |
| 5. the open check only within the same kind | `test_one_open_proposal_for_a_name` | failed |
| 6. out of date: the group's name never checked | `test_a_group_whose_name_was_taken_since_is_out_of_date` | failed |
| 7. accepting a category: the tax flag dropped | `test_a_person_accepts_a_category_in_the_terminal` | failed |
| 8. `_proposal_item`: `"new"` only on the new kinds | `test_a_proposal_and_its_listing` | failed |
| 9. `proposed_text`: the flag words in another order | `test_the_texts_for_a_group_and_a_category` | failed |

## Out of scope

Absent: a category in a proposed group; a transaction or rule in a proposed category; `parent_id` set to anything but None; "waits for" (the given migration docstring names the column 41c will use); cascading declines; a new web route or template; a tool that creates a group or category.

## Probe

None.
