# Phase 30a: tax categories and the year's totals

## Goal

A person can mark categories as tax-relevant and see a calendar year's totals. After this phase:

- categories carry a tax flag; the migration sets it on the seeded `Medical`, `Gifts & Donations`, and `Taxes`, and `fin categories tax` turns it on or off for any category, recorded in the audit trail;
- `fin year` shows a year's spending by group and by category, the tax-relevant categories pulled out (each flagged category, with $0.00 when it had nothing), and the year's summary;
- the year counts a split transaction's parts as Phase 28e's category reports do.

Phase 30 is split (see `docs/roadmap.md`): 30b puts the year and the flag on the web; 30c exports CSV from the terminal; 30d from the web.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/domain/models.py` (`Category`), `src/finances/db/orm.py` (`CategoryRow`, `to_category`), `src/finances/db/repositories/categories.py` (`_category_row`, `create_category`, `record_change` use)
- `src/finances/analysis/spending.py` (`load_flows`, `parts=True`), `src/finances/domain/spending.py` (`spending_lines`, `summarize`, `SpendingLine`, `SpendingSummary`)
- `src/finances/views/spending.py` (`spending_rows`, `spending_summary`), `src/finances/cli/reports.py` (`spending_command`), `src/finances/cli/categories.py`, `src/finances/cli/main.py`

## Starting state

N is `3765` when Phase 29c is the last phase built. The newest migration is `0020`. Migrations run with foreign keys on, and batch mode rebuilds a table: that fails for `categories`, which other tables point at. The given migration therefore adds and drops the column in place (SQLite's own `ADD COLUMN` and `DROP COLUMN`); it was run up, down, and up with a rule pointing at a category.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0021_tax_categories.py` | new: given (R1) |
| `src/finances/domain/models.py`, `src/finances/db/orm.py` | `Category.is_tax`, `CategoryRow.is_tax`, `to_category` (R1) |
| `src/finances/db/repositories/categories.py`, `src/finances/db/repositories/__init__.py` | `set_tax_relevant` (R2) |
| `src/finances/domain/audit.py` | one action (R2) |
| `src/finances/analysis/yearend.py` (new) | `YearReport`, `year_report` (R3) |
| `src/finances/views/spending.py` | `line_rows`, `summary_lines` (R4) |
| `src/finances/views/yearend.py` (new) | `year_heading` (R4) |
| `src/finances/cli/reports.py`, `src/finances/cli/main.py` | `fin year` (R5) |
| `src/finances/cli/categories.py` | `fin categories tax` (R6) |
| `tests/integration/test_migration_0008.py`, `tests/unit/test_audit_rules.py`, `tests/e2e/test_cli_audit.py`, `tests/unit/test_repositories_split.py` | the given diff (R7) |
| `tests/integration/test_migration_0021.py`, `tests/e2e/test_cli_year.py` | new: given |
| `tests/integration/test_year_report.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- The year and the flag on the web (30b); CSV export (30c, 30d); the flag in `fin categories list`, the Categories page, or the `list_categories` MCP tool.
- A tax flag on a group, income by category, a year other than a calendar year, or comparing years.

## Dependencies

None new. One migration, given below.

## Design

```python
# src/finances/domain/models.py
@dataclass(frozen=True)
class Category:
    ...                      # the fields of today, unchanged and in order
    is_tax: bool = False

# src/finances/db/orm.py, CategoryRow
is_tax: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

# src/finances/db/repositories/categories.py
def set_tax_relevant(session: Session, name: str, tax: bool) -> Category: ...

# src/finances/analysis/yearend.py
@dataclass(frozen=True)
class YearReport:
    year: int
    start: date               # 1 January
    end: date                 # 31 December
    summary: SpendingSummary
    groups: list[SpendingLine]
    categories: list[SpendingLine]
    tax: list[SpendingLine]   # one per tax-relevant category, by name

def year_report(session: Session, year: int) -> YearReport: ...

# src/finances/views/spending.py
def line_rows(lines: Iterable[SpendingLine]) -> list[SpendingRow]: ...  # what spending_rows does per line
def summary_lines(summary: SpendingSummary) -> list[str]: ...         # what spending_summary prints

