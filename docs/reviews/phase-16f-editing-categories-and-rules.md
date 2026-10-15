# Review: Phase 16f

- Verdict: PASS
- Passed: 2692
- Findings: 0
- Approved deviations: None
- For the architect: when a phase adds `GET /path/{id}` beside existing `POST /path/add` and `POST /path/delete`, say that GET on `add` and `delete` must stay 405. Without an explicit guard, the parameterized route answers 404 and breaks earlier token-refusal tests.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: `GET /categories/rules/{rule_id}` answers 405 when the id is `add` or `delete`, so earlier tests that expect Method Not Allowed on those POST-only paths still pass.

## Gates

- `scripts/check.py`: `2692 passed`, `All checks passed.` (N + 32 = 2684; 8 more are the coder's)
- Given tests: `32 passed`
- Earlier category tests: `tests/integration/test_web_categories.py tests/e2e/test_cli_categories.py`, all passed
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists exactly the guide's 9 paths, plus this review
- Given files: `categories.html`, `rule_edit.html`, `tests/e2e/test_cli_category_editing.py`, and `tests/integration/test_web_category_editing.py` are identical to the spec's blocks

## Requirement checklist

- R1: `rename_category` (`repositories.py:945`) finds by name, checks length and uniqueness of another row, allows a change of its own case. Tests: given rename tests; `test_renaming_a_group_keeps_its_categories`, `test_renaming_keeps_a_change_of_its_own_case`.
- R2: `delete_category` (`repositories.py:962`) refuses a non-empty group, moves assignments and rules when `move_to` is given, keeps an assignment's source. Tests: given delete tests; `test_a_moved_assignment_keeps_its_source`, `test_an_unused_category_with_a_move_to`, `test_deleting_a_group_ignores_move_to`.
- R3: `edit_rule` (`repositories.py:1026`) fills missing arguments from the rule, checks as `create_rule` does, and excludes itself from the duplicate check (line 1052). Tests: given rule-edit tests; `test_editing_only_the_priority_keeps_the_rest`, `test_editing_refuses_an_empty_pattern`.
- R4, R5: the given CLI tests pass.
- R6, R7: the given web tests pass. Routes use `refused`; the rule edit page is `_rule_edit_page`; POST runs `edit_rule` then `categorize` in one session (`change_rule`, line 858).
- R8: the given templates are used as shown; the rules table keeps its columns with the ID linking to the edit page.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the three 16f test files run, and the file restored.

1. Deleting a category moves its transactions but not its rules: `test_a_category_in_use_moves_before_it_goes`, `test_delete_a_category_after_moving_what_uses_it`, and `test_a_moved_assignment_keeps_its_source` fail.
2. Editing a rule on the web does not run the rules again: `test_edit_a_rule` fails.
3. A group with categories can be deleted: `test_a_refused_delete` (the Food group case) fails.
4. Renaming a category to a group's name is allowed: `test_a_refused_rename[Dining-food-...]` fails.
5. `edit_rule` counts the rule itself as a duplicate: `test_edit_a_rule_and_the_rules_run_again`, `test_edit_a_rule`, and `test_editing_only_the_priority_keeps_the_rest` fail.

## Out of scope

Absent: a migration; account changes; bulk categorizing; moving a category between groups.
