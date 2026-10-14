# Phase 11a: categories, merchants, and rules

## Goal

Every transaction can have a category, so later phases can say where the money goes.

After this phase:

- the database holds a **two-level category tree**: groups (Food, Home, Transport, ...) with categories inside (Groceries, Dining, Coffee & Dessert, ...), seeded with a default tree. Some groups are marked as transfers, income, or sensitive (health);
- each transaction's **merchant** is worked out from its description by one cleaning function (`SQ *ACME COFFEE` and `ACME COFFEE #12` both become `ACME COFFEE`);
- **rules** ("a merchant containing ACME COFFEE is Coffee & Dessert") categorize transactions: the highest priority wins, and a category **set by hand is never overwritten**. Adding or deleting a rule re-runs the rules over every transaction at once (the owner's choice);
- new transactions are categorized as they arrive: `fin import statement`, `fin import folder`, and `fin sync run` run the rules quietly when they finish;
- the terminal gains `fin categories list|add`, `fin rules list|add|delete`, `fin categorize`, `fin uncategorized`, and `fin transactions set-category`.

The web pages come in Phase 11b; matching transfers between the household's own accounts in Phase 11c; refunds and spending totals in Phase 12. SimpleFIN supplies no categories, so rules and the household's own choices are the only sources.

## Read first

- `AGENTS.md` (thin interfaces; text that fits its column; `finances.domain.text`), `docs/architecture.md` (the `categorize/` package)
- `docs/statement-formats.md`: the descriptions the cleaning function meets
- `src/finances/domain/models.py` (it may import only the standard library), `src/finances/domain/text.py`, `src/finances/db/orm.py`, `src/finances/db/repositories.py` (`delete_feed_transaction`, `list_transactions`, `create_account`), `src/finances/views/`, `src/finances/cli/common.py`, `src/finances/cli/listing.py`, `src/finances/cli/importing.py`, `src/finances/cli/sync.py` (`run_command`), `src/finances/cli/main.py`
- `src/finances/db/migrations/versions/0007_feed_seen_accounts.py` and `tests/integration/test_migration_0007.py`

## Starting state

- Phase 23 is committed. `git status --short` prints nothing.
- Run `.venv/bin/python scripts/check.py`; it ends with `All checks passed.`. Note the number passed in its `tests` step. This spec calls it **N**. It is `2060` when Phase 23 is the last phase built.
- The newest migration is `0007`. Transactions are deleted in one place only: `delete_feed_transaction`. Foreign keys are enforced.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0008_categories.py` | new: given below |
| `src/finances/domain/text.py` | `CATEGORY_NAME_LIMIT`, `RULE_PATTERN_LIMIT` |
| `src/finances/domain/models.py` | `MANUAL`, `BY_RULE`, `Category`, `CategoryRule`, `CategoryAssignment` |
| `src/finances/domain/merchants.py` | new: `clean_merchant` |
| `src/finances/domain/rules.py` | new: `MATCHES`, `normalize_pattern`, `rule_matches`, `pick_rule` |
| `src/finances/db/orm.py` | `CategoryRow`, `CategoryRuleRow`, `TransactionCategoryRow`, and their `to_` functions |
| `src/finances/db/repositories.py` | the functions of Part 3; `delete_feed_transaction` (R12) |
| `src/finances/categorize/__init__.py`, `categorize/service.py` | new: `CategorizeResult`, `categorize` |
| `src/finances/views/categories.py` | new: rows for the commands now and the web in 11b |
| `src/finances/cli/categories.py` | new: the commands of Part 5 |
| `src/finances/cli/main.py`, `cli/importing.py`, `cli/sync.py` | registering the commands; quiet categorizing (R22) |
| `tests/unit/test_merchants.py`, `tests/unit/test_category_rules.py`, `tests/integration/test_migration_0008.py`, `tests/e2e/test_cli_categories.py` | new: given, do not change |
| `tests/integration/test_category_repositories.py`, `tests/integration/test_categorize_service.py` | new: yours |
| `docs/progress.md` | one new entry |

No other production file and no existing test changes.

## Out of scope

- Web pages (11b), transfer pairing (11c), refunds and spending totals (Phase 12).
- Renaming, moving, or deleting categories or groups; adding a group; changing a rule (delete it and add a new one).
- A stored `merchants` table, merchant kinds, or merchant aliases. The merchant is computed from the description every time.
- A category column in `fin transactions list` (its output is pinned by earlier tests).
- Splitting one transaction across categories.
- Adding the new modules to `scripts/critical_modules.txt` (its test pins the list; a later phase).
- Categorizing in the web's Sync now (11b).

## Dependencies

None new.

## Design

```python
# src/finances/domain/text.py  (added)
CATEGORY_NAME_LIMIT = 50
RULE_PATTERN_LIMIT = 100
```

```python
# src/finances/domain/models.py  (standard library only, as now)
MANUAL = "manual"
BY_RULE = "rule"


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    group_id: int | None     # None for a group
    is_transfer: bool
    is_income: bool
    is_sensitive: bool


@dataclass(frozen=True)
class CategoryRule:
    id: int
    pattern: str             # upper case, single spaces
    match: str               # "contains", "starts_with", or "equals"
    priority: int
    category_id: int


@dataclass(frozen=True)
class CategoryAssignment:
    transaction_id: int
    category_id: int
    source: str              # MANUAL or BY_RULE
    rule_id: int | None      # the rule that set it, None when set by hand
```

```python
# src/finances/domain/merchants.py
def clean_merchant(description: str) -> str: ...

# src/finances/domain/rules.py
MATCHES = ("contains", "starts_with", "equals")
def normalize_pattern(text: str) -> str: ...
def rule_matches(rule: CategoryRule, merchant: str) -> bool: ...
def pick_rule(merchant: str, rules: list[CategoryRule]) -> CategoryRule | None: ...
```

```python
# src/finances/db/repositories.py
class CategoryExistsError(Exception): ...
def list_categories(session) -> list[Category]: ...
def get_category_by_name(session, name: str) -> Category | None: ...
def create_category(session, name: str, group: str) -> Category: ...
def list_rules(session) -> list[CategoryRule]: ...
def create_rule(session, pattern: str, category: str, match: str = "contains", priority: int = 0) -> CategoryRule: ...
def delete_rule(session, rule_id: int) -> None: ...
def list_category_assignments(session) -> dict[int, CategoryAssignment]: ...
def assign_by_rule(session, transaction_id: int, rule: CategoryRule) -> None: ...
def remove_category(session, transaction_id: int) -> None: ...
def set_category_by_hand(session, transaction_id: int, category: str) -> Category: ...
def clear_category_by_hand(session, transaction_id: int) -> None: ...
def list_transaction_descriptions(session) -> list[tuple[int, str]]: ...
def list_uncategorized(session, limit: int) -> list[Transaction]: ...
```

```python
# src/finances/categorize/service.py
@dataclass(frozen=True)
class CategorizeResult:
    total: int
    changed: int
    uncategorized: int


def categorize(session: Session) -> CategorizeResult: ...
```

```python
# src/finances/views/categories.py
@dataclass(frozen=True)
class CategoryLine:     # group, category, kind
    group: str
    category: str
    kind: str

@dataclass(frozen=True)
class RuleLine:         # id, priority, match, pattern, category
    id: str
    priority: str
    match: str
    pattern: str
    category: str

@dataclass(frozen=True)
class UncategorizedLine:  # id, date, account, merchant, amount
    id: str
    date: str
    account: str
    merchant: str
    amount: str

def category_lines(session) -> list[CategoryLine]: ...
def rule_lines(session) -> list[RuleLine]: ...
def uncategorized_lines(session, limit: int) -> list[UncategorizedLine]: ...
def categorized_text(result: CategorizeResult) -> str: ...
```

The migration, in full (`src/finances/db/migrations/versions/0008_categories.py`):

```python
"""Create categories (seeded with a default two-level tree), category_rules, and
transaction_categories."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Each group, its kind ("" when none), and its categories, in the order they are inserted.
DEFAULT_TREE = (
    ("Food", "", ("Groceries", "Dining", "Coffee & Dessert")),
    ("Home", "", ("Rent & Mortgage", "Utilities & Internet", "Home & Garden")),
    (
        "Transport",
        "",
        ("Gas", "Parking & Tolls", "Public Transit", "Rideshare & Taxi", "Car Maintenance"),
    ),
    ("Shopping", "", ("General Shopping", "Clothing", "Electronics")),
    ("Subscriptions", "", ("Subscriptions & Digital",)),
    ("Health", "sensitive", ("Medical", "Pharmacy", "Fitness")),
    ("Personal", "", ("Personal Care", "Gifts & Donations", "Education")),
    ("Travel", "", ("Flights", "Lodging", "Travel Other")),
    ("Entertainment", "", ("Entertainment & Events", "Gaming")),
    ("Financial", "", ("Fees & Interest", "Insurance", "Taxes")),
    ("Transfers", "transfer", ("Transfer", "Credit Card Payment")),
    ("Income", "income", ("Paycheck", "Interest Income", "Other Income")),
)


def upgrade() -> None:
    categories = op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("is_transfer", sa.Boolean(), nullable=False),
        sa.Column("is_income", sa.Boolean(), nullable=False),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["categories.id"], name="fk_categories_parent_id_categories"
        ),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern", sa.String(100), nullable=False),
        sa.Column("match", sa.String(12), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_category_rules"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], name="fk_category_rules_category_id_categories"
        ),
        sa.UniqueConstraint("match", "pattern", name="uq_category_rules_match_pattern"),
    )
    op.create_table(
        "transaction_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_categories"),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_transaction_categories_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_transaction_categories_category_id_categories",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["category_rules.id"],
            name="fk_transaction_categories_rule_id_category_rules",
        ),
        sa.UniqueConstraint("transaction_id", name="uq_transaction_categories_transaction_id"),
    )
    rows = []
    next_id = len(DEFAULT_TREE) + 1
    for group_id, (group, kind, children) in enumerate(DEFAULT_TREE, start=1):
        flags = {
            "is_transfer": kind == "transfer",
            "is_income": kind == "income",
            "is_sensitive": kind == "sensitive",
        }
        rows.append({"id": group_id, "name": group, "parent_id": None, **flags})
        for child in children:
            rows.append({"id": next_id, "name": child, "parent_id": group_id, **flags})
            next_id += 1
    op.bulk_insert(categories, rows)


def downgrade() -> None:
    op.drop_table("transaction_categories")
    op.drop_table("category_rules")
    op.drop_table("categories")
```

The ORM classes map these three tables exactly (`test_migration_0008.py` compares them), using `CATEGORY_NAME_LIMIT` for `categories.name` and `RULE_PATTERN_LIMIT` for `category_rules.pattern`.

Messages, in full:

| Where | Message |
|---|---|
| a category name, after outer spaces are removed, empty or longer than 50 | `a category name must be 1 to 50 characters` |
| the group is not found, or is a category | `group not found` |
| the name is taken by any category or group, ignoring case | `a category with this name already exists` (`CategoryExistsError`) |
| a rule pattern, after `normalize_pattern`, empty or longer than 100 | `a rule pattern must be 1 to 100 characters` |
| a match outside `MATCHES` | `match must be one of: contains, starts_with, equals` |
| no category of that name | `category not found` |
| a group given where a category is needed | `rules and transactions take a category, not a group` |
| the same match and pattern exist | `a rule with this pattern and match already exists` |
| no rule with that id | `rule not found` |
| no transaction with that id | `transaction not found` |
| `--category` and `--clear` both or neither | `give either --category or --clear` |

## Requirements

### Part 1: the merchant

- **R1.** `clean_merchant(description)` returns the description's merchant, by these steps in order:
  1. `text` is the description with whitespace collapsed (`collapse_ws`) and in upper case.
  2. The first of these leading wrappers that `text` starts with is removed: `DEBIT CARD RECURRING PYMT `, `DEBIT CARD PURCHASE `, `POS PURCHASE `. Then, if `text` ends with ` DEBIT CARD PURCHASE`, that is removed.
  3. The first of these processor prefixes that `text` starts with is removed: `PAYPAL *`, `GOOGLE *`, `SQ *`, `SQ*`, `TST* `, `TST*`, `PP*`, `SP `.
  4. If `text` holds a `*`, it is cut there (the `*` and everything after it go).
  5. If `text` holds a space followed by a date `[0-9]{2}-[0-9]{2}` that is followed by a space or the end, it is cut at that space.
  6. If `text` holds `#` followed by an ASCII digit, it is cut at the `#`.
  7. Every remaining word that contains `#` is dropped.
  8. Phone numbers `[0-9]{3}-[0-9]{3}-[0-9]{4}` and runs of five or more ASCII digits are removed.
  9. Whitespace is collapsed again, and spaces, `-`, `,`, `.`, and `*` are stripped from both ends.
  10. If nothing is left, the result is the text of step 1.

  Only ASCII digits `0` to `9` count as digits. The given tests show each step on synthetic descriptions.

### Part 2: rules, without a database

- **R2.** `normalize_pattern(text)` is `collapse_ws(text).upper()`.
- **R3.** `rule_matches(rule, merchant)` compares `normalize_pattern(rule.pattern)` with `normalize_pattern(merchant)`: `contains` is true when the pattern occurs in the merchant, `starts_with` when the merchant starts with it, `equals` when they are equal. Any other match is false.
- **R4.** `pick_rule(merchant, rules)` returns, among the rules that match, the one with the highest priority, and among equal priorities the lowest id; `None` when none match. The list is not changed.

### Part 3: the database

- **R5.** Migration `0008` is the given file. The ORM classes map its tables.
- **R6.** `list_categories(session)` returns every group and category, ordered by name ignoring case, then id. `get_category_by_name` finds a group or category by name, ignoring case and outer spaces, or returns `None`.
- **R7.** `create_category(session, name, group)` checks, in this order: the name (outer spaces removed) is 1 to `CATEGORY_NAME_LIMIT` characters; `group` names a group (not a category); no group or category has the name, ignoring case. It stores the category under the group with the group's three flags, and returns it.
- **R8.** `create_rule(session, pattern, category, match, priority)` checks, in this order: `normalize_pattern(pattern)` is 1 to `RULE_PATTERN_LIMIT` characters; `match` is in `MATCHES`; `category` names a group or category (`category not found`); it is a category, not a group; no rule has the same match and normalized pattern. It stores the normalized pattern and returns the rule. `list_rules` returns every rule in the order `pick_rule` tries them: priority highest first, then id.
- **R9.** `delete_rule(session, rule_id)` raises `rule not found` for an unknown id; otherwise it removes the assignments that rule set, then the rule.
- **R10.** `list_category_assignments` maps each categorized transaction's id to its `CategoryAssignment`. `assign_by_rule(session, transaction_id, rule)` stores (or replaces) the transaction's assignment as `BY_RULE` with the rule's category and id. `remove_category` removes the transaction's assignment, if any.
- **R11.** `set_category_by_hand(session, transaction_id, category)` checks: the transaction exists; the category is found; it is not a group. It stores (or replaces) the assignment as `MANUAL` with no rule, and returns the category. `clear_category_by_hand(session, transaction_id)` checks the transaction exists and removes its assignment.
- **R12.** `delete_feed_transaction` removes the transaction's assignment before the transaction, so a categorized feed row a statement drops is deleted without an error. An upgraded feed row keeps its id and so its category.
- **R13.** `list_transaction_descriptions(session)` returns `(id, description)` of every transaction in id order. `list_uncategorized(session, limit)` returns the transactions without an assignment, latest posted date first, then highest id, at most `limit` (at least 1, else `ValueError("limit must be at least 1")`).

### Part 4: categorizing

- **R14.** `categorize(session)` goes through every transaction in id order. A transaction with a `MANUAL` assignment is left as it is. For every other, `rule = pick_rule(clean_merchant(description), list_rules(session))`: with a rule, `assign_by_rule`; without one, `remove_category`. The result counts `total` (every transaction), `changed` (those whose category, or lack of one, differs afterwards), and `uncategorized` (those without a category afterwards). The caller commits.
- **R15.** `categorized_text(result)` is `Categorized TOTAL transactions: CHANGED changed, NONE without a category.`, with `transaction` in the singular when `TOTAL` is 1.

### Part 5: the commands

Every command calls `require_current_schema()` first, reports a `ValueError` (or `CategoryExistsError`) with `cli.common.fail`, and prints tables with `print_table`.

- **R16.** `fin categories list` prints a table `Group | Category | Kind`: one row per category, groups in name order ignoring case, categories within a group in name order ignoring case. `Kind` is `transfer`, `income`, `sensitive`, or empty (several joined with `, ` in that order).
- **R17.** `fin categories add --name NAME --group GROUP` prints `Added category "NAME" to GROUP.` with both names as stored.
- **R18.** `fin rules list` prints `ID | Priority | Match | Pattern | Category` in `list_rules` order, or `No rules.`. `fin rules add --pattern P --category C [--match contains|starts_with|equals] [--priority N]` (match defaults to `contains`, priority to 0, any whole number) prints `Added rule ID: MATCH "PATTERN" -> CATEGORY.`, then categorizes and prints `categorized_text`. `fin rules delete --id N` prints `Deleted rule N.`, then categorizes and prints `categorized_text`.
- **R19.** `fin categorize` categorizes and prints `categorized_text`.
- **R20.** `fin uncategorized [--limit N]` (1 to 1000, default 50; Typer refuses others with exit 2) prints `ID | Date | Account | Merchant | Amount` from `uncategorized_lines` (the date in ISO form, the account's name, `clean_merchant`, `format_cents`), or `No uncategorized transactions.`.
- **R21.** `fin transactions set-category --id N (--category C | --clear)`, registered on the existing `transactions` group: with `--category`, prints `Transaction N: CATEGORY, set by hand.` with the stored name; with `--clear`, prints `Transaction N: category left to the rules.`, then categorizes and prints `categorized_text`. Giving both or neither fails with the message of the table.
- **R22.** `fin import statement`, `fin import folder` (except with `--dry-run`), and `fin sync run` (when at least one link ran) call `categorize` in their own session after their work and print nothing more. Their output and exit codes are unchanged.
- **R23.** `fin categories` and `fin rules` are registered in `cli/main.py` as `app.add_typer(categories_app, name="categories")` and `app.add_typer(rules_app, name="rules")`; `categorize` and `uncategorized` as top-level commands.

## Given tests

Create these four files exactly as shown and do not change them. If one fails, the code is wrong.

`tests/unit/test_merchants.py`

```python
import pytest

from finances.domain.merchants import clean_merchant


@pytest.mark.parametrize(
    ("description", "merchant"),
    [
        ("FOOBAR CHICKEN #123TUCKERGA", "FOOBAR CHICKEN"),
        ("ACME GROCERY #123 DECATUR GA", "ACME GROCERY"),
        ("acme  gas #1234 allen tx", "ACME GAS"),
        ("  ACME COFFEE  ", "ACME COFFEE"),
        ("DEBIT CARD PURCHASE ACME*Terminal3 08-15 Lisboa", "ACME"),
        ("DEBIT CARD RECURRING PYMT STREAMCO.COM 08-19 866-555-0100", "STREAMCO.COM"),
        ("EXAMPLESTREAM.COM 08-01 SURREY BC 1234 DEBIT CARD PURCHASE", "EXAMPLESTREAM.COM"),
        ("POS PURCHASE FOOBAR DINER", "FOOBAR DINER"),
        ("DEBIT CARD PURCHASE SQ *ACME COFFEE 08-15 DECATUR", "ACME COFFEE"),
        ("SQ *ACME COFFEE", "ACME COFFEE"),
        ("SQ*ACME COFFEE", "ACME COFFEE"),
        ("TST* FOOBAR DINER 0042", "FOOBAR DINER 0042"),
        ("TST*FOOBAR DINER", "FOOBAR DINER"),
        ("PAYPAL *STREAMCO", "STREAMCO"),
        ("GOOGLE *FOOBAR GAMES", "FOOBAR GAMES"),
        ("PP*ACME STORE", "ACME STORE"),
        ("SP ACME OUTDOORS", "ACME OUTDOORS"),
        ("AMAZON MKTPL*AB12CD34E", "AMAZON MKTPL"),
        ("PAYMENT FROM CHK 9999 CONF#M00000000", "PAYMENT FROM CHK 9999"),
        ("EXAMPLE BANK MOBILE PYMT", "EXAMPLE BANK MOBILE PYMT"),
        ("ONLINE PAYMENT, THANK YOU", "ONLINE PAYMENT, THANK YOU"),
        ("INCOMING WIRE TRANSFER WIRE REF# 20260814-00000000", "INCOMING WIRE TRANSFER WIRE"),
        (
            "Probe Person PAYMENT ID ABC000000000 ZELLE PAYMENT TO",
            "PROBE PERSON PAYMENT ID ABC ZELLE PAYMENT TO",
        ),
        (
            "ACHDepositInternettransferfromEXAMPLE BANKDDAaccount",
            "ACHDEPOSITINTERNETTRANSFERFROMEXAMPLE BANKDDAACCOUNT",
        ),
        ("STREAMCO.COM 866-555-0100", "STREAMCO.COM"),
        ("ACME MARKET 08-15", "ACME MARKET"),
        ("ACME 12-PACK STORE", "ACME 12-PACK STORE"),
        ("ACME #١٢٣", "ACME"),
        ("INTEREST CHARGE ON PURCHASES", "INTEREST CHARGE ON PURCHASES"),
    ],
)
def test_clean_merchant(description: str, merchant: str) -> None:
    assert clean_merchant(description) == merchant


@pytest.mark.parametrize(
    ("description", "merchant"),
    [("#1234", "#1234"), ("12345678", "12345678"), ("  *  ", "*"), ("sq *", "SQ *")],
)
def test_when_nothing_is_left_the_description_is_kept(description: str, merchant: str) -> None:
    assert clean_merchant(description) == merchant


def test_cleaning_twice_changes_nothing() -> None:
    for description in ("SQ *ACME COFFEE", "ACME GROCERY #123 DECATUR GA", "STREAMCO.COM"):
        once = clean_merchant(description)
        assert clean_merchant(once) == once
```

`tests/unit/test_category_rules.py`

```python
import pytest

from finances.domain.models import CategoryRule
from finances.domain.rules import MATCHES, normalize_pattern, pick_rule, rule_matches


def rule(rule_id: int, pattern: str, match: str = "contains", priority: int = 0) -> CategoryRule:
    return CategoryRule(rule_id, pattern, match, priority, 100 + rule_id)


def test_the_kinds_of_match() -> None:
    assert MATCHES == ("contains", "starts_with", "equals")


@pytest.mark.parametrize(
    ("text", "pattern"),
    [("acme  coffee", "ACME COFFEE"), ("  Foobar\tGrocery ", "FOOBAR GROCERY"), ("", "")],
)
def test_a_pattern_is_upper_case_with_single_spaces(text: str, pattern: str) -> None:
    assert normalize_pattern(text) == pattern


@pytest.mark.parametrize(
    ("match", "pattern", "merchant", "matched"),
    [
        ("contains", "COFFEE", "ACME COFFEE", True),
        ("contains", "COFFEE", "ACME TEA", False),
        ("contains", "acme  coffee", "ACME COFFEE", True),
        ("contains", "ACME", "acme coffee", True),
        ("starts_with", "ACME", "ACME COFFEE", True),
        ("starts_with", "ACME", "THE ACME", False),
        ("equals", "ACME COFFEE", "ACME COFFEE", True),
        ("equals", "ACME", "ACME COFFEE", False),
        ("equals", "ACME COFFEE", "acme  coffee", True),
        ("regex", "ACME", "ACME", False),
    ],
)
def test_rule_matches(match: str, pattern: str, merchant: str, matched: bool) -> None:
    assert rule_matches(rule(1, pattern, match), merchant) is matched


def test_the_highest_priority_wins() -> None:
    rules = [
        rule(1, "COFFEE"),
        rule(2, "ACME", "starts_with", priority=5),
        rule(3, "ACME C", priority=2),
    ]
    assert pick_rule("ACME COFFEE", rules) == rules[1]


def test_equal_priorities_go_to_the_older_rule() -> None:
    rules = [
        rule(7, "COFFEE", priority=1),
        rule(3, "ACME", priority=1),
        rule(9, "ACME COFFEE", "equals", priority=1),
    ]
    assert pick_rule("ACME COFFEE", rules) == rules[1]


def test_a_rule_that_does_not_match_is_passed_over() -> None:
    rules = [rule(1, "TEA", priority=9), rule(2, "COFFEE")]
    assert pick_rule("ACME COFFEE", rules) == rules[1]


def test_no_rule_matches() -> None:
    assert pick_rule("ACME COFFEE", [rule(1, "TEA")]) is None
    assert pick_rule("ACME COFFEE", []) is None


def test_the_rules_are_not_reordered() -> None:
    rules = [rule(2, "A"), rule(1, "A", priority=3)]
    before = list(rules)
    pick_rule("A", rules)
    assert rules == before
```

`tests/integration/test_migration_0008.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import Base, CategoryRow, CategoryRuleRow, TransactionCategoryRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0008_categories.py"
COLUMNS = {
    "categories": [
        ("id", "INTEGER", False),
        ("name", "VARCHAR(50)", False),
        ("parent_id", "INTEGER", True),
        ("is_transfer", "BOOLEAN", False),
        ("is_income", "BOOLEAN", False),
        ("is_sensitive", "BOOLEAN", False),
    ],
    "category_rules": [
        ("id", "INTEGER", False),
        ("pattern", "VARCHAR(100)", False),
        ("match", "VARCHAR(12)", False),
        ("priority", "INTEGER", False),
        ("category_id", "INTEGER", False),
    ],
    "transaction_categories": [
        ("id", "INTEGER", False),
        ("transaction_id", "INTEGER", False),
        ("category_id", "INTEGER", False),
        ("source", "VARCHAR(10)", False),
        ("rule_id", "INTEGER", True),
    ],
}
UNIQUES = {
    "categories": [("uq_categories_name", ["name"])],
    "category_rules": [("uq_category_rules_match_pattern", ["match", "pattern"])],
    "transaction_categories": [("uq_transaction_categories_transaction_id", ["transaction_id"])],
}
FOREIGN_KEYS = {
    "categories": [("fk_categories_parent_id_categories", ["parent_id"], "categories")],
    "category_rules": [("fk_category_rules_category_id_categories", ["category_id"], "categories")],
    "transaction_categories": [
        ("fk_transaction_categories_category_id_categories", ["category_id"], "categories"),
        ("fk_transaction_categories_rule_id_category_rules", ["rule_id"], "category_rules"),
        (
            "fk_transaction_categories_transaction_id_transactions",
            ["transaction_id"],
            "transactions",
        ),
    ],
}
TREE = {
    "Food": ("", ["Groceries", "Dining", "Coffee & Dessert"]),
    "Home": ("", ["Rent & Mortgage", "Utilities & Internet", "Home & Garden"]),
    "Transport": (
        "",
        ["Gas", "Parking & Tolls", "Public Transit", "Rideshare & Taxi", "Car Maintenance"],
    ),
    "Shopping": ("", ["General Shopping", "Clothing", "Electronics"]),
    "Subscriptions": ("", ["Subscriptions & Digital"]),
    "Health": ("sensitive", ["Medical", "Pharmacy", "Fitness"]),
    "Personal": ("", ["Personal Care", "Gifts & Donations", "Education"]),
    "Travel": ("", ["Flights", "Lodging", "Travel Other"]),
    "Entertainment": ("", ["Entertainment & Events", "Gaming"]),
    "Financial": ("", ["Fees & Interest", "Insurance", "Taxes"]),
    "Transfers": ("transfer", ["Transfer", "Credit Card Payment"]),
    "Income": ("income", ["Paycheck", "Interest Income", "Other Income"]),
}


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def at_0008(url: str) -> str:
    command.upgrade(make_config(url), "0008")
    return url


def rows(url: str, sql: str) -> list[tuple]:
    engine = get_engine(url)
    with engine.connect() as connection:
        found = [tuple(row) for row in connection.execute(text(sql)).all()]
    engine.dispose()
    return found


def test_0008_follows_0007(url: str) -> None:
    script = ScriptDirectory.from_config(make_config(url)).get_revision("0008")
    assert script.down_revision == "0007"


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


@pytest.mark.parametrize("table", sorted(COLUMNS))
def test_columns_keys_and_constraints(at_0008: str, table: str) -> None:
    engine = get_engine(at_0008)
    found = inspect(engine)
    columns = [
        (column["name"], str(column["type"]), column["nullable"])
        for column in found.get_columns(table)
    ]
    primary = found.get_pk_constraint(table)
    uniques = [(item["name"], item["column_names"]) for item in found.get_unique_constraints(table)]
    foreign = sorted(
        (item["name"], item["constrained_columns"], item["referred_table"])
        for item in found.get_foreign_keys(table)
    )
    engine.dispose()
    assert columns == COLUMNS[table]
    assert (primary["name"], primary["constrained_columns"]) == (f"pk_{table}", ["id"])
    assert uniques == UNIQUES[table]
    assert foreign == sorted(FOREIGN_KEYS[table])


@pytest.mark.parametrize(
    ("row_class", "table"),
    [
        (CategoryRow, "categories"),
        (CategoryRuleRow, "category_rules"),
        (TransactionCategoryRow, "transaction_categories"),
    ],
)
def test_the_orm_classes_match_the_migrated_tables(at_0008: str, row_class, table: str) -> None:
    assert row_class.__table__ is Base.metadata.tables[table]
    assert [
        (column.name, str(column.type), column.nullable) for column in row_class.__table__.columns
    ] == COLUMNS[table]


def test_the_default_tree_is_seeded(at_0008: str) -> None:
    groups = rows(
        at_0008,
        "SELECT id, name, is_transfer, is_income, is_sensitive FROM categories"
        " WHERE parent_id IS NULL ORDER BY id",
    )
    assert [name for _, name, *_ in groups] == list(TREE)
    assert [row[0] for row in groups] == list(range(1, 13))
    found = {}
    for group_id, group, *flags in groups:
        kind, _ = TREE[group]
        assert flags == [kind == "transfer", kind == "income", kind == "sensitive"]
        children = rows(
            at_0008,
            "SELECT name, is_transfer, is_income, is_sensitive FROM categories"
            f" WHERE parent_id = {group_id} ORDER BY id",
        )
        found[group] = [name for name, *_ in children]
        assert all(list(child[1:]) == flags for child in children)
    assert found == {group: names for group, (_, names) in TREE.items()}
    assert rows(at_0008, "SELECT min(id), max(id), count(*) FROM categories")[0] == (1, 46, 46)


def test_category_names_are_unique(at_0008: str) -> None:
    engine = get_engine(at_0008)
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.execute(
            text(
                "INSERT INTO categories (name, parent_id, is_transfer, is_income, is_sensitive)"
                " VALUES ('Dining', 1, 0, 0, 0)"
            )
        )
    engine.dispose()


def test_downgrade_removes_only_the_three_tables(at_0008: str) -> None:
    command.downgrade(make_config(at_0008), "0007")
    engine = get_engine(at_0008)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert names.isdisjoint({"categories", "category_rules", "transaction_categories"})
    assert "transactions" in names
```

`tests/e2e/test_cli_categories.py`

```python
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
GROUP_GIVEN = "rules and transactions take a category, not a group"
LINE = "Categorized {} transactions: {} changed, {} without a category.\n"


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    return tmp_settings


@pytest.fixture
def spending(migrated: Settings) -> Settings:
    """Transactions 1 to 4, posted on 1 to 4 May 2026 in this order."""
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card", last4="9999")
        for day, cents, description in (
            (1, -450, "SQ *ACME COFFEE"),
            (2, -500, "ACME COFFEE #12"),
            (3, -2599, "FOOBAR GROCERY #77 DECATUR GA"),
            (4, 300000, "PAYCHECK EXAMPLE CORP"),
        ):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{day}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return migrated


@pytest.mark.parametrize(
    "args",
    [
        ("categories", "list"),
        ("categories", "add", "--name", "X", "--group", "Food"),
        ("rules", "list"),
        ("rules", "add", "--pattern", "X", "--category", "Dining"),
        ("rules", "delete", "--id", "1"),
        ("categorize",),
        ("uncategorized",),
        ("transactions", "set-category", "--id", "1", "--clear"),
    ],
)
def test_every_command_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


# Categories


def test_the_default_categories(migrated: Settings) -> None:
    rows = table_rows(run("categories", "list").stdout)
    assert rows[0] == ["Group", "Category", "Kind"]
    assert len(rows) == 35
    assert rows[1:3] == [
        ["Entertainment", "Entertainment & Events", ""],
        ["Entertainment", "Gaming", ""],
    ]
    assert ["Health", "Fitness", "sensitive"] in rows
    assert ["Transfers", "Credit Card Payment", "transfer"] in rows
    assert ["Income", "Interest Income", "income"] in rows
    groups = [row[0] for row in rows[1:]]
    assert groups == sorted(groups, key=str.lower)
    assert [row[1] for row in rows if row[0] == "Food"] == [
        "Coffee & Dessert",
        "Dining",
        "Groceries",
    ]


def test_add_a_category_to_a_group(migrated: Settings) -> None:
    result = run("categories", "add", "--name", "  Therapy ", "--group", "health")
    assert (result.exit_code, result.stdout) == (0, 'Added category "Therapy" to Health.\n')
    assert ["Health", "Therapy", "sensitive"] in table_rows(run("categories", "list").stdout)


@pytest.mark.parametrize(
    ("name", "group", "message"),
    [
        ("Therapy", "Nope", "group not found"),
        ("Therapy", "Dining", "group not found"),
        ("dining", "Food", "a category with this name already exists"),
        ("food", "Food", "a category with this name already exists"),
        ("  ", "Food", "a category name must be 1 to 50 characters"),
        ("N" * 51, "Food", "a category name must be 1 to 50 characters"),
    ],
)
def test_a_refused_category(migrated: Settings, name: str, group: str, message: str) -> None:
    assert failed_cleanly(run("categories", "add", "--name", name, "--group", group), message)


# Rules and categorizing


def test_rules_categorize_past_transactions(spending: Settings) -> None:
    result = run("rules", "add", "--pattern", "acme  coffee", "--category", "coffee & dessert")
    assert (result.exit_code, result.stdout) == (
        0,
        'Added rule 1: contains "ACME COFFEE" -> Coffee & Dessert.\n' + LINE.format(4, 2, 2),
    )
    result = run(
        "rules",
        "add",
        "--pattern",
        "ACME",
        "--match",
        "starts_with",
        "--priority",
        "5",
        "--category",
        "Dining",
    )
    assert result.stdout == 'Added rule 2: starts_with "ACME" -> Dining.\n' + LINE.format(4, 2, 2)
    assert table_rows(run("rules", "list").stdout) == [
        ["ID", "Priority", "Match", "Pattern", "Category"],
        ["2", "5", "starts_with", "ACME", "Dining"],
        ["1", "0", "contains", "ACME COFFEE", "Coffee & Dessert"],
    ]
    result = run("rules", "delete", "--id", "2")
    assert (result.exit_code, result.stdout) == (0, "Deleted rule 2.\n" + LINE.format(4, 2, 2))
    assert run("categorize").stdout == LINE.format(4, 0, 2)


def test_uncategorized_transactions(spending: Settings) -> None:
    headings = ["ID", "Date", "Account", "Merchant", "Amount"]
    assert table_rows(run("uncategorized").stdout) == [
        headings,
        ["4", "2026-05-04", "Test Card", "PAYCHECK EXAMPLE CORP", "$3,000.00"],
        ["3", "2026-05-03", "Test Card", "FOOBAR GROCERY", "-$25.99"],
        ["2", "2026-05-02", "Test Card", "ACME COFFEE", "-$5.00"],
        ["1", "2026-05-01", "Test Card", "ACME COFFEE", "-$4.50"],
    ]
    assert table_rows(run("uncategorized", "--limit", "1").stdout)[1:] == [
        ["4", "2026-05-04", "Test Card", "PAYCHECK EXAMPLE CORP", "$3,000.00"]
    ]
    run("rules", "add", "--pattern", "ACME COFFEE", "--category", "Dining")
    assert [row[0] for row in table_rows(run("uncategorized").stdout)[1:]] == ["4", "3"]
    run("rules", "add", "--pattern", "FOOBAR", "--category", "Groceries")
    run("rules", "add", "--pattern", "PAYCHECK", "--category", "Paycheck")
    assert run("uncategorized").stdout == "No uncategorized transactions.\n"
    assert run("uncategorized", "--limit", "0").exit_code == 2
    assert run("uncategorized", "--limit", "1001").exit_code == 2


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--pattern", "X", "--category", "Nope"), "category not found"),
        (("--pattern", "X", "--category", "Food"), GROUP_GIVEN),
        (
            ("--pattern", "X", "--category", "Dining", "--match", "regex"),
            "match must be one of: contains, starts_with, equals",
        ),
        (
            ("--pattern", "   ", "--category", "Dining"),
            "a rule pattern must be 1 to 100 characters",
        ),
        (
            ("--pattern", "P" * 101, "--category", "Dining"),
            "a rule pattern must be 1 to 100 characters",
        ),
    ],
)
def test_a_refused_rule(spending: Settings, args, message: str) -> None:
    assert failed_cleanly(run("rules", "add", *args), message)
    assert run("rules", "list").stdout == "No rules.\n"


def test_the_same_rule_twice_is_refused(spending: Settings) -> None:
    run("rules", "add", "--pattern", "ACME", "--category", "Dining")
    result = run("rules", "add", "--pattern", "acme", "--category", "Groceries")
    assert failed_cleanly(result, "a rule with this pattern and match already exists")
    assert (
        run(
            "rules", "add", "--pattern", "acme", "--match", "equals", "--category", "Groceries"
        ).exit_code
        == 0
    )


def test_deleting_an_unknown_rule(spending: Settings) -> None:
    assert failed_cleanly(run("rules", "delete", "--id", "9"), "rule not found")


# Setting a category by hand


def test_a_category_set_by_hand_is_kept(spending: Settings) -> None:
    result = run("transactions", "set-category", "--id", "3", "--category", "groceries")
    assert (result.exit_code, result.stdout) == (0, "Transaction 3: Groceries, set by hand.\n")
    run("rules", "add", "--pattern", "ACME COFFEE", "--category", "Coffee & Dessert")
    assert run("categorize").stdout == LINE.format(4, 0, 1)
    result = run("rules", "add", "--pattern", "FOOBAR", "--category", "Dining")
    assert result.stdout == 'Added rule 2: contains "FOOBAR" -> Dining.\n' + LINE.format(4, 0, 1)
    result = run("transactions", "set-category", "--id", "3", "--clear")
    assert (result.exit_code, result.stdout) == (
        0,
        "Transaction 3: category left to the rules.\n" + LINE.format(4, 1, 1),
    )


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--id", "99", "--category", "Dining"), "transaction not found"),
        (("--id", "99", "--clear"), "transaction not found"),
        (("--id", "1", "--category", "Nope"), "category not found"),
        (("--id", "1", "--category", "Food"), GROUP_GIVEN),
        (("--id", "1"), "give either --category or --clear"),
        (("--id", "1", "--category", "Dining", "--clear"), "give either --category or --clear"),
    ],
)
def test_a_refused_category_by_hand(spending: Settings, args, message: str) -> None:
    assert failed_cleanly(run("transactions", "set-category", *args), message)


def test_one_transaction_is_counted_in_the_singular(migrated: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=card.id,
                posted_date=date(2026, 5, 1),
                amount_cents=-450,
                description="ACME COFFEE",
                source="statement",
                fingerprint="x".ljust(64, "0"),
            )
        )
    engine.dispose()
    assert (
        run("categorize").stdout == "Categorized 1 transaction: 0 changed, 1 without a category.\n"
    )


# New transactions are categorized as they arrive


def test_an_import_categorizes_quietly(
    migrated: Settings, fake_bank, fake_statement_pdf, tmp_path: Path
) -> None:
    details = ["--institution", "Fake Bank", "--type", "credit_card", "--last4", "1111"]
    assert run("accounts", "add", "--name", "Fake Card", *details).exit_code == 0
    run("rules", "add", "--pattern", "ACME COFFEE", "--category", "Coffee & Dessert")
    path = tmp_path / "statement.pdf"
    path.write_bytes(fake_statement_pdf())
    result = run("import", "statement", path)
    assert result.exit_code == 0
    assert "Categorized" not in result.stdout
    merchants = [row[3] for row in table_rows(run("uncategorized").stdout)[1:]]
    assert sorted(merchants) == ["FOOBAR GROCERY", "PAYMENT THANK YOU"]
```

## Tests to write

`tests/integration/test_category_repositories.py`, on a migrated database (`db_engine`):

- `list_categories` order; `get_category_by_name` ignoring case and spaces, for a group and a category, and `None`;
- `create_category`: each refusal in R7's order (a name that is empty and a group that is unknown gives the name message), the stored name without outer spaces, the copied flags, and `CategoryExistsError` for a group's name;
- `create_rule`: the stored normalized pattern, each refusal in R8's order, and `list_rules` order with equal priorities;
- `delete_rule`: an unknown id, and that only that rule's assignments go;
- `assign_by_rule` replacing an assignment; `remove_category` with and without one;
- `set_category_by_hand` and `clear_category_by_hand`: each refusal, replacing a rule's assignment, and clearing;
- `delete_feed_transaction` of a categorized feed row: the row and its assignment go, other assignments stay;
- `list_uncategorized`: order, limit, a limit of 0, and that manual and rule assignments both count as categorized;
- `list_transaction_descriptions` order.

`tests/integration/test_categorize_service.py`:

- the three counts on a known set, including a transaction whose rule assignment moves to another rule with the same category (not counted as changed);
- a manual assignment untouched even when a higher-priority rule matches;
- a deleted rule's transactions falling to the next matching rule or to none;
- running twice changes nothing the second time;
- a feed pull then a statement import (Phase 8's upgrade and drop) with categorized feed rows, without an error.

Coverage of `finances.categorize`, `finances.domain`, `finances.db`, `finances.views`, and `finances.cli` must stay at 100%.

## Rules for this phase

- **One migration, never edited later.**
- **`domain/models.py` imports only the standard library** (an existing test checks it). `domain/merchants.py` and `domain/rules.py` import only from `finances.domain`.
- **Text fits its column.** Category names and rule patterns are refused when too long, since a person types them.
- **Thin interfaces.** Commands call repositories, `categorize`, and `views`; they hold no rule.
- **Synthetic data only** in your tests: invented merchants and amounts.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.
- Do not run `fin` against the real database in `data/`; the owner runs `fin db upgrade` after verification.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; in the `tests` step, 0 failed, 0 skipped, 0 xfailed, at least N + 98 passed |
| `.venv/bin/python -m pytest tests/unit/test_merchants.py tests/unit/test_category_rules.py tests/integration/test_migration_0008.py tests/e2e/test_cli_categories.py --no-cov` | exactly `98 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the two searches below | no output |
| `git diff HEAD --stat -- tests src/finances/db/migrations/versions/000[1-7]*` | nothing |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.categorize --cov=finances.domain --cov=finances.db --cov=finances.views --cov=finances.cli --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain`

`git grep -n --untracked -E "select\(|session\.(add|execute|delete)|pick_rule|clean_merchant\(" -- src/finances/cli`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 11a: categories, merchants, and rules (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. In your final message, give the last ten lines of `scripts/check.py`'s output, the output line of each other acceptance command, and for each of R1 to R23 the name of a test that covers it.
