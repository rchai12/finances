# Phase 28d: splits stored

## Goal

A transaction can be split into parts, each with its own amount and category, that add up to it exactly. After this phase:

- a new table holds the parts, written only through `set_split` and `clear_split`, which check the parts with a pure rule in a new **critical** module, `domain/splits.py`, and record each change in the audit trail;
- a split transaction counts as decided by a person everywhere a category is decided: the rules leave it alone, by-hand setting and the agent's category proposals refuse it, it is not in the uncategorized queue, and it is never a transfer;
- what deletes or rewrites a transaction looks after its parts: feed deletions take them along, a feed update that changes the amount clears the split, and deleting a category moves or refuses its parts as it does transactions;
- the reports show a split transaction under a category and group named `Split`, until Phase 28e makes them count the parts.

There is no command or page to split a transaction yet: 28e adds the reports and the terminal, a later sub-phase the web.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/testing.md` ("Critical modules")
- `src/finances/db/orm.py` (`TransactionTagRow`, the nearest table), `src/finances/db/repositories/assignments.py` (the by-hand functions, `_require_transaction`, `list_uncategorized`, `count_uncategorized`, `remove_category`), `src/finances/db/repositories/categories.py` (`delete_category`, `_leaf_category`)
- `src/finances/db/repositories/proposals.py` (`decided_by_a_person`, `proposal_out_of_date`), `src/finances/db/repositories/transfers.py` (`list_transfer_movements`, `_check_transfer`), `src/finances/db/repositories/feed.py` (`delete_feed_transaction`, `update_feed_transaction`)
- `src/finances/categorize/service.py` (`categorize`), `src/finances/analysis/spending.py` (`flows_for`)

## Starting state

N is `3574` when Phase 28c is the last phase built. The newest migration is `0018`. SQLite enforces foreign keys, so a row naming a transaction or a category must go before it does. The sync rewrites a stored feed transaction in place with `update_feed_transaction`, which may change its amount.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0019_transaction_splits.py` | new: given (R1) |
| `src/finances/db/orm.py` | `TransactionSplitRow`, `to_split_part` (R1) |
| `src/finances/domain/splits.py` (new) | `MAX_PARTS`, `SPLIT`, `SplitPart`, `check_split` (R2) |
| `scripts/critical_modules.txt`, `docs/testing.md`, `tests/unit/test_check_script.py` | `domain/splits.py` added to the critical list (R2) |
| `src/finances/domain/audit.py` | two actions (R3) |
| `src/finances/db/repositories/splits.py` (new), `src/finances/db/repositories/__init__.py` | three functions (R4, R5) |
| `src/finances/db/repositories/assignments.py`, `proposals.py`, `transfers.py`, `feed.py`, `categories.py` | split transactions treated as decided (R6 to R9) |
| `src/finances/categorize/service.py` | the rules skip a split transaction (R6) |
| `src/finances/analysis/spending.py` | the `Split` label (R10) |
| `tests/unit/test_audit_rules.py`, `tests/e2e/test_cli_audit.py`, `tests/unit/test_repositories_split.py` | the given diff (R11) |
| `tests/unit/test_splits.py`, `tests/integration/test_migration_0019.py` | new: given |
| `tests/integration/test_splits_stored.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Counting the parts in any report, and how search and drill-downs show a split (28e); any command, page, or MCP tool to split a transaction or show its parts.
- Splitting a pending transaction or a transfer; a part without a category; more than `MAX_PARTS` parts.
- Keeping a split when a feed update changes the transaction's amount.

## Dependencies

None new. One migration, given below.

## Design

```python
# src/finances/domain/splits.py (imports only from finances.domain; critical)
MAX_PARTS = 10
SPLIT = "Split"  # the category and group a report shows for a split transaction

@dataclass(frozen=True)
class SplitPart:
    transaction_id: int
    position: int       # 1, 2, ... in the order the parts were given
    amount_cents: int   # signed as the transaction is
    category_id: int

def check_split(amount_cents: int, parts: Sequence[int]) -> None: ...  # or ValueError (R2)

