# Phase 21: people and ownership

## Goal

Let every view say **whose** money it is. The household is two people with several shared cards. After this phase:

- the household's people are stored (`fin people add`, `fin people list`);
- each account is owned by one person or is **Joint** (`fin accounts set-owner`);
- each cardholder name that a statement prints (`SAM DOE` on a shared card) can be tied to a person (`fin people alias`);
- every transaction is **attributed**: to the cardholder's person when the statement names a known cardholder, otherwise to the account's owner (a person or Joint), otherwise to nobody yet (**unassigned**);
- `fin accounts list` shows each account's owner, and `fin transactions list` shows each transaction's person and can keep one person's (`--person`).

This is a view, not access control: both people see everything. It was decided with the owner, and reports and the agent's tools will group by person from here on.

A SimpleFIN link (Phase 17c) is a different thing: it says whose SimpleFIN subscription an account's feed comes through, not who owns the account. Nothing in this phase touches links.

## Read first

- `AGENTS.md`: "Architecture rules", "Testing"
- `docs/architecture.md`: "People"
- `src/finances/db/repositories.py`: `create_account`, `get_account_by_name`, `list_accounts`, `list_transactions`
- `src/finances/cli/accounts.py`, `src/finances/cli/listing.py`, `src/finances/cli/common.py`
- `tests/e2e/test_cli_listing.py`: how command tests read a table

## Starting state

- Phase 17d is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1454` when Phase 17d is the last phase built.
- The newest migration is `0005`.
- Statements store a cardholder name on a transaction only for cards that print one (Capital One and Citi); the name is stored as printed, with runs of whitespace made one space.
- The architect has already loosened four tests that pinned the exact columns of the transactions and accounts tables (`transaction_rows` in `tests/e2e/test_cli_listing.py`, and two assertions in `tests/e2e/test_cli_table_width.py`). They compare the columns that exist before this phase, and pass before and after it.
- There is no `src/finances/analysis/` package yet.
- `finances.db`, `finances.domain`, and `finances.cli` are at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0006_people.py` | new: three tables |
| `src/finances/domain/models.py` | one class added: `Person` |
| `src/finances/domain/people.py` | new: the attribution rule and name checks, pure |
| `src/finances/db/orm.py` | added: `PersonRow`, `AccountOwnerRow`, `CardholderAliasRow`, `to_person` |
| `src/finances/db/repositories.py` | added: `PersonExistsError` and seven functions (Part 3) |
| `src/finances/analysis/__init__.py` | new: a docstring only |
| `src/finances/analysis/people.py` | new: `Attribution`, `load_attribution`, `list_transactions_with_people` |
| `src/finances/cli/people.py` | new: `fin people add`, `list`, `alias` |
| `src/finances/cli/accounts.py` | `fin accounts set-owner`; an `Owner` column in `fin accounts list` |
| `src/finances/cli/listing.py` | a `Person` column and `--person` in `fin transactions list` |
| `src/finances/cli/main.py` | the `people` group registered |
| `tests/integration/test_migration_0006.py`, `tests/unit/test_people_rules.py`, `tests/integration/test_people_attribution.py`, `tests/e2e/test_cli_people.py` | given, do not change |
| `tests/integration/test_people_repositories.py` | new, written by you |
| `docs/progress.md` | one new entry |

You may add private helpers. Do not change any other production file, any existing test, or a shipped migration.

## Out of scope

- Reports, totals, or spending by person. Phase 12.
- The agent's tools. Phase 14.
- Removing a person, renaming one, or clearing an account's owner. Owners and aliases can be changed, not removed.
- Splitting one transaction between people.
- Any change to statements, the feed, links, or `fin statements list`.
- New dependencies.

## Dependencies

None new.

## Design

### The tables (migration `0006`, `down_revision = "0005"`)

`people`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | Integer | no | primary key `pk_people` |
| `name` | String(100) | no | unique constraint `uq_people_name` |

`account_owners`: at most one row per account. A row whose `person_id` is null means the account is **Joint**. An account with no row has no owner yet.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | Integer | no | primary key `pk_account_owners` |
| `account_id` | Integer | no | foreign key `fk_account_owners_account_id_accounts`; unique constraint `uq_account_owners_account_id` |
| `person_id` | Integer | yes | foreign key `fk_account_owners_person_id_people` |

`cardholder_aliases`: a cardholder name as statements print it, normalized (below), and its person.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | Integer | no | primary key `pk_cardholder_aliases` |
| `cardholder` | String(100) | no | unique constraint `uq_cardholder_aliases_cardholder` |
| `person_id` | Integer | no | foreign key `fk_cardholder_aliases_person_id_people` |

