# Review: Phase 28f

- Verdict: PASS
- Passed: 3657
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3657 passed`, `All checks passed.` (N + 9 = 3649; extra 8 from extra tests)
- Given tests: `9 passed`
- Coverage of db.repositories, analysis.search, web.routes.transactions: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: only `tests/unit/test_repositories_split.py` and `tests/unit/test_web_split.py`
- `git grep -n "TransactionTagRow\\|TransactionNoteRow" -- src/finances/web src/finances/analysis src/finances/views`: no output
- Given tests match the spec blocks; `tagged_with` is one `select` of `transaction_id` on `transaction_tags`

## Requirement checklist

- R1: `test_a_transaction_with_tags_and_a_note`; `test_a_refused_tag_keeps_tags_and_note_on_the_400_page`
- R2: `test_adding_and_removing_a_tag`; `test_a_refused_form`
- R3: `test_saving_and_removing_the_note`
- R4: `test_get_on_the_new_paths_is_405` (three paths)
- R5: `test_adding_and_removing_a_tag`; `test_saving_and_removing_the_note`; `NOTICES` are `Tag added.`, `Tag removed.`, `Note saved.`, `Note removed.`
- R6: `test_the_tag_filter`; `test_select_all_keeps_the_tag_filter`
- R7: `test_tagged_with_normalizes_and_refuses_a_blank`; `tagged_with` queries `transaction_tags` once
- R8: `test_the_tag_filter`; `test_a_tag_filter_that_is_refused`; `test_search_by_tag_and_category_and_a_split_is_found_per_part`
- R9: `git diff --stat HEAD -- tests` lists only the two given-diff files

## Tests to write

- GET on each of the three new paths is 405: `test_get_on_the_new_paths_is_405`
- a refused tag keeps tags and note on the 400 page: `test_a_refused_tag_keeps_tags_and_note_on_the_400_page`
- `tagged_with("  TRIP ")` finds tagged ids; `tagged_with("")` is refused: `test_tagged_with_normalizes_and_refuses_a_blank`
- tag plus Dining, and a split tagged `trip` once per part: `test_search_by_tag_and_category_and_a_split_is_found_per_part`
- select-all on `/transactions?tag=trip` keeps `tag=trip`: `test_select_all_keeps_the_tag_filter`
- a form without a valid token is 403: `test_a_form_without_a_valid_token_is_refused`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. `search_transactions` compares the tag as typed: `test_the_tag_filter` failed (`tag=TRIP` found none)
2. `search_transactions` ignores the tag: `test_the_tag_filter` failed (all three rows)
3. a refused tag treated as no tag: `test_a_tag_filter_that_is_refused` failed (200)
4. `_SEARCH_FIELDS` without `tag`: `test_the_tag_filter` failed (bulk `back` lost `tag=TRIP`)
5. the note route always `note-saved`: `test_saving_and_removing_the_note` failed (`note-saved` after an empty text)
6. the remove route calls `add_tags`: `test_adding_and_removing_a_tag` failed (`tax` and `trip` left)
7. `_transaction_page` supplies `tags` only on a 200: `test_a_refused_tag_keeps_tags_and_note_on_the_400_page` failed (`No tags.`)

## Probe

On a temporary `FIN_DATA_DIR` (never the owner's `data/`): three card purchases (ACME, FOOBAR, BAZ, May 2026); `fin web` on port 18765; transaction 1 gained tag `trip` and note `split with a friend`; `/transactions?tag=trip` showed only ACME with Tag selected as `trip`. `FAILURES 0`.

## Out of scope

Absent: a Tags or Note column on the Transactions page; tags or notes in an MCP tool, `fin transactions list`, or a report; tagging from the bulk form; renaming or merging tags.

## Progress log

`docs/progress.md` has the Phase 28f entry in the required form. Deviations: None.
