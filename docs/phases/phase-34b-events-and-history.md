# Phase 34b: the system's events, and the History page

## Goal

The audit trail of 34a gains the events that do not come from a person editing a record, and becomes visible on the web. After this phase:

- importing a statement records `statement_imported`, as the **system** (the rows come from the file);
- deleting a backup on the Backups page records `backup_deleted`, and restoring one (on the page or with `fin backup restore`) records `backup_restored` in the **restored** database, so it keeps its own history and gains one row. Both are a **person**'s acts (a button or a command), which corrects the roadmap's outline, which listed restores under `system`;
- a read-only **History** page (`/history`, in the menu) lists the trail newest first, filtered by action and from a day, each row linking to the page of the thing it changed.

A database that is not at the newest revision has no trail, so nothing is recorded there: a backup deleted before `fin db upgrade`, or a restored backup from an older version (the page already says to upgrade it).

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-34a-audit-trail.md`; `src/finances/domain/audit.py`, `src/finances/db/repositories/audit.py`, `src/finances/views/audit.py`
- `src/finances/db/repositories/statements.py` (`create_statement`), `src/finances/db/backup.py` (`delete_backup`, `restore_backup`), `src/finances/db/migrate.py` (`current_revision`, `head_revision`), `src/finances/web/routes/backups.py`, `src/finances/cli/backup.py`, `src/finances/web/app.py` (the router list), `src/finances/web/helpers.py` (`_day`)

## Starting state

N is `3323` when Phase 34a is the last phase built.

`db/backup.py` is a critical module; this phase does not change it. The web's delete route works on a database that is not migrated (it checks only the form), so recording must cope with one.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/audit.py` | three actions, two kinds (R1) |
| `src/finances/db/repositories/statements.py` | the import hook (R2) |
| `src/finances/db/backup_records.py` | new (R3) |
| `src/finances/web/routes/backups.py`, `src/finances/cli/backup.py` | call it (R4) |
| `src/finances/views/audit.py` | `change_link` (R5) |
| `src/finances/web/routes/history.py`, `src/finances/web/app.py` | the page (R6) |
| `src/finances/web/templates/history.html` | new: given |
| `src/finances/web/templates/layout.html` | the given diff (R7) |
| three earlier test files | the given diff (R8) |
| `tests/integration/test_audit_events.py`, `tests/integration/test_web_history.py` | new: given |
| `tests/integration/test_history_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Sync events, feed mappings, links; `agent` and proposals (Phase 19); a terminal `fin backup delete` (backlog).
- Editing, deleting, or exporting rows; paging past the newest 200 on the page (the filters narrow it).

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/audit.py: ACTIONS gains, at the end, "statement_imported", "backup_deleted",
# "backup_restored"; KINDS gains, at the end, "statement", "backup".

# src/finances/db/backup_records.py
def note_backup_deleted(url: str, name: str) -> bool: ...
def note_backup_restored(url: str, name: str) -> bool: ...

# src/finances/views/audit.py
def change_link(change: Change) -> str: ...

# src/finances/web/routes/history.py
HISTORY_LIMIT = 200
ACTION_REFUSED = "choose an action from the list"

@router.get("/history")
def history(request: Request) -> Response: ...
```

## Requirements

- **R1.** `ACTIONS` ends with `statement_imported`, `backup_deleted`, `backup_restored`; `KINDS` ends with `statement`, `backup`.
- **R2.** `create_statement` records `statement_imported` after its flush: who `system`, kind `statement`, the statement's id, after `"<parser_name>, <period_start> to <period_end>"` (ISO days). Never the file's name or contents.
- **R3.** `note_backup_deleted(url, name)` and `note_backup_restored(url, name)` return False and record nothing when `current_revision(url)` is not `head_revision()`; otherwise they open the database at `url`, record `backup_deleted` (before the name) or `backup_restored` (after the name), who `person`, kind `backup`, no record id, commit, dispose of the engine, and return True.
- **R4.** The web's delete route calls `note_backup_deleted` with the database URL and the deleted file's name after `delete_backup` succeeds; the web's restore route calls `note_backup_restored` inside the restore gate, right after `restore_backup`; `fin backup restore` calls it after the restore. A refused delete or restore records nothing.
- **R5.** `change_link` gives `/transactions/<id>` for a transaction, and otherwise the area's page: account `/accounts`, person `/people`, category and rule `/categories`, transfer `/transfers`, statement `/statements`, backup `/backups`.
- **R6.** `GET /history` stops with the not-migrated page as the others do. It reads `action` (empty, or one of `ACTIONS`, else status 400 with `ACTION_REFUSED`) and `since` (empty, or a day through `_day(text, "since")`, else 400 with its message), and shows `list_changes(..., limit=HISTORY_LIMIT)` with the given template: `rows` is a list of `(change_rows(...)[i], change_link(change))` pairs; `form` holds the two texts; `actions` is `ACTIONS`; `limit` is `HISTORY_LIMIT`. The router is a new area, registered after `backups` in `create_app`.
- **R7.** Apply the given diff to `layout.html`: **History** joins the menu after Backups (the Sync now button stays last).
- **R8.** Apply the given diff to three earlier test files: 34a's lists and unknown-action message gain the new values, and the web's route and area lists gain `/history`. No other earlier test changes.

