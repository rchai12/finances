# Phase 36c: views that only format (sync, transfers, backups), and the CLI tables

## Goal

No behaviour change. This finishes what 36b started: after it, **no `views` module loads data**. The sync, transfers, and backups views take plain data from three new `analysis` modules; the Keychain check moves to `sync/links.py`, where the Keychain is already used; seven CLI commands that build their tables by hand use `print_rows`; and the two identical `_change` helpers become one `change_text`. A test then forbids any `views` import of the database, SQLAlchemy, the Keychain, or any of `sync` but the run-result type, and any `views` function that takes a session.

One item of the audit's list is settled by a rule instead of a move: `analysis` may call `categorize`'s read functions (`transfer_suggestions`), since the architecture puts both in one tier. `docs/architecture.md` says so from this phase.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-36b-views-that-only-format.md` (the same pattern, done for accounts, people, and categories)
- `src/finances/views/sync.py`, `views/transfers.py`, `views/backups.py`, `views/format.py`, `views/months.py`, `views/insights.py`; `src/finances/sync/links.py`; `src/finances/cli/common.py` (`print_rows`)
- the callers: `src/finances/cli/sync.py`, `cli/transfers.py`, `cli/backup.py`, `cli/accounts.py`, `cli/budgets.py`, `cli/health.py`, `cli/listing.py`, `cli/people.py`; `src/finances/web/routes/sync.py`, `routes/transfers.py`, `routes/transactions.py`, `routes/backups.py`

## Starting state

N is `3286` when Phase 36b is the last phase built.

`print_rows` builds exactly what those seven commands build by hand (a `Table` with one plain column per heading and one row per dataclass), so their output does not change. Three tables are built from other cells (`fin import` folder results, `fin doctor`, the SimpleFIN account list) and stay as they are.

## Scope

| Path | What changes |
|---|---|
| `src/finances/analysis/simplefin.py`, `analysis/transfers.py`, `analysis/backups.py` | new (R1 to R3) |
| `src/finances/sync/links.py` | `keychain_state` (R1) |
| `src/finances/views/sync.py`, `views/transfers.py`, `views/backups.py` | take data (R4 to R6) |
| `src/finances/views/format.py`, `views/months.py`, `views/insights.py` | `change_text` (R7) |
| the callers above | load, then format; `print_rows` (R8, R9) |
| `tests/integration/test_views.py`, `test_transfer_views.py`, `test_transfer_store.py` | the given diff (R11) |
| `tests/unit/test_views_only_format.py` | new: given |
| `docs/progress.md` | one new entry |

## Out of scope

- Any change to what a page or command shows, or to a template.
- The three tables built from other cells; `analysis.dashboard`'s use of `categorize` (allowed by the rule above).

## Dependencies

None new. No migration.

## Design

```python
# src/finances/sync/links.py
def keychain_state(link: str) -> str: ...  # moved from views/sync.py unchanged: "yes", "no", or "unknown"

# src/finances/analysis/simplefin.py
@dataclass(frozen=True)
class MappingStatus:
    link: str
    account: str
    feed_account: str
    keychain: str
    last_pull: FeedPull | None
    balanced: FeedPull | None      # the newest pull with a balance

@dataclass(frozen=True)
class SetupOffer: ...               # moved from views/sync.py unchanged

def mapping_status(session: Session, keychain: Callable[[str], str]) -> list[MappingStatus]: ...
def waiting_counts(session: Session, runs: list[LinkRun]) -> list[tuple[str, int]]: ...  # moved
def unmapped_accounts(session: Session) -> list[Account]: ...                            # moved
def setup_offers(session: Session) -> list[SetupOffer]: ...                              # moved

# src/finances/analysis/transfers.py
@dataclass(frozen=True)
class PairListing:
    pair: TransferPair
    out: Transaction
    into: Transaction
    from_account: str
    to_account: str

@dataclass(frozen=True)
class SuggestionListing:
    out: Transaction
    into: Transaction
    from_account: str
    to_account: str

def pair_listing(session: Session) -> list[PairListing]: ...
def pair_of(session: Session, transaction_id: int) -> PairListing | None: ...
def suggestion_listing(session: Session) -> list[SuggestionListing]: ...

# src/finances/analysis/backups.py
@dataclass(frozen=True)
class BackupFile:
    name: str
    taken: datetime     # db.backup.taken_at
    size: int           # bytes

def backup_file(path: Path) -> BackupFile: ...
def backup_files(paths: list[Path]) -> list[BackupFile]: ...

# src/finances/views/sync.py      (StatusRow, RunRow, failure_lines, run_rows, simplefin_messages unchanged)
def status_rows(statuses: list[MappingStatus]) -> list[StatusRow]: ...

