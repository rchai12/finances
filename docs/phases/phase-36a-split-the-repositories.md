# Phase 36a: split the repositories, and two more critical modules

## Goal

No behaviour change. `src/finances/db/repositories.py` has grown to 1433 lines (every table since Phase 2), and Phases 34 and 19 will add more. After this phase it is a **package**, `src/finances/db/repositories/`, with one module per area and an `__init__.py` that re-exports every name, so every existing `from finances.db.repositories import ...` (in 145 files) keeps working unchanged. Every function moves as it is.

The phase also does what `docs/testing.md` has promised since Phase 11: `domain/transfers.py` and `domain/spending.py` join the critical modules (both are already at 100% branch coverage).

The rest of the audit's tidy (rules out of `views`, the last hand-built tables) is Phase 36b.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-32-split-the-web-app.md` (the same kind of change, done for the web app)
- `src/finances/db/repositories.py`; `scripts/critical_modules.txt`, `scripts/check.py`, `tests/unit/test_check_script.py`, `docs/testing.md` ("Critical modules")

## Starting state

N is `3259` when Phase 14e is the last phase built.

The architect checked today's code: the module defines 86 public names, and other code imports every one of them and nothing else (no private name, no constant from elsewhere); no test replaces a repository function at run time or reads the file's source. A mechanical move into the areas below imports cleanly (no cycle), keeps every module under 400 lines, and passes the whole suite unchanged.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/repositories.py` | removed |
| `src/finances/db/repositories/__init__.py` and nine area modules | new (R1 to R4) |
| `scripts/critical_modules.txt`, `tests/unit/test_check_script.py`, `docs/testing.md` | the given diff (R5) |
| `tests/unit/test_repositories_split.py` | new: given |
| `docs/progress.md` | one new entry |

No other source file changes: callers keep importing from `finances.db.repositories`.

## Out of scope

- Any change to a function's body, signature, name, or behaviour; renaming the package; moving code out of `db`.
- Phase 36b's work (`views`, the CLI tables); a change to `orm.py`.

## Dependencies

None new. No migration.

## Design

Each name, public or private, lives in exactly one module:

| Module | Holds |
|---|---|
| `db/repositories/accounts.py` | `AccountExistsError`, `_ACCOUNT_TYPES`, `get_account_by_name`, `create_account`, `find_accounts_by_last4`, `list_accounts`, `account_names`, `get_account`, `rename_account`, `set_account_active`, `add_balance_snapshot`, `latest_balance`, `list_balance_snapshots`, `set_balance_snapshot`, `account_data_span` |
| `db/repositories/statements.py` | `create_statement`, `find_statement_by_hash`, `list_statements`, `statement_periods`, `statement_covers` |
| `db/repositories/transactions.py` | `_FINGERPRINT_CHUNK`, `existing_fingerprints`, `insert_transactions`, `list_transactions`, `list_transactions_between`, `list_transactions_by_day`, `list_transaction_descriptions`, `get_transaction`, `_require_transaction`, `_distinct_transaction_ids` |
| `db/repositories/feed.py` | `_feed_item`, `find_feed_transactions`, `insert_feed_transaction`, `update_feed_transaction`, `delete_feed_transaction`, `feed_posted_total`, `create_feed_pull`, `latest_feed_pull`, `list_provisional_transactions`, `confirm_transaction`, `find_unlinked_statement_transactions`, `link_feed_transaction` |
| `db/repositories/feed_links.py` | `map_feed_account`, `list_feed_accounts`, `record_seen_feed_account`, `list_new_feed_accounts`, `set_feed_account_ignored`, `list_feed_links`, `list_pending_feed_ids`, `record_sync_failure`, `clear_sync_failure`, `list_sync_failures` |
| `db/repositories/people.py` | `PersonExistsError`, `create_person`, `get_person_by_name`, `resolve_owner`, `list_people`, `set_account_owner`, `list_account_owners`, `set_cardholder_alias`, `list_cardholder_aliases` |
| `db/repositories/categories.py` | `CategoryExistsError`, `list_categories`, `_category_row`, `get_category_by_name`, `create_category`, `_leaf_category`, `list_rules`, `create_rule`, `delete_rule`, `CategoryDeletion`, `rename_category`, `_delete_budget_for`, `delete_category`, `edit_rule`, `list_category_assignments`, `_assignment_row`, `_assign`, `assign_by_rule`, `remove_category`, `set_categories_by_hand`, `clear_categories_by_hand`, `set_category_by_hand`, `clear_category_by_hand`, `list_uncategorized`, `count_uncategorized` |
| `db/repositories/budgets.py` | `_BUDGET_MIN`, `_BUDGET_MAX`, `set_budget`, `remove_budget`, `list_budgets` |
| `db/repositories/transfers.py` | `_names`, `list_transfer_movements`, `list_transfer_rejections`, `list_transfer_pairs`, `find_transfer_pair`, `_check_transfer`, `_drop_rejection`, `_store_rejection`, `create_transfer_pair`, `reject_transfer`, `unpair_transfer` |

The import direction between areas is one way: `budgets` imports from `categories`; `categories` and `feed` import from `transactions` and `transfers`; `feed` also imports from `categories`. No area imports the package itself.

## Requirements

- **R1.** Every definition of today's `repositories.py` (function, class, and module constant) moves, unchanged, into the module the table names. Each module keeps the imports it needs (from `sqlalchemy`, `finances.db.orm`, `finances.domain`, and the other areas, by their module paths) and no others; ruff passes.
- **R2.** `db/repositories/__init__.py` holds a one-line docstring, `from finances.db.repositories.<area> import ...` lines for every public name, and `__all__` listing the 86 public names; it defines nothing itself.
- **R3.** No area module imports `finances.db.repositories` itself (only other areas by their full module path), so importing any one area works on its own.
- **R4.** No module of the package is longer than 400 lines. `src/finances/db/repositories.py` no longer exists.
- **R5.** Apply the given diff: `scripts/critical_modules.txt` and the copy of the list in `tests/unit/test_check_script.py` gain `domain/transfers.py` and `domain/spending.py`, and `docs/testing.md` lists them with the others. `scripts/check.py`'s critical coverage then holds both at 100% of lines and branches.

## Given tests

14 tests in one file. Two of them already pass on today's code as guards (they check the package's area modules, of which there are none yet).

`tests/unit/test_repositories_split.py`

```python
import ast
import importlib
from pathlib import Path

