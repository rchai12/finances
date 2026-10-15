# Verify Phase 16f: editing and bulk

Spec: `docs/phases/phase-16f-editing-and-bulk.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added renaming and deleting categories (moving their uses first), editing rules, renaming, closing, and reopening accounts, and categorizing several transactions at once, in the terminal and on the web. Four templates and two test files were given; no migration.

These are correct and must not be reported: `update()` statements in the repositories for moving assignments and rules; a private helper in `app.py` that rebuilds the filter query; Typer's `list[int]` for `--id`.

## 1. Gates

N is `2652` when Phase 24b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 61 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/e2e/test_cli_editing.py tests/integration/test_web_editing.py --no-cov` | exactly `61 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_pages.py tests/integration/test_web_categories.py tests/integration/test_web_search.py tests/e2e/test_cli_categories.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.cli.categories --cov=finances.cli.accounts --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|update\(" -- src/finances/web src/finances/cli/categories.py src/finances/cli/accounts.py` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/cli/accounts.py
 M src/finances/cli/categories.py
 M src/finances/db/repositories.py
 M src/finances/web/app.py
 M src/finances/web/templates/accounts.html
 M src/finances/web/templates/categories.html
 M src/finances/web/templates/transactions.html
?? src/finances/web/templates/rule_edit.html
?? tests/e2e/test_cli_editing.py
?? tests/integration/test_editing_repositories.py
?? tests/integration/test_web_editing.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R16 | gates 2 and 3 | pass |
| R1, R2, R3, R4, R6 (edges) | the coder's `tests/integration/test_editing_repositories.py` | each item of the spec's "Tests to write" has a test |
| R6 | read the bulk functions | every id and the category are checked before any change |
| R15 | read the bulk route | `back` keeps only the page's filter fields; the redirect is built from them |

## 4. Probe

None: the given tests drive every command and route. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. Deleting a category moves its transactions but not its rules.
2. Editing a rule does not run the rules again on the web.
3. The bulk redirect keeps an unknown field from `back`.
4. A group with categories can be deleted.
5. Renaming a category to a group's name is allowed.

## 6. Out of scope

Each must be absent: a migration; moving a category between groups; deleting an account; JavaScript.