No index. The migration imports nothing from `finances`, uses no `server_default`, names every constraint, and its `downgrade` drops the three tables only. The three tables are kept apart from `accounts` and `transactions` so that those tables, and their tests, stay as they are.

### The rule, in `src/finances/domain/people.py` (imports nothing from the project)

```python
JOINT = "Joint"
RESERVED_NAMES = ("joint", "unassigned")
NAME_LIMIT = 100


def normalize_cardholder(text: str) -> str: ...
def validate_person_name(name: str) -> str: ...
def person_for(cardholder: str | None, owner: str | None, aliases: Mapping[str, str]) -> str | None: ...
```

```python
# domain/models.py
@dataclass(frozen=True)
class Person:
    """One person in the household."""

    id: int
    name: str
```

### The attribution, in `src/finances/analysis/people.py`

```python
JOINT_FILTER = "joint"
UNASSIGNED_FILTER = "unassigned"


@dataclass(frozen=True)
class Attribution:
    """Who owns each account and who each statement cardholder name is."""

    owners: dict[int, str]      # account id -> a person's name, or JOINT
    aliases: dict[str, str]     # normalized cardholder -> a person's name

    def owner(self, account_id: int) -> str | None: ...
    def person(self, transaction: Transaction) -> str | None: ...


def load_attribution(session: Session) -> Attribution: ...


def list_transactions_with_people(
    session: Session,
    account_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = 100,
    person: str | None = None,
) -> list[tuple[Transaction, str | None]]: ...
```

`analysis` reads through `db` repositories and writes nothing. The commands call it; they contain no attribution logic.

## Requirements

### Part 1: the tables

- **R1.** Migration `0006` creates the three tables exactly as designed, and its `downgrade` removes them and nothing else.
- **R2.** `PersonRow`, `AccountOwnerRow`, and `CardholderAliasRow` declare the same columns, nullability, and constraint names. `to_person` returns the `Person` for a row.

### Part 2: the rule

- **R3.** `normalize_cardholder(text)` makes every run of whitespace one space, removes outer whitespace, and returns the result in upper case.
- **R4.** `validate_person_name(name)` returns the name without outer whitespace. It raises `ValueError("a person's name must be 1 to 100 characters")` when that is empty or longer than 100 characters, and `ValueError("joint and unassigned are reserved names")` when it is `joint` or `unassigned` in any case.
- **R5.** `person_for(cardholder, owner, aliases)` returns, in this order: the person that `aliases` gives for `normalize_cardholder(cardholder)`, when `cardholder` is not `None` and is found there; otherwise `owner`. `owner` is a person's name, `JOINT`, or `None` (no owner yet), so the result is a person's name, `JOINT`, or `None` (unassigned).

### Part 3: repository functions

All take the session first, return domain objects or plain values, and leave the commit to the caller.

- **R6.** `create_person(session, name) -> Person` checks the name with `validate_person_name`, raises `PersonExistsError("a person with this name already exists")` when a person has the same name in any case, and otherwise adds the person with the cleaned name.
- **R7.** `get_person_by_name(session, name) -> Person | None` finds a person by name, ignoring case and outer whitespace.
- **R8.** `list_people(session) -> list[Person]` returns everyone, sorted by name without regard to case, then by id.
- **R9.** `set_account_owner(session, account_id, person_id: int | None) -> None` makes the person own the account, or makes it Joint when `person_id` is `None`, replacing an earlier owner.
- **R10.** `list_account_owners(session) -> dict[int, int | None]` maps each account that has an owner row to its person's id, or `None` for Joint. Accounts without a row are absent.
- **R11.** `set_cardholder_alias(session, cardholder, person_id) -> str` normalizes the name with `normalize_cardholder`, raises `ValueError("a cardholder name must be 1 to 100 characters")` when the result is empty or longer than 100 characters, stores it for the person (replacing an earlier person for the same name), and returns the normalized name.
- **R12.** `list_cardholder_aliases(session) -> dict[str, int]` maps every stored cardholder name to its person's id.

### Part 4: attribution

