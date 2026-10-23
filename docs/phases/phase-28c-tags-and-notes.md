# Phase 28c: tags and notes

## Goal

A person can label transactions with tags (many per transaction, such as `work trip` or `tax`) and keep one note on any transaction. After this phase:

- two new tables hold them, written only through repository functions that record each change in the audit trail;
- the terminal tags and untags transactions, sets and removes a note, and lists the tags in use with how many transactions carry each;
- a feed transaction that is deleted (a statement shows it never happened, or a pending one vanished) takes its tags and note with it.

The web half (tags and the note on a transaction's page, a tag filter on the Transactions page) is Phase 28f, after the splits (28d and 28e).

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/domain/text.py`, `src/finances/domain/audit.py`
- `src/finances/db/orm.py` (`CategoryRuleRow`, its named two-column unique constraint), `src/finances/db/repositories/assignments.py` (`set_categories_by_hand`, `_distinct_transaction_ids`, `_require_transaction`), `src/finances/db/repositories/feed.py` (`delete_feed_transaction`)
- `src/finances/cli/listing.py` (`transactions_app`), `src/finances/cli/categories.py` (`set_category_command`, which registers on `transactions_app`), `src/finances/cli/common.py`

## Starting state

N is `3550` when Phase 19e is the last phase built. The newest migration is `0017`. SQLite enforces foreign keys (`PRAGMA foreign_keys=ON` in `db/engine.py`), so a row that names a transaction must go before the transaction does; `delete_feed_transaction` already removes a transaction's category and transfer rows first.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0018_tags_and_notes.py` | new: given (R1) |
| `src/finances/domain/text.py` | `TAG_LIMIT`, `NOTE_LIMIT` (R1) |
| `src/finances/db/orm.py` | `TransactionTagRow`, `TransactionNoteRow` (R1) |
| `src/finances/domain/tags.py` (new) | `TagCount`, `normalize_tag`, `clean_note` (R2) |
| `src/finances/domain/audit.py` | four actions (R3) |
| `src/finances/db/repositories/tags.py` (new), `src/finances/db/repositories/__init__.py` | six functions (R4 to R6) |
| `src/finances/db/repositories/feed.py` | `delete_feed_transaction` (R7) |
| `src/finances/cli/tags.py` (new), `src/finances/cli/main.py` | four commands on `transactions_app` (R8, R9) |
| `tests/unit/test_audit_rules.py`, `tests/e2e/test_cli_audit.py`, `tests/unit/test_repositories_split.py` | the given diff (R10) |
| `tests/integration/test_migration_0018.py`, `tests/e2e/test_cli_tags.py` | new: given |
| `tests/unit/test_tag_rules.py`, `tests/integration/test_tags_and_notes.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Anything on the web (28f); a tag filter or a Tags column in `fin transactions list`; tags or notes in any MCP tool or report.
- Renaming or merging tags; a note on anything but a transaction; more than one note per transaction.
- Carrying tags or a note over when a statement takes the place of a feed transaction (a matched row is confirmed in place and keeps them already).

## Dependencies

None new. One migration, given below.

## Design

```python
# src/finances/domain/text.py
TAG_LIMIT = 30
NOTE_LIMIT = 500

# src/finances/domain/tags.py (imports only from finances.domain)
@dataclass(frozen=True)
class TagCount:
    tag: str
    transactions: int

def normalize_tag(text: str) -> str: ...  # runs of white space made one space, lower case; or ValueError
def clean_note(text: str) -> str: ...     # outer white space removed; "" means no note; or ValueError

# src/finances/db/orm.py
class TransactionTagRow(Base):
    __tablename__ = "transaction_tags"
    __table_args__ = (
        UniqueConstraint("transaction_id", "tag", name="uq_transaction_tags_transaction_id_tag"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    tag: Mapped[str] = mapped_column(String(TAG_LIMIT), nullable=False)

class TransactionNoteRow(Base):
    __tablename__ = "transaction_notes"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_transaction_notes_transaction_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    text: Mapped[str] = mapped_column(String(NOTE_LIMIT), nullable=False)

# src/finances/db/repositories/tags.py
def add_tags(session: Session, transaction_ids: Iterable[int], tag: str) -> tuple[int, str]: ...
def remove_tags(session: Session, transaction_ids: Iterable[int], tag: str) -> tuple[int, str]: ...
# both: (how many distinct transactions were named, the normalized tag)
def tags_for(session: Session, transaction_ids: Iterable[int]) -> dict[int, list[str]]: ...
def list_tags(session: Session) -> list[TagCount]: ...
def set_note(session: Session, transaction_id: int, text: str) -> str | None: ...
# the note stored, or None when the text was empty and the note is gone
def note_of(session: Session, transaction_id: int) -> str | None: ...
```

New commands on `transactions_app`, from a new module `cli/tags.py` that `cli/main.py` imports (as `cli/categories.py` adds `set-category`):

| Command | Options | Prints |
|---|---|---|
| `fin transactions tag` | `--id` (one or more), `--tag TEXT` | `Transaction 1: tagged "tax".` for one id, `2 transactions: tagged "work trip".` for more |
| `fin transactions untag` | `--id` (one or more), `--tag TEXT` | `Transaction 2: "trip" removed.`, `2 transactions: "trip" removed.` |
| `fin transactions note` | `--id INT`, `--text TEXT` | `Transaction 3: note saved.`, or `Transaction 3: note removed.` when the text is empty |
| `fin transactions tags` | none | a table with headings `Tag`, `Transactions`, one row per tag by tag; or `No tags.` |

The tag printed is the normalized one. Each command calls `require_current_schema()` first; a refusal is `fail(message)`.

## Requirements

### Storage and rules

- **R1.** Add the given migration exactly. `TAG_LIMIT` is 30 and `NOTE_LIMIT` 500. The two row classes as designed; their foreign keys take their names from the naming convention.
- **R2.** `normalize_tag` makes runs of white space one space and lower-cases (`"  Work   Trip "` gives `"work trip"`), and refuses a result outside 1 to `TAG_LIMIT` characters (`a tag must be 1 to 30 characters`). `clean_note` strips the outer white space and refuses a result longer than `NOTE_LIMIT` (`a note is at most 500 characters`); a note a person typed is refused, never cut.
- **R3.** `ACTIONS` ends with `"tag_added"`, `"tag_removed"`, `"note_set"`, `"note_cleared"`. The kind of each is the existing `"transaction"`.

### The repository

- **R4.** `add_tags` and `remove_tags` take each id once, check that **every** transaction exists before anything else (`transaction not found`), then normalize the tag, so a list is changed all or none. `add_tags` adds the tag to each transaction that lacks it; `remove_tags` removes it from each that has it, and a transaction without it is no error. For each transaction that changed, and only those, they record `tag_added` (`after` the tag) or `tag_removed` (`before` the tag), kind `transaction`, the transaction's id.
- **R5.** `set_note` checks the transaction exists (`transaction not found`), then cleans the text. A non-empty note is stored, replacing any note, and records `note_set` with `before` the old note (or None) and `after` the new, unless the text is unchanged, which records nothing. An empty text deletes the note and records `note_cleared` with `before` the old note; with no note to delete it records nothing. Audit texts pass through `record_change`, which fits them to its column. `note_of` returns the note or None.
- **R6.** `tags_for` maps each named transaction that has tags to its tags in order; `list_tags` gives each tag in use with how many transactions carry it, by tag. All six functions are re-exported from `finances.db.repositories`.
- **R7.** `delete_feed_transaction` also deletes the transaction's tags and note before the transaction.

### The terminal

- **R8.** `fin transactions tag` and `untag` as designed: `--id` may be given several times; the count in the message is how many distinct ids were named.
- **R9.** `fin transactions note` and `fin transactions tags` as designed. No rule of R2 to R5 is repeated in `cli/tags.py`.
- **R10.** Apply the given diff to the three earlier test files. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0018_tags_and_notes.py` (do not change)

```python
"""Create transaction_tags (many tags per transaction) and transaction_notes (one note each)."""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transaction_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_transaction_tags_transaction_id_transactions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_tags"),
        sa.UniqueConstraint(
            "transaction_id", "tag", name="uq_transaction_tags_transaction_id_tag"
        ),
    )
    op.create_table(
        "transaction_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(500), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_transaction_notes_transaction_id_transactions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_notes"),
        sa.UniqueConstraint("transaction_id", name="uq_transaction_notes_transaction_id"),
    )


def downgrade() -> None:
    op.drop_table("transaction_notes")
    op.drop_table("transaction_tags")
```

## Given diff to earlier tests

```text
diff --git a/tests/e2e/test_cli_audit.py b/tests/e2e/test_cli_audit.py
index e9df352..d15663e 100644
--- a/tests/e2e/test_cli_audit.py
+++ b/tests/e2e/test_cli_audit.py
@@ -60,7 +60,8 @@ UNKNOWN = (
     "ed, category_deleted, rule_added, rule_edited, rule_deleted, category_set, categ"
     "ory_cleared, budget_set, budget_removed, transfer_confirmed, transfer_rejected, "
     "transfer_unpaired, statement_imported, backup_deleted, backup_restored, proposal"
-    "_accepted, proposal_declined, alias_added, alias_deleted"
+    "_accepted, proposal_declined, alias_added, alias_deleted, tag_added, tag_removed, "
+    "note_set, note_cleared"
 )
 
 
diff --git a/tests/unit/test_audit_rules.py b/tests/unit/test_audit_rules.py
index 4ef1b4d..f380ec9 100644
--- a/tests/unit/test_audit_rules.py
+++ b/tests/unit/test_audit_rules.py
@@ -32,6 +32,10 @@ def test_the_lists() -> None:
         "proposal_declined",
         "alias_added",
         "alias_deleted",
+        "tag_added",
+        "tag_removed",
+        "note_set",
+        "note_cleared",
     )
     assert KINDS == (
         "account",
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 0a74ec4..14fe4b1 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -130,6 +130,14 @@ HOMES = {
         "remove_budget",
         "set_budget",
     ],
+    "tags": [
+        "add_tags",
+        "list_tags",
+        "note_of",
+        "remove_tags",
+        "set_note",
+        "tags_for",
+    ],
     "transfers": [
         "create_transfer_pair",
         "find_transfer_pair",
@@ -151,7 +159,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 105
+    assert len(expected) == 111
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

14 tests in two files. Do not change them.

`tests/integration/test_migration_0018.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import TransactionNoteRow, TransactionTagRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
TAGS = [
    ("id", "INTEGER", False),
    ("transaction_id", "INTEGER", False),
    ("tag", "VARCHAR(30)", False),
]
NOTES = [
    ("id", "INTEGER", False),
    ("transaction_id", "INTEGER", False),
    ("text", "VARCHAR(500)", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0018_follows_0017() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0018")
    assert script.down_revision == "0017"


@pytest.mark.parametrize(
    ("table", "columns", "row", "unique"),
    [
        (
            "transaction_tags",
            TAGS,
            TransactionTagRow,
            ("uq_transaction_tags_transaction_id_tag", ["transaction_id", "tag"]),
        ),
        (
            "transaction_notes",
            NOTES,
            TransactionNoteRow,
            ("uq_transaction_notes_transaction_id", ["transaction_id"]),
        ),
    ],
)
def test_the_tables_and_their_row_classes(
    url: str, table: str, columns: list, row: type, unique: tuple
) -> None:
    command.upgrade(make_config(url), "0018")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns(table)]
    primary = found.get_pk_constraint(table)
    uniques = [(u["name"], u["column_names"]) for u in found.get_unique_constraints(table)]
    keys = [
        (k["name"], k["constrained_columns"], k["referred_table"])
        for k in found.get_foreign_keys(table)
    ]
    engine.dispose()
    assert shown == columns
    assert (primary["name"], primary["constrained_columns"]) == (f"pk_{table}", ["id"])
    assert uniques == [unique]
    assert keys == [(f"fk_{table}_transaction_id_transactions", ["transaction_id"], "transactions")]
    orm = [(c.name, str(c.type), c.nullable) for c in row.__table__.columns]
    assert orm[: len(columns)] == columns


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0018")
    command.downgrade(config, "0017")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "transaction_tags" not in names and "transaction_notes" not in names
    command.upgrade(config, "0018")
```

`tests/e2e/test_cli_tags.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, note_of
from tests.support import failed_cleanly, run, table_rows


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """Three card purchases: 1 ACME COFFEE, 2 FOOBAR GROCERY, 3 BAZ CAFE."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-450, "ACME COFFEE"), (-2599, "FOOBAR GROCERY"), (-500, "BAZ CAFE")), start=1
        ):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return tmp_settings


def stored_note(transaction_id: int) -> str | None:
    engine = get_engine()
    with session_scope(engine) as session:
        found = note_of(session, transaction_id)
    engine.dispose()
    return found


def test_tagging(card: Settings) -> None:
    many = run("transactions", "tag", "--id", "1", "--id", "2", "--tag", "  Work   Trip ")
    assert (many.exit_code, many.stdout) == (0, '2 transactions: tagged "work trip".\n')
    one = run("transactions", "tag", "--id", "1", "--tag", "Tax")
    assert (one.exit_code, one.stdout) == (0, 'Transaction 1: tagged "tax".\n')
    assert table_rows(run("transactions", "tags").stdout) == [
        ["Tag", "Transactions"],
        ["tax", "1"],
        ["work trip", "2"],
    ]


def test_untagging(card: Settings) -> None:
    run("transactions", "tag", "--id", "1", "--id", "2", "--tag", "trip")
    removed = run("transactions", "untag", "--id", "2", "--tag", "TRIP")
    assert (removed.exit_code, removed.stdout) == (0, 'Transaction 2: "trip" removed.\n')
    assert table_rows(run("transactions", "tags").stdout) == [
        ["Tag", "Transactions"],
        ["trip", "1"],
    ]


def test_no_tags(card: Settings) -> None:
    assert run("transactions", "tags").stdout == "No tags.\n"


def test_a_note(card: Settings) -> None:
    saved = run("transactions", "note", "--id", "3", "--text", "  split with a friend ")
    assert (saved.exit_code, saved.stdout) == (0, "Transaction 3: note saved.\n")
    assert stored_note(3) == "split with a friend"
    removed = run("transactions", "note", "--id", "3", "--text", "")
    assert (removed.exit_code, removed.stdout) == (0, "Transaction 3: note removed.\n")
    assert stored_note(3) is None


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("tag", "--id", "9", "--tag", "trip"), "transaction not found"),
        (("tag", "--id", "1", "--tag", "   "), "a tag must be 1 to 30 characters"),
        (("tag", "--id", "9", "--tag", "   "), "transaction not found"),
        (("untag", "--id", "1", "--tag", "x" * 31), "a tag must be 1 to 30 characters"),
        (("note", "--id", "1", "--text", "x" * 501), "a note is at most 500 characters"),
        (("note", "--id", "9", "--text", "hi"), "transaction not found"),
    ],
)
def test_refused(card: Settings, args: tuple[str, ...], message: str) -> None:
    assert failed_cleanly(run("transactions", *args), message)
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/unit/test_tag_rules.py`:

- `normalize_tag` at 30 characters is kept and at 31 refused; `clean_note` at 500 characters is kept, and `"   "` gives `""`.

`tests/integration/test_tags_and_notes.py`:

- `add_tags([1, 1], ...)` counts 1; tagging a transaction that already has the tag adds no row and records nothing; the audit rows of a tag added and removed;
- `remove_tags` of a tag a transaction does not have changes nothing, records nothing, and raises nothing;
- `add_tags([1, 9], "trip")` stores nothing for 1 (all or none);
- `set_note`: the first note records `note_set` with `before` None; a changed note has the old one as `before`; the same text again records nothing; clearing records `note_cleared`; clearing with no note records nothing;
- `tags_for([1, 2, 3])` leaves out a transaction with no tags and gives each one's tags in order; `list_tags` counts each transaction once per tag;
- a feed transaction with a tag and a note is deleted by `delete_feed_transaction` without an error, and both are gone.

## Rules for this phase

- `domain/tags.py` imports only from `finances.domain`; `cli/tags.py` only parses options, calls one repository function, and prints.
- A tag and a note are typed by a person: too long is refused (R2), never cut. No message echoes a tag, a note, or a description.
- Keep each module under `src/finances/db/repositories/` under 400 lines.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 14 tests; at least N + 14 passed in all;
- `git diff --stat HEAD -- tests` lists only the three files of the given diff;
- `git grep -n "TransactionTagRow\|TransactionNoteRow" -- src/finances/cli src/finances/web src/finances/analysis` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.tags --cov=finances.domain.audit --cov=finances.db.repositories --cov=finances.cli.tags --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 28c: tags and notes (YYYY-MM-DD)`.
