# Verify Phase 16j: accounts and bulk categorizing

Spec: `docs/phases/phase-16j-accounts-and-bulk.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added renaming, closing, and reopening accounts and categorizing several transactions at once, in the terminal and on the web. Two templates and two test files were given; no migration.

These are correct and must not be reported: Typer's `list[int]` for `--id`; a private helper in `app.py` that rebuilds the filter query.

## 1. Gates

N is the passed count in Phase 16f's progress entry.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 29 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/e2e/test_cli_accounts_and_bulk.py tests/integration/test_web_accounts_and_bulk.py --no-cov` | exactly `29 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_pages.py tests/integration/test_web_search.py tests/integration/test_web_forms.py tests/e2e/test_cli_categories.py --no-cov` | all passed |
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
 M src/finances/web/templates/transactions.html
?? tests/e2e/test_cli_accounts_and_bulk.py
?? tests/integration/test_account_and_bulk_repositories.py
?? tests/integration/test_web_accounts_and_bulk.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R9 | gates 2 and 3 | pass |
| R1, R3 (edges), closing | the coder's `tests/integration/test_account_and_bulk_repositories.py` | each item of the spec's "Tests to write" has a test |
| R3 | read the bulk functions | every id and the category are checked before any change |
| R8 | read the bulk route | `back` keeps only the page's filter fields |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. The bulk redirect keeps an unknown field from `back`.
2. One distinct id prints the several-transactions line.
3. A closed account still shows on the Accounts page by default.
4. `select=all` does not check the boxes.
5. Renaming an account to another account's name in another case is allowed.

## 6. Out of scope

Each must be absent: a migration; deleting an account; changing an account's type or institution; JavaScript.