## Given template and diffs

`src/finances/web/templates/history.html` (new; do not change)

```html
{% extends "layout.html" %}
{% block title %}History · Finances{% endblock %}
{% block content %}
<h1>History</h1>
{% include "messages.html" %}
<form method="get" action="/history" class="fields">
  <label>Action
    <select name="action">
      <option value=""{% if not form.action %} selected{% endif %}>Every action</option>
      {% for name in actions %}<option value="{{ name }}"{% if name == form.action %} selected{% endif %}>{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Since <input type="date" name="since" value="{{ form.since }}"></label>
  <button type="submit">Show</button>
</form>
<section class="card">
<h2>Changes</h2>
{% if rows %}
<table>
<thead><tr><th>When (UTC)</th><th>Who</th><th>Action</th><th>Record</th><th>Before</th><th>After</th></tr></thead>
<tbody>
{% for row, link in rows %}<tr><td>{{ row.when }}</td><td>{{ row.who }}</td><td>{{ row.action }}</td><td><a href="{{ link }}">{{ row.record }}</a></td><td>{{ row.before }}</td><td>{{ row.after }}</td></tr>
{% endfor %}</tbody>
</table>
{% if rows|length >= limit %}<p class="hint">Showing the {{ limit }} newest. Choose an action or a day to see others.</p>{% endif %}
{% else %}
<p class="empty">No changes recorded.</p>
{% endif %}
</section>
{% endblock %}
```

`layout.html`:

```text
diff --git a/src/finances/web/templates/layout.html b/src/finances/web/templates/layout.html
index 229a3a3..5833cce 100644
--- a/src/finances/web/templates/layout.html
+++ b/src/finances/web/templates/layout.html
@@ -23,6 +23,7 @@
   <a href="/ahead"{% if section == "ahead" %} aria-current="page"{% endif %}>Ahead</a>
   <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
   <a href="/backups"{% if section == "backups" %} aria-current="page"{% endif %}>Backups</a>
+  <a href="/history"{% if section == "history" %} aria-current="page"{% endif %}>History</a>
   <form method="post" action="/sync/run" class="nav-sync"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit">Sync now</button></form>
 </nav>
 <main>
```

Earlier tests:

```text
diff --git a/tests/e2e/test_cli_audit.py b/tests/e2e/test_cli_audit.py
index 912cabb..5219c98 100644
--- a/tests/e2e/test_cli_audit.py
+++ b/tests/e2e/test_cli_audit.py
@@ -59,7 +59,7 @@ UNKNOWN = (
     "eopened, owner_set, person_added, cardholder_set, category_added, category_renam"
     "ed, category_deleted, rule_added, rule_edited, rule_deleted, category_set, categ"
     "ory_cleared, budget_set, budget_removed, transfer_confirmed, transfer_rejected, "
-    "transfer_unpaired"
+    "transfer_unpaired, statement_imported, backup_deleted, backup_restored"
 )
 
 
diff --git a/tests/unit/test_audit_rules.py b/tests/unit/test_audit_rules.py
index 7fb871a..17e3b52 100644
--- a/tests/unit/test_audit_rules.py
+++ b/tests/unit/test_audit_rules.py
@@ -25,8 +25,20 @@ def test_the_lists() -> None:
         "transfer_confirmed",
         "transfer_rejected",
         "transfer_unpaired",
+        "statement_imported",
+        "backup_deleted",
+        "backup_restored",
+    )
+    assert KINDS == (
+        "account",
+        "person",
+        "category",
+        "rule",
+        "transaction",
+        "transfer",
+        "statement",
+        "backup",
     )
-    assert KINDS == ("account", "person", "category", "rule", "transaction", "transfer")
     assert AUDIT_TEXT_LIMIT == 200
 
 
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 60eee13..117b375 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -16,6 +16,7 @@ AREAS = [
     "backups",
     "budgets",
     "categories",
+    "history",
     "home",
     "people",
     "reports",
@@ -76,6 +77,7 @@ ROUTES = {
     ("POST", "/backups/delete"),
     ("GET", "/backups/restore"),
     ("POST", "/backups/restore"),
+    ("GET", "/history"),
 }
 
 
```

