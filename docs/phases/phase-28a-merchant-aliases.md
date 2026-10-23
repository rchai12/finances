# Phase 28a: merchant aliases

## Goal

A person can merge one merchant into another, so that `SQ *ACME CAFE` and `ACME COFFEE` count as one merchant. After this phase:

- an **alias** maps a cleaned merchant name (what `clean_merchant` gives) to the merchant it is merged into, managed with `fin aliases add`, `list`, and `delete`;
- every report that groups by merchant (spending by merchant, `fin merchants`, recurring charges and income, the forecast, insights, refund matching, merchant names) sees the **merged** name;
- a rule matches a transaction when it matches **either** the cleaned name or the merged name, so adding an alias never takes a category away; the rules run again after each alias change, as after `fin rules add`.

Phase 28 is split (see `docs/roadmap.md`): 28b puts aliases on the web and adds the rule preview; 28c tags and notes; 28d and 28e splits. The agent's alias proposals (19e) come after 28a.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/domain/merchants.py` (`clean_merchant`), `src/finances/domain/rules.py` (`pick_rule`, `rule_matches`), `src/finances/domain/audit.py`, `src/finances/domain/text.py`
- `src/finances/db/orm.py` (`CardholderAliasRow`, the nearest table), `src/finances/db/repositories/categories.py` (`create_rule`, its `record_change` call), `src/finances/db/repositories/proposals.py` (`propose_rule`, check 6)
- `src/finances/analysis/spending.py` (`flows_for`), `src/finances/analysis/refunds.py` (`refund_facts`), `src/finances/categorize/service.py` (`categorize`)
- `src/finances/cli/categories.py` (`categorize_all`, `add_rule_command`), `src/finances/cli/common.py` (`fail`, `print_rows`), `src/finances/views/categories.py` (`categorized_text`, `rule_lines`)

## Starting state

N is `3482` when Phase 19d is the last phase built. The newest migration is `0015`. Seven places call `clean_merchant` on a description: `flows_for` (the one place every merchant report reads), `refund_facts`, `categorize`, `propose_rule`, the `list_uncategorized` tool, and two lines in `views/categories.py`. This phase changes the first four.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0016_merchant_aliases.py` | new: given (R1) |
| `src/finances/domain/text.py` | `MERCHANT_NAME_LIMIT` (R1) |
| `src/finances/db/orm.py` | `MerchantAliasRow`, `to_merchant_alias` (R1) |
| `src/finances/domain/merchants.py` | `MerchantAlias`, `normalize_merchant`, `merchant_name`, `merchant_names`, `check_alias` (R2) |
| `src/finances/domain/rules.py` | `pick_rule_for` (R3) |
| `src/finances/domain/audit.py` | two actions and one kind (R4) |
| `src/finances/db/repositories/aliases.py` (new), `src/finances/db/repositories/__init__.py` | four functions (R5) |
| `src/finances/analysis/spending.py`, `src/finances/analysis/refunds.py` | the merged name (R6) |
| `src/finances/categorize/service.py`, `src/finances/db/repositories/proposals.py` | rules see either name (R7) |
| `src/finances/views/categories.py` | `AliasRow`, `alias_rows` (R8) |
| `src/finances/cli/aliases.py` (new), `src/finances/cli/main.py` | `fin aliases` (R8) |
| `tests/unit/test_audit_rules.py`, `tests/unit/test_repositories_split.py` | the given diff (R9) |
| `tests/integration/test_migration_0016.py`, `tests/e2e/test_cli_aliases.py` | new: given |
| `tests/unit/test_merchant_aliases.py`, `tests/integration/test_merchant_aliases.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Aliases on the web and the rule preview (28b); an MCP tool that lists or proposes aliases (19e).
- The uncategorized lists (`fin uncategorized`, the Categories page, the `list_uncategorized` tool) keep showing the cleaned name: a rule written from it still matches (R7).
- Editing an alias (delete it and add another), chains of aliases, mending a chain for the person, and checking that a name occurs in any transaction.

## Dependencies

None new. One migration, given below.

## Design

