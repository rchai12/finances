# Phase 42: the agent's notes beside the findings

## Goal

The agent keeps notes with `log_advice`: advice it gave, or something to remember. Today they show only in a table on the Review page; `fin review` in the terminal never lists them, and nothing marks one as read. With the owner's choices (2026-10-25):

- `fin review list` shows the latest notes after the proposals, in a table of their own; with no notes it prints exactly what it prints today;
- the Insights page shows every note not yet dismissed in a **From the agent** block above the findings, newest first, whichever month is shown, marked as the agent's advice, not computed findings;
- a person dismisses a note on the Insights page, on the Review page, or with `fin review dismiss-note --id N`;
- a dismissed note leaves the Insights page and stays in the Review table and `fin review list`, its State `dismissed`; the agent sees `dismissed_at` through `list_advice`.

Dismissing is not recorded in History: a note is the agent's, not the household's data, and dismissing it changes nothing else.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/db/repositories/proposals.py` (`log_advice`, `list_advice`, `_now`), `src/finances/domain/proposals.py` (`Advice`), `src/finances/db/orm.py` (`AdviceRow`, `to_advice`), `src/finances/views/review.py` (`AdviceRow`, `advice_rows`), `src/finances/cli/review.py`, `src/finances/web/routes/review.py`, `src/finances/web/routes/reports.py` (`insights`), `src/finances/mcp_server/tools.py` (`log_advice`, `list_advice`), `src/finances/mcp_server/server.py`

## Starting state

N is `4136` when Phase 41c is the last phase built. **Sections: migrations, core, mcp, cli, web.** The newest migration is `0022`. `repositories/proposals.py` is at the 400 lines the split test allows, and an earlier test patches `proposals._now` to stamp notes, so `log_advice` and `list_advice` stay where they are and the new functions go in a new area module.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0023_advice_dismissed.py` | new: given (R1) |
| `src/finances/db/orm.py`, `src/finances/domain/proposals.py` | `dismissed_at` on `AdviceRow` and `Advice`; `to_advice` (R1) |
| `src/finances/db/repositories/advice.py` (new), `__init__.py` | `dismiss_advice`, `list_open_advice` (R2) |
| `src/finances/views/review.py` | `AdviceRow.id` and `.state` (R3) |
| `src/finances/cli/review.py` | the notes in `list`; `dismiss-note` (R4) |
| `src/finances/web/routes/review.py`, `src/finances/web/routes/reports.py`, `src/finances/web/render.py` | `POST /notes/dismiss`; `notes` on the Insights page; the notice (R5) |
| `src/finances/web/templates/review.html`, `insights.html` | the given diff (R5) |
| `src/finances/mcp_server/tools.py`, `server.py` | `"dismissed_at"` on each note; the description (R6) |
| five earlier test files | the given diff (R7) |
| `tests/integration/test_migration_0023.py`, `tests/e2e/test_cli_notes.py`, `tests/integration/test_web_notes.py` | new: given |
| `tests/integration/test_notes_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Undoing a dismissal; dismissing from MCP (the agent cannot dismiss its own notes); notes in `fin insights` or on the dashboard; a History record for a dismissal.

## Dependencies

None new.

## Design

```python
# src/finances/domain/proposals.py: Advice gains, last
    dismissed_at: datetime | None = None

# src/finances/db/repositories/advice.py
def dismiss_advice(session: Session, advice_id: int) -> Advice: ...
# Sets dismissed_at to its own _now(). The caller commits. Refused: ValueError("note not found");
# ValueError(f"note {advice_id} is already dismissed").
def list_open_advice(session: Session, *, limit: int = 50) -> list[Advice]: ...
# The notes not dismissed, newest first (created_at, then id, both descending), at most limit.

# src/finances/views/review.py
@dataclass(frozen=True)
class AdviceRow:
    id: str
    when: str
    subject: str
    text: str
    state: str      # "" for a note not dismissed, "dismissed" for one dismissed