# src/finances/views/transfers.py (TransferLine, SuggestionLine unchanged; transfer_of removed)
def transfer_line(item: PairListing) -> TransferLine: ...
def transfer_lines(listing: list[PairListing]) -> list[TransferLine]: ...
def suggestion_lines(listing: list[SuggestionListing]) -> list[SuggestionLine]: ...

# src/finances/views/backups.py
def taken_text(taken: datetime) -> str: ...
def backup_rows(files: list[BackupFile]) -> list[BackupRow]: ...

# src/finances/views/format.py
def change_text(cents: int) -> str: ...  # "+$1.00" when above zero, else format_cents
```

## Requirements

### Part 1: loading moves to `analysis` and `sync`

- **R1.** `keychain_state` moves to `sync/links.py` unchanged. `mapping_status` gives one item per `list_feed_accounts` mapping, in that order, calling `keychain(link)` once per link; the caller passes `keychain_state`. `waiting_counts`, `unmapped_accounts`, `setup_offers`, and `SetupOffer` move from `views/sync.py` unchanged.
- **R2.** `pair_listing` gives every pair in `list_transfer_pairs`' order with its two transactions and account names; `pair_of` the pair holding a transaction, or None; `suggestion_listing` the pairings of `transfer_suggestions` in its order.
- **R3.** `backup_file` reads a backup's name, `taken_at`, and size in bytes.

### Part 2: the views only format

- **R4.** `status_rows` formats each `MappingStatus` exactly as today (last pull through `last_pull_text`, the balance day and drift through the balanced pull).
- **R5.** `transfer_lines` formats and sorts as today (latest outflow date first, then highest pair id first); `transfer_line` formats one pair; `suggestion_lines` formats in the given order. The transaction page uses `pair_of` and `transfer_line`.
- **R6.** `backup_rows` and `taken_text` format `BackupFile`s and a `datetime` exactly as today.
- **R7.** `change_text` replaces the two `_change` helpers in `views/months.py` and `views/insights.py`.

### Part 3: the callers and the rule

- **R8.** Each caller loads with the `analysis` function and formats with the view, in the same reading session as today.
- **R9.** `fin accounts list`, `fin budgets list`, `fin health`, `fin transactions list`, `fin people list`, `fin sync run`, and `fin sync status` print their tables with `print_rows`; only `cli/common.py`, `cli/importing.py`, `cli/main.py`, and one table of `cli/sync.py` still build a `Table` by hand.
- **R10.** No `views` module imports `finances.db`, `sqlalchemy`, `keyring`, or any `finances.sync` module but `finances.sync.runner`; no `views` function takes a `Session`.
- **R11.** Apply the given diff to three earlier test files: they import the moved names from their new modules and load before formatting. No other earlier test changes.

## Given tests

8 tests in one file: the rules of R9 and R10 as checks on the source, the moved Keychain check, and each view given hand-built data.

`tests/unit/test_views_only_format.py`

```python
import ast
from datetime import UTC, date, datetime
from pathlib import Path

import finances.cli
import finances.views
from finances.analysis.backups import BackupFile
from finances.analysis.simplefin import MappingStatus
from finances.analysis.transfers import PairListing, SuggestionListing
from finances.domain.models import DataSource, FeedPull, Transaction, TransferPair
from finances.sync.links import keychain_state
from finances.views.backups import BackupRow, backup_rows, taken_text
from finances.views.format import change_text
from finances.views.sync import StatusRow, status_rows
from finances.views.transfers import SuggestionLine, TransferLine, suggestion_lines, transfer_lines

VIEWS = Path(finances.views.__file__).parent
CLI = Path(finances.cli.__file__).parent
CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def imported(path: Path) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
    return names


def test_no_view_loads_data() -> None:
    found = {
        path.name: name
        for path in VIEWS.glob("*.py")
        for name in imported(path)
        if name.startswith(("finances.db", "sqlalchemy", "keyring"))
        or (name.startswith("finances.sync") and name != "finances.sync.runner")
    }
    assert found == {}


def test_no_view_takes_a_session() -> None:
    takers = []
    for path in VIEWS.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef):
                for argument in node.args.args + node.args.kwonlyargs:
                    if argument.annotation is not None and "Session" in ast.unparse(
                        argument.annotation
                    ):
                        takers.append(f"{path.name}:{node.name}")
    assert takers == []


def test_one_change_text() -> None:
    assert (change_text(100), change_text(0), change_text(-250)) == ("+$1.00", "$0.00", "-$2.50")
    helpers = [
        path.name
        for path in VIEWS.glob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef) and node.name == "_change"
    ]
    assert helpers == []


def test_the_cli_tables_go_through_print_rows() -> None:
    hand_built = {
        path.name: path.read_text(encoding="utf-8").count("Table()")
        for path in CLI.glob("*.py")
        if "Table()" in path.read_text(encoding="utf-8")
    }
    assert hand_built == {"common.py": 1, "importing.py": 1, "main.py": 1, "sync.py": 1}