## Given tests

21 tests in two files. A backup older than the trail is built by upgrading a file to revision `0011` only.

`tests/integration/test_audit_events.py`

```python
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

import finances.db
from finances.config import Settings
from finances.db.backup import make_backup
from finances.db.backup_records import note_backup_deleted, note_backup_restored
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import create_account, create_person, create_statement, list_changes
from finances.web.app import create_app
from tests.support import WEB_PORT, post, run

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
FIRST = "finances-20261015-143005.db"
OLDER = "finances-20261014-020000.db"


def trail() -> list[tuple]:
    engine = get_engine()
    with session_scope(engine) as session:
        found = [
            (item.who, item.action, item.kind, item.record_id, item.before, item.after)
            for item in reversed(list_changes(session, limit=1000))
        ]
    engine.dispose()
    return found


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A card added, then a backup FIRST taken; the trail's clock reads NOON."""
    monkeypatch.setattr("finances.db.repositories.audit._now", lambda: NOON)
    monkeypatch.setattr(
        "finances.web.app._now", lambda: datetime(2026, 10, 17, 9, 0, 0, tzinfo=UTC)
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
    engine.dispose()
    make_backup(
        tmp_settings.effective_database_url,
        tmp_settings.effective_backup_dir,
        14,
        datetime(2026, 10, 15, 14, 30, 5, tzinfo=UTC),
    )
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    found.get("/backups")
    return found


def test_a_statement_import_is_recorded_as_the_system(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_statement(
            session,
            account_id=1,
            source_filename="card.pdf",
            file_sha256="a" * 64,
            parser_name="test",
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            opening_balance_cents=0,
            closing_balance_cents=0,
            lines_parsed=0,
            rows_inserted=0,
            rows_duplicate=0,
        )
    engine.dispose()
    assert trail()[-1] == (
        "system",
        "statement_imported",
        "statement",
        1,
        None,
        "test, 2026-04-01 to 2026-04-30",
    )


def test_deleting_a_backup_on_the_web(client: TestClient) -> None:
    response = post(client, "/backups/delete", name=FIRST)
    assert response.status_code == 303
    assert trail()[-1] == ("person", "backup_deleted", "backup", None, FIRST, None)


def test_a_restore_keeps_the_restored_history_and_adds_one_row(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_person(session, "Pat Example")
    engine.dispose()
    response = post(client, "/backups/restore", name=FIRST, confirm=FIRST)
    assert response.headers["location"] == "/backups?notice=restored"
    assert trail() == [
        ("person", "account_added", "account", 1, None, "Test Card"),
        ("person", "backup_restored", "backup", None, None, FIRST),
    ]


def test_restoring_a_backup_from_before_the_trail_records_nothing(
    client: TestClient, tmp_settings: Settings
) -> None:
    older = tmp_settings.effective_backup_dir / OLDER
    config = Config()
    config.set_main_option("script_location", str(Path(finances.db.__file__).parent / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{older.as_posix()}")
    command.upgrade(config, "0011")
    response = post(client, "/backups/restore", name=OLDER, confirm=OLDER)
    assert response.headers["location"] == "/backups?notice=restored-old"
    assert note_backup_restored(tmp_settings.effective_database_url, OLDER) is False


def test_restoring_in_the_terminal(client: TestClient, tmp_settings: Settings) -> None:
    result = run("backup", "restore", str(tmp_settings.effective_backup_dir / FIRST), "--yes")
    assert result.exit_code == 0
    assert trail()[-1] == ("person", "backup_restored", "backup", None, None, FIRST)


def test_nothing_is_noted_on_a_database_that_is_not_migrated(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"
    assert note_backup_deleted(url, FIRST) is False
    assert note_backup_restored(url, FIRST) is False
```

`tests/integration/test_web_history.py`

