# Phase 31: tidy

## Goal

A clean-up after the audit of 2026-10-16. One behaviour changes, on purpose:

- **One "today".** Every page and command that shows today, the current month, or days since something reads the machine's **local** date through `finances.clock.today()`. Until now the web used the UTC date and the terminal the local one, so near a month's end in the evening (US time) `/budgets` and `fin budgets list` could show different months.

Nothing else changes what the household sees, except that `fin backup list` gains the Size column the Backups page already has. The rest removes duplication left over from Phases 11c to 26a.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/architecture.md`, "Dependency direction" (the date rule)
- `src/finances/web/app.py` (`_today`, `_now`, the Sync routes), `src/finances/cli/reports.py`, `cli/budgets.py`, `cli/health.py`, `cli/listing.py`, `cli/categories.py`, `cli/transfers.py`, `cli/backup.py`, `cli/common.py`
- `src/finances/views/statements.py`, `src/finances/views/backups.py`, `src/finances/domain/budgets.py`

## Starting state

N is `2887` when Phase 26b is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/clock.py` | new: given |
| `src/finances/web/app.py` | `_today` (R1); the Sync routes keep the UTC date (R2); the budget message (R5) |
| `src/finances/cli/reports.py`, `cli/budgets.py`, `cli/health.py` | `clock.today()` (R1); `print_rows` (R4); the budget message (R5) |
| `src/finances/cli/common.py` | new: `print_rows` (R4) |
| `src/finances/cli/categories.py`, `cli/transfers.py` | `print_rows` (R4) |
| `src/finances/cli/listing.py` | `fin statements list` uses `statement_rows` (R3) |
| `src/finances/cli/backup.py` | `fin backup list` uses `backup_rows` (R6) |
| `src/finances/domain/budgets.py` | new: `AMOUNT_MESSAGE` (R5) |
| `src/finances/db/repositories.py` | the budget message (R5) |
| `tests/integration/test_one_today.py` | new: given |
| `tests/e2e/test_cli_backup.py` | `test_list_backups`: given change (below) |
| `docs/progress.md` | one new entry |

## Out of scope

- Splitting `web/app.py` (Phase 32).
- The UTC timestamps stored with feed pulls, imports, and backups' names, and the dates `sync/` works with: unchanged.
- Any other output change; any new feature.

## Dependencies

None new. No migration.

## Given module

`src/finances/clock.py`

```python
"""Today's date as the household reads it: the local date of this machine.

Every page and command that shows "today", the current month, or days since something reads
the date here. Callers use `clock.today()` (not `from finances.clock import today`), so a test
can replace `finances.clock.today`. Stored timestamps are UTC and do not come from here.
"""

from datetime import date


def today() -> date:
    return date.today()
```

## Requirements

- **R1.** Every place that took today's date from `date.today()` in `cli/` (`fin spending`, `fin months`, `fin recurring`, `fin insights`, `fin merchants`, `fin budgets list`, `fin health`) and the web's `_today()` read it from `clock.today()`, called through the module (`from finances import clock`, then `clock.today()`). The web's `_today()` stays, returning `clock.today()`, so tests that replace `finances.web.app._today` keep working.
- **R2.** The two web routes that call SimpleFIN (`GET /sync/accounts` and `POST /sync/run`) keep passing the **UTC** date, through a private `_utc_today()` that returns what `_today()` returned before; `cli/sync.py` is unchanged. `_now()` (UTC, for backup names) is unchanged.
- **R3.** `fin statements list` builds its rows with `views.statements.statement_rows`; its private `_statement_cells` goes. Its output does not change.
- **R4.** `cli/common.py` gains `print_rows(headings: Sequence[str], rows: Iterable[object]) -> None`, which prints a table of the dataclass rows (as the three private copies do now); `cli/categories.py`, `cli/transfers.py`, and `cli/reports.py` use it, and their `_print_rows` go. No output changes.
- **R5.** `domain/budgets.py` gains `AMOUNT_MESSAGE = "a budget must be an amount from $0.01 to $1,000,000.00"`; the repository, `fin budgets set`, and `POST /budgets/set` use it, and their own copies go.
- **R6.** `fin backup list` builds its rows with `views.backups.backup_rows` and prints the columns `File`, `Taken (UTC)`, `Size`; its private `_taken` goes.