import pytest

import finances.db.repositories as repositories

PACKAGE = Path(repositories.__file__).parent
HOMES = {
    "accounts": [
        "AccountExistsError",
        "account_data_span",
        "account_names",
        "add_balance_snapshot",
        "create_account",
        "find_accounts_by_last4",
        "get_account",
        "get_account_by_name",
        "latest_balance",
        "list_accounts",
        "list_balance_snapshots",
        "rename_account",
        "set_account_active",
        "set_balance_snapshot",
    ],
    "statements": [
        "create_statement",
        "find_statement_by_hash",
        "list_statements",
        "statement_covers",
        "statement_periods",
    ],
    "transactions": [
        "existing_fingerprints",
        "get_transaction",
        "insert_transactions",
        "list_transaction_descriptions",
        "list_transactions",
        "list_transactions_between",
        "list_transactions_by_day",
    ],
    "feed": [
        "confirm_transaction",
        "create_feed_pull",
        "delete_feed_transaction",
        "feed_posted_total",
        "find_feed_transactions",
        "find_unlinked_statement_transactions",
        "insert_feed_transaction",
        "latest_feed_pull",
        "link_feed_transaction",
        "list_provisional_transactions",
        "update_feed_transaction",
    ],
    "feed_links": [
        "clear_sync_failure",
        "list_feed_accounts",
        "list_feed_links",
        "list_new_feed_accounts",
        "list_pending_feed_ids",
        "list_sync_failures",
        "map_feed_account",
        "record_seen_feed_account",
        "record_sync_failure",
        "set_feed_account_ignored",
    ],
    "people": [
        "PersonExistsError",
        "create_person",
        "get_person_by_name",
        "list_account_owners",
        "list_cardholder_aliases",
        "list_people",
        "resolve_owner",
        "set_account_owner",
        "set_cardholder_alias",
    ],
    "categories": [
        "CategoryDeletion",
        "CategoryExistsError",
        "assign_by_rule",
        "clear_categories_by_hand",
        "clear_category_by_hand",
        "count_uncategorized",
        "create_category",
        "create_rule",
        "delete_category",
        "delete_rule",
        "edit_rule",
        "get_category_by_name",
        "list_categories",
        "list_category_assignments",
        "list_rules",
        "list_uncategorized",
        "remove_category",
        "rename_category",
        "set_categories_by_hand",
        "set_category_by_hand",
    ],
    "budgets": [
        "list_budgets",
        "remove_budget",
        "set_budget",
    ],
    "transfers": [
        "create_transfer_pair",
        "find_transfer_pair",
        "list_transfer_movements",
        "list_transfer_pairs",
        "list_transfer_rejections",
        "reject_transfer",
        "unpair_transfer",
    ],
}


