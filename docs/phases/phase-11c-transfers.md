# Phase 11c: transfers

## Goal

Money moved between the household's own accounts is recognised as a transfer, so that a card payment or a move to savings is not mistaken for spending and income. After this phase:

- an outflow and an inflow of the same amount, in two different accounts, at most **5 days** apart, are a **candidate** transfer;
- a candidate is **clear** when neither side has any other candidate; clear candidates are paired automatically (`auto`), after every import, `fin sync run`, `fin categorize`, and the web's **Sync now**, quietly;
- the rest **wait for review**: `fin transfers review` lists them, `fin transfers confirm` pairs one (`confirmed`), and `fin transfers reject` records that two transactions are not a transfer;
- `fin transfers list` shows the pairs, and `fin transfers unpair` removes one, which also records it as rejected so it is never paired again;
- `fin transfers find` pairs and counts on demand;
- a paired transaction no longer shows as uncategorized.

The web pages for transfers come in Phase 11d. Leaving transfers out of spending is Phase 12.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-11a-categories-and-rules.md`: `categorize`, `categorize_all`, and the CLI's patterns
- `src/finances/db/repositories.py` (`delete_feed_transaction`, `list_uncategorized`, `get_transaction`), `src/finances/cli/categories.py`, `src/finances/views/categories.py`, `src/finances/web/app.py` (`POST /sync/run`)
- `tests/integration/test_web_categories.py`: how Sync now is tested with a fake feed

## Starting state

N is `2249` when Phase 11b is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/models.py` | new: `TransferPair`, `AUTO`, `CONFIRMED` |
| `src/finances/domain/transfers.py` | new (R1, R2) |
| `src/finances/db/migrations/versions/0009_transfers.py` | new: given |
| `src/finances/db/orm.py` | new: `TransferPairRow`, `TransferRejectionRow` |
| `src/finances/db/repositories.py` | new functions (R3 to R8); `delete_feed_transaction` (R9); `list_uncategorized` (R10) |
| `src/finances/categorize/transfers.py` | new (R11, R12) |
| `src/finances/views/transfers.py` | new (R13) |
| `src/finances/cli/transfers.py` | new (R14 to R19) |
| `src/finances/cli/main.py` | registers `transfers` |
| `src/finances/cli/categories.py` | `categorize_all` (R20) |
| `src/finances/web/app.py` | Sync now (R21) |
| `tests/unit/test_transfers.py`, `tests/integration/test_migration_0009.py`, `tests/e2e/test_cli_transfers.py` | new: given |
| `tests/integration/test_transfer_store.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Any web page or form for transfers (11d); Sync now shows nothing new.
- Leaving transfers out of totals, or treating `is_transfer` categories as transfers (Phase 12).
- Pairing changing a category, or a category changing pairing; a paired transaction keeps any category it has.
- Splitting one transfer over several transactions, or transfers between currencies.

## Dependencies

None new.

## Design

```python
# src/finances/domain/models.py
AUTO = "auto"
CONFIRMED = "confirmed"


@dataclass(frozen=True)
class TransferPair:
    id: int
    out_transaction_id: int
    in_transaction_id: int
    status: str  # AUTO or CONFIRMED
```

```python
# src/finances/domain/transfers.py
TRANSFER_MAX_DAYS = 5


@dataclass(frozen=True)
class Movement:
    transaction_id: int
    account_id: int
    amount_cents: int
    day: date  # the posted date


def transfer_candidates(
    movements: Iterable[Movement],
    rejected: Collection[tuple[int, int]] = frozenset(),
    max_days: int = TRANSFER_MAX_DAYS,
) -> list[tuple[int, int]]: ...
def clear_pairs(candidates: Sequence[tuple[int, int]]) -> list[tuple[int, int]]: ...
```

```python
# src/finances/db/repositories.py
def list_transfer_movements(session: Session) -> list[Movement]: ...
def list_transfer_rejections(session: Session) -> set[tuple[int, int]]: ...
def list_transfer_pairs(session: Session) -> list[TransferPair]: ...
def create_transfer_pair(session: Session, out_id: int, in_id: int, status: str) -> TransferPair: ...
def reject_transfer(session: Session, out_id: int, in_id: int) -> None: ...
def unpair_transfer(session: Session, pair_id: int) -> TransferPair: ...
```

```python
# src/finances/categorize/transfers.py
@dataclass(frozen=True)
class TransferResult:
    paired: int
    waiting: int