```python
# src/finances/domain/text.py
MERCHANT_NAME_LIMIT = 100

# src/finances/domain/merchants.py
@dataclass(frozen=True)
class MerchantAlias:
    id: int
    source: str  # a cleaned merchant name, normalized
    target: str  # the merchant it is merged into, normalized

def normalize_merchant(text: str) -> str: ...  # runs of white space made one space, upper case
def merchant_name(description: str, aliases: Mapping[str, str]) -> str: ...
# the alias's target for clean_merchant(description), or the cleaned name when it has none
def merchant_names(description: str, aliases: Mapping[str, str]) -> tuple[str, ...]: ...
# (cleaned,) without an alias, (cleaned, target) with one
def check_alias(source: str, target: str, aliases: Mapping[str, str]) -> tuple[str, str]: ...
# both names normalized, or ValueError (R2)

# src/finances/domain/rules.py
def pick_rule_for(names: Sequence[str], rules: list[CategoryRule]) -> CategoryRule | None: ...
# among rules matching any of the names: the highest priority, the oldest among equals

# src/finances/db/orm.py
class MerchantAliasRow(Base):
    __tablename__ = "merchant_aliases"
    __table_args__ = (UniqueConstraint("source", name="uq_merchant_aliases_source"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(MERCHANT_NAME_LIMIT), nullable=False)
    target: Mapped[str] = mapped_column(String(MERCHANT_NAME_LIMIT), nullable=False)

def to_merchant_alias(row: MerchantAliasRow) -> MerchantAlias: ...

# src/finances/db/repositories/aliases.py
def list_aliases(session: Session) -> list[MerchantAlias]: ...  # by source
def alias_map(session: Session) -> dict[str, str]: ...         # source -> target
def add_alias(session: Session, source: str, target: str) -> MerchantAlias: ...
def delete_alias(session: Session, source: str) -> MerchantAlias: ...

# src/finances/views/categories.py
@dataclass(frozen=True)
class AliasRow:
    source: str
    target: str

def alias_rows(aliases: list[MerchantAlias]) -> list[AliasRow]: ...
```

`fin aliases` (a new Typer app, `aliases_app`, registered in `cli/main.py` with `app.add_typer(aliases_app, name="aliases")`, help `Merge one merchant into another.`):

| Command | Options | Prints |
|---|---|---|
| `fin aliases add` | `--from TEXT` (the name to merge), `--to TEXT` (the merchant it joins) | `Merged "<source>" into "<target>".` then the categorize line |
| `fin aliases list` | none | a table with headings `From`, `To`, one row per alias by source; or `No aliases.` |
| `fin aliases delete` | `--from TEXT` | `Removed the alias for "<source>".` then the categorize line |

The names printed are the normalized, stored ones. The categorize line is `categorized_text` of `categorize_all()` from `finances.cli.categories`, as `fin rules add` prints it. A refusal is `fail(message)`: `Error: <message>` on stderr, exit code 1, nothing on stdout, nothing stored, and the rules not run.

## Requirements

### Storage and rules

- **R1.** Add the given migration exactly. `MERCHANT_NAME_LIMIT` is 100. `MerchantAliasRow` and `to_merchant_alias` as designed.
- **R2.** `normalize_merchant` makes runs of white space one space and upper-cases (`"  acme   cafe "` gives `"ACME CAFE"`). `merchant_name` and `merchant_names` as designed. `check_alias` normalizes both names, then refuses with `ValueError`, in this order:
  1. the source is 1 to `MERCHANT_NAME_LIMIT` characters (`a merchant name must be 1 to 100 characters`);
  2. the target is too (the same message);
  3. the two are not the same name (`a merchant cannot be merged into itself`);
  4. the source has no alias yet (`this merchant is already merged into another`);
  5. the target has no alias of its own (`the merchant to merge into is itself merged into another`);
  6. no alias merges into the source (`other merchants are merged into this one`).

  It returns `(source, target)` normalized. Checks 4 to 6 keep every alias one step long.
