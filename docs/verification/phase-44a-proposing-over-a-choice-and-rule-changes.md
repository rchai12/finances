# Verify Phase 44a: proposing over a person's choice, and changing a rule

Spec: `docs/phases/phase-44a-proposing-over-a-choice-and-rule-changes.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder let `propose_category` propose over a category a person set, made a category proposal out of date only when a person changed the category since, and added `propose_rule_change` to edit or delete a rule. A migration, a diff to `tests/support.py` and twelve earlier test files, and two test files were given.

These are correct and must not be reported: the rule-change checks reusing private helpers of `categories.py`; a small private helper that gives a transaction's current category name; an import inside a function to avoid a cycle between `proposals.py` and `rule_changes.py`; a private helper moved out of `proposals.py` to keep it within 400 lines.

## 1. Gates

N is `4163` when Phase 43 was the last phase built. Sections: migrations, core, mcp, cli, web.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first migrations,core,mcp,cli,web` | last line `All checks passed.`; the summary lists `tests (migrations,core,mcp,cli,web): passed`; at least N + 17 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/integration/test_migration_0024.py tests/integration/test_mcp_rule_changes.py --no-cov` | exactly `17 passed` |
| `.venv/bin/python -m coverage report --include="*/finances/db/orm.py,*/finances/domain/proposals.py,*/finances/db/repositories/proposals.py,*/finances/db/repositories/rule_changes.py,*/finances/categorize/service.py,*/finances/analysis/review.py,*/finances/views/review.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | `tests/support.py` and the twelve files of the given diff, no other |
| `git grep -n -e "edit_rule" -e "delete_rule" -- src/finances/mcp_server` | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope (`rule_changes.py` and the migration new), the thirteen files of the given diff, and three new test files. The migration, the given test files, and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0024.py`) | pass |
| R2 | gate 1 (`test_proposal_rules.py`, `test_rule_proposal_rules.py`); the coder's History case | pass |
| R3 | gate 2 (`test_a_persons_choice_can_be_proposed_over`, `test_the_category_it_has_is_refused`); gate 1 (`test_proposals.py`, `test_splits_stored.py`); the coder's split-and-transfer case | pass |
| R4 | gate 2 (`test_a_person_changing_it_since_puts_it_out_of_date`); the coder's three before cases | pass |
| R5 | gate 2 (`test_the_agent_proposes_changing_a_rule`, `test_a_refused_rule_change`, `test_one_open_change_for_a_rule`, `test_a_declined_change_is_not_proposed_again`); the coder's duplicate cases | pass |
| R6 | gate 2 (the edit and delete accept tests, `test_a_rule_edited_since_puts_it_out_of_date`) | pass |
| R7 | gate 2 (the review rows); the coder's Review page case | pass |
| R8 | gate 1 (`test_mcp_more.py`, `test_mcp_accounts.py`, `test_mcp_proposals.py`); gate 2; gate 5 | pass |
| R9 | gate 4 | only those files |

## 4. Probe

None.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `propose_category`: a person's choice still refused | given `test_a_persons_choice_can_be_proposed_over` (transaction 2) | stored | `a person has already decided this transaction` |
| 2. `propose_category`: the current category not checked | given `test_the_category_it_has_is_refused` (`groceries`) | refused | stored |
| 3. out of date: today's rule (set by hand) kept | given `test_a_persons_choice_can_be_proposed_over` | `open` | `out of date` |
| 4. out of date: `before` ignored, never out of date | given `test_a_person_changing_it_since_puts_it_out_of_date` | `out of date` | `open` |
| 5. `propose_rule_change`: no sameness check | given `test_a_refused_rule_change` (`category: dining`) | refused | stored |
| 6. `propose_rule_change`: fields allowed with delete | the same test (`CHANGE` with `delete`) | refused | stored |
| 7. a rule change's out of date not checked | given `test_a_rule_edited_since_puts_it_out_of_date` | `out of date`, accept refused | accepted |
| 8. `accept_proposals`: no categorize after a rule change | given `test_the_agent_proposes_changing_a_rule` | the `Categorized 2 transactions` line | missing |
| 9. the declined check without the values | given `test_a_declined_change_is_not_proposed_again` (priority 6) | proposal 2 | refused |
| 10. `review_items`: the rule's id read as a transaction's | given `test_the_agent_proposes_changing_a_rule` (rule 1, transaction 1 exists) | empty cells | transaction 1's date and amount |

## 6. Out of scope

Each must be absent: renaming or deleting a category or group; a rule change into a proposed category; a split or transfer given one category by a proposal.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