```

`list_advice` is unchanged: every note, dismissed or not, at most `limit`.

| Front end | Behaviour |
|---|---|
| `fin review list` | prints the proposals table, or `No open proposals.`, as today; then, when `list_advice(session, limit=20)` holds any note, the line `Notes:` and a table with the headings `ID`, `When (UTC)`, `Subject`, `Note`, `State` (the `AdviceRow` fields, `when` as today) |
| `fin review dismiss-note --id N` | prints `Dismissed note N.`; a refusal prints its message through `fail` (exit 1); an unmigrated database gives the usual message |
| `POST /notes/dismiss` (`id`, `back`, `month`) | `id` must be a whole number (else the Review page, 400, `note not found`); a refusal of `dismiss_advice`: the Review page, 400, its message; done: 303 to `/insights?month=<month>&notice=note-dismissed` when `back` is `insights` and `month` is `YYYY-MM` (four digits, a dash, two digits), to `/insights?notice=note-dismissed` when `back` is `insights` otherwise, and to `/review?notice=note-dismissed` for any other `back`. The notice is `Note dismissed.` |
| The Insights page | `notes` is `advice_rows(list_open_advice(session))` on the page that shows a month; the given template shows the block only when there are any |
| MCP `log_advice`, `list_advice` | each note gains `"dismissed_at"`: its time in ISO form, or None |

The new description, exactly:

```python
LIST_ADVICE_DESCRIPTION = (
    "Your notes, newest first, at most limit (1 to 200, default 20), with when each was kept "
    "and when a person dismissed it (dismissed_at, or none)."
)
```

## Requirements

- **R1.** Apply the given migration exactly; `dismissed_at` on `AdviceRow` and `Advice`, mapped by `to_advice`.
- **R2.** `dismiss_advice` and `list_open_advice` as designed, exported from `finances.db.repositories`.
- **R3.** `AdviceRow` and `advice_rows` as designed.
- **R4.** `fin review list` and `fin review dismiss-note` as designed.
- **R5.** `POST /notes/dismiss`, the Insights page's `notes`, and the notice as designed; apply the given template diff exactly.
- **R6.** `"dismissed_at"` on each MCP note and the description as designed.
- **R7.** Apply the given diff to the five earlier test files. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0023_advice_dismissed.py` (do not change). It was run up, down, and up again on a database holding a note, which it keeps.

```python
"""Add advice_log.dismissed_at: when a person dismissed one of the agent's notes."""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("advice_log") as batch:
        batch.add_column(sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("advice_log") as batch:
        batch.drop_column("dismissed_at")
```

## Given template diff

Applied to `src/finances/web/templates/` (do not change). It was checked against every earlier test: all pass, apart from the two migration tests that compare the database with the ORM until `AdviceRow.dismissed_at` exists, and the two Review page tests in the diff below.

```text
diff --git a/src/finances/web/templates/insights.html b/src/finances/web/templates/insights.html
index 0b32706..825310c 100644
--- a/src/finances/web/templates/insights.html
+++ b/src/finances/web/templates/insights.html
@@ -9,6 +9,18 @@
 </form>
 {% if report %}
 <p class="summary">{{ report.heading }}</p>
+{% if notes %}
+<section class="card">
+<h2>From the agent</h2>
+<p class="hint">Notes the agent left, newest first, until you dismiss them. They are its advice, not findings the app computed.</p>
+<table>
+<thead><tr><th>When (UTC)</th><th>Subject</th><th>Note</th><th></th></tr></thead>
+<tbody>
+{% for row in notes %}<tr><td>{{ row.when }}</td><td>{{ row.subject }}</td><td>{{ row.text }}</td><td><form method="post" action="/notes/dismiss" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="id" value="{{ row.id }}"><input type="hidden" name="back" value="insights"><input type="hidden" name="month" value="{{ form.month }}"><button type="submit">Dismiss</button></form></td></tr>
+{% endfor %}</tbody>
+</table>
+</section>
+{% endif %}
 <section class="card">
 <h2>Findings</h2>
 {% if report.findings %}
diff --git a/src/finances/web/templates/review.html b/src/finances/web/templates/review.html
index a37e3e3..8efd17d 100644
--- a/src/finances/web/templates/review.html
+++ b/src/finances/web/templates/review.html
@@ -25,9 +25,9 @@
 <h2>The agent's notes</h2>
 {% if notes %}
 <table>
-<thead><tr><th>When (UTC)</th><th>Subject</th><th>Note</th></tr></thead>
+<thead><tr><th>When (UTC)</th><th>Subject</th><th>Note</th><th>State</th><th></th></tr></thead>
 <tbody>
-{% for row in notes %}<tr><td>{{ row.when }}</td><td>{{ row.subject }}</td><td>{{ row.text }}</td></tr>
+{% for row in notes %}<tr><td>{{ row.when }}</td><td>{{ row.subject }}</td><td>{{ row.text }}</td><td>{{ row.state }}</td><td>{% if not row.state %}<form method="post" action="/notes/dismiss" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="id" value="{{ row.id }}"><input type="hidden" name="back" value="review"><button type="submit">Dismiss</button></form>{% endif %}</td></tr>
 {% endfor %}</tbody>
 </table>
 {% else %}
```

