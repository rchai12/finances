# Phase 36b: views that only format (accounts, people, categories)

## Goal

No behaviour change. Today several `views` modules open the database themselves, so the layer meant to turn results into text also loads data and, in two places, applies a rule. After this phase the accounts, people, and categories views take plain data and only format it; the loading moves to two new `analysis` modules; the counting rule of 35b's card-credit note moves to `analysis`; and the transaction page's refund text, which the route builds today, moves to a new `views/refunds.py`. Every page and command shows exactly what it shows today.

Phase 36c does the same for the sync and transfers views (including the Keychain read), shares the last hand-built CLI tables and the two `_change` helpers, and then forbids any `views` import of the database. This phase freezes the list of `views` modules that still load data, so it can only shrink.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/architecture.md`, "Dependency direction" and the known drift it lists
- `src/finances/views/accounts.py`, `views/people.py`, `views/categories.py`; `src/finances/analysis/people.py` (`load_attribution`), `analysis/refunds.py` (`RefundFacts`)
- the callers: `src/finances/cli/accounts.py`, `cli/people.py`, `cli/categories.py`, `src/finances/web/routes/accounts.py`, `routes/people.py`, `routes/categories.py`, `routes/budgets.py`, `routes/transactions.py`

## Starting state

N is `3273` when Phase 36a is the last phase built.

`analysis/people.py` is a critical module; this phase does not touch it (the new loaders live in a new module).

## Scope

| Path | What changes |
|---|---|
| `src/finances/analysis/listings.py`, `src/finances/analysis/categories.py` | new (R1, R2) |
| `src/finances/views/accounts.py`, `views/people.py`, `views/categories.py` | take data (R3, R4) |
| `src/finances/views/refunds.py` | new (R5) |
| the eight callers above | load, then format (R6) |
| `tests/integration/test_views.py`, `tests/integration/test_category_views.py` | the given diff (R8) |
| `tests/unit/test_views_take_data.py` | new: given |
| `docs/progress.md` | one new entry |

## Out of scope

- `views/sync.py`, `views/transfers.py`, `views/backups.py` (36c); the CLI tables and `_change` (36c).
- Any change to what a page or command shows, to a template, or to `analysis/people.py`.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/analysis/listings.py
@dataclass(frozen=True)
class AccountListing:
    account: Account
    owner: str | None           # the owner's name, "Joint", or None

@dataclass(frozen=True)
class PersonListing:
    name: str
    owns: list[str]             # account names, closed too, in list_accounts' order
    cardholders: list[str]      # sorted

def account_listing(session: Session, *, include_inactive: bool = False) -> list[AccountListing]: ...
def people_listing(session: Session) -> list[PersonListing]: ...

# src/finances/analysis/categories.py
@dataclass(frozen=True)
class RuleListing:
    rule: CategoryRule
    category: str

@dataclass(frozen=True)
class UncategorizedItem:
    transaction: Transaction
    account: Account

@dataclass(frozen=True)
class TransactionFacts:
    transaction: Transaction
    account: str                          # the account's name
    category: str | None
    assignment: CategoryAssignment | None

def category_tree(session: Session) -> list[tuple[Category, list[Category]]]: ...
def rule_listing(session: Session) -> list[RuleListing]: ...
def uncategorized_items(session: Session, limit: int) -> list[UncategorizedItem]: ...
def card_credit_count(items: list[UncategorizedItem]) -> int: ...
def transaction_facts(session: Session, transaction_id: int) -> TransactionFacts | None: ...

# src/finances/views/accounts.py, views/people.py
def account_rows(listing: list[AccountListing]) -> list[AccountRow]: ...
def people_rows(listing: list[PersonListing]) -> list[PersonRow]: ...

# src/finances/views/categories.py  (row classes and CARD_CREDITS unchanged)
def category_lines(tree: list[tuple[Category, list[Category]]]) -> list[CategoryLine]: ...
def category_choices(tree: list[tuple[Category, list[Category]]]) -> list[tuple[str, list[str]]]: ...
def rule_lines(listing: list[RuleListing]) -> list[RuleLine]: ...
def card_credits_note(count: int) -> str | None: ...
def uncategorized_lines(items: list[UncategorizedItem]) -> list[UncategorizedLine]: ...
def transaction_detail(facts: TransactionFacts) -> TransactionDetail: ...

# src/finances/views/refunds.py
@dataclass(frozen=True)
class RefundLine:
    id: int
    date: str        # the transaction's day (bought, else posted), ISO
    amount: str      # format_cents

@dataclass(frozen=True)
class RefundView:
    amount: str                  # the refund's amount as its page shows it
    purchase: RefundLine | None

def refund_view(facts: RefundFacts, amount: str) -> RefundView | None: ...
def refunded_lines(facts: RefundFacts) -> list[RefundLine]: ...
```

