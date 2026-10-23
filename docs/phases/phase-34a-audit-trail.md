# Phase 34a: the audit trail, and every change a person makes

## Goal

The household can see who changed what. After this phase a new table, `audit_log`, gets one row for every change a person makes to the household's data through the repositories (an account added, renamed, closed; an owner set; a category or rule added, edited, deleted; a transaction's category set by hand; a budget set; a transfer confirmed or rejected), written **in the same transaction as the change**, so the change and its record commit together or not at all. `fin audit` lists them, newest first. Rows are never edited or deleted by the app.

What the app does on its own is not recorded here: rules setting categories, automatic transfer pairing, syncs. Phase 34b adds the system's own events (statement imports, backup restores and deletions) and a History page; Phase 19 will record accepted proposals.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/roadmap.md`, Phase 34
- `src/finances/db/repositories/` (the areas this phase hooks: `accounts.py`, `people.py`, `categories.py`, `budgets.py`, `transfers.py`), `src/finances/db/orm.py`, `src/finances/domain/text.py` (`fit`), `src/finances/db/migrations/versions/0011_sync_failures.py`, `tests/unit/test_repositories_split.py`

## Starting state

N is `3298` when Phase 36c is the last phase built. The newest migration is `0011`.

No earlier test depends on the new table being empty: the architect ran the whole suite with this design on a scratch copy, and only the split test (which pins the repository areas) needed a change.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0012_audit_log.py` | new: given (R1) |
| `src/finances/domain/text.py` | `AUDIT_TEXT_LIMIT` (R1) |
| `src/finances/db/orm.py` | `AuditRow`, `to_change` (R1) |
| `src/finances/domain/audit.py` | new (R2) |
| `src/finances/db/repositories/audit.py` | new (R3) |
| `src/finances/db/repositories/assignments.py` | new: functions moved from `categories.py` (R4) |
| `src/finances/db/repositories/__init__.py` and the five areas above | re-exports and hooks (R4 to R9) |
| `src/finances/views/audit.py`, `src/finances/cli/audit.py`, `src/finances/cli/main.py` | `fin audit` (R10) |
| `tests/unit/test_repositories_split.py` | the given diff (R11) |
| `tests/unit/test_audit_rules.py`, `tests/integration/test_migration_0012.py`, `tests/integration/test_audit_trail.py`, `tests/e2e/test_cli_audit.py` | new: given |
| `tests/integration/test_audit_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Statement imports, backup restores and deletions, sync events, a History page (34b); proposals and `agent` (Phase 19).
- Recording what rules, automatic pairing, or syncs do; recording reads; undoing, exporting, or deleting audit rows.

## Dependencies

None new. One migration, given below.

## Design

```python
# src/finances/domain/text.py
AUDIT_TEXT_LIMIT = 200

# src/finances/domain/audit.py  (standard library and finances.domain only)
PERSON = "person"
SYSTEM = "system"
WHO = (PERSON, SYSTEM)
ACTIONS = (
    "account_added", "account_renamed", "account_closed", "account_reopened", "owner_set",
    "person_added", "cardholder_set", "category_added", "category_renamed", "category_deleted",
    "rule_added", "rule_edited", "rule_deleted", "category_set", "category_cleared",
    "budget_set", "budget_removed", "transfer_confirmed", "transfer_rejected", "transfer_unpaired",
)
KINDS = ("account", "person", "category", "rule", "transaction", "transfer")

@dataclass(frozen=True)
class Change:
    id: int
    at: datetime          # UTC
    who: str
    action: str
    kind: str
    record_id: int | None
    before: str | None
    after: str | None

def rule_text(match: str, pattern: str, category: str, priority: int) -> str: ...
    # 'contains "ACME COFFEE" -> Coffee & Dessert (priority 5)'
def pair_text(out_id: int, in_id: int) -> str: ...   # "2 -> 3"

# src/finances/db/orm.py
class AuditRow(Base): ...            # the table of the given migration; text columns String(AUDIT_TEXT_LIMIT)
def to_change(row: AuditRow) -> Change: ...

# src/finances/db/repositories/audit.py
def _now() -> datetime: ...          # datetime.now(UTC); looked up when called, so tests can replace it
def record_change(
    session: Session, *, action: str, kind: str, record_id: int | None,
    before: str | None = None, after: str | None = None, who: str = PERSON,
) -> Change: ...
def list_changes(
    session: Session, *, since: date | None = None, action: str | None = None, limit: int = 50
) -> list[Change]: ...

# src/finances/views/audit.py
@dataclass(frozen=True)
class ChangeRow:
    when: str      # at, "YYYY-MM-DD HH:MM" (UTC)
    who: str
    action: str
    record: str    # "kind record_id", or the kind alone
    before: str    # "" for None
    after: str

def change_rows(changes: list[Change]) -> list[ChangeRow]: ...

# src/finances/cli/audit.py
def audit_command(since: datetime | None, action: str | None, limit: int) -> None: ...  # fin audit
```