# src/finances/views/yearend.py
def year_heading(report: YearReport) -> str: ...  # "Year 2026, from 2026-01-01 to 2026-12-31."
```

| Command | Options | Prints |
|---|---|---|
| `fin year` (on the main app, as `fin merchants` is) | `--year INT` (1 to 9999; this year by default, from `clock.today()`) | the heading; `By group:` and a table (`Group`, `Spent`, `Refunds`, `Net`, `Count`) or `No spending.`; `By category:` and a table (`Category`, ...) or `No spending.`; `Tax-relevant:` and a table (`Category`, ...) or `No tax-relevant categories.`; then `summary_lines` |
| `fin categories tax` | `--name NAME`, `--off` (a flag) | `Medical is tax-relevant.` or `Medical is not tax-relevant.`, with the category's own name |

## Requirements

### The flag

- **R1.** Add the given migration exactly. `Category.is_tax` and `CategoryRow.is_tax` as designed; `to_category` reads it; a category made by `create_category` is not tax-relevant.
- **R2.** `set_tax_relevant` refuses a name that is not a group or category (`category not found`) and a group (`a group cannot be tax-relevant; mark its categories`); when the flag changes it sets it, flushes, and records `category_tax_set` (kind `category`, the category's id, `before` and `after` `tax` or `not tax`); when it does not change it records nothing. It returns the category, and is re-exported from `finances.db.repositories`. `ACTIONS` ends with `"category_tax_set"`.

### The year

- **R3.** `year_report` refuses a year outside 1 to 9999 (`year must be from 1 to 9999`). It reads `load_flows(session, 1 January, 31 December, parts=True)`, so both ends are in the year and a split counts as its parts; `summary` is `summarize` of them, `groups` and `categories` are `spending_lines` by `group` and by `category`, and `tax` has one line for each tax-relevant category, by name: its line from `categories`, or `SpendingLine(name, 0, 0, 0)` when it had none.
- **R4.** `line_rows` and `summary_lines` as designed; `spending_rows` and `spending_summary` call them, so `fin spending` prints exactly as before. `year_heading` as designed.
- **R5.** `fin year` as designed; it calls `require_current_schema()` first, and a refusal is `fail(message)`.
- **R6.** `fin categories tax` as designed, a refusal through `fail`.
- **R7.** Apply the given diff to the four earlier test files. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0021_tax_categories.py` (do not change)

```python
"""Add categories.is_tax, and mark the seeded Medical, Gifts & Donations, and Taxes."""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

TAX = ("Medical", "Gifts & Donations", "Taxes")


def upgrade() -> None:
    op.add_column(
        "categories", sa.Column("is_tax", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    categories = sa.table(
        "categories",
        sa.column("name", sa.String()),
        sa.column("parent_id", sa.Integer()),
        sa.column("is_tax", sa.Boolean()),
    )
    op.execute(
        categories.update()
        .where(categories.c.name.in_(TAX), categories.c.parent_id.is_not(None))
        .values(is_tax=True)
    )


def downgrade() -> None:
    op.drop_column("categories", "is_tax")
```

## Given diff to earlier tests

```text
diff --git a/tests/e2e/test_cli_audit.py b/tests/e2e/test_cli_audit.py
index 24eb317..e002902 100644
--- a/tests/e2e/test_cli_audit.py
+++ b/tests/e2e/test_cli_audit.py
@@ -62,7 +62,7 @@ UNKNOWN = (
     "transfer_unpaired, statement_imported, backup_deleted, backup_restored, proposal"
     "_accepted, proposal_declined, alias_added, alias_deleted, tag_added, tag_removed, "
     "note_set, note_cleared, split_set, split_cleared, share_set, share_cleared, settlement_a"
-    "dded, settlement_deleted"
+    "dded, settlement_deleted, category_tax_set"
 )
 
 
diff --git a/tests/integration/test_migration_0008.py b/tests/integration/test_migration_0008.py
index 280c895..8b622fb 100644
--- a/tests/integration/test_migration_0008.py
+++ b/tests/integration/test_migration_0008.py
@@ -142,9 +142,10 @@ def test_columns_keys_and_constraints(at_0008: str, table: str) -> None:
 )
 def test_the_orm_classes_match_the_migrated_tables(at_0008: str, row_class, table: str) -> None:
     assert row_class.__table__ is Base.metadata.tables[table]
-    assert [
+    found = [
         (column.name, str(column.type), column.nullable) for column in row_class.__table__.columns
-    ] == COLUMNS[table]
+    ]
+    assert found[: len(COLUMNS[table])] == COLUMNS[table]
 
 
 def test_the_default_tree_is_seeded(at_0008: str) -> None:
diff --git a/tests/unit/test_audit_rules.py b/tests/unit/test_audit_rules.py
index 95bce7c..59e33e5 100644
--- a/tests/unit/test_audit_rules.py
+++ b/tests/unit/test_audit_rules.py
@@ -42,6 +42,7 @@ def test_the_lists() -> None:
         "share_cleared",
         "settlement_added",
         "settlement_deleted",
+        "category_tax_set",
     )
     assert KINDS == (
         "account",
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index c6c1175..a3a747f 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -120,6 +120,7 @@ HOMES = {
         "delete_category",
         "delete_rule",
         "edit_rule",
+        "set_tax_relevant",
         "get_category_by_name",
         "list_categories",
         "list_rules",
@@ -175,7 +176,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 123
+    assert len(expected) == 124
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

9 tests in two files. Do not change them. Two of the migration's (it follows 0020; it goes down and up with a rule in place) pass once the given migration is in.

`tests/integration/test_migration_0021.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import CategoryRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def columns(url: str) -> list[tuple]:
    engine = get_engine(url)
    found = [
        (c["name"], str(c["type"]), c["nullable"])
        for c in inspect(engine).get_columns("categories")
    ]
    engine.dispose()
    return found