## Given diff to earlier tests

The Review page's notes table gains its State and Dismiss columns, MCP's note gains `"dismissed_at"`, the route list gains `POST /notes/dismiss`, and the repositories gain the `advice` area.

```text
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index 273ad86..29d715e 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -142,6 +142,7 @@ def test_the_agents_notes(one: Settings) -> None:
         "created_at": "2026-05-25T12:00:00+00:00",
         "subject": "budgets",
         "text": "Suggested a coffee budget.",
+        "dismissed_at": None,
     }
     assert kept.structured_content == {"advice": note}
     assert call("list_advice").structured_content == {"advice": [note]}
diff --git a/tests/integration/test_web_review.py b/tests/integration/test_web_review.py
index 06d16cb..5564154 100644
--- a/tests/integration/test_web_review.py
+++ b/tests/integration/test_web_review.py
@@ -112,8 +112,8 @@ def test_the_review_page(review: TestClient) -> None:
             "ACME is a coffee shop",
             "open",
         ],
-        ["When (UTC)", "Subject", "Note"],
-        ["2026-05-25 12:00", "budgets", "Suggested a coffee budget."],
+        ["When (UTC)", "Subject", "Note", "State", ""],
+        ["2026-05-25 12:00", "budgets", "Suggested a coffee budget.", "", "Dismiss"],
     ]
     form = found.find("/review")
     assert form["method"] == "post"
diff --git a/tests/integration/test_web_review_more.py b/tests/integration/test_web_review_more.py
index 41b65e2..2febd07 100644
--- a/tests/integration/test_web_review_more.py
+++ b/tests/integration/test_web_review_more.py
@@ -116,9 +116,9 @@ def test_the_notes_table_shows_at_most_twenty_newest_first(
             log_advice(session, f"Probe note {index}.", f"n{index:02d}")
     engine.dispose()
     rows = page(client, "/review").rows
-    assert rows[0] == ["When (UTC)", "Subject", "Note"]
-    assert rows[1] == ["2026-05-25 12:20", "n20", "Probe note 20."]
-    assert rows[20] == ["2026-05-25 12:01", "n01", "Probe note 1."]
+    assert rows[0] == ["When (UTC)", "Subject", "Note", "State", ""]
+    assert rows[1] == ["2026-05-25 12:20", "n20", "Probe note 20.", "", "Dismiss"]
+    assert rows[20] == ["2026-05-25 12:01", "n01", "Probe note 1.", "", "Dismiss"]
     assert len(rows) == 21
 
 
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 11e9535..476a2c7 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -8,6 +8,10 @@ import finances.db.repositories as repositories
 
 PACKAGE = Path(repositories.__file__).parent
 HOMES = {
+    "advice": [
+        "dismiss_advice",
+        "list_open_advice",
+    ],
     "aliases": [
         "add_alias",
         "alias_map",
@@ -187,7 +191,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 131
+    assert len(expected) == 133
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 14860a5..8f75cc6 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -106,6 +106,7 @@ ROUTES = {
     ("POST", "/login"),
     ("POST", "/logout"),
     ("GET", "/review"),
+    ("POST", "/notes/dismiss"),
     ("POST", "/review"),
 }
 
```

## Given tests

16 tests in three files. Do not change them. Two (`test_with_no_notes_the_list_is_as_before`, `test_no_block_without_notes`) are guards that pass today and must still pass.