# src/finances/db/orm.py
class TransactionSplitRow(Base):
    __tablename__ = "transaction_splits"
    __table_args__ = (
        UniqueConstraint(
            "transaction_id", "position", name="uq_transaction_splits_transaction_id_position"
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)

def to_split_part(row: TransactionSplitRow) -> SplitPart: ...

# src/finances/db/repositories/splits.py
def set_split(
    session: Session, transaction_id: int, parts: Sequence[tuple[int, str]]
) -> list[SplitPart]: ...   # each part: (signed cents, category name)
def clear_split(session: Session, transaction_id: int) -> None: ...
def splits_for(session: Session, transaction_ids: Iterable[int]) -> dict[int, list[SplitPart]]: ...
```

## Requirements

### Storage and the rule

- **R1.** Add the given migration exactly. `TransactionSplitRow` and `to_split_part` as designed; the foreign keys take their names from the naming convention.
- **R2.** `check_split` refuses with `ValueError`, in this order: a transaction of 0 cents (`a transaction of zero cannot be split`); fewer than 2 or more than `MAX_PARTS` parts (`a split has 2 to 10 parts`); a part that is zero or has the other sign from the transaction (`each part must have the transaction's sign and not be zero`); parts whose sum is not the transaction's amount (`the parts must add up to the transaction`). It returns None. `domain/splits.py` joins the critical list in `scripts/critical_modules.txt`, `docs/testing.md` ("Critical modules", with "added in Phase 28d"), and `tests/unit/test_check_script.py` (the given diff).
- **R3.** `ACTIONS` ends with `"split_set"`, `"split_cleared"`; the kind of each is `"transaction"`.

### The repository

- **R4.** `set_split` refuses, in this order: a transaction that does not exist (`transaction not found`); a pending one (`a pending transaction cannot be split`); one in a transfer pair (`a transfer cannot be split`); parts `check_split` refuses; a category `_leaf_category` refuses (its messages). It then replaces any parts the transaction had with the new ones, at positions 1, 2, ... in the order given, removes the transaction's own category (`remove_category`), flushes, and records `split_set` with `after` the parts' category names in order joined by `, ` (`Dining, Groceries`) and `before` the old parts' names the same way, or None. It returns the parts.
- **R5.** `clear_split` refuses a transaction that does not exist (`transaction not found`) or has no parts (`the transaction is not split`), deletes the parts, and records `split_cleared` with `before` the parts' names; the transaction then has no category, and the caller runs the rules. `splits_for` maps each named transaction that is split to its parts by position. All three are re-exported from `finances.db.repositories`.

### A split transaction is decided

- **R6.** `categorize` skips a split transaction as it skips one set by hand. `set_category_by_hand`, `set_categories_by_hand`, `clear_category_by_hand`, and `clear_categories_by_hand` refuse a split transaction (`a split transaction takes its categories from its parts`) after their existence checks and before anything changes, so a list is all or none.
- **R7.** `decided_by_a_person` is true for a split transaction, so `propose_category` refuses it; a category proposal for a transaction split since is out of date (`proposal_out_of_date`). `list_uncategorized` and `count_uncategorized` leave split transactions out.
- **R8.** `list_transfer_movements` leaves split transactions out, so the rules never pair one; `_check_transfer` refuses one (`a split transaction cannot be in a transfer`) after its three checks, so `create_transfer_pair` and the agent's pair proposals refuse it too.

### What rewrites or deletes looks after the parts

- **R9.** `delete_feed_transaction` deletes the parts before the transaction. `update_feed_transaction`, when the new amount differs from the stored one and the transaction is split, deletes the parts and records `split_cleared` (`before` the names) with `who` `system`; with the same amount the split stays. `delete_category` counts each transaction that has a part in the category among its `transactions` (the message is unchanged), and with `move_to` moves those parts too.

### Reports

- **R10.** `flows_for` gives a split transaction's flow the category and group `SPLIT`, and its kind as `flow_kind` gives for no category. Nothing else in `analysis` changes.
- **R11.** Apply the given diff to the four earlier test files. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0019_transaction_splits.py` (do not change)

```python
"""Create transaction_splits: the parts of a transaction, each with its own category."""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transaction_splits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_transaction_splits_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_transaction_splits_category_id_categories",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_splits"),
        sa.UniqueConstraint(
            "transaction_id", "position", name="uq_transaction_splits_transaction_id_position"
        ),
    )