def test_the_keychain_state_lives_with_the_links(keychain) -> None:
    keychain.passwords[("finances-simplefin", "alex")] = "https://u:p@bridge.simplefin.org/x"
    assert (keychain_state("alex"), keychain_state("sam")) == ("yes", "no")


def test_status_rows_from_mappings() -> None:
    pulled = FeedPull(1, 1, 1, 0, 0, 0, -100, -100, date(2026, 5, 9), -250, CREATED)
    found = status_rows(
        [
            MappingStatus("alex", "Test Card", "ACT-1", "yes", pulled, pulled),
            MappingStatus("sam", "Test Checking", "ACT-2", "unknown", None, None),
        ]
    )
    assert found[0].balance_date == "2026-05-09" and found[0].drift == "-$2.50"
    assert found[1] == StatusRow("sam", "Test Checking", "ACT-2", "unknown", "never", "", "")


def transaction(id: int, account: int, day: int, cents: int) -> Transaction:
    return Transaction(
        id,
        account,
        None,
        date(2026, 5, day),
        None,
        cents,
        "TRANSFER",
        None,
        None,
        None,
        None,
        DataSource.STATEMENT,
        False,
        f"t{id:02d}".ljust(64, "0"),
        CREATED,
    )


def test_transfer_lines_sort_and_suggestions() -> None:
    early = PairListing(
        TransferPair(1, 1, 2, "confirmed"),
        transaction(1, 1, 2, -500),
        transaction(2, 2, 3, 500),
        "Test Checking",
        "Test Savings",
    )
    late = PairListing(
        TransferPair(2, 3, 4, "auto"),
        transaction(3, 1, 9, -2599),
        transaction(4, 3, 9, 2599),
        "Test Checking",
        "Test Card",
    )
    assert transfer_lines([early, late]) == [
        TransferLine("2", "2026-05-09", "Test Checking", "Test Card", "$25.99", "3", "4", "auto"),
        TransferLine(
            "1", "2026-05-02", "Test Checking", "Test Savings", "$5.00", "1", "2", "confirmed"
        ),
    ]
    waiting = SuggestionListing(
        transaction(5, 1, 5, -2000), transaction(6, 2, 6, 2000), "Test Checking", "Test Savings"
    )
    assert suggestion_lines([waiting]) == [
        SuggestionLine(
            "5", "2026-05-05", "Test Checking", "6", "2026-05-06", "Test Savings", "$20.00"
        )
    ]


def test_backup_rows_from_files() -> None:
    taken = datetime(2026, 5, 25, 2, 0, 0, tzinfo=UTC)
    assert taken_text(taken) == "2026-05-25 02:00:00"
    assert backup_rows([BackupFile("finances-20260525-020000.db", taken, 2048)]) == [
        BackupRow("finances-20260525-020000.db", "2026-05-25 02:00:00", "2 KB")
    ]
```

The diff to earlier tests (apply it exactly):

```text
diff --git a/tests/integration/test_transfer_store.py b/tests/integration/test_transfer_store.py
index 42461b5..d91bd89 100644
--- a/tests/integration/test_transfer_store.py
+++ b/tests/integration/test_transfer_store.py
@@ -7,6 +7,7 @@ from fastapi.testclient import TestClient
 from sqlalchemy import Engine, func, select
 from sqlalchemy.orm import Session
 
+from finances.analysis.transfers import pair_listing
 from finances.categorize.transfers import TransferResult, pair_transfers, transfer_suggestions
 from finances.config import Settings
 from finances.db.engine import get_engine, session_scope
@@ -262,7 +263,7 @@ def test_transfer_lines_latest_outflow_first_then_highest_pair(session: Session)
     create_transfer_pair(session, late_out, late_in, AUTO)
     create_transfer_pair(session, early_out, early_in, CONFIRMED)
     create_transfer_pair(session, same_out, same_in, AUTO)