- **R13.** `load_attribution(session)` returns an `Attribution` whose `owners` maps each account with an owner row to its person's name, or `JOINT`, and whose `aliases` maps each stored cardholder name to its person's name.
- **R14.** `Attribution.owner(account_id)` returns the owner's name, `JOINT`, or `None` when the account has no owner row. `Attribution.person(transaction)` is `person_for(transaction.cardholder, self.owner(transaction.account_id), self.aliases)`.
- **R15.** `list_transactions_with_people(...)` returns the transactions that `list_transactions` would return for the account and dates, newest first, each paired with its person (R14). With `person` given, only that person's transactions are kept, and the `limit` applies **after** that filter, so a person's rows are not cut short by other people's. `person` is matched without regard to case or outer whitespace: `joint` keeps the Joint rows, `unassigned` keeps the rows whose person is `None`, and any other value must be a stored person's name, else `ValueError("person not found")`. A `limit` below 1 raises `ValueError("limit must be at least 1")`.

### Part 5: the commands

Every error is printed to standard error as `Error: <message>`, with exit code 1, as in the other commands. Every command here first checks the database with `require_current_schema`. Every table is printed with `print_table`.

- **R16.** `fin people add --name NAME` adds the person and prints `Added person "NAME" (id N)` with the stored name. The errors of R4 and R6 are printed as errors.
- **R17.** `fin people list` prints `No people.` when there is nobody, otherwise a table with the headings `Name`, `Owns`, `Cardholder names`: one row per person in `list_people` order; `Owns` is the names of the accounts, active or not, that the person owns, in `list_accounts` order, joined with `, `; `Cardholder names` is the person's stored cardholder names, sorted, joined with `, `.
- **R18.** `fin people alias --person NAME --cardholder TEXT` fails with `person not found` for an unknown person, prints the error of R11, or prints `Cardholder "NORMALIZED" is NAME.` with the normalized cardholder name and the person's stored name.
- **R19.** `fin accounts set-owner --account NAME --owner OWNER` fails with `account not found` for an unknown account (found as `get_account_by_name` finds it). `OWNER` is `joint` in any case, which makes the account Joint, or a person's name, else `person not found`. It prints `Owner of "ACCOUNT" is OWNER.` with the account's stored name and either the person's stored name or `Joint`.
- **R20.** `fin accounts list` gains a last column `Owner`: the owner's name, `Joint`, or empty. Nothing else about the command changes.
- **R21.** `fin transactions list` gains a last column `Person` (the person's name, `Joint`, or empty for unassigned) and an option `--person` (help text `Only one person's, or joint, or unassigned.`). It lists through `list_transactions_with_people`; the `ValueError` of R15 is printed as an error. With no rows it prints `No transactions.` as before. Nothing else about the command changes.
- **R22.** `fin people` is registered in `main.py` as `app.add_typer(people_app, name="people")`, after `sync`, with the help text `Manage the household's people.`.

## Given tests

Create these four files exactly as shown and do not change them. If one of their tests fails, the production code is wrong.

`tests/integration/test_migration_0006.py`

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
from finances.db.orm import Base

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0006_people.py"
COLUMNS = {
    "people": [("id", "INTEGER", False), ("name", "VARCHAR(100)", False)],
    "account_owners": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("person_id", "INTEGER", True),
    ],
    "cardholder_aliases": [
        ("id", "INTEGER", False),
        ("cardholder", "VARCHAR(100)", False),
        ("person_id", "INTEGER", False),
    ],
}
UNIQUES = {
    "people": [("uq_people_name", ["name"])],
    "account_owners": [("uq_account_owners_account_id", ["account_id"])],
    "cardholder_aliases": [("uq_cardholder_aliases_cardholder", ["cardholder"])],
}
FOREIGN_KEYS = {
    "people": [],
    "account_owners": [
        ("fk_account_owners_account_id_accounts", ["account_id"], "accounts"),
        ("fk_account_owners_person_id_people", ["person_id"], "people"),
    ],
    "cardholder_aliases": [
        ("fk_cardholder_aliases_person_id_people", ["person_id"], "people"),
    ],
}
TABLES = sorted(COLUMNS)


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def table_names(url: str) -> list[str]:
    engine = get_engine(url)
    names = sorted(inspect(engine).get_table_names())
    engine.dispose()
    return names