def test_the_package_holds_one_module_per_area() -> None:
    assert (PACKAGE / "__init__.py").is_file()
    assert not (PACKAGE.parent / "repositories.py").exists()
    names = sorted(path.stem for path in PACKAGE.glob("*.py") if path.stem != "__init__")
    assert names == sorted(HOMES)


def test_the_facade_offers_every_name_and_only_those() -> None:
    expected = sorted(name for names in HOMES.values() for name in names)
    assert len(expected) == 86
    assert sorted(repositories.__all__) == expected
    public = sorted(name for name in vars(repositories) if not name.startswith("_"))
    assert sorted(set(public) - set(HOMES)) == expected


@pytest.mark.parametrize("area", sorted(HOMES))
def test_each_name_lives_in_its_area(area: str) -> None:
    module = importlib.import_module(f"finances.db.repositories.{area}")
    for name in HOMES[area]:
        found = getattr(repositories, name)
        assert found is getattr(module, name), name
        assert found.__module__ == f"finances.db.repositories.{area}", name


def test_the_facade_only_imports() -> None:
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, ast.ImportFrom):
            assert node.module is not None and node.module.startswith("finances.db.repositories.")
            continue
        assert isinstance(node, ast.Assign) and [t.id for t in node.targets] == ["__all__"]


def test_no_area_imports_the_facade() -> None:
    for path in PACKAGE.glob("*.py"):
        if path.stem == "__init__":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "finances.db.repositories", path.name
            if isinstance(node, ast.Import):
                assert all(alias.name != "finances.db.repositories" for alias in node.names), (
                    path.name
                )


def test_no_module_is_longer_than_400_lines() -> None:
    sizes = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in PACKAGE.glob("*.py")
    }
    assert {name: size for name, size in sizes.items() if size > 400} == {}
```

The critical-modules diff (apply it exactly):

```text
diff --git a/docs/testing.md b/docs/testing.md
index 25ff4cc..49fe574 100644
--- a/docs/testing.md
+++ b/docs/testing.md
@@ -38,7 +38,8 @@ Bugs here silently corrupt money data, so every line and every branch of each mu
 - `domain/feed_setup.py` (guessing how to set up a new SimpleFIN account)
 - `analysis/people.py` (whose money a transaction is)
 - `db/backup.py` (copying, checking, and restoring the database)
-- Planned for Phase 36: `domain/transfers.py` (transfer candidates and clear pairs, Phase 11c) and `domain/spending.py` (kinds, spending lines, refunds, Phase 12a and 35), both built without joining this list
+- `domain/transfers.py` (transfer candidates and clear pairs; added in Phase 36a)
+- `domain/spending.py` (kinds, spending lines, refunds; added in Phase 36a)
 
 ## Commands
 
diff --git a/scripts/critical_modules.txt b/scripts/critical_modules.txt
index 9ef0fae..e738497 100644
--- a/scripts/critical_modules.txt
+++ b/scripts/critical_modules.txt
@@ -10,3 +10,5 @@ sync/simplefin.py
 domain/feed_setup.py
 analysis/people.py
 db/backup.py
+domain/transfers.py
+domain/spending.py
diff --git a/tests/unit/test_check_script.py b/tests/unit/test_check_script.py
index 1b73e6c..f25f027 100644
--- a/tests/unit/test_check_script.py
+++ b/tests/unit/test_check_script.py
@@ -18,6 +18,8 @@ CRITICAL = [
     "domain/feed_setup.py",
     "analysis/people.py",
     "db/backup.py",
+    "domain/transfers.py",
+    "domain/spending.py",
 ]
 
 
```

## Tests to write

None. The whole suite is the test that nothing changed; the verifier also compares every definition with the last commit's.

## Rules for this phase

- Move, do not edit: a body that changes, even to tidy it, is outside this phase.
- Earlier tests change only by the given diff (`tests/unit/test_check_script.py`); every other earlier test passes unchanged.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`; the verifier compares against the last commit.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file: `tests/unit/test_repositories_split.py`, 14 tests; at least N + 14 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/unit/test_check_script.py`;
- `git diff --stat HEAD -- src` lists only `src/finances/db/repositories.py` (deleted), with the package untracked;
- `.venv/bin/python scripts/check.py` shows `critical coverage: passed` with the two new modules.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 36a: split the repositories (YYYY-MM-DD)`.