`tests/integration/test_migration_0023.py`

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import AdviceRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
ADDED = ("dismissed_at", "DATETIME", True)


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def columns(url: str) -> list[tuple]:
    engine = get_engine(url)
    found = [
        (c["name"], str(c["type"]), c["nullable"])
        for c in inspect(engine).get_columns("advice_log")
    ]
    engine.dispose()
    return found


def notes(url: str) -> list[str]:
    engine = get_engine(url)
    with engine.connect() as connection:
        found = list(connection.execute(text("SELECT text FROM advice_log ORDER BY id")).scalars())
    engine.dispose()
    return found


def test_0023_follows_0022() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0023")
    assert script.down_revision == "0022"


def test_the_column_comes_and_goes_and_the_notes_stay(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0022")
    engine = get_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO advice_log (created_at, subject, text)"
                " VALUES ('2026-05-25 12:00:00.000000', 'budgets', 'A coffee budget.')"
            )
        )
    engine.dispose()
    command.upgrade(config, "0023")
    found = columns(url)
    assert found[-1] == ADDED
    orm = [(c.name, str(c.type), c.nullable) for c in AdviceRow.__table__.columns]
    assert orm[: len(found)] == found
    assert notes(url) == ["A coffee budget."]
    command.downgrade(config, "0022")
    assert columns(url)[-1] == ("text", "VARCHAR(1000)", False)
    assert notes(url) == ["A coffee budget."]
    command.upgrade(config, "0023")
    assert columns(url)[-1] == ADDED
```

`tests/e2e/test_cli_notes.py`

```python
from datetime import UTC, datetime

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import log_advice
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, plain_lines, run, table_rows

HEADINGS = ["ID", "When (UTC)", "Subject", "Note", "State"]


@pytest.fixture
def notes(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Note 1 (budgets) at 12:00 and note 2 (no subject) at 12:05; no proposals."""
    stamps = iter([datetime(2026, 5, 25, 12, minute, tzinfo=UTC) for minute in (0, 5)])
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: next(stamps))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        log_advice(session, "Suggested a coffee budget.", "budgets")
        log_advice(session, "Watch ACME COFFEE.")
    engine.dispose()
    return tmp_settings


def test_the_list_shows_the_notes_after_the_proposals(notes: Settings) -> None:
    listed = run("review", "list")
    assert listed.exit_code == 0
    assert plain_lines(listed.stdout) == ["No open proposals.", "Notes:"]
    assert table_rows(listed.stdout) == [
        HEADINGS,
        ["2", "2026-05-25 12:05", "", "Watch ACME COFFEE.", ""],
        ["1", "2026-05-25 12:00", "budgets", "Suggested a coffee budget.", ""],
    ]


def test_with_no_notes_the_list_is_as_before(tmp_settings: Settings) -> None:
    upgrade_to_head()
    assert run("review", "list").stdout == "No open proposals.\n"


def test_dismissing_a_note(notes: Settings) -> None:
    dismissed = run("review", "dismiss-note", "--id", "1")
    assert (dismissed.exit_code, dismissed.stdout) == (0, "Dismissed note 1.\n")
    rows = table_rows(run("review", "list").stdout)
    assert [row[0] + " " + row[4] for row in rows[1:]] == ["2 ", "1 dismissed"]


@pytest.mark.parametrize(
    ("ids", "message"),
    [
        (["9"], "note not found"),
        (["1", "1"], "note 1 is already dismissed"),
    ],
)
def test_a_refused_dismissal(notes: Settings, ids: list[str], message: str) -> None:
    for proposal_id in ids[:-1]:
        run("review", "dismiss-note", "--id", proposal_id)
    assert failed_cleanly(run("review", "dismiss-note", "--id", ids[-1]), message)


def test_dismiss_note_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("review", "dismiss-note", "--id", "1")
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)
```

`tests/integration/test_web_notes.py`

```python
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import log_advice
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

FROM_THE_AGENT = ["When (UTC)", "Subject", "Note", ""]
NOTES = ["When (UTC)", "Subject", "Note", "State", ""]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Note 1 (budgets) at 12:00 and note 2 (no subject) at 12:05."""
    stamps = iter([datetime(2026, 5, 25, 12, minute, tzinfo=UTC) for minute in (0, 5)])
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: next(stamps))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        log_advice(session, "Suggested a coffee budget.", "budgets")
        log_advice(session, "Watch ACME COFFEE.")
    engine.dispose()
    client.get("/review")
    return client


