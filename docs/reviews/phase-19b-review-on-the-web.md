# Review: Phase 19b

- Verdict: PASS
- Passed: 3417
- Findings: 0
- Approved deviations: extra tests also cover a current open proposal kept in `open_suggestions`; `open_suggestions` lists with limit 10_000 because `list_proposals` always takes a limit
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: one extra test in `tests/integration/test_web_review_more.py` that keeps a current open proposal in `open_suggestions` (needed for the True branch of `proposal_out_of_date`)

## Gates

- `scripts/check.py`: `3417 passed`, `All checks passed.` (N + 12 = 3409; extra 8 from extra tests and one new split-area parametrize case)
- Given tests: `12 passed`
- Earlier categories, split, nav, and cli review tests: `76 passed`
- Coverage of analysis.review, views.review, web.routes.review, and web.routes.categories: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: the two files of the given diff
- Given template and tests match the spec blocks; both diffs applied

## Requirement checklist

- R1: `test_the_suggestions_beside_uncategorized_transactions`; `test_open_suggestions_leave_out_a_set_by_hand_transaction`; `test_open_suggestions_leave_out_a_deleted_transaction`
- R2: `test_the_review_page`; `test_the_notes_table_shows_at_most_twenty_newest_first`
- R3: `test_the_review_page`; `test_nothing_yet`; `test_a_database_that_is_not_migrated`
- R4: `test_accepting_several`; `test_declining_an_out_of_date_one`; `test_all_or_none`; `test_nothing_chosen_or_a_bad_form`; `test_the_form_token_is_checked`
- R5: `test_the_suggestions_beside_uncategorized_transactions`; `test_the_suggested_column_is_empty_after_a_decline`
- R6: `test_the_review_page`; `test_the_review_link_is_current_only_on_its_page`
- R7: `test_the_categories_page`; `test_one_router_module_per_area[review]`; `test_the_same_routes_as_before_the_split`
- R1, R4 edges: `tests/integration/test_web_review_more.py`

## Probe

None. Browser look on `fin web serve --port 18768` with a temporary `FIN_DATA_DIR` (never the owner's `data/`): one ACME PROBE COFFEE transaction and one `propose_category` of Coffee & Dessert; ticking it and Accept chosen showed `Proposals accepted, as your choice.` and `/transactions/1` had Category Coffee & Dessert.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Commit after each id: `test_all_or_none` fails (`{1: 'accepted'} != {1: 'open'}`).
2. Read the ids with `str.isdigit` alone: `test_nothing_chosen_or_a_bad_form[accept-ids3]` fails (`303 == 400`).
3. Skip `refused` on the post: `test_the_form_token_is_checked` fails (`(303, '') == (403, 'Bad form token')`).

## Out of scope

Absent: a migration; a dashboard block; a change to the MCP tools or `fin review`; transfer or rule proposals.