## Requirements

- **R1.** `account_listing` and `people_listing` load what `account_rows` and `people_rows` load today, in the same order, and return the data unformatted (`owner` from `load_attribution(...).owner`).
- **R2.** `category_tree` gives each group with its categories, both in `list_categories`' order; `rule_listing` each rule in `list_rules`' order with its category's name; `uncategorized_items` each of `list_uncategorized(session, limit)` with its account (closed accounts included); `card_credit_count` how many items are above zero on a `credit_card` account; `transaction_facts` the transaction, its account's name, its category's name or None, and its assignment, or None for an unknown id.
- **R3.** `account_rows` and `people_rows` format a listing exactly as today (owner `""` when None; the names joined with `, `).
- **R4.** `views/categories.py` keeps its row classes, `CARD_CREDITS`, `categorized_text`, and every text it produces today; its functions take the data above instead of a session. `card_credits_note(count)` is None for 0.
- **R5.** `refund_view` is None when `facts.is_refund` is false, else `RefundView(amount, purchase)` with the purchase as a `RefundLine` or None; `refunded_lines` gives one `RefundLine` per `facts.refunds`. The template reads them by the same names it reads today (`refund.amount`, `refund.purchase.id`, `item.date`, and so on), so it does not change.
- **R6.** Each caller loads with the `analysis` function and formats with the view, inside the same reading session as today; the transaction route builds no text of its own (no `format_cents`, no dict of refund fields).
- **R7.** `views/accounts.py`, `views/people.py`, `views/categories.py`, and `views/refunds.py` import nothing from `finances.db`, `finances.sync`, `sqlalchemy`, or `keyring`; only `views/backups.py`, `views/sync.py`, and `views/transfers.py` still may, until 36c.
- **R8.** Apply the given diff to two earlier test files: they call the loader and then the view. No other earlier test changes; every page and command test passes unchanged.

## Given tests

8 tests in one file: each view given hand-built data (no database), the refund sections, and the frozen list of `views` modules that may still load data.

`tests/unit/test_views_take_data.py`