def table(found: Page, heading: list[str]) -> list[list[str]]:
    """The rows of the table whose heading row is this one, without the heading."""
    rows = found.rows
    if heading not in rows:
        return []
    start = rows.index(heading) + 1
    end = next((i for i in range(start, len(rows)) if rows[i] and rows[i][0] == "When (UTC)"), None)
    found_rows = rows[start:end]
    return [row for row in found_rows if len(row) == len(heading)]


def test_the_insights_page_shows_the_notes(home: TestClient) -> None:
    found = page(home, "/insights?month=2026-05")
    assert table(found, FROM_THE_AGENT) == [
        ["2026-05-25 12:05", "", "Watch ACME COFFEE.", "Dismiss"],
        ["2026-05-25 12:00", "budgets", "Suggested a coffee budget.", "Dismiss"],
    ]
    form = found.all("/notes/dismiss")[0]
    assert form["inputs"]["back"] == ("hidden", "insights")
    assert form["inputs"]["month"] == ("hidden", "2026-05")


def test_dismissing_on_insights_returns_to_the_month(home: TestClient) -> None:
    response = post(home, "/notes/dismiss", id="1", back="insights", month="2026-05")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/insights?month=2026-05&notice=note-dismissed",
    )
    found = page(home, response.headers["location"])
    assert texts(found, "notice") == ["Note dismissed."]
    assert table(found, FROM_THE_AGENT) == [
        ["2026-05-25 12:05", "", "Watch ACME COFFEE.", "Dismiss"],
    ]
    assert table(page(home, "/review"), NOTES) == [
        ["2026-05-25 12:05", "", "Watch ACME COFFEE.", "", "Dismiss"],
        ["2026-05-25 12:00", "budgets", "Suggested a coffee budget.", "dismissed", ""],
    ]


def test_dismissing_on_review_returns_to_review(home: TestClient) -> None:
    response = post(home, "/notes/dismiss", id="2", back="review")
    assert response.headers["location"] == "/review?notice=note-dismissed"


def test_a_month_that_is_not_one_is_left_out(home: TestClient) -> None:
    response = post(home, "/notes/dismiss", id="2", back="insights", month="May")
    assert response.headers["location"] == "/insights?notice=note-dismissed"


@pytest.mark.parametrize("note", ["9", "x", ""])
def test_a_note_that_is_not_there(home: TestClient, note: str) -> None:
    response = post(home, "/notes/dismiss", id=note, back="review")
    assert (response.status_code, texts(Page(response.text), "error")) == (
        400,
        ["note not found"],
    )


def test_no_block_without_notes(client: TestClient) -> None:
    upgrade_to_head()
    assert "From the agent" not in client.get("/insights?month=2026-05").text
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_notes_more.py` (section core):

- `list_open_advice` leaves out a dismissed note, keeps newest first when two share a time (the higher id first), and honours `limit`;
- `dismiss_advice` stamps `dismissed_at` from `advice._now` (patched), and a refused one changes nothing;
- MCP `list_advice` after a dismissal gives that note's `dismissed_at` in ISO form and None for the others;
- `fin review list` with an open proposal and a note prints the proposals table, then `Notes:`, then the notes table;
- dismissing a note records nothing in History (`list_changes` is the same before and after);
- the Insights page for a month that is refused (`month=May`, 400) shows no block and does not fail.

## Rules for this phase

- The MCP server gains no tool and no way to dismiss.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first migrations,core,mcp,cli,web`;
- the given test files above, 16 tests; at least N + 16 passed in all;
- `git diff --stat HEAD -- tests` lists only the five files of the given diff;
- `git grep -n "dismiss" -- src/finances/mcp_server` lists only the description and the `dismissed_at` keys;
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/db/orm.py,*/finances/domain/proposals.py,*/finances/db/repositories/advice.py,*/finances/views/review.py,*/finances/cli/review.py,*/finances/web/routes/review.py,*/finances/web/routes/reports.py,*/finances/web/render.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 42: the agent's notes beside the findings (YYYY-MM-DD)`.
