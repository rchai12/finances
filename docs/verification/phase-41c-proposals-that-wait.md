# Verify Phase 41c: proposals that wait for another

Spec: `docs/phases/phase-41c-proposals-that-wait.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder let a new category name a proposed group, and a transaction or rule name a proposed category; such a proposal waits for its parent, is accepted only with or after it, and is declined with it. A template diff, a diff to seven earlier test files, and two test files were given.

These are correct and must not be reported: the target's existence worked out by a private helper shared by `waits_for` and the cascade; an import inside a function to avoid a cycle between `chains.py`, `proposals.py`, and `new_categories.py`; `accepting_order` written with recursion or a loop.

## 1. Gates

N is `4116` when Phase 41b was the last phase built. Sections: core, mcp, cli, web.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first core,mcp,cli,web` | last line `All checks passed.`; the summary lists `tests (core,mcp,cli,web): passed`; at least N + 12 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/integration/test_mcp_chains.py tests/integration/test_web_chains.py --no-cov` | exactly `12 passed` |
| `.venv/bin/python -m coverage report --include="*/finances/db/repositories/chains.py,*/finances/db/repositories/proposals.py,*/finances/db/repositories/new_categories.py,*/finances/categorize/service.py,*/finances/analysis/review.py,*/finances/views/review.py,*/finances/cli/review.py,*/finances/web/routes/review.py,*/finances/web/render.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | only the seven files of the given diff |

This search must list only `src/finances/db/repositories/chains.py` and `src/finances/db/repositories/proposals.py` (no front end declines one by one any more): `git grep -n "decline_proposal(" -- src/finances`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files and template of the spec's Scope (`chains.py` new), the seven files of the given diff, and three new test files. The template, the given test files, and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_each_proposal_names_what_it_waits_for`, `test_made_by_hand_the_proposals_stop_waiting`); the coder's declined-parent case | pass |
| R2 | gate 2 (`test_each_proposal_names_what_it_waits_for`, `test_an_unknown_name_is_still_refused`); the coder's accepted-or-declined-name case | pass |
| R3 | gate 2 (`test_made_by_hand_the_proposals_stop_waiting`); the coder's declined-parent and decided-transaction cases | pass |
| R4 | gate 2 (`test_a_waiting_proposal_is_not_accepted_alone`) | pass |
| R5 | gate 2 (`test_a_chain_accepted_together_goes_parents_first`); the coder's `[3, 9, 1, 2]` case | pass |
| R6 | gate 2 (`test_declining_a_parent_declines_what_waits_on_it`, `test_a_parent_and_its_child_declined_together`, the web declines); gate 5; the coder's refusal cases | pass |
| R7 | gate 2 (`test_the_list_shows_what_waits`, `test_the_review_page_shows_what_waits`); the coder's suggestions case | pass |
| R8 | gate 2 (the decline lines; `test_declining_a_parent_says_what_else_was_declined`, `test_declining_with_nothing_waiting_keeps_the_old_notice`) | pass |
| R9 | gate 1 (`test_mcp_more.py`, the given diff's item tests); gate 2 | pass |
| R10 | gate 4 | only those files |

## 4. Probe

None. Look once on a temporary `FIN_DATA_DIR`: with a group, a category in it, and a transaction proposal in that category, open the Review page, see `waits for #N` twice, decline the group, and see the notice and an empty list.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `waits_for`: the target's existence not checked | given `test_made_by_hand_the_proposals_stop_waiting` | `open` for 3 and 4 | `waits for #2` |
| 2. `accept_proposal`: a waiting one accepted | given `test_a_waiting_proposal_is_not_accepted_alone` (`--id 3`) | refused | `Pets` absent but 3 accepted, or an error from `set_category_by_hand` |
| 3. `accepting_order`: the ids as given | given `test_a_chain_accepted_together_goes_parents_first` (`3, 2, 1`) | lines 1, 2, 3 | refused at 3 |
| 4. `decline_proposals`: no cascade | given `test_declining_a_parent_declines_what_waits_on_it` | four lines | one line |
| 5. `decline_proposals`: one level only | the same test | 3 and 4 declined | only 2 |
| 6. `decline_proposals`: an id the cascade declined declined again | given `test_a_parent_and_its_child_declined_together` (`2, 3`) | three lines | refused: already declined |
| 7. the cascade without the target check | given `test_made_by_hand_the_proposals_stop_waiting` (decline 2) | one line | 3 and 4 declined too |
| 8. `propose_new_category`: the group as given | given `test_each_proposal_names_what_it_waits_for` (`pets`) | `Pets` | `pets` |
| 9. the web: the old notice always | given `test_declining_a_parent_says_what_else_was_declined` | `proposals-declined-waiting` | `proposals-declined` |

## 6. Out of scope

Each must be absent: a confirmation page; a grouped or indented list; accepting a parent for a dependent; a chain through a transfer or an alias; a migration.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