def downgrade() -> None:
    op.drop_table("transaction_splits")
```

## Given diff to earlier tests

```text
diff --git a/tests/e2e/test_cli_audit.py b/tests/e2e/test_cli_audit.py
index d15663e..6a74193 100644
--- a/tests/e2e/test_cli_audit.py
+++ b/tests/e2e/test_cli_audit.py
@@ -61,7 +61,7 @@ UNKNOWN = (
     "ory_cleared, budget_set, budget_removed, transfer_confirmed, transfer_rejected, "
     "transfer_unpaired, statement_imported, backup_deleted, backup_restored, proposal"
     "_accepted, proposal_declined, alias_added, alias_deleted, tag_added, tag_removed, "
-    "note_set, note_cleared"
+    "note_set, note_cleared, split_set, split_cleared"
 )
 
 
diff --git a/tests/unit/test_audit_rules.py b/tests/unit/test_audit_rules.py
index f380ec9..dec8a2b 100644
--- a/tests/unit/test_audit_rules.py
+++ b/tests/unit/test_audit_rules.py
@@ -36,6 +36,8 @@ def test_the_lists() -> None:
         "tag_removed",
         "note_set",
         "note_cleared",
+        "split_set",
+        "split_cleared",
     )
     assert KINDS == (
         "account",
diff --git a/tests/unit/test_check_script.py b/tests/unit/test_check_script.py
index f25f027..8d17158 100644
--- a/tests/unit/test_check_script.py
+++ b/tests/unit/test_check_script.py
@@ -20,6 +20,7 @@ CRITICAL = [
     "db/backup.py",
     "domain/transfers.py",
     "domain/spending.py",
+    "domain/splits.py",
 ]
 
 
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 14fe4b1..fc3920e 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -130,6 +130,11 @@ HOMES = {
         "remove_budget",
         "set_budget",
     ],
+    "splits": [
+        "clear_split",
+        "set_split",
+        "splits_for",
+    ],
     "tags": [
         "add_tags",
         "list_tags",
@@ -159,7 +164,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 111
+    assert len(expected) == 114
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

19 tests in two files. Do not change them. `tests/unit/test_splits.py` covers every line and branch of the critical module.

`tests/unit/test_splits.py`

```python
import pytest

from finances.domain.splits import MAX_PARTS, SPLIT, SplitPart, check_split


def test_the_constants_and_a_part() -> None:
    assert (MAX_PARTS, SPLIT) == (10, "Split")
    assert SplitPart(4, 2, -800, 7) == SplitPart(
        transaction_id=4, position=2, amount_cents=-800, category_id=7
    )


@pytest.mark.parametrize(
    ("amount", "parts"),
    [
        (-2000, [-1200, -800]),
        (5000, [2500, 2500]),
        (-1000, [-100] * 10),
        (-3, [-1, -1, -1]),
    ],
)
def test_a_split_that_adds_up(amount: int, parts: list[int]) -> None:
    assert check_split(amount, parts) is None


@pytest.mark.parametrize(
    ("amount", "parts", "message"),
    [
        (0, [0, 0], "a transaction of zero cannot be split"),
        (0, [100], "a transaction of zero cannot be split"),
        (-2000, [-2000], "a split has 2 to 10 parts"),
        (-1100, [-100] * 11, "a split has 2 to 10 parts"),
        (-2000, [100], "a split has 2 to 10 parts"),
        (-2000, [-2100, 100], "each part must have the transaction's sign and not be zero"),
        (-2000, [-2000, 0], "each part must have the transaction's sign and not be zero"),
        (2000, [2100, -100], "each part must have the transaction's sign and not be zero"),
        (-2000, [-1200, -799], "the parts must add up to the transaction"),
        (-2000, [-1201, -800], "the parts must add up to the transaction"),
        (2000, [1000, 1001], "the parts must add up to the transaction"),
    ],
)
def test_a_split_that_is_refused(amount: int, parts: list[int], message: str) -> None:
    with pytest.raises(ValueError) as raised:
        check_split(amount, parts)
    assert str(raised.value) == message
```

`tests/integration/test_migration_0019.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import TransactionSplitRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("transaction_id", "INTEGER", False),
    ("position", "INTEGER", False),
    ("amount_cents", "INTEGER", False),
    ("category_id", "INTEGER", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0019_follows_0018() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0019")
    assert script.down_revision == "0018"


def test_the_table_and_its_row_class(url: str) -> None:
    command.upgrade(make_config(url), "0019")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [
        (c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("transaction_splits")
    ]
    primary = found.get_pk_constraint("transaction_splits")
    uniques = [
        (u["name"], u["column_names"]) for u in found.get_unique_constraints("transaction_splits")
    ]
    keys = sorted(
        (k["name"], k["constrained_columns"], k["referred_table"])
        for k in found.get_foreign_keys("transaction_splits")
    )
    engine.dispose()
    assert shown == COLUMNS
    assert (primary["name"], primary["constrained_columns"]) == ("pk_transaction_splits", ["id"])
    assert uniques == [
        ("uq_transaction_splits_transaction_id_position", ["transaction_id", "position"])
    ]
    assert keys == [
        ("fk_transaction_splits_category_id_categories", ["category_id"], "categories"),
        ("fk_transaction_splits_transaction_id_transactions", ["transaction_id"], "transactions"),
    ]
    orm = [(c.name, str(c.type), c.nullable) for c in TransactionSplitRow.__table__.columns]
    assert orm[: len(COLUMNS)] == COLUMNS


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0019")
    command.downgrade(config, "0018")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "transaction_splits" not in names
    command.upgrade(config, "0019")
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_splits_stored.py`, on a card purchase of -$20.00 (`FOOBAR GROCERY`, 1), a pending purchase (2), a checking outflow of -$50.00 and a savings inflow of $50.00 on the same day (3 and 4), and a rule `contains "FOOBAR" -> Groceries` already run:

- `set_split(1, [(-1200, "groceries"), (-800, "Home & Garden")])` returns the two parts at positions 1 and 2 with the categories' ids; transaction 1 has no own category; `split_set` is recorded with `after` `Groceries, Home & Garden`; splitting it again records the old names as `before`;
- each refusal of R4 once, nothing stored; a pending transaction with parts that do not add up gives the pending message (the order);
- `clear_split` removes the parts and records `split_cleared`; a transaction that is not split is refused;
- `categorize` after the split leaves 1 without an own category and counts it in `total` but not in `uncategorized`;
- `set_categories_by_hand([3, 1], "Dining")` is refused and 3 keeps its category (all or none); `clear_category_by_hand(1)` is refused;
- `propose_category(1, ...)` is refused with `a person has already decided this transaction`; an open category proposal for 1, made before the split, is out of date after it;
- `list_uncategorized` and `count_uncategorized` leave 1 out once it is split;
- with 3 split, `pair_transfers` pairs nothing, and `create_transfer_pair(3, 4, ...)` is refused with R8's message;
- a split feed transaction is deleted by `delete_feed_transaction` without an error; `update_feed_transaction` with a new amount clears its split and records `split_cleared` by `system`, and with the same amount and a new description keeps it;
- deleting `Home & Garden` while a part uses it is refused with `Home & Garden is in use (transactions: 1, rules: 0); choose a category to move them to`; with `move_to="Dining"` the part moves;
- `load_flows` gives transaction 1 one flow with category and group `Split`.

## Rules for this phase

- Money is integer cents, signed from the account holder's side: a purchase's parts are negative, a refund's positive. `check_split` takes `int` only and never rounds.
- `domain/splits.py` imports only from `finances.domain` and is covered 100% by `tests/unit/test_splits.py`.
- Messages are constant and echo no amount, description, or category a person did not type; `delete_category`'s message keeps its form.
- Keep each module under `src/finances/db/repositories/` under 400 lines.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 19 tests; at least N + 19 passed in all;
- `git diff --stat HEAD -- tests` lists only the four files of the given diff;
- `git grep -n "TransactionSplitRow" -- src/finances/analysis src/finances/categorize src/finances/cli src/finances/web` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.splits --cov=finances.domain.audit --cov=finances.db.repositories --cov=finances.categorize.service --cov=finances.analysis.spending --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 28d: splits stored (YYYY-MM-DD)`.