def versions(url: str) -> list[str]:
    engine = get_engine(url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    engine.dispose()
    return [row[0] for row in rows]


def reflect(url: str, table: str, what: str) -> list:
    engine = get_engine(url)
    result = getattr(inspect(engine), what)(table)
    engine.dispose()
    return result


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def at_0006(url: str) -> str:
    """A database at revision 0006 only, with two accounts."""
    command.upgrade(make_config(url), "0006")
    engine = get_engine(url)
    with session_scope(engine) as session:
        for name in ("Test Card", "Test Checking"):
            session.execute(
                text(
                    "INSERT INTO accounts"
                    " (name, institution, type, currency, is_active, created_at)"
                    " VALUES (:name, 'Test Bank', 'checking', 'USD', 1, '2026-01-01 00:00:00')"
                ),
                {"name": name},
            )
    engine.dispose()
    return url


def execute(url: str, sql: str, **values: object) -> None:
    engine = get_engine(url)
    with session_scope(engine) as session:
        session.execute(text(sql), values)
    engine.dispose()


def test_0006_follows_0005(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_revision("0006").down_revision == "0005"
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


@pytest.mark.parametrize("table", TABLES)
def test_columns_keys_and_constraints(at_0006: str, table: str) -> None:
    assert versions(at_0006) == ["0006"]
    columns = reflect(at_0006, table, "get_columns")
    assert [(c["name"], str(c["type"]), c["nullable"]) for c in columns] == COLUMNS[table]
    assert all(c["default"] is None for c in columns)
    primary_key = reflect(at_0006, table, "get_pk_constraint")
    assert (primary_key["name"], primary_key["constrained_columns"]) == (f"pk_{table}", ["id"])
    uniques = reflect(at_0006, table, "get_unique_constraints")
    assert sorted((u["name"], u["column_names"]) for u in uniques) == UNIQUES[table]
    keys = reflect(at_0006, table, "get_foreign_keys")
    found = sorted((k["name"], k["constrained_columns"], k["referred_table"]) for k in keys)
    assert found == FOREIGN_KEYS[table]
    assert reflect(at_0006, table, "get_indexes") == []


@pytest.mark.parametrize("table", TABLES)
def test_the_orm_class_matches_the_migrated_table(at_0006: str, table: str) -> None:
    declared = Base.metadata.tables[table]
    assert [(c.name, c.nullable) for c in declared.columns] == [
        (name, nullable) for name, _, nullable in COLUMNS[table]
    ]
    found = {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in declared.constraints
        if type(constraint).__name__ == "UniqueConstraint"
    }
    assert found == {(name, tuple(columns)) for name, columns in UNIQUES[table]}


def test_the_tables_hold_people_owners_and_aliases(at_0006: str) -> None:
    execute(at_0006, "INSERT INTO people (name) VALUES ('Alex'), ('Sam')")
    execute(at_0006, "INSERT INTO account_owners (account_id, person_id) VALUES (1, 1), (2, NULL)")
    execute(at_0006, "INSERT INTO cardholder_aliases (cardholder, person_id) VALUES ('SAM DOE', 2)")
    with pytest.raises(IntegrityError):
        execute(at_0006, "INSERT INTO people (name) VALUES ('Alex')")
    with pytest.raises(IntegrityError):
        execute(at_0006, "INSERT INTO account_owners (account_id, person_id) VALUES (1, 2)")
    with pytest.raises(IntegrityError):
        execute(at_0006, "INSERT INTO account_owners (account_id, person_id) VALUES (99, 1)")
    with pytest.raises(IntegrityError):
        execute(at_0006, "INSERT INTO account_owners (account_id, person_id) VALUES (2, 99)")
    with pytest.raises(IntegrityError):
        execute(
            at_0006, "INSERT INTO cardholder_aliases (cardholder, person_id) VALUES ('SAM DOE', 1)"
        )
    with pytest.raises(IntegrityError):
        execute(
            at_0006, "INSERT INTO cardholder_aliases (cardholder, person_id) VALUES ('X', NULL)"
        )


def test_downgrade_removes_only_the_three_tables(at_0006: str) -> None:
    before = table_names(at_0006)
    command.downgrade(make_config(at_0006), "0005")
    assert table_names(at_0006) == [
        name for name in before if name not in ("people", "account_owners", "cardholder_aliases")
    ]
    assert versions(at_0006) == ["0005"]
    command.upgrade(make_config(at_0006), "0006")
    assert {"people", "account_owners", "cardholder_aliases"} <= set(table_names(at_0006))
```

`tests/unit/test_people_rules.py`

```python
import pytest

from finances.domain.people import (
    JOINT,
    NAME_LIMIT,
    RESERVED_NAMES,
    normalize_cardholder,
    person_for,
    validate_person_name,
)

ALIASES = {"SAM DOE": "Sam", "ALEX Q DOE": "Alex"}


def test_the_constants() -> None:
    assert (JOINT, RESERVED_NAMES, NAME_LIMIT) == ("Joint", ("joint", "unassigned"), 100)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sam Doe", "SAM DOE"),
        ("  sam   doe ", "SAM DOE"),
        ("SAM\tDOE", "SAM DOE"),
        ("o'neil-smith", "O'NEIL-SMITH"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalize_cardholder(text: str, expected: str) -> None:
    assert normalize_cardholder(text) == expected


@pytest.mark.parametrize(
    ("name", "expected"), [("Alex", "Alex"), ("  Sam Doe ", "Sam Doe"), ("x" * 100, "x" * 100)]
)
def test_usable_person_names(name: str, expected: str) -> None:
    assert validate_person_name(name) == expected


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "a person's name must be 1 to 100 characters"),
        ("   ", "a person's name must be 1 to 100 characters"),
        ("x" * 101, "a person's name must be 1 to 100 characters"),
        ("joint", "joint and unassigned are reserved names"),
        (" JOINT ", "joint and unassigned are reserved names"),
        ("Unassigned", "joint and unassigned are reserved names"),
    ],
)
def test_unusable_person_names(name: str, message: str) -> None:
    with pytest.raises(ValueError) as caught:
        validate_person_name(name)
    assert str(caught.value) == message