```python
import ast
from datetime import UTC, date, datetime
from pathlib import Path

import finances.views
from finances.analysis.categories import (
    RuleListing,
    TransactionFacts,
    UncategorizedItem,
    card_credit_count,
)
from finances.analysis.listings import AccountListing, PersonListing
from finances.analysis.refunds import RefundFacts
from finances.domain.models import (
    MANUAL,
    Account,
    AccountType,
    Category,
    CategoryAssignment,
    CategoryRule,
    DataSource,
    Transaction,
)
from finances.views.accounts import AccountRow, account_rows
from finances.views.categories import (
    CategoryLine,
    RuleLine,
    TransactionDetail,
    UncategorizedLine,
    card_credits_note,
    category_choices,
    category_lines,
    rule_lines,
    transaction_detail,
    uncategorized_lines,
)
from finances.views.people import PersonRow, people_rows
from finances.views.refunds import RefundLine, RefundView, refund_view, refunded_lines

VIEWS = Path(finances.views.__file__).parent
STILL_LOADING = {"backups.py", "sync.py", "transfers.py"}
CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
CARD = Account(1, "Test Card", "Test Bank", AccountType.CREDIT_CARD, "USD", "1111", True, CREATED)
CHECKING = Account(
    2, "Test Checking", "Test Bank", AccountType.CHECKING, "USD", None, False, CREATED
)
FOOD = Category(1, "Food", None, False, False, False)
GROCERIES = Category(2, "Groceries", 1, False, False, False)
INCOME = Category(3, "Income", None, False, True, False)
PAYCHECK = Category(4, "Paycheck", 3, False, True, False)


def transaction(id: int, account: int, cents: int, *, card: str | None = None) -> Transaction:
    return Transaction(
        id,
        account,
        None,
        date(2026, 5, id),
        None,
        cents,
        "SQ *ACME COFFEE #12",
        None,
        card,
        None,
        None,
        DataSource.STATEMENT,
        False,
        f"t{id:02d}".ljust(64, "0"),
        CREATED,
    )


def test_account_rows_from_a_listing() -> None:
    listing = [AccountListing(CARD, "Alex"), AccountListing(CHECKING, None)]
    assert account_rows(listing) == [
        AccountRow("Test Card", "Test Bank", "credit_card", "••1111", "yes", "Alex"),
        AccountRow("Test Checking", "Test Bank", "checking", "", "no", ""),
    ]


def test_people_rows_from_a_listing() -> None:
    listing = [PersonListing("Alex", ["Test Card", "Test Old Card"], ["A DOE", "ALEX DOE"])]
    assert people_rows(listing) == [
        PersonRow("Alex", "Test Card, Test Old Card", "A DOE, ALEX DOE")
    ]


def test_the_category_tree_as_lines_and_choices() -> None:
    tree = [(FOOD, [GROCERIES]), (INCOME, [PAYCHECK])]
    assert category_lines(tree) == [
        CategoryLine("Food", "Groceries", ""),
        CategoryLine("Income", "Paycheck", "income"),
    ]
    assert category_choices(tree) == [("Food", ["Groceries"]), ("Income", ["Paycheck"])]


def test_rule_lines_from_a_listing() -> None:
    rule = CategoryRule(7, "ACME COFFEE", "contains", 5, 2)
    assert rule_lines([RuleListing(rule, "Groceries")]) == [
        RuleLine("7", "5", "contains", "ACME COFFEE", "Groceries")
    ]


def test_uncategorized_lines_and_the_card_note() -> None:
    items = [
        UncategorizedItem(transaction(3, 1, 599), CARD),
        UncategorizedItem(transaction(4, 1, -599), CARD),
        UncategorizedItem(transaction(5, 2, 2500), CHECKING),
    ]
    assert uncategorized_lines(items[:1]) == [
        UncategorizedLine("3", "2026-05-03", "Test Card", "ACME COFFEE", "$5.99")
    ]
    assert card_credit_count(items) == 1
    assert card_credits_note(1) == (
        "Money in on a card: 1, likely a refund or a card payment."
        " Set a category, or pair it on the Transfers page."
    )
    assert card_credits_note(0) is None


def test_the_detail_of_a_transaction() -> None:
    assignment = CategoryAssignment(3, 2, MANUAL, None)
    facts = TransactionFacts(
        transaction(3, 1, -2599, card="4321"), "Test Card", "Groceries", assignment
    )
    assert transaction_detail(facts) == TransactionDetail(
        3,
        "2026-05-03",
        "Test Card",
        "SQ *ACME COFFEE #12",
        "ACME COFFEE",
        "-$25.99",
        "••4321",
        "Groceries",
        "by hand",
    )


def test_the_refund_sections() -> None:
    purchase = transaction(2, 1, -2599)
    refund = RefundFacts(True, purchase, [])
    assert refund_view(refund, "$5.99") == RefundView(
        "$5.99", RefundLine(2, "2026-05-02", "-$25.99")
    )
    assert refund_view(RefundFacts(True, None, []), "$5.99") == RefundView("$5.99", None)
    assert refund_view(RefundFacts(False, None, [transaction(9, 1, 599)]), "-$25.99") is None
    assert refunded_lines(RefundFacts(False, None, [transaction(9, 1, 599)])) == [
        RefundLine(9, "2026-05-09", "$5.99")
    ]


def test_only_the_frozen_views_still_load_data() -> None:
    loading = set()
    for path in VIEWS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                if name.startswith(("finances.db", "finances.sync", "keyring", "sqlalchemy")):
                    loading.add(path.name)
    assert loading <= STILL_LOADING
    assert {"accounts.py", "people.py", "categories.py", "refunds.py"}.isdisjoint(loading)
```

The diff to earlier tests (apply it exactly):