def pair_transfers(session: Session) -> TransferResult: ...
def transfer_suggestions(session: Session) -> list[tuple[int, int]]: ...
```

```python
# src/finances/views/transfers.py  (every field is text)
@dataclass(frozen=True)
class TransferLine:
    pair: str
    date: str          # the outflow's posted date, ISO
    from_account: str  # the outflow's account name
    to_account: str    # the inflow's account name
    amount: str        # format_cents of the inflow
    out_id: str
    in_id: str
    how: str           # the status


@dataclass(frozen=True)
class SuggestionLine:
    out_id: str
    out_date: str
    from_account: str
    in_id: str
    in_date: str
    to_account: str
    amount: str        # format_cents of the inflow


def transfer_lines(session: Session) -> list[TransferLine]: ...
def suggestion_lines(session: Session) -> list[SuggestionLine]: ...
```

Messages, in full. Every one is a `ValueError` from the repositories, shown by the CLI as `Error: <message>` with exit code 1. `create_transfer_pair` checks them in this order and stops at the first:

| Order | When | Message |
|---|---|---|
| 1 | either id is not a transaction | `transaction not found` |
| 2 | both are in the same account | `a transfer goes from one account to another` |
| 3 | the out amount is not below zero, or the in amount is not its negation | `a transfer pairs money out with the same amount in` |
| 4 | the out side, then the in side, is already in a pair | `transaction N is already in a transfer` (N that side's id) |
| | `unpair_transfer` with an unknown pair id | `transfer not found` |

## Requirements

### Part 1: finding transfers (pure)

- **R1.** `transfer_candidates` returns every `(out id, in id)` where the out amount is below zero, the in amount is its negation, the accounts differ, the days are at most `max_days` apart either way, and the pair is not in `rejected`; ordered by out id, then in id.
- **R2.** `clear_pairs` returns, in their order, the candidates whose out id appears in no other candidate's out id and whose in id appears in no other candidate's in id.

### Part 2: storing them

- **R3.** The given migration and two ORM classes matching it (`transfer_pairs`, `transfer_rejections`).
- **R4.** `list_transfer_movements` returns a `Movement` for each transaction that is not pending, has an amount other than zero, and is in no pair, ordered by id. `list_transfer_rejections` returns the stored `(out id, in id)` pairs. `list_transfer_pairs` returns the pairs ordered by id.
- **R5.** `create_transfer_pair` checks the messages in order, refuses a status other than `AUTO` or `CONFIRMED` (`status must be auto or confirmed`), removes a rejection of the same `(out id, in id)`, and stores the pair.
- **R6.** `reject_transfer` checks messages 1 to 3, removes a pair holding exactly these two transactions, and stores the rejection once (rejecting twice keeps one row).
- **R7.** `unpair_transfer` deletes the pair, stores its `(out id, in id)` as rejected (once), and returns the deleted pair.
- **R8.** None of these commit; the caller does.
- **R9.** `delete_feed_transaction` also deletes every pair and rejection that names the transaction, before deleting it. (A statement import replacing a feed row, and the feed dropping a pending one, both go through it.)
- **R10.** `list_uncategorized` also leaves out transactions that are in a pair.

### Part 3: the service and views

- **R11.** `pair_transfers` computes the candidates from `list_transfer_movements` and `list_transfer_rejections`, stores each clear one as `AUTO`, and returns how many it stored and how many candidates remain (`waiting`, the candidates that were not clear).
- **R12.** `transfer_suggestions` returns the candidates that are not clear, in candidate order, without storing anything.
- **R13.** `transfer_lines` returns one line per pair, latest outflow date first, then highest pair id first. `suggestion_lines` returns one line per suggestion, in its order.

### Part 4: the terminal

Every command first checks the schema as the other commands do (`database is not up to date (run: fin db upgrade)`), and works in one session.

- **R14.** `fin transfers list`: a table with columns `Pair`, `Date`, `From`, `To`, `Amount`, `Out`, `In`, `How` from `transfer_lines`; with none, `No transfers.`
- **R15.** `fin transfers review`: a table with columns `Out`, `Out date`, `From`, `In`, `In date`, `To`, `Amount` from `suggestion_lines`; with none, `No transfers wait for review.`
- **R16.** `fin transfers find`: `pair_transfers`, then `Transfers: P paired, W waiting for review.`
- **R17.** `fin transfers confirm --out A --in B`: `create_transfer_pair(..., CONFIRMED)`, then `Transactions A and B are now a transfer.`
- **R18.** `fin transfers reject --out A --in B`: `reject_transfer`, then `Transactions A and B will not be paired.`
- **R19.** `fin transfers unpair --pair P`: `unpair_transfer`, then `Transfer P removed; transactions A and B will not be paired again.`

### Part 5: pairing after categorizing

- **R20.** `categorize_all` runs `pair_transfers` in the same session after `categorize`, and still returns the `CategorizeResult`. Import, `fin sync run`, and `fin categorize` therefore pair quietly; their output does not change.
- **R21.** The web's `POST /sync/run` runs `pair_transfers` in the same session right after its `categorize`, and shows nothing more.

## Given migration

`src/finances/db/migrations/versions/0009_transfers.py`

```python
"""Create transfer_pairs (an outflow and an inflow that are one transfer) and transfer_rejections
(pairs the household said are not a transfer)."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transfer_pairs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("out_transaction_id", sa.Integer(), nullable=False),
        sa.Column("in_transaction_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_transfer_pairs"),
        sa.ForeignKeyConstraint(
            ["out_transaction_id"],
            ["transactions.id"],
            name="fk_transfer_pairs_out_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["in_transaction_id"],
            ["transactions.id"],
            name="fk_transfer_pairs_in_transaction_id_transactions",
        ),
        sa.UniqueConstraint("out_transaction_id", name="uq_transfer_pairs_out_transaction_id"),
        sa.UniqueConstraint("in_transaction_id", name="uq_transfer_pairs_in_transaction_id"),
    )
    op.create_table(
        "transfer_rejections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("out_transaction_id", sa.Integer(), nullable=False),
        sa.Column("in_transaction_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_transfer_rejections"),
        sa.ForeignKeyConstraint(
            ["out_transaction_id"],
            ["transactions.id"],
            name="fk_transfer_rejections_out_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["in_transaction_id"],
            ["transactions.id"],
            name="fk_transfer_rejections_in_transaction_id_transactions",
        ),
        sa.UniqueConstraint(
            "out_transaction_id", "in_transaction_id", name="uq_transfer_rejections_pair"
        ),
    )


def downgrade() -> None:
    op.drop_table("transfer_rejections")
    op.drop_table("transfer_pairs")
```

## Given tests

41 tests in three files. They import `TransferPairRow` and `TransferRejectionRow` from `finances.db.orm`.

`tests/unit/test_transfers.py`

```python
from datetime import date

import pytest

from finances.domain.transfers import (
    TRANSFER_MAX_DAYS,
    Movement,
    clear_pairs,
    transfer_candidates,
)


def m(transaction_id: int, account_id: int, cents: int, day: int) -> Movement:
    return Movement(transaction_id, account_id, cents, date(2026, 5, day))


def test_the_reach_is_five_days() -> None:
    assert TRANSFER_MAX_DAYS == 5


def test_a_card_payment_from_checking() -> None:
    movements = [m(1, 1, -50000, 3), m(2, 2, 50000, 4), m(3, 2, -1250, 4)]
    assert transfer_candidates(movements) == [(1, 2)]


@pytest.mark.parametrize(
    "other",
    [
        m(2, 1, 50000, 4),
        m(2, 2, 49999, 4),
        m(2, 2, -50000, 4),
        m(2, 2, 50000, 9),
    ],
    ids=["same-account", "other-amount", "same-sign", "six-days-later"],
)
def test_not_a_transfer(other: Movement) -> None:
    assert transfer_candidates([m(1, 1, -50000, 3), other]) == []


@pytest.mark.parametrize("day", [8, 1, 3])
def test_up_to_five_days_either_way(day: int) -> None:
    assert transfer_candidates([m(1, 1, -500, 3), m(2, 2, 500, day)]) == [(1, 2)]


def test_a_rejected_pair_is_not_a_candidate() -> None:
    movements = [m(1, 1, -500, 3), m(2, 2, 500, 3), m(3, 3, 500, 4)]
    assert transfer_candidates(movements, {(1, 2)}) == [(1, 3)]


def test_candidates_come_by_outflow_then_inflow() -> None:
    movements = [m(9, 2, 500, 3), m(4, 1, -500, 3), m(2, 3, 500, 4), m(7, 3, -500, 2)]
    assert transfer_candidates(movements) == [(4, 2), (4, 9), (7, 9)]


def test_a_given_reach_replaces_the_default() -> None:
    movements = [m(1, 1, -500, 1), m(2, 2, 500, 3)]
    assert transfer_candidates(movements, max_days=1) == []
    assert transfer_candidates(movements, max_days=2) == [(1, 2)]


def test_only_pairs_with_one_choice_on_each_side_are_clear() -> None:
    candidates = [(1, 2), (3, 4), (3, 5), (6, 8), (7, 8), (9, 10)]
    assert clear_pairs(candidates) == [(1, 2), (9, 10)]


def test_no_candidates() -> None:
    assert transfer_candidates([]) == []
    assert clear_pairs([]) == []
```

`tests/integration/test_migration_0009.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import Base, TransferPairRow, TransferRejectionRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0009_transfers.py"
COLUMNS = {
    "transfer_pairs": [
        ("id", "INTEGER", False),
        ("out_transaction_id", "INTEGER", False),
        ("in_transaction_id", "INTEGER", False),
        ("status", "VARCHAR(10)", False),
    ],
    "transfer_rejections": [
        ("id", "INTEGER", False),
        ("out_transaction_id", "INTEGER", False),
        ("in_transaction_id", "INTEGER", False),
    ],
}
UNIQUES = {
    "transfer_pairs": [
        ("uq_transfer_pairs_in_transaction_id", ["in_transaction_id"]),
        ("uq_transfer_pairs_out_transaction_id", ["out_transaction_id"]),
    ],
    "transfer_rejections": [
        ("uq_transfer_rejections_pair", ["out_transaction_id", "in_transaction_id"])
    ],
}


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def at_0009(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    command.upgrade(make_config(url), "0009")
    return url


def test_0009_follows_0008(tmp_path: Path) -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0009")
    assert script.down_revision == "0008"


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


@pytest.mark.parametrize("table", sorted(COLUMNS))
def test_columns_keys_and_constraints(at_0009: str, table: str) -> None:
    engine = get_engine(at_0009)
    found = inspect(engine)
    columns = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns(table)]
    uniques = sorted((u["name"], u["column_names"]) for u in found.get_unique_constraints(table))
    foreign = sorted(
        (item["constrained_columns"], item["referred_table"])
        for item in found.get_foreign_keys(table)
    )
    primary = found.get_pk_constraint(table)
    engine.dispose()
    assert columns == COLUMNS[table]
    assert uniques == UNIQUES[table]
    assert foreign == [
        (["in_transaction_id"], "transactions"),
        (["out_transaction_id"], "transactions"),
    ]
    assert (primary["name"], primary["constrained_columns"]) == (f"pk_{table}", ["id"])


@pytest.mark.parametrize(
    ("row_class", "table"),
    [(TransferPairRow, "transfer_pairs"), (TransferRejectionRow, "transfer_rejections")],
)
def test_the_orm_classes_match(at_0009: str, row_class, table: str) -> None:
    assert row_class.__table__ is Base.metadata.tables[table]
    assert [
        (column.name, str(column.type), column.nullable) for column in row_class.__table__.columns
    ] == COLUMNS[table]


def test_downgrade_removes_only_the_two_tables(at_0009: str) -> None:
    command.downgrade(make_config(at_0009), "0008")
    engine = get_engine(at_0009)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert names.isdisjoint({"transfer_pairs", "transfer_rejections"})
    assert "transaction_categories" in names
```

`tests/e2e/test_cli_transfers.py`

```python
from datetime import date

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
LIST = ["Pair", "Date", "From", "To", "Amount", "Out", "In", "How"]
REVIEW = ["Out", "Out date", "From", "In", "In date", "To", "Amount"]
TO_SAVINGS = ["3", "2026-05-05", "Test Checking", "{}", "2026-05-0{}", "Test Savings", "$20.00"]


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


def to_savings(in_id: int) -> list[str]:
    return [cell.format(in_id, in_id + 1) for cell in TO_SAVINGS]


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    return tmp_settings


@pytest.fixture
def money(migrated: Settings) -> Settings:
    """1 and 2: a clear card payment. 3 with 4 or 5: unclear. 6 and 7: not transfers."""
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        for number, (account, day, cents, description) in enumerate(
            (
                (checking, 3, -50000, "PAYMENT TO TEST CARD"),
                (card, 4, 50000, "PAYMENT THANK YOU"),
                (checking, 5, -2000, "TRANSFER TO SAVINGS"),
                (savings, 5, 2000, "TRANSFER FROM CHECKING"),
                (savings, 6, 2000, "TRANSFER FROM CHECKING"),
                (card, 6, -1250, "SQ *ACME COFFEE"),
                (savings, 20, 50000, "DEPOSIT EXAMPLE"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return migrated


@pytest.mark.parametrize(
    "args",
    [
        ("list",),
        ("review",),
        ("find",),
        ("confirm", "--out", "1", "--in", "2"),
        ("reject", "--out", "1", "--in", "2"),
        ("unpair", "--pair", "1"),
    ],
)
def test_every_command_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run("transfers", *args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


def test_nothing_yet(money: Settings) -> None:
    assert run("transfers", "list").stdout == "No transfers.\n"
    assert table_rows(run("transfers", "review").stdout) == [REVIEW, to_savings(4), to_savings(5)]


def test_find_pairs_the_clear_ones_and_leaves_the_rest(money: Settings) -> None:
    result = run("transfers", "find")
    assert (result.exit_code, result.stdout) == (0, "Transfers: 1 paired, 2 waiting for review.\n")
    assert table_rows(run("transfers", "list").stdout) == [
        LIST,
        ["1", "2026-05-03", "Test Checking", "Test Card", "$500.00", "1", "2", "auto"],
    ]
    assert table_rows(run("transfers", "review").stdout) == [REVIEW, to_savings(4), to_savings(5)]
    assert [row[0] for row in table_rows(run("uncategorized").stdout)[1:]] == [
        "7",
        "6",
        "5",
        "4",
        "3",
    ]
    assert run("transfers", "find").stdout == "Transfers: 0 paired, 2 waiting for review.\n"


def test_confirm_one_of_the_choices(money: Settings) -> None:
    run("transfers", "find")
    result = run("transfers", "confirm", "--out", "3", "--in", "5")
    assert (result.exit_code, result.stdout) == (0, "Transactions 3 and 5 are now a transfer.\n")
    assert run("transfers", "review").stdout == "No transfers wait for review.\n"
    assert table_rows(run("transfers", "list").stdout)[1:] == [
        ["2", "2026-05-05", "Test Checking", "Test Savings", "$20.00", "3", "5", "confirmed"],
        ["1", "2026-05-03", "Test Checking", "Test Card", "$500.00", "1", "2", "auto"],
    ]
    assert run("transfers", "find").stdout == "Transfers: 0 paired, 0 waiting for review.\n"


def test_a_rejected_choice_makes_the_other_clear(money: Settings) -> None:
    result = run("transfers", "reject", "--out", "3", "--in", "4")
    assert (result.exit_code, result.stdout) == (0, "Transactions 3 and 4 will not be paired.\n")
    assert run("transfers", "review").stdout == "No transfers wait for review.\n"
    assert run("transfers", "find").stdout == "Transfers: 2 paired, 0 waiting for review.\n"


def test_an_unpaired_transfer_is_not_paired_again(money: Settings) -> None:
    run("transfers", "find")
    result = run("transfers", "unpair", "--pair", "1")
    assert (result.exit_code, result.stdout) == (
        0,
        "Transfer 1 removed; transactions 1 and 2 will not be paired again.\n",
    )
    assert run("transfers", "list").stdout == "No transfers.\n"
    assert run("transfers", "find").stdout == "Transfers: 0 paired, 2 waiting for review.\n"
    assert run("transfers", "list").stdout == "No transfers.\n"


def test_rejecting_a_transfer_removes_it(money: Settings) -> None:
    run("transfers", "find")
    assert run("transfers", "reject", "--out", "1", "--in", "2").exit_code == 0
    assert run("transfers", "list").stdout == "No transfers.\n"
    assert run("transfers", "find").stdout == "Transfers: 0 paired, 2 waiting for review.\n"


def test_categorizing_also_pairs_quietly(money: Settings) -> None:
    result = run("categorize")
    assert result.stdout == "Categorized 7 transactions: 0 changed, 7 without a category.\n"
    assert [row[-1] for row in table_rows(run("transfers", "list").stdout)] == ["How", "auto"]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("confirm", "--out", "99", "--in", "2"), "transaction not found"),
        (("confirm", "--out", "1", "--in", "3"), "a transfer goes from one account to another"),
        (
            ("confirm", "--out", "2", "--in", "1"),
            "a transfer pairs money out with the same amount in",
        ),
        (
            ("confirm", "--out", "6", "--in", "4"),
            "a transfer pairs money out with the same amount in",
        ),
        (("confirm", "--out", "1", "--in", "7"), "transaction 1 is already in a transfer"),
        (("reject", "--out", "1", "--in", "99"), "transaction not found"),
        (("unpair", "--pair", "9"), "transfer not found"),
    ],
)
def test_a_refused_command(money: Settings, args, message: str) -> None:
    run("transfers", "find")
    assert failed_cleanly(run("transfers", *args), message)
```

## Tests to write

`tests/integration/test_transfer_store.py`:

- `list_transfer_movements` leaves out pending, zero, and paired transactions;
- `create_transfer_pair`: each message, the in side already paired, a wrong status, and a rejection removed by confirming;
- `reject_transfer` twice keeps one row; `unpair_transfer` of an unknown id;
- `delete_feed_transaction` on a paired and on a rejected feed transaction (with foreign keys on, as the app runs);
- `pair_transfers` and `transfer_suggestions` with a rejection, and `transfer_lines` ordering;
- Sync now pairs a clear transfer that the feed brought (as `test_web_categories.py` tests that it categorizes).

## Rules for this phase

- **Thin.** `cli/transfers.py` and the web call repositories, the service, and views; they hold no query and no pairing rule.
- `domain/transfers.py` imports only the standard library and `finances.domain`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_transfers.py tests/integration/test_migration_0009.py tests/e2e/test_cli_transfers.py`, 41 tests;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.transfers --cov=finances.categorize.transfers --cov=finances.views.transfers --cov=finances.cli.transfers --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` and `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|transfer_candidates|clear_pairs" -- src/finances/cli src/finances/web`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 11c: transfers (YYYY-MM-DD)`.
