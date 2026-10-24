# Phase 29a: shared expenses stored

## Goal

A person can mark a transaction as shared: one person paid it, another owes them a share (half by default). Settlements record money paid back. After this phase:

- two new tables hold shares and settlements, written only through repository functions that record each change in the audit trail;
- a new **critical** pure module, `domain/shared.py`, computes a share in integer cents and nets every share and settlement into who owes whom;
- the payer is found as Phase 21 finds whose money a transaction is (a known cardholder's person, else the account's owner), unless the caller names one;
- like a split, a shared transaction is never a transfer, and a feed deletion or amount change looks after its share;
- `owed_report` gives who owes whom, for the terminal and the web of Phase 29b.

There is no command or page yet: 29b adds them.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/testing.md` ("Critical modules"), `docs/phases/phase-28d-splits-stored.md` (the same pattern for transfers and the feed)
- `src/finances/domain/people.py` (`person_for`, `JOINT`), `src/finances/analysis/people.py` (`load_attribution`, for how the payer is found)
- `src/finances/db/repositories/people.py` (`get_person_by_name`, `list_account_owners`, `list_cardholder_aliases`, `list_people`), `src/finances/db/repositories/transfers.py`, `src/finances/db/repositories/feed.py`, `src/finances/db/repositories/splits.py` (the nearest repository)

## Starting state

N is `3678` when Phase 28g is the last phase built. The newest migration is `0019`. SQLite enforces foreign keys. `_check_transfer` and `list_transfer_movements` already leave split transactions out (28d); `update_feed_transaction` already clears a split when the amount changes.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0020_shared_expenses.py` | new: given (R1) |
| `src/finances/db/orm.py` | `SharedExpenseRow`, `SettlementRow` (R1) |
| `src/finances/domain/shared.py` (new) | `Share`, `Settlement`, `Owed`, `half_share`, `signed_share`, `balances` (R2) |
| `scripts/critical_modules.txt`, `docs/testing.md`, `tests/unit/test_check_script.py` | `domain/shared.py` added to the critical list (R2) |
| `src/finances/domain/audit.py` | four actions and one kind (R3) |
| `src/finances/db/repositories/shared.py` (new), `src/finances/db/repositories/__init__.py` | six functions (R4 to R6) |
| `src/finances/db/repositories/transfers.py`, `feed.py` | a shared transaction in transfers and the feed (R7, R8) |
| `src/finances/analysis/shared.py` (new) | `owed_report` (R9) |
| `tests/unit/test_audit_rules.py`, `tests/e2e/test_cli_audit.py`, `tests/unit/test_repositories_split.py` | the given diff (R10) |
| `tests/unit/test_shared.py`, `tests/integration/test_migration_0020.py` | new: given |
| `tests/integration/test_shared_stored.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Any command, page, or MCP tool (29b); a share among more than two people on one transaction; shares by percentage.
- Linking a settlement to the transfer that paid it; editing a settlement (delete it and record another).
- Sharing a pending transaction or a transfer; keeping a share through a feed amount change.

## Dependencies

None new. One migration, given below.

## Design

```python
# src/finances/domain/shared.py (imports only from finances.domain; critical)
@dataclass(frozen=True)
class Share:
    transaction_id: int
    payer: str        # the person who paid
    debtor: str       # the person who owes the payer
    owed_cents: int   # what the debtor owes for it: positive for a purchase, negative for a refund

@dataclass(frozen=True)
class Settlement:
    id: int
    payer: str        # the person who paid money back
    payee: str        # the person who received it
    amount_cents: int # more than zero
    day: date

@dataclass(frozen=True)
class Owed:
    debtor: str
    creditor: str
    cents: int        # more than zero

def half_share(amount_cents: int) -> int: ...
def signed_share(amount_cents: int, size_cents: int) -> int: ...
def balances(shares: Iterable[Share], settlements: Iterable[Settlement]) -> list[Owed]: ...