```text
diff --git a/tests/integration/test_category_views.py b/tests/integration/test_category_views.py
index e53a5e3..612deef 100644
--- a/tests/integration/test_category_views.py
+++ b/tests/integration/test_category_views.py
@@ -6,6 +6,7 @@ from fastapi.testclient import TestClient
 from sqlalchemy import Engine
 from sqlalchemy.orm import Session
 
+from finances.analysis.categories import category_tree, transaction_facts
 from finances.config import Settings
 from finances.db.engine import session_scope
 from finances.db.migrate import upgrade_to_head
@@ -66,13 +67,18 @@ def test_an_unknown_transaction_is_none(session: Session) -> None:
 # transaction_detail
 
 
+def detail_of(session: Session, transaction_id: int) -> TransactionDetail | None:
+    facts = transaction_facts(session, transaction_id)
+    return None if facts is None else transaction_detail(facts)
+
+
 def test_the_detail_of_an_unknown_transaction_is_none(session: Session) -> None:
-    assert transaction_detail(session, 99) is None
+    assert transaction_facts(session, 99) is None
 
 
 def test_a_transaction_without_a_category(session: Session) -> None:
     made = add_transaction(session, 3, "SQ *ACME COFFEE #12", cents=-2599)
-    assert transaction_detail(session, made) == TransactionDetail(
+    assert detail_of(session, made) == TransactionDetail(
         id=made,
         date="2026-05-03",
         account="Test Card",
@@ -87,7 +93,7 @@ def test_a_transaction_without_a_category(session: Session) -> None:
 
 def test_the_card_is_masked(session: Session) -> None:
     made = add_transaction(session, 3, "ACME COFFEE", card="4321")
-    detail = transaction_detail(session, made)
+    detail = detail_of(session, made)
     assert detail is not None
     assert detail.card == "••4321"
 
@@ -95,7 +101,7 @@ def test_the_card_is_masked(session: Session) -> None:
 def test_a_category_set_by_hand(session: Session) -> None:
     made = add_transaction(session, 3, "FOOBAR GROCERY")
     set_category_by_hand(session, made, "groceries")
-    detail = transaction_detail(session, made)
+    detail = detail_of(session, made)
     assert detail is not None
     assert (detail.category, detail.set_by) == ("Groceries", "by hand")
 
@@ -105,7 +111,7 @@ def test_a_category_set_by_a_rule(session: Session) -> None:
     create_rule(session, "ACME", "Dining")
     rule = create_rule(session, "ACME COFFEE", "Coffee & Dessert", priority=5)
     assign_by_rule(session, made, rule)
-    detail = transaction_detail(session, made)
+    detail = detail_of(session, made)
     assert detail is not None
     assert (detail.category, detail.set_by) == ("Coffee & Dessert", f"by rule {rule.id}")
 
@@ -115,7 +121,7 @@ def test_a_category_set_by_a_rule(session: Session) -> None:
 
 def test_groups_and_their_categories_in_name_order(session: Session) -> None:
     create_category(session, "aquarium", "Home")
-    choices = category_choices(session)
+    choices = category_choices(category_tree(session))
     groups = [group for group, _ in choices]
     assert groups == sorted(groups, key=str.lower)
     names = dict(choices)["Home"]
diff --git a/tests/integration/test_views.py b/tests/integration/test_views.py
index 7a12faf..560af35 100644
--- a/tests/integration/test_views.py
+++ b/tests/integration/test_views.py
@@ -7,6 +7,7 @@ import keyring.errors
 import pytest
 from sqlalchemy import Engine
 
+from finances.analysis.listings import account_listing, people_listing
 from finances.db.engine import session_scope
 from finances.db.orm import AccountRow as AccountTable
 from finances.db.repositories import (
@@ -128,11 +129,11 @@ def test_pull_texts() -> None:
 
 def test_account_rows(household: Engine) -> None:
     with session_scope(household) as session:
-        assert account_rows(session) == [
+        assert account_rows(account_listing(session)) == [
             AccountRow("Test Card", "Test Bank", "credit_card", "••1111", "yes", "Alex"),
             AccountRow("Test Checking", "Test Bank", "checking", "", "yes", "Joint"),
         ]
-        every = account_rows(session, include_inactive=True)
+        every = account_rows(account_listing(session, include_inactive=True))
     assert [row.name for row in every] == [
         "Test Card",
         "Test Checking",
@@ -153,7 +154,7 @@ def test_an_account_row_lists_its_cells_in_column_order() -> None:
 
 def test_people_rows(household: Engine) -> None:
     with session_scope(household) as session:
-        assert people_rows(session) == [
+        assert people_rows(people_listing(session)) == [
             PersonRow("Alex", "Test Card", ""),
             PersonRow("Sam", "Test Old Card", "S DOE, SAM DOE"),
         ]
@@ -172,7 +173,11 @@ def test_account_names_include_closed_accounts(household: Engine) -> None:
 
 def test_no_people_or_accounts(db_engine: Engine) -> None:
     with session_scope(db_engine) as session:
-        assert (account_rows(session), people_rows(session), account_names(session)) == (
+        assert (
+            account_rows(account_listing(session)),
+            people_rows(people_listing(session)),
+            account_names(session),
+        ) == (
             [],
             [],
             {},
```

## Tests to write

`tests/integration/test_listings_more.py`: `account_listing` with `include_inactive`; `people_listing` with no people; `uncategorized_items` on a closed account; `transaction_facts` for a rule's category; `card_credit_count` on an empty list.

## Rules for this phase

- No output changes: the architect ran the whole suite with this design on a scratch copy (every earlier page and command test passed, with only the two diffs above).
- `analysis` returns data, never text; `views` formats, never loads.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file: `tests/unit/test_views_take_data.py`, 8 tests; at least N + 8 passed in all;
- `git diff --stat HEAD -- tests` lists only the two files of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.listings --cov=finances.analysis.categories --cov=finances.views.accounts --cov=finances.views.people --cov=finances.views.categories --cov=finances.views.refunds --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the search `git grep -n --untracked -E "^ *(from|import) +(finances\.(db|sync)|sqlalchemy|keyring)" -- src/finances/views/accounts.py src/finances/views/people.py src/finances/views/categories.py src/finances/views/refunds.py`: no output.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 36b: views that only format (YYYY-MM-DD)`.