## Given tests

`tests/integration/test_one_today.py` (8 tests). It replaces `finances.clock.today` with 25 May 2026 and expects every command and page to show that date's month.

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances import clock
from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from tests.support import WEB_PORT, page, run, texts

TODAY = date(2026, 5, 25)


@pytest.fixture
def migrated(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr("finances.clock.today", lambda: TODAY)
    upgrade_to_head()
    return tmp_settings


def test_today_is_the_local_date() -> None:
    assert clock.today() == date.today()


@pytest.mark.parametrize(
    ("args", "first_line"),
    [
        (("budgets", "list"), "Budgets for 2026-05."),
        (("spending",), "Spending from 2026-05-01 to 2026-05-31, by category."),
        (("months",), "Months from 2025-12 to 2026-05."),
        (("insights",), "Insights for 2026-05."),
        (("merchants",), "Merchants for 2026-05."),
    ],
)
def test_every_command_reads_one_today(migrated: Settings, args, first_line: str) -> None:
    assert run(*args).stdout.splitlines()[0] == first_line


def test_health_counts_days_from_the_same_today(migrated: Settings) -> None:
    folder = migrated.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / "finances-20260524-020000.db").write_bytes(b"")
    assert run("health").stdout == "No problems found.\n"


def test_every_page_reads_the_same_today(migrated: Settings) -> None:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    assert texts(page(client, "/"), "summary")[0] == "Today is 2026-05-25."
    assert texts(page(client, "/budgets"), "summary")[0] == "Budgets for 2026-05."
    assert "Spending from 2026-05-01 to 2026-05-31, by category." in texts(
        page(client, "/reports"), "summary"
    )
    assert texts(page(client, "/insights"), "summary")[0] == "Insights for 2026-05."
```

The change to `tests/e2e/test_cli_backup.py`, exactly this diff:

```diff
diff --git a/tests/e2e/test_cli_backup.py b/tests/e2e/test_cli_backup.py
index 34470b3..3a3dab3 100644
--- a/tests/e2e/test_cli_backup.py
+++ b/tests/e2e/test_cli_backup.py
@@ -78,9 +78,9 @@ def test_list_backups(money: Settings) -> None:
     for name in ("finances-20261015-143005.db", "finances-20261016-020000.db", "notes.txt"):
         (folder / name).write_bytes(b"")
     assert table_rows(run("backup", "list").stdout) == [
-        ["File", "Taken (UTC)"],
-        ["finances-20261016-020000.db", "2026-10-16 02:00:00"],
-        ["finances-20261015-143005.db", "2026-10-15 14:30:05"],
+        ["File", "Taken (UTC)", "Size"],
+        ["finances-20261016-020000.db", "2026-10-16 02:00:00", "0 B"],
+        ["finances-20261015-143005.db", "2026-10-15 14:30:05", "0 B"],
     ]
 
 
```

## Tests to write

None, unless coverage shows a branch the given and earlier tests do not reach; then add `tests/integration/test_tidy_more.py` and list it in your report.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_one_today.py`, 8 tests;
- every earlier test passes unchanged except `test_list_backups` (the diff above);
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.clock --cov=finances.cli --cov=finances.web --cov=finances.domain.budgets --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches, each with the output shown: `git grep -n -E "date\.today\(\)" -- src/finances` (only `src/finances/clock.py`), `git grep -n -E "def _print_rows|def _statement_cells|def _taken" -- src/finances/cli` (no output), `git grep -n "a budget must be an amount" -- src` (only `src/finances/domain/budgets.py`).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 31: tidy (YYYY-MM-DD)`.
