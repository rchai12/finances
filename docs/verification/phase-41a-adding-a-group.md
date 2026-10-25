# Verify Phase 41a: adding a group

Spec: `docs/phases/phase-41a-adding-a-group.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added `create_group`, `fin categories add-group`, and a form on the Categories page, and made an empty group show in the category list. A template diff, diffs to two earlier tests, and two test files were given.

These are correct and must not be reported: the web's kind turned into flags by a small private helper; the CLI's flag words built by a private helper or shared with `_kind`.

## 1. Gates

N is `4069` when Phase 40 was the last phase built. Sections: core, web, cli.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first core,web,cli` | last line `All checks passed.`; the summary lists `tests (core,web,cli): passed`; at least N + 16 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/e2e/test_cli_groups.py tests/integration/test_web_groups.py --no-cov` | exactly `16 passed` |
| `.venv/bin/python -m coverage report --include="*/finances/db/repositories/categories.py,*/finances/cli/categories.py,*/finances/web/routes/categories.py,*/finances/views/categories.py,*/finances/web/render.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_repositories_split.py` and `tests/unit/test_web_split.py` |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files and template of the spec's Scope, the two split tests, and three new test files. The given test files, the template, and the test diffs equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2; gate 1 (`test_repositories_split.py`) | pass |
| R2 | gate 2 (`test_a_refused_group`, `test_both_kinds_are_refused_before_a_taken_name`); the coder's records-none case | pass |
| R3 | gate 2 (`test_a_spending_group`, `test_a_group_with_flags`, `test_add_group_needs_a_migrated_database`) | pass |
| R4 | gate 2 (the five web tests); gate 1 (`test_web_split.py`) | pass |
| R5 | gate 2 (`test_an_empty_group_is_listed`); the coder's transfer-group line | pass |
| R6 | gate 4 | only those files |

## 4. Probe

None. Look once in a real browser on a temporary `FIN_DATA_DIR`: add a sensitive spending group on the Categories page, see `Group added.` and the group in the list with no category, then add a category to it with the form below.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `create_group`: the taken name checked before both kinds | given `test_both_kinds_are_refused_before_a_taken_name` (`Food`, `--transfer --income`) | the both-kinds message | the taken message |
| 2. `create_group`: the name not stripped | given `test_a_refused_group` (`"   "`) | the length message | a group named with spaces |
| 3. `create_group`: `transfer` ignored | given `test_a_category_takes_its_new_groups_flags` | `Wire Out` is a transfer | not a transfer |
| 4. the route: an unknown kind taken as spending | given `test_an_unknown_kind_is_refused_and_the_form_kept` (`savings`) | 400, no group | 303, a group |
| 5. `category_lines`: an empty group left out | given `test_an_empty_group_is_listed` | `Pets`, empty, `sensitive` | no line |
| 6. `category_lines`: a group line even when it has categories | the same test, after `Dog Food` | no empty line | an empty line |
| 7. the CLI: the flag words in another order | given `test_a_group_with_flags` | `(income, sensitive)` | `(sensitive, income)` |

## 6. Out of scope

Each must be absent: a way to change a group's flags; a first category added with the group; a tax flag on a group; anything of 41b or 41c (proposals, the Review page).

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
