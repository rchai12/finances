# Verify Phase 44b: renaming and deleting categories by proposal

Spec: `docs/phases/phase-44b-category-changes.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added `propose_category_change`: renaming a category or group, or deleting one, checked by running the real change inside a savepoint that is rolled back, and accepted through `rename_category` and `delete_category`. Accepting a rename carries the agent's other open proposals to the new name; a delete puts them out of date. A diff to `tests/support.py` and eleven earlier test files and one test file were given.

These are correct and must not be reported: the dry run written as one private helper used by the checks and by out of date; an import inside a function to avoid a cycle with `proposals.py`, `chains.py`, or `rule_changes.py`.

## 1. Gates

N is `4190` when Phase 44a was the last phase built. Sections: core, mcp, cli, web.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first core,mcp,cli,web` | last line `All checks passed.`; the summary lists `tests (core,mcp,cli,web): passed`; at least N + 18 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/integration/test_mcp_category_changes.py --no-cov` | exactly `18 passed` |
| `.venv/bin/python -m coverage report --include="*/finances/domain/proposals.py,*/finances/db/repositories/proposals.py,*/finances/db/repositories/chains.py,*/finances/db/repositories/rule_changes.py,*/finances/db/repositories/category_changes.py,*/finances/analysis/review.py,*/finances/views/review.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | `tests/support.py` and the eleven files of the given diff, no other |
| `git grep -n -e "rename_category" -e "delete_category" -- src/finances/mcp_server` | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope (`category_changes.py` new), the twelve files of the given diff, and two new test files. The given test file and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 1 (`test_proposal_rules.py`, `test_rule_proposal_rules.py`); the coder's History case | pass |
| R2 | gate 2 (`test_a_refused_change`, `test_one_open_change_for_a_category`, `test_a_declined_change_is_not_proposed_again`); the coder's dry-run case | pass |
| R3 | gate 2 (the rename, delete, and empty-group tests) | pass |
| R4 | gate 2 (`test_a_category_renamed_by_hand_since_puts_it_out_of_date`, `test_a_delete_puts_the_agents_other_proposals_out_of_date`); the coder's `move_to` and taken-name cases | pass |
| R5 | gate 2 (`test_a_rename_carries_the_agents_other_proposals`); the coder's group and rule-change cases | pass |
| R6 | gate 2 (the review rows); the coder's Review page case | pass |
| R7 | gate 1 (`test_mcp_more.py`, `test_mcp_accounts.py`, `test_mcp_proposals.py`); gate 2; gate 5 | pass |
| R8 | gate 4 | only those files |

## 4. Probe

None.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. the dry run not rolled back | given `test_one_open_change_for_a_category` (the rename's dry run, then a delete of `Dining`) | `this category already has an open proposal` | `category not found` |
| 2. no dry run: only the name checked | given `test_a_refused_change` (`Dining` delete without `move_to`) | the in-use message | stored |
| 3. no sameness check | the same test (`rename_to: Dining`) | `the name already is like this` | the taken message from `rename_category` |
| 4. out of date by id only, the name not compared | given `test_a_category_renamed_by_hand_since_puts_it_out_of_date` | `out of date` | accepted |
| 5. a rename leaves the other proposals as they were | given `test_a_rename_carries_the_agents_other_proposals` | `Restaurants`, open | `Dining`, out of date or refused |
| 6. a `CATEGORY` proposal into a deleted category not out of date | given `test_a_delete_puts_the_agents_other_proposals_out_of_date` | `out of date` | `open` |
| 7. `move_to` stored as given | given `test_the_agent_proposes_deleting_a_category` (`coffee & dessert`) | `Coffee & Dessert` | lower case |
| 8. `review_items`: the category's id read as a transaction's | given `test_the_agent_proposes_renaming_a_category` | empty cells | a transaction's date and amount |

## 6. Out of scope

Each must be absent: moving a category to another group; changing a group's flags; a `move_to` still only proposed.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