- **R3.** `pick_rule_for` returns, among the rules that match **any** of the names by `rule_matches`, the one with the highest priority, the lowest id among equals, or None. `pick_rule` is unchanged.
- **R4.** `ACTIONS` ends with `"alias_added"`, `"alias_deleted"`, and `KINDS` with `"alias"`.
- **R5.** `add_alias` checks with `check_alias` against `alias_map(session)`, stores the pair, flushes, records `alias_added` (kind `alias`, the alias's id, `after` `ACME CAFE -> ACME COFFEE`), and returns it. `delete_alias` normalizes the source, refuses one with no alias (`alias not found`), deletes it, records `alias_deleted` with that text as `before`, and returns what it deleted. Neither runs the rules. All four functions are re-exported from `finances.db.repositories`.

### Where the merged name counts

- **R6.** `flows_for` gives each flow `merchant_name(description, aliases)`, with the aliases loaded once per call, so every report built on flows sees the merged name. `refund_facts` names a transaction's merchant the same way, so a refund under one name finds a purchase under the other.
- **R7.** `categorize` picks a transaction's rule with `pick_rule_for(merchant_names(description, aliases), rules)`, the aliases loaded once per run. `propose_rule`'s check 6 passes when the rule matches any of `merchant_names` of the example; its message is unchanged.

### The terminal

- **R8.** `fin aliases` as designed, with `alias_rows` giving the table's rows. Each command calls `require_current_schema()` first. `add` and `delete` change the alias in one session, then run `categorize_all()` and print its line. No business rule lives in `cli/aliases.py`.
- **R9.** Apply the given diff to the two earlier test files. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0016_merchant_aliases.py` (do not change)

```python
"""Create merchant_aliases: a cleaned merchant name merged into another."""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("target", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_merchant_aliases"),
        sa.UniqueConstraint("source", name="uq_merchant_aliases_source"),
    )


def downgrade() -> None:
    op.drop_table("merchant_aliases")
```

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_audit_rules.py b/tests/unit/test_audit_rules.py
index a05c140..4ef1b4d 100644
--- a/tests/unit/test_audit_rules.py
+++ b/tests/unit/test_audit_rules.py
@@ -30,6 +30,8 @@ def test_the_lists() -> None:
         "backup_restored",
         "proposal_accepted",
         "proposal_declined",
+        "alias_added",
+        "alias_deleted",
     )
     assert KINDS == (
         "account",
@@ -41,6 +43,7 @@ def test_the_lists() -> None:
         "statement",
         "backup",
         "proposal",
+        "alias",
     )
     assert AUDIT_TEXT_LIMIT == 200
 
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index fed3cfe..a1fc465 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -8,6 +8,12 @@ import finances.db.repositories as repositories
 
 PACKAGE = Path(repositories.__file__).parent
 HOMES = {
+    "aliases": [
+        "add_alias",
+        "alias_map",
+        "delete_alias",
+        "list_aliases",
+    ],
     "assignments": [
         "assign_by_rule",
         "clear_categories_by_hand",
@@ -143,7 +149,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 99
+    assert len(expected) == 103
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

10 tests in two files. Do not change them.

`tests/integration/test_migration_0016.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import MerchantAliasRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("source", "VARCHAR(100)", False),
    ("target", "VARCHAR(100)", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0016_follows_0015() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0016")
    assert script.down_revision == "0015"


def test_the_table_and_its_row_class(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0016")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [
        (c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("merchant_aliases")
    ]
    primary = found.get_pk_constraint("merchant_aliases")
    uniques = [
        (u["name"], u["column_names"]) for u in found.get_unique_constraints("merchant_aliases")
    ]
    extras = (found.get_foreign_keys("merchant_aliases"), found.get_indexes("merchant_aliases"))
    engine.dispose()
    assert shown == COLUMNS
    assert (primary["name"], primary["constrained_columns"]) == ("pk_merchant_aliases", ["id"])
    assert uniques == [("uq_merchant_aliases_source", ["source"])]
    assert extras == ([], [])
    orm = [(c.name, str(c.type), c.nullable) for c in MerchantAliasRow.__table__.columns]
    assert orm[: len(COLUMNS)] == COLUMNS
    command.downgrade(config, "0015")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "merchant_aliases" not in names
    command.upgrade(config, "0016")
```

`tests/e2e/test_cli_aliases.py`

```python
from datetime import date

import pytest

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule
from tests.support import failed_cleanly, run, table_rows


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """ACME CAFE (1) and ACME COFFEE (2) on a card; a rule puts ACME COFFEE in Dining, so 2
    is categorized and 1 is not."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-450, "ACME CAFE"), (-500, "ACME COFFEE")), start=1
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
        session.flush()
        create_rule(session, "ACME COFFEE", "Dining")
        categorize(session)
    engine.dispose()
    return tmp_settings


def test_merging_a_merchant(card: Settings) -> None:
    added = run("aliases", "add", "--from", "  acme   cafe ", "--to", "Acme Coffee")
    assert (added.exit_code, added.stdout) == (
        0,
        'Merged "ACME CAFE" into "ACME COFFEE".\n'
        "Categorized 2 transactions: 1 changed, 0 without a category.\n",
    )
    assert table_rows(run("aliases", "list").stdout) == [
        ["From", "To"],
        ["ACME CAFE", "ACME COFFEE"],
    ]


def test_removing_it(card: Settings) -> None:
    run("aliases", "add", "--from", "ACME CAFE", "--to", "ACME COFFEE")
    removed = run("aliases", "delete", "--from", "acme cafe")
    assert (removed.exit_code, removed.stdout) == (
        0,
        'Removed the alias for "ACME CAFE".\n'
        "Categorized 2 transactions: 1 changed, 1 without a category.\n",
    )
    assert run("aliases", "list").stdout == "No aliases.\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("add", "--from", " ", "--to", "BAZ CAFE"), "a merchant name must be 1 to 100 characters"),
        (
            ("add", "--from", "acme cafe", "--to", "Acme Cafe"),
            "a merchant cannot be merged into itself",
        ),
        (
            ("add", "--from", "acme cafe", "--to", "BAZ CAFE"),
            "this merchant is already merged into another",
        ),
        (
            ("add", "--from", "BAZ CAFE", "--to", "ACME CAFE"),
            "the merchant to merge into is itself merged into another",
        ),
        (
            ("add", "--from", "ACME COFFEE", "--to", "BAZ CAFE"),
            "other merchants are merged into this one",
        ),
        (("delete", "--from", "BAZ CAFE"), "alias not found"),
    ],
)
def test_refused(card: Settings, args: tuple[str, ...], message: str) -> None:
    run("aliases", "add", "--from", "ACME CAFE", "--to", "ACME COFFEE")
    assert failed_cleanly(run("aliases", *args), message)
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/unit/test_merchant_aliases.py`:

- `normalize_merchant`; `merchant_name` and `merchant_names` of `SQ *ACME CAFE 12345` with no aliases and with `{"ACME CAFE": "ACME COFFEE"}`;
- `check_alias`: the target-length refusal with a 101-character target; the normalized pair it returns;
- `pick_rule_for` with `contains "ACME CAFE"` at priority 0 (id 1) and `contains "ACME COFFEE"` at priority 5 (id 2) over `("ACME CAFE", "ACME COFFEE")` gives id 2; at equal priorities it gives id 1 whichever name matched it; no match gives None.

`tests/integration/test_merchant_aliases.py`:

- `add_alias`, `list_aliases` (two aliases added out of order come back by source), `alias_map`, `delete_alias`, and their two audit rows (`after` and `before` `ACME CAFE -> ACME COFFEE`); a refused alias stores nothing and records nothing;
- with a rule `contains "ACME CAFE" -> Dining` that set `ACME CAFE`, adding `ACME CAFE -> ACME COFFEE` and running `categorize` keeps it in Dining (a run on the merged name alone would take the category away);
- `load_flows` gives `ACME COFFEE` as the merchant of an `ACME CAFE` purchase once the alias exists, and `ACME CAFE` before;
- `refund_facts` of a refund `ACME COFFEE` (+$5.00, 2026-05-10) finds the purchase `ACME CAFE` (-$5.00, 2026-05-01) with the alias, and none without;
- `propose_rule` with example `ACME CAFE` and `equals "ACME COFFEE"` is stored with the alias and refused without it.

## Rules for this phase

- `domain` imports only from `finances.domain`; `cli/aliases.py` only parses options, calls the repository and `categorize_all`, and prints.
- Merchant names come from statements and the feed. No exception message or log line echoes a name: every message in R2 and R5 is a constant.
- Every name stored fits `MERCHANT_NAME_LIMIT`: a name a person typed that is too long is refused (R2), never cut.
- Keep each module under `src/finances/db/repositories/` under 400 lines (`tests/unit/test_repositories_split.py`).

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 10 tests; at least N + 10 passed in all;
- `git diff --stat HEAD -- tests` lists only the two files of the given diff;
- `git grep -n "clean_merchant(" -- src/finances/analysis/spending.py src/finances/analysis/refunds.py src/finances/categorize src/finances/db` and `git grep -n "pick_rule(" -- src/finances/categorize` print nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.merchants --cov=finances.domain.rules --cov=finances.domain.audit --cov=finances.db.repositories --cov=finances.analysis.spending --cov=finances.analysis.refunds --cov=finances.categorize.service --cov=finances.views.categories --cov=finances.cli.aliases --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 28a: merchant aliases (YYYY-MM-DD)`.
