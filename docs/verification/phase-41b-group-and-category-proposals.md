# Verify Phase 41b: the agent proposes a group or a category

Spec: `docs/phases/phase-41b-group-and-category-proposals.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added two proposal kinds, a new group and a new category in an existing group, with their MCP tools, their texts in `fin review` and on the Review page, and their accepting through `create_group` and `create_category`. A migration, a diff to `tests/support.py` and ten earlier test files, and two test files were given.

These are correct and must not be reported: private helpers in `new_categories.py` that `proposals.py` calls for out of date and accepting; the kind's flags worked out by a small pure function in `domain/proposals.py`; an import inside a function to avoid a cycle between `proposals.py` and `new_categories.py`.

## 1. Gates

N is `4092` when Phase 41a was the last phase built. Sections: migrations, core, mcp, cli, web.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first migrations,core,mcp,cli,web` | last line `All checks passed.`; the summary lists `tests (migrations,core,mcp,cli,web): passed`; at least N + 15 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/integration/test_migration_0022.py tests/integration/test_mcp_new_categories.py --no-cov` | exactly `15 passed` |
| `.venv/bin/python -m coverage report --include="*/finances/domain/proposals.py,*/finances/db/repositories/proposals.py,*/finances/db/repositories/new_categories.py,*/finances/db/orm.py,*/finances/views/review.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | `tests/support.py` and the ten files of the given diff, no other |

This search must print nothing: `git grep -n -e "create_group" -e "create_category" -- src/finances/mcp_server` (the tools only store proposals).

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope (`new_categories.py` and the migration new), the eleven test files of the given diff, and three new test files. The migration, the given test files, and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0022.py`) | pass |
| R2 | gate 1 (`test_proposal_rules.py`, `test_rule_proposal_rules.py`); the coder's text cases | pass |
| R3 | gate 2 (`test_the_agent_proposes_a_group`, `test_a_refused_proposal`, `test_one_open_proposal_for_a_name`, `test_a_declined_name_is_not_proposed_again`); the coder's kind and stored-flags cases | pass |
| R4 | gate 2 (`test_the_agent_proposes_a_category_in_a_group`, `test_a_refused_proposal`); the coder's spelling and per-kind cases | pass |
| R5 | gate 2 (`test_a_group_whose_name_was_taken_since_is_out_of_date`); the coder's deleted-group case | pass |
| R6 | gate 2 (the two accept tests); the coder's History case | pass |
| R7 | gate 2 (the two accept tests' rows and lines); the coder's text cases | pass |
| R8 | gate 1 (`test_mcp_more.py`, `test_mcp_accounts.py`, `test_mcp_proposals.py`); gate 2 | pass |
| R9 | gate 4 | only those files |

## 4. Probe

None.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `propose_group`: the name compared with case | given `test_a_refused_proposal` (`food`) | taken | stored |
| 2. `propose_group`: the name not stripped | given `test_the_agent_proposes_a_group` (`" Pets "`) | `Pets` | `" Pets "` |
| 3. `propose_new_category`: a category accepted as the group | given `test_a_refused_proposal` (group `Dining`) | `group not found` | stored |
| 4. `propose_new_category`: the group stored as given | given `test_the_agent_proposes_a_category_in_a_group` (`home`) | `Home` | `home` |
| 5. the open check only within the same kind | given `test_one_open_proposal_for_a_name` (category `pets` after group `Pets`) | refused | stored |
| 6. out of date: the group's name never checked | given `test_a_group_whose_name_was_taken_since_is_out_of_date` | `out of date`, accept refused | accepted |
| 7. accepting a category: the tax flag dropped | given `test_a_person_accepts_a_category_in_the_terminal` | `is_tax` True | False |
| 8. `_proposal_item`: `"new"` only on the new kinds | given diff (`test_mcp_proposals.py`, a category item) | `"new": None` present | key missing |
| 9. `proposed_text`: the flag words in another order | the coder's income-and-sensitive case | `(income, sensitive)` | `(sensitive, income)` |

## 6. Out of scope

Each must be absent: a category in a proposed group; a transaction or rule in a proposed category; `parent_id` ever set; "waits for"; cascading declines; a new web route or template; a tool that creates a group or category.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