@pytest.mark.parametrize(
    ("cardholder", "owner", "expected"),
    [
        ("SAM DOE", "Alex", "Sam"),
        ("sam  doe", JOINT, "Sam"),
        ("SAM DOE", None, "Sam"),
        ("PAT DOE", "Alex", "Alex"),
        ("PAT DOE", JOINT, JOINT),
        ("PAT DOE", None, None),
        (None, "Alex", "Alex"),
        (None, JOINT, JOINT),
        (None, None, None),
        ("", "Alex", "Alex"),
    ],
)
def test_person_for(cardholder: str | None, owner: str | None, expected: str | None) -> None:
    assert person_for(cardholder, owner, ALIASES) == expected


def test_person_for_with_no_aliases() -> None:
    assert person_for("SAM DOE", "Alex", {}) == "Alex"
```

`tests/integration/test_people_attribution.py`

```python
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.people import (
    Attribution,
    list_transactions_with_people,
    load_attribution,
)
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    set_account_owner,
    set_cardholder_alias,
)
from finances.domain.people import JOINT


def add(session: Session, account_id: int, day: int, cents: int, cardholder: str | None) -> None:
    session.add(
        TransactionRow(
            account_id=account_id,
            posted_date=date(2026, 5, day),
            amount_cents=cents,
            description=f"ACME {day}",
            cardholder=cardholder,
            source="statement",
            fingerprint=f"{account_id}-{day}".ljust(64, "x"),
        )
    )
    session.flush()


@pytest.fixture
def session(db_engine: Engine):
    """Alex owns the card, the checking account is joint, the savings account has no owner.

    Sam's cardholder name is SAM DOE. Transactions, newest first: savings on the 9th, a card
    purchase by SAM DOE on the 8th, checking on the 7th, a card purchase by PAT DOE (no alias)
    on the 6th, and a card purchase with no cardholder on the 5th.
    """
    with session_scope(db_engine) as opened:
        card = create_account(opened, "Test Card", "Test Bank", "credit_card")
        checking = create_account(opened, "Test Checking", "Test Bank", "checking")
        savings = create_account(opened, "Test Savings", "Test Bank", "savings")
        alex = create_person(opened, "Alex")
        sam = create_person(opened, "Sam")
        set_account_owner(opened, card.id, alex.id)
        set_account_owner(opened, checking.id, None)
        set_cardholder_alias(opened, "Sam  Doe", sam.id)
        add(opened, savings.id, 9, 1000, None)
        add(opened, card.id, 8, -800, "SAM DOE")
        add(opened, checking.id, 7, -700, None)
        add(opened, card.id, 6, -600, "PAT DOE")
        add(opened, card.id, 5, -500, None)
        yield opened


def people(found: list) -> list[tuple[int, str | None]]:
    return [(row.amount_cents, who) for row, who in found]


def test_load_attribution(session: Session) -> None:
    attribution = load_attribution(session)
    assert attribution == Attribution(owners={1: "Alex", 2: JOINT}, aliases={"SAM DOE": "Sam"})
    assert (attribution.owner(1), attribution.owner(2), attribution.owner(3)) == (
        "Alex",
        JOINT,
        None,
    )


def test_every_transaction_with_its_person(session: Session) -> None:
    assert people(list_transactions_with_people(session)) == [
        (1000, None),
        (-800, "Sam"),
        (-700, JOINT),
        (-600, "Alex"),
        (-500, "Alex"),
    ]