def tax_names(url: str) -> list[str]:
    engine = get_engine(url)
    with engine.connect() as connection:
        found = connection.execute(
            text("SELECT name FROM categories WHERE is_tax ORDER BY name")
        ).scalars()
        names = list(found)
    engine.dispose()
    return names


def test_0021_follows_0020() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0021")
    assert script.down_revision == "0020"


def test_the_flag_and_the_seeded_tax_categories(url: str) -> None:
    command.upgrade(make_config(url), "0021")
    found = columns(url)
    assert found[-1] == ("is_tax", "BOOLEAN", False)
    orm = [(c.name, str(c.type), c.nullable) for c in CategoryRow.__table__.columns]
    assert orm[: len(found)] == found
    assert tax_names(url) == ["Gifts & Donations", "Medical", "Taxes"]


def test_down_and_up_again_with_rows_that_point_at_categories(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0021")
    engine = get_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO category_rules (pattern, match, priority, category_id) VALUES "
                "('ACME CLINIC', 'contains', 0, 30)"
            )
        )
    engine.dispose()
    command.downgrade(config, "0020")
    assert "is_tax" not in [name for name, _, _ in columns(url)]
    command.upgrade(config, "0021")
    assert tax_names(url) == ["Gifts & Donations", "Medical", "Taxes"]
```

`tests/e2e/test_cli_year.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, set_category_by_hand, set_split
from tests.support import failed_cleanly, plain_lines, run, table_rows

HEADINGS = ["Spent", "Refunds", "Net", "Count"]
GROUPS = [
    ["Group", *HEADINGS],
    ["Health", "$130.00", "$20.00", "$110.00", "3"],
    ["Personal", "$51.00", "$0.00", "$51.00", "2"],
    ["Food", "$20.00", "$0.00", "$20.00", "1"],
]
CATEGORIES = [
    ["Category", *HEADINGS],
    ["Medical", "$130.00", "$20.00", "$110.00", "3"],
    ["Gifts & Donations", "$51.00", "$0.00", "$51.00", "2"],
    ["Groceries", "$20.00", "$0.00", "$20.00", "1"],
]
TAX = [
    ["Category", *HEADINGS],
    ["Gifts & Donations", "$51.00", "$0.00", "$51.00", "2"],
    ["Medical", "$130.00", "$20.00", "$110.00", "3"],
    ["Taxes", "$0.00", "$0.00", "$0.00", "0"],
]


