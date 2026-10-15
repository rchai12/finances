# Verify Phase 16f: editing categories and rules

Spec: `docs/phases/phase-16f-editing-categories-and-rules.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added renaming and deleting categories and groups (moving a category's uses first) and editing rules, in the terminal and on the web. Two templates and two test files were given; no migration.

These are correct and must not be reported: `update()` statements for moving assignments and rules; a private helper in `app.py` for the rule edit page.

## 1. Gates

N is `2652` when Phase 24b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 32 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/e2e/test_cli_category_editing.py tests/integration/test_web_category_editing.py --no-cov` | exactly `32 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_categories.py tests/e2e/test_cli_categories.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.cli.categories --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|update\(" -- src/finances/web src/finances/cli/categories.py` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/cli/categories.py
 M src/finances/db/repositories.py
 M src/finances/web/app.py
 M src/finances/web/templates/categories.html
?? src/finances/web/templates/rule_edit.html
?? tests/e2e/test_cli_category_editing.py
?? tests/integration/test_category_editing_repositories.py
?? tests/integration/test_web_category_editing.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R8 | gates 2 and 3 | pass |
| R1 to R3 (edges) | the coder's `tests/integration/test_category_editing_repositories.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. Deleting a category moves its transactions but not its rules.
2. Editing a rule on the web does not run the rules again.
3. A group with categories can be deleted.
4. Renaming a category to a group's name is allowed.
5. `edit_rule` counts the rule itself as a duplicate.

## 6. Out of scope

Each must be absent: a migration; account changes; bulk categorizing; moving a category between groups.