@pytest.mark.parametrize(
    ("person", "expected"),
    [
        ("Alex", [(-600, "Alex"), (-500, "Alex")]),
        ("  sAm ", [(-800, "Sam")]),
        ("joint", [(-700, JOINT)]),
        ("JOINT", [(-700, JOINT)]),
        ("unassigned", [(1000, None)]),
        (" Unassigned ", [(1000, None)]),
    ],
)
def test_one_persons_transactions(session: Session, person: str, expected: list) -> None:
    assert people(list_transactions_with_people(session, person=person)) == expected


def test_the_limit_applies_after_the_person_filter(session: Session) -> None:
    assert people(list_transactions_with_people(session, limit=1, person="alex")) == [
        (-600, "Alex")
    ]
    assert people(list_transactions_with_people(session, limit=2)) == [(1000, None), (-800, "Sam")]


def test_the_other_filters_still_apply(session: Session) -> None:
    found = list_transactions_with_people(
        session, account_id=1, start=date(2026, 5, 6), end=date(2026, 5, 8)
    )
    assert people(found) == [(-800, "Sam"), (-600, "Alex")]
    assert people(list_transactions_with_people(session, account_id=1, person="sam")) == [
        (-800, "Sam")
    ]


def test_an_unknown_person(session: Session) -> None:
    with pytest.raises(ValueError) as caught:
        list_transactions_with_people(session, person="Nobody")
    assert str(caught.value) == "person not found"


def test_a_limit_below_one(session: Session) -> None:
    with pytest.raises(ValueError) as caught:
        list_transactions_with_people(session, limit=0, person="alex")
    assert str(caught.value) == "limit must be at least 1"


def test_changing_an_owner_or_an_alias_changes_the_attribution(session: Session) -> None:
    pat = create_person(session, "Pat")
    set_cardholder_alias(session, "pat doe", pat.id)
    set_account_owner(session, 1, None)
    assert people(list_transactions_with_people(session, account_id=1)) == [
        (-800, "Sam"),
        (-600, "Pat"),
        (-500, JOINT),
    ]
```

`tests/e2e/test_cli_people.py`

```python
from datetime import date

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, TransactionRow

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
ACCOUNT_HEADINGS = ["Name", "Institution", "Type", "Last 4", "Active", "Owner"]
TRANSACTION_HEADINGS = ["Date", "Account", "Description", "Amount", "Card", "Section", "Person"]
PEOPLE_HEADINGS = ["Name", "Owns", "Cardholder names"]


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
    """Three accounts (Test Card, Test Checking, Test Savings), and no people yet."""
    assert run("db", "upgrade").exit_code == 0
    for name, kind in (
        ("Test Card", "credit_card"),
        ("Test Checking", "checking"),
        ("Test Savings", "savings"),
    ):
        assert (
            run(
                "accounts", "add", "--name", name, "--institution", "Test Bank", "--type", kind
            ).exit_code
            == 0
        )
    return tmp_settings


@pytest.fixture
def household(migrated: Settings) -> Settings:
    """Alex owns the card, the checking account is joint, and SAM DOE on statements is Sam."""
    assert run("people", "add", "--name", "Alex").exit_code == 0
    assert run("people", "add", "--name", "Sam").exit_code == 0
    assert run("accounts", "set-owner", "--account", "Test Card", "--owner", "Alex").exit_code == 0
    assert (
        run("accounts", "set-owner", "--account", "Test Checking", "--owner", "joint").exit_code
        == 0
    )
    assert run("people", "alias", "--person", "Sam", "--cardholder", "Sam Doe").exit_code == 0
    engine = get_engine(migrated.effective_database_url)
    with session_scope(engine) as session:
        for account_id, day, cents, cardholder in (
            (3, 9, 1000, None),
            (1, 8, -800, "SAM DOE"),
            (2, 7, -700, None),
            (1, 6, -600, "PAT DOE"),
        ):
            session.add(
                TransactionRow(
                    account_id=account_id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=f"ACME {day}",
                    cardholder=cardholder,
                    source="statement",
                    fingerprint=f"{day}".ljust(64, "x"),
                )
            )
    engine.dispose()
    return migrated


# ----- fin people -----


def test_add_people(migrated: Settings) -> None:
    result = run("people", "add", "--name", "  Alex ")
    assert (result.exit_code, result.stdout) == (0, 'Added person "Alex" (id 1)\n')
    assert run("people", "add", "--name", "Sam").stdout == 'Added person "Sam" (id 2)\n'


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("alex", "a person with this name already exists"),
        ("Joint", "joint and unassigned are reserved names"),
        ("unassigned", "joint and unassigned are reserved names"),
        ("   ", "a person's name must be 1 to 100 characters"),
        ("x" * 101, "a person's name must be 1 to 100 characters"),
    ],
)
def test_names_that_cannot_be_added(migrated: Settings, name: str, message: str) -> None:
    assert run("people", "add", "--name", "Alex").exit_code == 0
    assert failed_cleanly(run("people", "add", "--name", name), message)