# src/finances/db/orm.py
class SharedExpenseRow(Base):
    __tablename__ = "shared_expenses"
    __table_args__ = (UniqueConstraint("transaction_id", name="uq_shared_expenses_transaction_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    payer_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    debtor_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    owed_cents: Mapped[int] = mapped_column(Integer, nullable=False)

class SettlementRow(Base):
    __tablename__ = "settlements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payer_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    payee_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)

# src/finances/db/repositories/shared.py
def share_transaction(
    session: Session, transaction_id: int, debtor: str, *, payer: str = "", size_cents: int | None = None
) -> Share: ...
def unshare_transaction(session: Session, transaction_id: int) -> None: ...
def list_shares(session: Session) -> list[Share]: ...   # by transaction id
def record_settlement(
    session: Session, payer: str, payee: str, amount_cents: int, day: date
) -> Settlement: ...
def delete_settlement(session: Session, settlement_id: int) -> Settlement: ...
def list_settlements(session: Session) -> list[Settlement]: ...  # by day, then id

# src/finances/analysis/shared.py
def owed_report(session: Session) -> list[Owed]: ...  # balances(list_shares, list_settlements)
```

## Requirements

### The rule

- **R1.** Add the given migration exactly. The two row classes as designed; their foreign keys take their names from the naming convention.
- **R2.** `half_share` and `signed_share` refuse a transaction of 0 cents (`a transaction of zero cannot be shared`). `half_share` gives half the amount's size, rounded down, so the payer keeps an odd cent. `signed_share` refuses a size that is not more than zero or is more than the amount's size (`a share must be more than zero and at most the transaction's amount`). Both are positive for a purchase (a negative amount) and negative for money in. `balances` nets, for each two people, every share one owes the other and every settlement one paid the other (a settlement paid by A to B lowers what A owes B), and gives one `Owed` per pair that does not net to zero, sorted by debtor, then creditor. `domain/shared.py` joins the critical list in `scripts/critical_modules.txt`, `docs/testing.md` (with "added in Phase 29a"), and `tests/unit/test_check_script.py` (the given diff).
- **R3.** `ACTIONS` ends with `"share_set"`, `"share_cleared"`, `"settlement_added"`, `"settlement_deleted"`; `KINDS` ends with `"settlement"`. A share's kind is `"transaction"`.

### The repository

- **R4.** `share_transaction` refuses, in this order: a transaction that does not exist (`transaction not found`); a pending one (`a pending transaction cannot be shared`); one in a transfer pair (`a transfer cannot be shared`); a `payer` named but not found (`person not found`); no `payer` named and `person_for` of the transaction's cardholder, its account's owner, and the cardholder aliases gives `Joint` or nobody (`say who paid: this transaction is joint or has no owner`); a `debtor` not found (`person not found`); a debtor who is the payer (`a person cannot owe themselves`); then `half_share` (no `size_cents`) or `signed_share` refuses. It then replaces any share the transaction had, flushes, and records `share_set` with `after` `Alex owes Sam` (debtor, then payer) and `before` the old share's text or None. It returns the share.
- **R5.** `unshare_transaction` refuses a transaction that does not exist (`transaction not found`) or has no share (`the transaction is not shared`), deletes the share, and records `share_cleared` with `before` its text. `list_shares` gives every share by transaction id.
- **R6.** `record_settlement` refuses a person not found (`person not found`, the payer checked first), a payer who is the payee (`a person cannot pay themselves`), and an amount that is not more than zero (`a settlement must be more than zero`); it stores the settlement and records `settlement_added` (kind `settlement`, its id, `after` `Alex paid Sam`). `delete_settlement` refuses an unknown id (`settlement not found`), deletes it, records `settlement_deleted` with `before` that text, and returns it. `list_settlements` gives every settlement by day, then id. All six functions are re-exported from `finances.db.repositories`.

### Transfers and the feed

- **R7.** `list_transfer_movements` leaves shared transactions out, so the rules never pair one; `_check_transfer` refuses one (`a shared transaction cannot be in a transfer`) after its existing checks.
- **R8.** `delete_feed_transaction` deletes the share before the transaction. `update_feed_transaction`, when the new amount differs from the stored one and the transaction is shared, deletes the share and records `share_cleared` (`before` its text) with `who` `system`; with the same amount the share stays.

### The report

- **R9.** `owed_report` gives `balances(list_shares(session), list_settlements(session))`.
- **R10.** Apply the given diff to the four earlier test files. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0020_shared_expenses.py` (do not change)

```python
"""Create shared_expenses (who owes the payer for a transaction) and settlements."""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shared_expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column("debtor_id", sa.Integer(), nullable=False),
        sa.Column("owed_cents", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_shared_expenses_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["payer_id"], ["people.id"], name="fk_shared_expenses_payer_id_people"
        ),
        sa.ForeignKeyConstraint(
            ["debtor_id"], ["people.id"], name="fk_shared_expenses_debtor_id_people"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shared_expenses"),
        sa.UniqueConstraint("transaction_id", name="uq_shared_expenses_transaction_id"),
    )
    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column("payee_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["payer_id"], ["people.id"], name="fk_settlements_payer_id_people"),
        sa.ForeignKeyConstraint(["payee_id"], ["people.id"], name="fk_settlements_payee_id_people"),
        sa.PrimaryKeyConstraint("id", name="pk_settlements"),
    )


def downgrade() -> None:
    op.drop_table("settlements")
    op.drop_table("shared_expenses")
```

## Given diff to earlier tests

```text
diff --git a/tests/e2e/test_cli_audit.py b/tests/e2e/test_cli_audit.py
index 6a74193..24eb317 100644
--- a/tests/e2e/test_cli_audit.py
+++ b/tests/e2e/test_cli_audit.py
@@ -61,7 +61,8 @@ UNKNOWN = (
     "ory_cleared, budget_set, budget_removed, transfer_confirmed, transfer_rejected, "
     "transfer_unpaired, statement_imported, backup_deleted, backup_restored, proposal"
     "_accepted, proposal_declined, alias_added, alias_deleted, tag_added, tag_removed, "
-    "note_set, note_cleared, split_set, split_cleared"
+    "note_set, note_cleared, split_set, split_cleared, share_set, share_cleared, settlement_a"
+    "dded, settlement_deleted"
 )
 
 
diff --git a/tests/unit/test_audit_rules.py b/tests/unit/test_audit_rules.py
index dec8a2b..95bce7c 100644
--- a/tests/unit/test_audit_rules.py
+++ b/tests/unit/test_audit_rules.py
@@ -38,6 +38,10 @@ def test_the_lists() -> None:
         "note_cleared",
         "split_set",
         "split_cleared",
+        "share_set",
+        "share_cleared",
+        "settlement_added",
+        "settlement_deleted",
     )
     assert KINDS == (
         "account",
@@ -50,6 +54,7 @@ def test_the_lists() -> None:
         "backup",
         "proposal",
         "alias",
+        "settlement",
     )
     assert AUDIT_TEXT_LIMIT == 200
 
diff --git a/tests/unit/test_check_script.py b/tests/unit/test_check_script.py
index 8d17158..46ed073 100644
--- a/tests/unit/test_check_script.py
+++ b/tests/unit/test_check_script.py
@@ -21,6 +21,7 @@ CRITICAL = [
     "domain/transfers.py",
     "domain/spending.py",
     "domain/splits.py",
+    "domain/shared.py",
 ]
 
 
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 2900f8d..f3efa6f 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -130,6 +130,14 @@ HOMES = {
         "remove_budget",
         "set_budget",
     ],
+    "shared": [
+        "delete_settlement",
+        "list_settlements",
+        "list_shares",
+        "record_settlement",
+        "share_transaction",
+        "unshare_transaction",
+    ],
     "splits": [
         "clear_split",
         "set_split",
@@ -166,7 +174,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 116
+    assert len(expected) == 122
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

25 tests in two files. Do not change them. `tests/unit/test_shared.py` covers every line and branch of the critical module.

`tests/unit/test_shared.py`

```python
from datetime import date

import pytest

from finances.domain.shared import Owed, Settlement, Share, balances, half_share, signed_share

DAY = date(2026, 5, 20)
ZERO = "a transaction of zero cannot be shared"
SIZE = "a share must be more than zero and at most the transaction's amount"


@pytest.mark.parametrize(
    ("amount", "owed"),
    [(-2000, 1000), (-2001, 1000), (2001, -1000), (-1, 0)],
)
def test_half_a_share(amount: int, owed: int) -> None:
    assert half_share(amount) == owed


@pytest.mark.parametrize(
    ("amount", "size", "owed"),
    [(-2000, 1200, 1200), (2000, 500, -500), (-2000, 2000, 2000), (-2000, 1, 1)],
)
def test_a_share_of_a_size(amount: int, size: int, owed: int) -> None:
    assert signed_share(amount, size) == owed


@pytest.mark.parametrize(
    ("work", "message"),
    [
        (lambda: half_share(0), ZERO),
        (lambda: signed_share(0, 100), ZERO),
        (lambda: signed_share(-2000, 2001), SIZE),
        (lambda: signed_share(2000, 2001), SIZE),
        (lambda: signed_share(-2000, 0), SIZE),
        (lambda: signed_share(-2000, -100), SIZE),
    ],
)
def test_a_share_that_is_refused(work, message: str) -> None:
    with pytest.raises(ValueError) as raised:
        work()
    assert str(raised.value) == message


def test_no_shares_owe_nothing() -> None:
    assert balances([], []) == []


def test_shares_net_against_each_other() -> None:
    shares = [
        Share(1, "Sam", "Alex", 1000),
        Share(2, "Sam", "Alex", -300),
        Share(3, "Alex", "Sam", 200),
    ]
    assert balances(shares, []) == [Owed("Alex", "Sam", 500)]


@pytest.mark.parametrize(
    ("paid", "owed"),
    [
        (500, []),
        (200, [Owed("Alex", "Sam", 300)]),
        (700, [Owed("Sam", "Alex", 200)]),
    ],
)
def test_a_settlement_pays_it_down(paid: int, owed: list[Owed]) -> None:
    shares = [Share(1, "Sam", "Alex", 1000), Share(2, "Alex", "Sam", 500)]
    assert balances(shares, [Settlement(1, "Alex", "Sam", paid, DAY)]) == owed


def test_a_settlement_the_other_way_adds_to_it() -> None:
    shares = [Share(1, "Sam", "Alex", 1000)]
    assert balances(shares, [Settlement(1, "Sam", "Alex", 250, DAY)]) == [Owed("Alex", "Sam", 1250)]


def test_three_people_by_debtor_then_creditor() -> None:
    shares = [
        Share(1, "Sam", "Alex", 1000),
        Share(2, "Sam", "Kai", 400),
        Share(3, "Kai", "Alex", 250),
    ]
    assert balances(shares, []) == [
        Owed("Alex", "Kai", 250),
        Owed("Alex", "Sam", 1000),
        Owed("Kai", "Sam", 400),
    ]
```

`tests/integration/test_migration_0020.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import SettlementRow, SharedExpenseRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SHARED = [
    ("id", "INTEGER", False),
    ("transaction_id", "INTEGER", False),
    ("payer_id", "INTEGER", False),
    ("debtor_id", "INTEGER", False),
    ("owed_cents", "INTEGER", False),
]
SETTLEMENTS = [
    ("id", "INTEGER", False),
    ("payer_id", "INTEGER", False),
    ("payee_id", "INTEGER", False),
    ("amount_cents", "INTEGER", False),
    ("day", "DATE", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0020_follows_0019() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0020")
    assert script.down_revision == "0019"


@pytest.mark.parametrize(
    ("table", "columns", "row", "uniques", "keys"),
    [
        (
            "shared_expenses",
            SHARED,
            SharedExpenseRow,
            [("uq_shared_expenses_transaction_id", ["transaction_id"])],
            [
                ("fk_shared_expenses_debtor_id_people", ["debtor_id"], "people"),
                ("fk_shared_expenses_payer_id_people", ["payer_id"], "people"),
                (
                    "fk_shared_expenses_transaction_id_transactions",
                    ["transaction_id"],
                    "transactions",
                ),
            ],
        ),
        (
            "settlements",
            SETTLEMENTS,
            SettlementRow,
            [],
            [
                ("fk_settlements_payee_id_people", ["payee_id"], "people"),
                ("fk_settlements_payer_id_people", ["payer_id"], "people"),
            ],
        ),
    ],
)
def test_the_tables_and_their_row_classes(
    url: str, table: str, columns: list, row: type, uniques: list, keys: list
) -> None:
    command.upgrade(make_config(url), "0020")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns(table)]
    primary = found.get_pk_constraint(table)
    unique = [(u["name"], u["column_names"]) for u in found.get_unique_constraints(table)]
    key = sorted(
        (k["name"], k["constrained_columns"], k["referred_table"])
        for k in found.get_foreign_keys(table)
    )
    engine.dispose()
    assert shown == columns
    assert (primary["name"], primary["constrained_columns"]) == (f"pk_{table}", ["id"])
    assert (unique, key) == (uniques, keys)
    orm = [(c.name, str(c.type), c.nullable) for c in row.__table__.columns]
    assert orm[: len(columns)] == columns


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0020")
    command.downgrade(config, "0019")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "shared_expenses" not in names and "settlements" not in names
    command.upgrade(config, "0020")
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_shared_stored.py`, with the people Sam and Alex; a card owned by Sam; a checking account owned by nobody (joint); a purchase of -$20.01 on the card (1); a purchase on the card whose cardholder name is an alias of Alex (2); a joint purchase (3); a pending purchase (4); and -$50.00 out of checking with $50.00 into another account the same day (5 and 6):

- `share_transaction(1, "alex")` gives `Share(1, "Sam", "Alex", 1000)`: Sam paid as the card's owner, Alex owes half rounded down; `share_set` is recorded with `after` `Alex owes Sam`; sharing 1 again with `size_cents=1200` records the old text as `before` and owes 1200;
- `share_transaction(2, "Sam")` has Alex as the payer: the cardholder's person comes before the owner;
- `share_transaction(3, "Alex")` is refused with the joint message, and `share_transaction(3, "Alex", payer="Sam")` is stored;
- each refusal of R4 once, nothing stored; the pending purchase shared with an unknown debtor gives the pending message (the order);
- `unshare_transaction` removes the share and records `share_cleared`; a transaction not shared is refused;
- `record_settlement("Alex", "Sam", 400, ...)`, `list_settlements`, `delete_settlement` and their audit rows; each refusal of R6 once;
- with 5 shared, `pair_transfers` pairs nothing, and `create_transfer_pair(5, 6, ...)` is refused with R7's message;
- a shared feed transaction is deleted by `delete_feed_transaction` without an error; `update_feed_transaction` with a new amount clears its share and records `share_cleared` by `system`, and with the same amount and a new description keeps it;
- `owed_report` after sharing 1 with Alex and Alex settling $4.00 gives `[Owed("Alex", "Sam", 600)]`.

## Rules for this phase

- Money is integer cents, from the account holder's side: a purchase is negative, so what a debtor owes for it is positive. `half_share`, `signed_share`, and `balances` take and return integers only and never round but as R2 says.
- `domain/shared.py` imports only from `finances.domain` and is covered 100% by `tests/unit/test_shared.py`. The repository finds the payer with `domain.people.person_for`, not through `analysis`.
- Messages are constant and echo no amount or description; the audit texts hold only people's names.
- Keep each module under `src/finances/db/repositories/` under 400 lines.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 25 tests; at least N + 25 passed in all;
- `git diff --stat HEAD -- tests` lists only the four files of the given diff;
- `git grep -n "SharedExpenseRow\|SettlementRow" -- src/finances/analysis src/finances/categorize src/finances/cli src/finances/web` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.shared --cov=finances.domain.audit --cov=finances.db.repositories --cov=finances.analysis.shared --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 29a: shared expenses stored (YYYY-MM-DD)`.