```python
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    create_rule,
    record_change,
    set_budget,
    set_category_by_hand,
)
from finances.domain.audit import Change
from finances.views.audit import change_link
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

HEADINGS = ["When (UTC)", "Who", "Action", "Record", "Before", "After"]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def changed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Five changes: a card on 24 May, then a person, a rule, a category set by hand, and a
    budget on 25 May."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        monkeypatch.setattr(
            "finances.db.repositories.audit._now", lambda: datetime(2026, 5, 24, 9, 0, tzinfo=UTC)
        )
        create_account(session, "Test Card", "Test Bank", "credit_card")
        monkeypatch.setattr(
            "finances.db.repositories.audit._now", lambda: datetime(2026, 5, 25, 14, 3, tzinfo=UTC)
        )
        create_person(session, "Pat Example")
        create_rule(session, "ACME", "Dining")
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 2),
                amount_cents=-500,
                description="ACME COFFEE",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.flush()
        set_category_by_hand(session, 1, "Groceries")
        set_budget(session, "Groceries", 15000)
    engine.dispose()
    return client


def test_the_history_newest_first_with_links(changed: TestClient) -> None:
    response = changed.get("/history")
    assert response.status_code == 200
    assert 'href="/history" aria-current="page">History</a>' in response.text
    found = Page(response.text)
    assert found.rows == [
        HEADINGS,
        ["2026-05-25 14:03", "person", "budget_set", "category 13", "", "$150.00"],
        ["2026-05-25 14:03", "person", "category_set", "transaction 1", "", "Groceries"],
        [
            "2026-05-25 14:03",
            "person",
            "rule_added",
            "rule 1",
            "",
            'contains "ACME" -> Dining (priority 0)',
        ],
        ["2026-05-25 14:03", "person", "person_added", "person 1", "", "Pat Example"],
        ["2026-05-24 09:00", "person", "account_added", "account 1", "", "Test Card"],
    ]
    links = [
        link
        for link in found.links
        if link in ("/categories", "/transactions/1", "/people", "/accounts")
    ]
    assert links[-5:] == ["/categories", "/transactions/1", "/categories", "/people", "/accounts"]


def test_one_action_and_one_day(changed: TestClient) -> None:
    assert page(changed, "/history?action=person_added").rows[1:] == [
        ["2026-05-25 14:03", "person", "person_added", "person 1", "", "Pat Example"]
    ]
    assert len(page(changed, "/history?since=2026-05-25").rows) == 5
    form = page(changed, "/history?action=budget_set&since=2026-05-25").find("/history")
    assert form["inputs"]["since"] == ("date", "2026-05-25")
    assert ("budget_set", True) in form["selects"]["action"]


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("action=nope", "choose an action from the list"),
        ("since=25-05-2026", "since must be a date as YYYY-MM-DD"),
    ],
)
def test_refused_filters(changed: TestClient, query: str, message: str) -> None:
    response = changed.get(f"/history?{query}")
    assert response.status_code == 400
    assert ("error", message) in Page(response.text).paragraphs


def test_nothing_yet(client: TestClient) -> None:
    upgrade_to_head()
    assert texts(page(client, "/history"), "empty") == ["No changes recorded."]


def test_only_the_newest_two_hundred(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        for number in range(201):
            record_change(
                session, action="person_added", kind="person", record_id=number, after="P"
            )
    engine.dispose()
    found = page(client, "/history")
    assert len(found.rows) == 201
    assert texts(found, "hint") == [
        "Showing the 200 newest. Choose an action or a day to see others."
    ]


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/history")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


@pytest.mark.parametrize(
    ("kind", "record_id", "link"),
    [
        ("account", 3, "/accounts"),
        ("person", 1, "/people"),
        ("category", 13, "/categories"),
        ("rule", 2, "/categories"),
        ("transaction", 7, "/transactions/7"),
        ("transfer", 1, "/transfers"),
        ("statement", 4, "/statements"),
        ("backup", None, "/backups"),
    ],
)
def test_each_kind_links_to_its_page(kind: str, record_id: int | None, link: str) -> None:
    change = Change(
        1, datetime(2026, 5, 25, tzinfo=UTC), "person", "x", kind, record_id, None, None
    )
    assert change_link(change) == link
```

## Tests to write

`tests/integration/test_history_more.py`: a real statement import through `fin import` records one `statement_imported`; a refused delete (unknown name) records nothing; `/history?action=` with `since` only; the History menu link is current only on its page.

## Rules for this phase

- `db/backup.py` (critical) does not change; recording happens after its functions return.
- Rows hold names and short values only: a backup's file name, a statement's parser and period.
- The route holds no rule beyond reading its two fields; nothing is logged.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_audit_events.py tests/integration/test_web_history.py`, 21 tests; at least N + 21 passed in all;
- `git diff --stat HEAD -- tests` lists only the three files of the given diff;
- `git diff --stat HEAD -- src/finances/db/backup.py`: nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.audit --cov=finances.db.backup_records --cov=finances.db.repositories --cov=finances.views.audit --cov=finances.web.routes.history --cov=finances.web.routes.backups --cov=finances.cli.backup --cov-branch --cov-report=term-missing --cov-fail-under=100` (it names the repositories **package**: naming one of its modules makes SQLAlchemy fail under coverage's import mode).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 34b: the system's events and the History page (YYYY-MM-DD)`.