def test_people_list(household: Settings) -> None:
    assert run("people", "alias", "--person", "sam", "--cardholder", "S DOE").exit_code == 0
    assert (
        run("accounts", "set-owner", "--account", "Test Savings", "--owner", "Alex").exit_code == 0
    )
    result = run("people", "list")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        PEOPLE_HEADINGS,
        ["Alex", "Test Card, Test Savings", ""],
        ["Sam", "", "S DOE, SAM DOE"],
    ]


def test_people_list_includes_closed_accounts(household: Settings) -> None:
    engine = get_engine(household.effective_database_url)
    with session_scope(engine) as session:
        session.scalars(
            select(AccountRow).where(AccountRow.name == "Test Card")
        ).one().is_active = False
    engine.dispose()
    assert table_rows(run("people", "list").stdout)[1] == ["Alex", "Test Card", ""]


def test_people_list_with_nobody(migrated: Settings) -> None:
    assert run("people", "list").stdout == "No people.\n"


def test_alias(migrated: Settings) -> None:
    assert run("people", "add", "--name", "Sam").exit_code == 0
    result = run("people", "alias", "--person", " SAM ", "--cardholder", "  sam   q doe ")
    assert (result.exit_code, result.stdout) == (0, 'Cardholder "SAM Q DOE" is Sam.\n')
    assert run("people", "add", "--name", "Pat").exit_code == 0
    moved = run("people", "alias", "--person", "Pat", "--cardholder", "SAM Q DOE")
    assert moved.stdout == 'Cardholder "SAM Q DOE" is Pat.\n'
    assert table_rows(run("people", "list").stdout)[1:] == [
        ["Pat", "", "SAM Q DOE"],
        ["Sam", "", ""],
    ]


def test_alias_refusals(migrated: Settings) -> None:
    assert failed_cleanly(
        run("people", "alias", "--person", "Nobody", "--cardholder", "X"), "person not found"
    )
    assert run("people", "add", "--name", "Sam").exit_code == 0
    assert failed_cleanly(
        run("people", "alias", "--person", "Sam", "--cardholder", "   "),
        "a cardholder name must be 1 to 100 characters",
    )
    assert failed_cleanly(
        run("people", "alias", "--person", "Sam", "--cardholder", "X" * 101),
        "a cardholder name must be 1 to 100 characters",
    )


# ----- fin accounts -----


def test_set_owner_and_list_accounts(household: Settings) -> None:
    result = run("accounts", "list")
    assert table_rows(result.stdout) == [
        ACCOUNT_HEADINGS,
        ["Test Card", "Test Bank", "credit_card", "", "yes", "Alex"],
        ["Test Checking", "Test Bank", "checking", "", "yes", "Joint"],
        ["Test Savings", "Test Bank", "savings", "", "yes", ""],
    ]
    changed = run("accounts", "set-owner", "--account", "test card", "--owner", "JOINT")
    assert (changed.exit_code, changed.stdout) == (0, 'Owner of "Test Card" is Joint.\n')
    changed = run("accounts", "set-owner", "--account", "Test Checking", "--owner", " sam ")
    assert changed.stdout == 'Owner of "Test Checking" is Sam.\n'
    assert [row[5] for row in table_rows(run("accounts", "list").stdout)[1:]] == [
        "Joint",
        "Sam",
        "",
    ]


def test_set_owner_refusals(household: Settings) -> None:
    assert failed_cleanly(
        run("accounts", "set-owner", "--account", "Nope", "--owner", "Alex"), "account not found"
    )
    assert failed_cleanly(
        run("accounts", "set-owner", "--account", "Test Card", "--owner", "Nobody"),
        "person not found",
    )


# ----- fin transactions -----


def test_transactions_show_their_person(household: Settings) -> None:
    result = run("transactions", "list")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        TRANSACTION_HEADINGS,
        ["2026-05-09", "Test Savings", "ACME 9", "$10.00", "", "", ""],
        ["2026-05-08", "Test Card", "ACME 8", "-$8.00", "", "", "Sam"],
        ["2026-05-07", "Test Checking", "ACME 7", "-$7.00", "", "", "Joint"],
        ["2026-05-06", "Test Card", "ACME 6", "-$6.00", "", "", "Alex"],
    ]