## Requirements

### Part 1: the table and the rules

- **R1.** Add the given migration `0012_audit_log.py` exactly, `AUDIT_TEXT_LIMIT`, and `AuditRow` with `to_change` (its `at` read back in UTC, as `to_sync_failure` does).
- **R2.** `domain/audit.py` is as designed; the lists keep their order.
- **R3.** `record_change` refuses an action, kind, or who not in its list with `ValueError("action must be one of: " + ", ".join(ACTIONS))` (and the same for `kind` with `KINDS`, `who` with `WHO`), cuts `before` and `after` with `fit(..., AUDIT_TEXT_LIMIT)`, stamps `at` with `_now()`, adds the row, flushes, and returns it. It never commits. `list_changes` refuses a limit below 1 with `ValueError("limit must be at least 1")` and returns changes from the start of `since` (midnight UTC) on, of `action` when given, newest first then highest id, at most `limit`.

### Part 2: the changes a person makes

Each hook calls `record_change` in the repository function, after the change is flushed, with `who` left as `person`. **No row is written when nothing changed** (the same name, the same owner, the same category, the same amount, an account already open), and a refused change writes nothing.

- **R4.** Move the transaction-category functions from `categories.py` to a new area `repositories/assignments.py` (so `categories.py` stays under 400 lines): `list_category_assignments`, `_assignment_row`, `_assign`, `assign_by_rule`, `remove_category`, `set_categories_by_hand`, `clear_categories_by_hand`, `set_category_by_hand`, `clear_category_by_hand`, `list_uncategorized`, `count_uncategorized`, and the private helpers this phase adds for them. The package keeps re-exporting every name; `repositories/audit.py` exports `record_change` and `list_changes`.
- **R5.** Accounts and people: `create_account` records `account_added` (kind `account`, after the name); `rename_account` `account_renamed` (old name, new name); `set_account_active` `account_closed` or `account_reopened` (`open`/`closed` before and after); `set_account_owner` `owner_set` (before the previous owner's name, `Joint`, or None when there was no owner row; after the new owner's name or `Joint`); `create_person` `person_added` (kind `person`, after the name); `set_cardholder_alias` `cardholder_set` (kind `person`, the person's id; before the previous person's name when the cardholder name was another person's, else None; after the cardholder name as stored).
- **R6.** Categories and rules: `create_category` `category_added` (after the name); `rename_category` `category_renamed`; `delete_category` `category_deleted` (before the name, after the category its uses moved to, or None); `create_rule` `rule_added` (kind `rule`, after `rule_text` of the stored rule); `edit_rule` `rule_edited` (the rule's text before and after, recorded only when it differs); `delete_rule` `rule_deleted` (before its text).
- **R7.** A transaction's category set by hand: `set_category_by_hand` and `set_categories_by_hand` record `category_set` for each transaction (kind `transaction`; before the previous category's name or None, after the new one); `clear_category_by_hand` and `clear_categories_by_hand` record `category_cleared` (before the category it had) for each transaction that had one. `assign_by_rule` and `remove_category` record nothing: they are what the rules do.
- **R8.** Budgets: `set_budget` `budget_set` (kind `category`, the group or category's id; before the previous amount as `format_cents` or None, after the new amount); `remove_budget` `budget_removed` (before the amount).
- **R9.** Transfers: `create_transfer_pair` records `transfer_confirmed` (kind `transfer`, the pair's id, after `pair_text`) only for `CONFIRMED`; automatic pairs record nothing. `reject_transfer` records `transfer_rejected` (kind `transaction`, the outflow's id, after `pair_text`); `unpair_transfer` `transfer_unpaired` (kind `transfer`, the pair's id, before `pair_text`).

### Part 3: reading it, and the split test

- **R10.** `fin audit [--since YYYY-MM-DD] [--action ACTION] [--limit 1..1000, default 50]` refuses an unknown action with `action must be one of: ...` (exit 1) before anything else, checks the schema, and prints a table with the columns `When (UTC)`, `Who`, `Action`, `Record`, `Before`, `After` from `change_rows`, or `No changes recorded.`
- **R11.** Apply the given diff to `tests/unit/test_repositories_split.py`: the package gains the `assignments` and `audit` areas and 88 names. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0012_audit_log.py` (add it exactly)

```python
"""Create audit_log: one row per change a person made to the household's data, never edited."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("who", sa.String(10), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("before", sa.String(200), nullable=True),
        sa.Column("after", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
```

## Given tests

15 tests in four files. `finances.db.repositories.audit._now` is replaced where a time is pinned; the record ids follow the seeded categories (46 rows, so a new category is 47; Groceries is 13).

`tests/unit/test_audit_rules.py`

```python
from finances.domain.audit import ACTIONS, KINDS, PERSON, SYSTEM, WHO, pair_text, rule_text
from finances.domain.text import AUDIT_TEXT_LIMIT


def test_the_lists() -> None:
    assert (PERSON, SYSTEM, WHO) == ("person", "system", ("person", "system"))
    assert ACTIONS == (
        "account_added",
        "account_renamed",
        "account_closed",
        "account_reopened",
        "owner_set",
        "person_added",
        "cardholder_set",
        "category_added",
        "category_renamed",
        "category_deleted",
        "rule_added",
        "rule_edited",
        "rule_deleted",
        "category_set",
        "category_cleared",
        "budget_set",
        "budget_removed",
        "transfer_confirmed",
        "transfer_rejected",
        "transfer_unpaired",
    )
    assert KINDS == ("account", "person", "category", "rule", "transaction", "transfer")
    assert AUDIT_TEXT_LIMIT == 200


def test_the_texts() -> None:
    assert rule_text("contains", "ACME COFFEE", "Coffee & Dessert", 5) == (
        'contains "ACME COFFEE" -> Coffee & Dessert (priority 5)'
    )
    assert pair_text(2, 3) == "2 -> 3"
```

`tests/integration/test_migration_0012.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import AuditRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("at", "DATETIME", False),
    ("who", "VARCHAR(10)", False),
    ("action", "VARCHAR(30)", False),
    ("kind", "VARCHAR(20)", False),
    ("record_id", "INTEGER", True),
    ("before", "VARCHAR(200)", True),
    ("after", "VARCHAR(200)", True),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0012_follows_0011() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0012")
    assert script.down_revision == "0011"


def test_the_table_and_its_row_class(url: str) -> None:
    command.upgrade(make_config(url), "0012")
    engine = get_engine(url)
    found = inspect(engine)
    columns = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("audit_log")]
    primary = found.get_pk_constraint("audit_log")
    extras = (
        found.get_unique_constraints("audit_log"),
        found.get_foreign_keys("audit_log"),
        found.get_indexes("audit_log"),
    )
    engine.dispose()
    assert columns == COLUMNS
    assert (primary["name"], primary["constrained_columns"]) == ("pk_audit_log", ["id"])
    assert extras == ([], [], [])
    assert [(c.name, str(c.type), c.nullable) for c in AuditRow.__table__.columns] == COLUMNS


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0012")
    command.downgrade(config, "0011")
    engine = get_engine(url)
    assert "audit_log" not in inspect(engine).get_table_names()
    engine.dispose()
    command.upgrade(config, "0012")
    engine = get_engine(url)
    assert "audit_log" in inspect(engine).get_table_names()
    engine.dispose()
```

`tests/integration/test_audit_trail.py`

```python
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    clear_category_by_hand,
    create_account,
    create_category,
    create_person,
    create_rule,
    create_transfer_pair,
    delete_category,
    delete_rule,
    edit_rule,
    list_changes,
    record_change,
    reject_transfer,
    remove_budget,
    rename_account,
    rename_category,
    set_account_active,
    set_account_owner,
    set_budget,
    set_cardholder_alias,
    set_category_by_hand,
    unpair_transfer,
)
from finances.domain.audit import Change
from finances.domain.models import CONFIRMED

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setattr("finances.db.repositories.audit._now", lambda: NOON)
    with session_scope(db_engine) as opened:
        yield opened


def add(session: Session, number: int, account: int, cents: int, description: str) -> None:
    session.add(
        TransactionRow(
            account_id=account,
            posted_date=date(2026, 5, number),
            amount_cents=cents,
            description=description,
            source="statement",
            fingerprint=f"t{number:02d}".ljust(64, "0"),
        )
    )
    session.flush()


def trail(session: Session) -> list[tuple]:
    return [
        (item.who, item.action, item.kind, item.record_id, item.before, item.after)
        for item in reversed(list_changes(session, limit=1000))
    ]


def test_each_change_a_person_makes(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    create_account(session, "Test Checking", "Test Bank", "checking")
    rename_account(session, 1, "Test Visa")
    set_account_active(session, 2, False)
    set_account_active(session, 2, True)
    create_person(session, "Pat Example")
    set_account_owner(session, 1, 1)
    set_account_owner(session, 1, None)
    set_cardholder_alias(session, "p example", 1)
    create_category(session, "Pets", "Home")
    rename_category(session, "Pets", "Pet Care")
    create_rule(session, "acme  coffee", "Coffee & Dessert")
    edit_rule(session, 1, priority=5)
    set_budget(session, "Groceries", 15000)
    set_budget(session, "Groceries", 20000)
    remove_budget(session, "Groceries")
    add(session, 1, 1, -500, "ACME COFFEE")
    add(session, 2, 2, -2000, "TRANSFER TO CARD")
    add(session, 3, 1, 2000, "PAYMENT THANK YOU")
    set_category_by_hand(session, 1, "Dining")
    set_category_by_hand(session, 1, "Groceries")
    clear_category_by_hand(session, 1)
    create_transfer_pair(session, 2, 3, CONFIRMED)
    unpair_transfer(session, 1)
    reject_transfer(session, 2, 3)
    delete_rule(session, 1)
    delete_category(session, "Pet Care")
    rule_5 = 'contains "ACME COFFEE" -> Coffee & Dessert (priority 5)'
    assert trail(session) == [
        ("person", "account_added", "account", 1, None, "Test Card"),
        ("person", "account_added", "account", 2, None, "Test Checking"),
        ("person", "account_renamed", "account", 1, "Test Card", "Test Visa"),
        ("person", "account_closed", "account", 2, "open", "closed"),
        ("person", "account_reopened", "account", 2, "closed", "open"),
        ("person", "person_added", "person", 1, None, "Pat Example"),
        ("person", "owner_set", "account", 1, None, "Pat Example"),
        ("person", "owner_set", "account", 1, "Pat Example", "Joint"),
        ("person", "cardholder_set", "person", 1, None, "P EXAMPLE"),
        ("person", "category_added", "category", 47, None, "Pets"),
        ("person", "category_renamed", "category", 47, "Pets", "Pet Care"),
        (
            "person",
            "rule_added",
            "rule",
            1,
            None,
            'contains "ACME COFFEE" -> Coffee & Dessert (priority 0)',
        ),
        (
            "person",
            "rule_edited",
            "rule",
            1,
            'contains "ACME COFFEE" -> Coffee & Dessert (priority 0)',
            rule_5,
        ),
        ("person", "budget_set", "category", 13, None, "$150.00"),
        ("person", "budget_set", "category", 13, "$150.00", "$200.00"),
        ("person", "budget_removed", "category", 13, "$200.00", None),
        ("person", "category_set", "transaction", 1, None, "Dining"),
        ("person", "category_set", "transaction", 1, "Dining", "Groceries"),
        ("person", "category_cleared", "transaction", 1, "Groceries", None),
        ("person", "transfer_confirmed", "transfer", 1, None, "2 -> 3"),
        ("person", "transfer_unpaired", "transfer", 1, "2 -> 3", None),
        ("person", "transfer_rejected", "transaction", 2, None, "2 -> 3"),
        ("person", "rule_deleted", "rule", 1, rule_5, None),
        ("person", "category_deleted", "category", 47, "Pet Care", None),
    ]


def test_nothing_is_recorded_when_nothing_changes(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    create_person(session, "Pat Example")
    set_account_owner(session, 1, 1)
    set_cardholder_alias(session, "P EXAMPLE", 1)
    add(session, 1, 1, -500, "ACME COFFEE")
    set_category_by_hand(session, 1, "Dining")
    set_budget(session, "Groceries", 15000)
    before = len(list_changes(session, limit=1000))
    rename_account(session, 1, "Test Card")
    set_account_active(session, 1, True)
    set_account_owner(session, 1, 1)
    set_cardholder_alias(session, "P EXAMPLE", 1)
    set_category_by_hand(session, 1, "Dining")
    set_budget(session, "Groceries", 15000)
    rename_category(session, "Dining", "Dining")
    add(session, 2, 1, 999, "BAZ CREDIT")
    clear_category_by_hand(session, 2)
    assert len(list_changes(session, limit=1000)) == before


def test_rules_and_automatic_pairing_record_nothing(session: Session) -> None:
    create_account(session, "Test Checking", "Test Bank", "checking")
    create_account(session, "Test Card", "Test Bank", "credit_card")
    create_rule(session, "ACME", "Dining")
    add(session, 1, 2, -500, "ACME COFFEE")
    add(session, 2, 1, -2000, "PAYMENT TO CARD")
    add(session, 3, 2, 2000, "PAYMENT THANK YOU")
    before = len(list_changes(session, limit=1000))
    categorize(session)
    pair_transfers(session)
    assert len(list_changes(session, limit=1000)) == before


def test_a_refused_change_records_nothing(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    with pytest.raises(ValueError, match="category not found"):
        set_budget(session, "Nope", 100)
    assert [item.action for item in list_changes(session)] == ["account_added"]


def test_record_change_checks_and_fits(session: Session) -> None:
    found = record_change(
        session, action="budget_set", kind="category", record_id=13, after="x" * 250, who="system"
    )
    assert found == Change(found.id, NOON, "system", "budget_set", "category", 13, None, "x" * 200)
    for field, value, message in (
        ("action", "nope", "action must be one of: account_added, "),
        (
            "kind",
            "nope",
            "kind must be one of: account, person, category, rule, transaction, transfer",
        ),
        ("who", "agent", "who must be one of: person, system"),
    ):
        arguments = {"action": "budget_set", "kind": "category", "record_id": 13, field: value}
        with pytest.raises(ValueError, match=message):
            record_change(session, **arguments)


def test_list_changes_newest_first_and_filters(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    for day, name in ((24, "Test A"), (25, "Test B"), (25, "Test C")):
        moment = datetime(2026, 5, day, 23, 30, tzinfo=UTC)
        monkeypatch.setattr("finances.db.repositories.audit._now", lambda moment=moment: moment)
        create_account(session, name, "Test Bank", "checking")
    create_person(session, "Pat Example")
    assert [item.after for item in list_changes(session)] == [
        "Pat Example",
        "Test C",
        "Test B",
        "Test A",
    ]
    assert [item.after for item in list_changes(session, since=date(2026, 5, 25))] == [
        "Pat Example",
        "Test C",
        "Test B",
    ]
    assert [item.after for item in list_changes(session, action="person_added")] == ["Pat Example"]
    assert [item.after for item in list_changes(session, limit=1)] == ["Pat Example"]
    with pytest.raises(ValueError, match="limit must be at least 1"):
        list_changes(session, limit=0)
```

`tests/e2e/test_cli_audit.py`

```python
from datetime import UTC, datetime

import pytest

from finances.config import Settings
from tests.support import failed_cleanly, run, table_rows

HEADINGS = ["When (UTC)", "Who", "Action", "Record", "Before", "After"]


@pytest.fixture
def changed(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr(
        "finances.db.repositories.audit._now", lambda: datetime(2026, 5, 25, 14, 3, 59, tzinfo=UTC)
    )
    assert run("db", "upgrade").exit_code == 0
    assert (
        run(
            "accounts",
            "add",
            "--name",
            "Test Card",
            "--institution",
            "Test Bank",
            "--type",
            "credit_card",
        ).exit_code
        == 0
    )
    assert run("people", "add", "--name", "Pat Example").exit_code == 0
    assert run("budgets", "set", "--name", "Groceries", "--amount", "150").exit_code == 0
    return tmp_settings


def test_every_change_newest_first(changed: Settings) -> None:
    result = run("audit")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        HEADINGS,
        ["2026-05-25 14:03", "person", "budget_set", "category 13", "", "$150.00"],
        ["2026-05-25 14:03", "person", "person_added", "person 1", "", "Pat Example"],
        ["2026-05-25 14:03", "person", "account_added", "account 1", "", "Test Card"],
    ]


def test_one_action_and_a_limit(changed: Settings) -> None:
    assert table_rows(run("audit", "--action", "person_added").stdout)[1:] == [
        ["2026-05-25 14:03", "person", "person_added", "person 1", "", "Pat Example"]
    ]
    assert len(table_rows(run("audit", "--limit", "2").stdout)) == 3


def test_nothing_since_a_later_day(changed: Settings) -> None:
    assert run("audit", "--since", "2026-05-26").stdout == "No changes recorded.\n"


UNKNOWN = (
    "action must be one of: account_added, account_renamed, account_closed, account_r"
    "eopened, owner_set, person_added, cardholder_set, category_added, category_renam"
    "ed, category_deleted, rule_added, rule_edited, rule_deleted, category_set, categ"
    "ory_cleared, budget_set, budget_removed, transfer_confirmed, transfer_rejected, "
    "transfer_unpaired"
)


def test_an_unknown_action(changed: Settings) -> None:
    assert failed_cleanly(run("audit", "--action", "nope"), UNKNOWN)
```

The diff to the earlier split test (apply it exactly):

```text
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 33d4eae..82139bb 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -8,6 +8,21 @@ import finances.db.repositories as repositories
 
 PACKAGE = Path(repositories.__file__).parent
 HOMES = {
+    "assignments": [
+        "assign_by_rule",
+        "clear_categories_by_hand",
+        "clear_category_by_hand",
+        "count_uncategorized",
+        "list_category_assignments",
+        "list_uncategorized",
+        "remove_category",
+        "set_categories_by_hand",
+        "set_category_by_hand",
+    ],
+    "audit": [
+        "list_changes",
+        "record_change",
+    ],
     "accounts": [
         "AccountExistsError",
         "account_data_span",
@@ -79,10 +94,6 @@ HOMES = {
     "categories": [
         "CategoryDeletion",
         "CategoryExistsError",
-        "assign_by_rule",
-        "clear_categories_by_hand",
-        "clear_category_by_hand",
-        "count_uncategorized",
         "create_category",
         "create_rule",
         "delete_category",
@@ -90,13 +101,8 @@ HOMES = {
         "edit_rule",
         "get_category_by_name",
         "list_categories",
-        "list_category_assignments",
         "list_rules",
-        "list_uncategorized",
-        "remove_category",
         "rename_category",
-        "set_categories_by_hand",
-        "set_category_by_hand",
     ],
     "budgets": [
         "list_budgets",
@@ -124,7 +130,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 86
+    assert len(expected) == 88
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Tests to write

`tests/integration/test_audit_more.py`: `set_categories_by_hand` and `clear_categories_by_hand` record one row per transaction; deleting a group records `category_deleted`; `edit_rule` that changes nothing records nothing; a rule text longer than 200 characters is cut; `fin audit` without a migrated database; `--since` keeps a change at 00:00 UTC that day.

## Rules for this phase

- The record and the change share one transaction: `record_change` flushes and never commits.
- Rows hold names, ids, and short values only: never a transaction's description, an amount other than a budget's, or a statement's contents. Nothing is logged outside the database.
- `domain/audit.py` imports only the standard library and `finances.domain`. Front ends write nothing to the trail themselves.
- One migration, given; never edit an earlier one.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_audit_rules.py tests/integration/test_migration_0012.py tests/integration/test_audit_trail.py tests/e2e/test_cli_audit.py`, 15 tests; at least N + 15 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/unit/test_repositories_split.py`;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.audit --cov=finances.db.repositories --cov=finances.views.audit --cov=finances.cli.audit --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` (no output) and `git grep -n --untracked -E "record_change|AuditRow" -- src/finances/cli src/finances/web` (no output: front ends never write the trail).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 34a: the audit trail (YYYY-MM-DD)`.