-    lines = transfer_lines(session)
+    lines = transfer_lines(pair_listing(session))
     assert [line.pair for line in lines] == ["3", "1", "2"]
     first = lines[1]
     assert (first.date, first.from_account, first.to_account, first.amount, first.how) == (
diff --git a/tests/integration/test_transfer_views.py b/tests/integration/test_transfer_views.py
index a6b42a0..d5c7eaf 100644
--- a/tests/integration/test_transfer_views.py
+++ b/tests/integration/test_transfer_views.py
@@ -5,11 +5,12 @@ import pytest
 from sqlalchemy import Engine
 from sqlalchemy.orm import Session
 
+from finances.analysis.transfers import pair_listing, pair_of
 from finances.db.engine import session_scope
 from finances.db.orm import TransactionRow
 from finances.db.repositories import create_account, create_transfer_pair, find_transfer_pair
 from finances.domain.models import AUTO, CONFIRMED
-from finances.views.transfers import TransferLine, transfer_lines, transfer_of
+from finances.views.transfers import TransferLine, transfer_line, transfer_lines
 
 CHECKING, SAVINGS, CARD = 1, 2, 3
 
@@ -71,17 +72,22 @@ def test_a_transaction_in_no_pair(session: Session) -> None:
 # transfer_of
 
 
+def transfer_of(session: Session, transaction_id: int) -> TransferLine | None:
+    found = pair_of(session, transaction_id)
+    return None if found is None else transfer_line(found)
+
+
 @pytest.mark.parametrize("transaction_id", [3, 4])
 def test_both_sides_show_their_pairs_line(session: Session, transaction_id: int) -> None:
     line = transfer_of(session, transaction_id)
     assert line == TransferLine(
         "2", "2026-05-09", "Test Checking", "Test Card", "$500.00", "3", "4", "auto"
     )
-    assert line == transfer_lines(session)[0]
+    assert line == transfer_lines(pair_listing(session))[0]
 
 
 def test_the_in_side_of_the_other_pair(session: Session) -> None:
-    assert transfer_of(session, 2) == transfer_lines(session)[1]
+    assert transfer_of(session, 2) == transfer_lines(pair_listing(session))[1]
 
 
 @pytest.mark.parametrize("transaction_id", [5, 99])
diff --git a/tests/integration/test_views.py b/tests/integration/test_views.py
index 560af35..7b14f7b 100644
--- a/tests/integration/test_views.py
+++ b/tests/integration/test_views.py
@@ -8,6 +8,13 @@ import pytest
 from sqlalchemy import Engine
 
 from finances.analysis.listings import account_listing, people_listing
+from finances.analysis.simplefin import (
+    SetupOffer,
+    mapping_status,
+    setup_offers,
+    unmapped_accounts,
+    waiting_counts,
+)
 from finances.db.engine import session_scope
 from finances.db.orm import AccountRow as AccountTable
 from finances.db.repositories import (
@@ -23,6 +30,7 @@ from finances.db.repositories import (
 )
 from finances.domain.feed_setup import AccountGuess
 from finances.domain.models import AccountType, DataSource, FeedPull, Transaction
+from finances.sync.links import keychain_state
 from finances.sync.runner import AccountSync, LinkRun, SyncReport
 from finances.views.accounts import AccountRow, account_rows
 from finances.views.format import (
@@ -33,18 +41,7 @@ from finances.views.format import (
     mask_last4,
 )
 from finances.views.people import PersonRow, people_rows
-from finances.views.sync import (
-    RunRow,
-    SetupOffer,
-    StatusRow,
-    keychain_state,
-    run_rows,
-    setup_offers,
-    simplefin_messages,
-    status_rows,
-    unmapped_accounts,
-    waiting_counts,
-)
+from finances.views.sync import RunRow, StatusRow, run_rows, simplefin_messages, status_rows
 from finances.views.transactions import TransactionRow, transaction_row
 
 SERVICE = "finances-simplefin"
@@ -274,7 +271,7 @@ def test_status_rows(household: Engine, keychain) -> None:
             drift_cents=None,
         )
     with session_scope(household) as session:
-        rows = status_rows(session)
+        rows = status_rows(mapping_status(session, keychain_state))
     assert [astuple(row)[:4] for row in rows] == [
         ("alex", "Test Card", "ACT-1", "yes"),
         ("sam", "Test Checking", "ACT-2", "no"),
@@ -286,7 +283,7 @@ def test_status_rows(household: Engine, keychain) -> None:
 
 def test_no_status_rows_without_mappings(household: Engine) -> None:
     with session_scope(household) as session:
-        assert status_rows(session) == []
+        assert status_rows(mapping_status(session, keychain_state)) == []
 
 
 # Sync now and fin sync run
```

## Tests to write

`tests/integration/test_listings_more_36c.py`: `pair_of` for each side of a pair and for a transaction in none; `mapping_status` asks the Keychain once for two mappings under one link; `backup_files` on an empty list; `suggestion_listing` with nothing waiting.

## Rules for this phase

- No output changes: the architect ran the whole suite with this design on a scratch copy (every earlier test passed, with only the three diffs above).
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file: `tests/unit/test_views_only_format.py`, 8 tests; at least N + 8 passed in all;
- `git diff --stat HEAD -- tests` lists only the three files of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.simplefin --cov=finances.analysis.transfers --cov=finances.analysis.backups --cov=finances.views --cov=finances.sync.links --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the search `git grep -n --untracked -E "^ *(from|import) +(finances\.db|sqlalchemy|keyring|finances\.sync\.(links|simplefin|service|transport|keychain))" -- src/finances/views`: no output.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 36c: views that only format, and the CLI tables (YYYY-MM-DD)`.