@pytest.mark.parametrize(
    ("person", "descriptions"),
    [
        ("alex", ["ACME 6"]),
        ("Sam", ["ACME 8"]),
        ("joint", ["ACME 7"]),
        ("unassigned", ["ACME 9"]),
    ],
)
def test_transactions_of_one_person(
    household: Settings, person: str, descriptions: list[str]
) -> None:
    result = run("transactions", "list", "--person", person)
    assert [row[2] for row in table_rows(result.stdout)[1:]] == descriptions


def test_the_limit_counts_the_persons_rows(household: Settings) -> None:
    result = run("transactions", "list", "--person", "unassigned", "--limit", "1")
    assert [row[2] for row in table_rows(result.stdout)[1:]] == ["ACME 9"]
    result = run("transactions", "list", "--account", "Test Card", "--person", "sam")
    assert [row[2] for row in table_rows(result.stdout)[1:]] == ["ACME 8"]


def test_transactions_of_someone_unknown_or_with_none(household: Settings) -> None:
    assert failed_cleanly(run("transactions", "list", "--person", "Nobody"), "person not found")
    assert run("people", "add", "--name", "Pat").exit_code == 0
    assert run("transactions", "list", "--person", "Pat").stdout == "No transactions.\n"


@pytest.mark.parametrize(
    "command",
    [
        ["people", "add", "--name", "A"],
        ["people", "list"],
        ["people", "alias", "--person", "A", "--cardholder", "B"],
        ["accounts", "set-owner", "--account", "A", "--owner", "B"],
    ],
)
def test_commands_need_a_migrated_database(tmp_settings: Settings, command: list[str]) -> None:
    result = run(*command)
    assert (result.exit_code, result.stderr, result.stdout) == (1, NOT_MIGRATED, "")
```

## Tests to write

`tests/integration/test_people_repositories.py`, on the `db_engine` fixture, one repository function at a time:

- R6: the stored name is cleaned; a duplicate in another case raises `PersonExistsError` with its exact message and adds nothing; the two `ValueError`s of R4
- R7: found in any case and with outer spaces; `None` for an unknown name
- R8: empty; the order by name without regard to case
- R9 and R10: an owner, Joint, a change of owner (one row per account), an account without an owner left out, and an unknown account or person raising `IntegrityError`
- R11 and R12: the returned name is normalized; the same name for another person replaces the first; the `ValueError` for an empty and for a 101-character name; an unknown person raising `IntegrityError`
- R2: `to_person` for a row; `Person` frozen with its fields in order
- that a later session sees what an earlier one wrote

Every line and branch of `finances.analysis`, `finances.db`, `finances.domain`, and `finances.cli` must be reached by a test.

## Rules for this phase

- **Pure rule.** `domain/people.py` imports nothing from the project. `analysis/people.py` reads through repository functions and writes nothing. The commands contain no attribution logic and write no query.
- **Constant messages.** The messages of this phase are the ones written in R4, R6, R11, R15, R18, and R19; the only varying parts are names.
- **Synthetic data only** in tests: invented names.
- **Shipped migrations stay as they are.**
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.
- Do not run `fin` against the real database in `data/`.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 74 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/integration/test_migration_0006.py tests/unit/test_people_rules.py tests/integration/test_people_attribution.py tests/e2e/test_cli_people.py --no-cov` | exactly `74 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the four searches below | no output |
| `git diff HEAD --stat -- src/finances/db/migrations/versions src/finances/ingest src/finances/sync src/finances/cli/sync.py src/finances/cli/importing.py tests/conftest.py tests/e2e/test_cli_listing.py tests/e2e/test_cli_table_width.py tests/e2e/test_cli_accounts.py` | no output (the new migration is untracked, so it does not appear) |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis --cov=finances.db --cov=finances.domain --cov=finances.cli --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/analysis src/finances/domain/people.py src/finances/cli/people.py`

`git grep -n --untracked -E "^ *(import|from) +finances" -- src/finances/domain/people.py`

`git grep -n --untracked -E "finances\.(cli|ingest|sync)" -- src/finances/analysis`

`git grep -n --untracked -E "select\(|finances\.db\.orm|session\.(add|execute)" -- src/finances/analysis src/finances/cli/people.py src/finances/cli/accounts.py src/finances/cli/listing.py`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 21: people and ownership (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. Under "Deviations", list your design choices and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command, and for each of R1 to R22 the name of a test that covers it.