@pytest.fixture
def year(tmp_settings: Settings) -> Settings:
    """2026 on a card: Medical -$120.00 and a refund of $20.00; Gifts & Donations -$50.00 and
    -$1.00 on the year's last day; -$30.00 split into Groceries -$20.00 and Medical -$10.00; a
    paycheck of $3,000.00. Medical -$99.99 on 2025-12-31 is the year before."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 2, 10), -12000, "ACME CLINIC", "Medical"),
            (date(2026, 3, 5), -5000, "BAZ CHARITY", "Gifts & Donations"),
            (date(2026, 4, 1), -3000, "FOOBAR GROCERY", None),
            (date(2026, 5, 1), 2000, "ACME CLINIC", "Medical"),
            (date(2026, 6, 1), 300000, "PAYCHECK EXAMPLE CORP", "Paycheck"),
            (date(2025, 12, 31), -9999, "ACME CLINIC", "Medical"),
            (date(2026, 12, 31), -100, "BAZ CHARITY", "Gifts & Donations"),
        ]
        for number, (day, cents, description, _) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for number, (_, _, _, category) in enumerate(rows, start=1):
            if category is not None:
                set_category_by_hand(session, number, category)
        set_split(session, 3, [(-2000, "Groceries"), (-1000, "Medical")])
    engine.dispose()
    return tmp_settings


def test_a_year(year: Settings) -> None:
    result = run("year", "--year", "2026")
    assert result.exit_code == 0
    assert plain_lines(result.stdout) == [
        "Year 2026, from 2026-01-01 to 2026-12-31.",
        "By group:",
        "By category:",
        "Tax-relevant:",
        "Spent: $201.00. Refunds: $20.00. Net: $181.00. Income: $3,000.00.",
        "Transfers left out: 0.",
    ]
    assert table_rows(result.stdout) == [*GROUPS, *CATEGORIES, *TAX]


def test_this_year_by_default(year: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("finances.clock.today", lambda: date(2024, 8, 1))
    assert plain_lines(run("year").stdout)[0] == "Year 2024, from 2024-01-01 to 2024-12-31."


def test_a_year_with_nothing(year: Settings) -> None:
    result = run("year", "--year", "2024")
    assert plain_lines(result.stdout) == [
        "Year 2024, from 2024-01-01 to 2024-12-31.",
        "By group:",
        "No spending.",
        "By category:",
        "No spending.",
        "Tax-relevant:",
        "Spent: $0.00. Refunds: $0.00. Net: $0.00. Income: $0.00.",
        "Transfers left out: 0.",
    ]
    assert table_rows(result.stdout) == [
        ["Category", *HEADINGS],
        ["Gifts & Donations", "$0.00", "$0.00", "$0.00", "0"],
        ["Medical", "$0.00", "$0.00", "$0.00", "0"],
        ["Taxes", "$0.00", "$0.00", "$0.00", "0"],
    ]


def test_marking_a_category(year: Settings) -> None:
    on = run("categories", "tax", "--name", "groceries")
    assert (on.exit_code, on.stdout) == (0, "Groceries is tax-relevant.\n")
    off = run("categories", "tax", "--name", "Taxes", "--off")
    assert (off.exit_code, off.stdout) == (0, "Taxes is not tax-relevant.\n")
    assert table_rows(run("year", "--year", "2026").stdout)[-3:] == [
        ["Gifts & Donations", "$51.00", "$0.00", "$51.00", "2"],
        ["Groceries", "$20.00", "$0.00", "$20.00", "1"],
        ["Medical", "$130.00", "$20.00", "$110.00", "3"],
    ]


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("Health", "a group cannot be tax-relevant; mark its categories"),
        ("Nope", "category not found"),
    ],
)
def test_marking_refused(year: Settings, name: str, message: str) -> None:
    assert failed_cleanly(run("categories", "tax", "--name", name), message)
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_year_report.py`:

- a category made by `create_category` is not tax-relevant; `list_categories` gives `is_tax` True for the three seeded ones;
- `set_tax_relevant` records `category_tax_set` with `before` `not tax` and `after` `tax`, and setting it again to the same records nothing;
- a tax category renamed keeps its flag (the flag is on the row, not the name);
- `year_report(session, 0)` and `year_report(session, 10000)` are refused with R3's message;
- a transfer between two accounts in the year is not in any line;
- `fin year` with no tax-relevant category (every flag turned off) prints `No tax-relevant categories.`.

## Rules for this phase

- Money is integer cents; the year adds nothing up itself: every figure comes from `spending_lines` and `summarize`.
- A migration that changes a table other tables point at changes it in place, never with batch mode, since migrations run with foreign keys on.
- Messages are constant and echo nothing typed but a category's own name in `fin categories tax`'s answer.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 9 tests; at least N + 9 passed in all;
- `git diff --stat HEAD -- tests` lists only the four files of the given diff;
- `git grep -n "is_tax" -- src/finances/cli src/finances/views` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.yearend --cov=finances.views.yearend --cov=finances.views.spending --cov=finances.db.repositories --cov=finances.cli.reports --cov=finances.cli.categories --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 30a: tax categories and the year's totals (YYYY-MM-DD)`.
