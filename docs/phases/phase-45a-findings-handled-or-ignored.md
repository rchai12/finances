# Phase 45a: findings a person handled or ignored

## Goal

The first part of Phase 45. Findings are worked out afresh each time a month is shown, and nothing remembers what a person did about one. With the owner's choices (2026-10-27):

- a person marks a finding **handled**, which covers that month's finding only (the same thing next month is open again), or **ignored**, which covers its type and subject in **every** month;
- a finding with a status leaves the Findings table, the dashboard's top three, and the "could save" total, and shows below the Findings table under **Handled or ignored**, with a **Reopen** button; `fin insights` prints the same second table;
- setting and reopening are recorded in History.

Phase 45b lets the agent see the statuses and propose one. In this phase `get_insights` keeps its code and so lists only the open findings.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/domain/insights.py` (`Finding`, `TYPES`, `order_findings`), `src/finances/analysis/insights.py`, `src/finances/views/insights.py`, `src/finances/cli/reports.py` (`insights_command`, `_first_day`), `src/finances/web/routes/reports.py` (`insights`, `_month_start`), `src/finances/web/routes/review.py` (`dismiss_note`, the shape of a form route), `src/finances/web/render.py` (`NOTICES`), `src/finances/db/repositories/audit.py` (`record_change`), `src/finances/domain/audit.py`

## Starting state

N is `4218` when Phase 44b is the last phase built. **Sections: migrations, core, cli, web.** The newest migration is `0024`. A finding already has a `key` (`type:subject:YYYY-MM`) that nothing uses; this phase stores type, subject, and month in their own columns instead.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0025_finding_statuses.py` | new: given (R1) |
| `src/finances/db/orm.py` | `FindingStatusRow`, `to_finding_status` (R1) |
| `src/finances/domain/findings.py` (new) | the statuses, `FindingStatus`, `ClosedFinding`, `finding_text`, `status_of`, `split_findings` (R2) |
| `src/finances/domain/audit.py` | three actions and one kind (R3) |
| `src/finances/db/repositories/findings.py` (new), `__init__.py` | `set_finding_status`, `reopen_finding`, `list_finding_statuses` (R4) |
| `src/finances/analysis/insights.py` | `InsightsReport.closed`, `find_finding` (R5) |
| `src/finances/views/insights.py` | `ClosedRow`, `closed_rows` (R6) |
| `src/finances/cli/findings.py` (new), `cli/main.py`, `cli/reports.py` | `fin findings handle`, `ignore`, `reopen`; the second table in `fin insights` (R7) |
| `src/finances/web/routes/reports.py`, `src/finances/web/render.py` | `POST /findings/status`, `POST /findings/reopen`, the Insights page's new values, three notices (R8) |
| `src/finances/web/templates/insights.html` | the given diff (R8) |
| `tests/support.py` and five earlier test files | the given diff (R9) |
| `tests/integration/test_migration_0025.py`, `tests/unit/test_finding_rules.py`, `tests/e2e/test_cli_findings.py`, `tests/integration/test_web_findings.py` | new: given |
| `tests/integration/test_findings_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Anything for the agent: statuses in `get_insights`, `propose_finding_status` (45b). Buttons on the dashboard. Listing every status ever set (`fin findings list`). A status for a merchant stat or a recurring charge. Changing a status without reopening first.

## Dependencies

None new.

## Design

```python
# src/finances/domain/findings.py (imports only domain modules)
HANDLED = "handled"
IGNORED = "ignored"
FINDING_STATUSES = (HANDLED, IGNORED)

@dataclass(frozen=True)
class FindingStatus:
    id: int
    type: str
    subject: str
    month: date | None    # the month's first day for handled; None for ignored (every month)
    status: str
    set_at: datetime

@dataclass(frozen=True)
class ClosedFinding:
    finding: Finding
    status: str

def finding_text(type: str, subject: str, month: date | None) -> str: ...
def status_of(finding: Finding, statuses: Iterable[FindingStatus]) -> str | None: ...
def split_findings(
    findings: Iterable[Finding], statuses: Iterable[FindingStatus]
) -> tuple[list[Finding], list[ClosedFinding]]: ...

# src/finances/db/repositories/findings.py
def set_finding_status(session: Session, finding: Finding, status: str) -> FindingStatus: ...
def reopen_finding(session: Session, type: str, subject: str, month: date) -> list[FindingStatus]: ...
def list_finding_statuses(session: Session) -> list[FindingStatus]: ...

# src/finances/analysis/insights.py
@dataclass(frozen=True)
class InsightsReport:
    month: date
    findings: list[Finding]          # now the open ones only
    merchants: list[MerchantStat]
    closed: list[ClosedFinding] = field(default_factory=list)

def find_finding(session: Session, month: date, type: str, subject: str) -> Finding: ...

# src/finances/views/insights.py
@dataclass(frozen=True)
class ClosedRow:
    severity: str
    type: str
    about: str
    saves: str
    detail: str
    status: str

def closed_rows(report: InsightsReport) -> list[ClosedRow]: ...
```

**Matching.** Type is compared exactly and subject ignoring case (`casefold`) everywhere: in `status_of`, `find_finding`, and `reopen_finding`. `status_of` gives `ignored` when an ignored status has the finding's type and subject, else `handled` when a handled status also has the finding's month, else None. `split_findings` keeps the findings' order in both lists.

**Texts.** `finding_text` is `"<type> for <subject>"`, or `"<type>"` when the subject is empty, then `" in YYYY-MM"`, or `" in every month"` when month is None: `spike for Dining in 2026-05`, `interest in every month`.

**Checks**, all `ValueError`:

| Function | Check, in order | Refusal |
|---|---|---|
| `find_finding` | type in `insights.TYPES` | `type must be one of: spike, frequent_small, ...` (every type, `", "` between) |
| | a finding of the month, open or closed, with that type and subject (stripped) | `no such finding: <finding_text(type, subject, month)>` |
| `set_finding_status` | status in `FINDING_STATUSES` | `status must be one of: handled, ignored` |
| | `status_of` the finding is None | `this finding is already handled` or `ignored` |
| `reopen_finding` | type in `insights.TYPES` | the same type message |
| | an ignored status for the type and subject, or a handled one for them and the month | `this finding is open` |

**Stored.** `set_finding_status` adds a row: the finding's type and subject (cut with `fit` to 100), `month` the finding's month when handled or None when ignored, the status, and `set_at` from `_now()` of its own module (UTC). It records `finding_handled` or `finding_ignored` (kind `finding`, the row's id, after `finding_text` of the row) and returns the row. `reopen_finding` deletes the ignored rows for the type and subject and the handled rows for them and the month's first day, records `finding_reopened` for each (ignored first, then by id; the row's id, before its text), and returns them in that order. `list_finding_statuses` returns every row by id. None commits.

**The report.** `insights_report` splits the ordered findings with `list_finding_statuses`: `findings` the open ones, `closed` the rest. Everything that reads `findings` (the dashboard's top three, `findings_summary`, `get_insights`) then covers open findings only, with no change of its own.

| Front end | Behaviour |
|---|---|
| `fin findings handle`, `ignore` | options `--type` (required), `--about` (default `""`), `--month` (YYYY-MM, this month by default, as `fin insights`); unmigrated database first, then the month, then `find_finding`, then `set_finding_status`; prints `Marked handled: <text>.` or `Ignoring: <text>.`, the text of the stored row (so the finding's own spelling); a refusal goes through `fail` (exit 1) |
| `fin findings reopen` | the same options; `reopen_finding`; prints `Reopened: <finding_text(type, about stripped, month)>.` |
| `fin insights` | as today; then, when `closed` is not empty, the line `Handled or ignored:` and a table with headings `Severity`, `Type`, `About`, `Saves a month`, `Detail`, `Status` (after `No findings.` when no finding is open) |
| `POST /findings/status` (`type`, `about`, `month`, `status`) | the form check (`refused`); `_month_start(month)`, `find_finding`, `set_finding_status`; done: 303 to `/insights?month=<the finding's YYYY-MM>&notice=finding-handled` or `finding-ignored`; a refusal: the Insights page with `report` None, the form's month, and the message, 400 |
| `POST /findings/reopen` (`type`, `about`, `month`) | the same, with `reopen_finding`; done: `notice=finding-reopened` |
| The Insights page | `report` gains `month` (the month shown, `YYYY-MM`) and `closed` (`closed_rows`) |

The notices: `finding-handled` `Finding marked handled.`, `finding-ignored` `Finding ignored in every month.`, `finding-reopened` `Finding reopened.`

## Requirements

- **R1.** The given migration; `FindingStatusRow` (table `finding_statuses`, the columns of the migration in its order) and `to_finding_status` (`set_at` in UTC).
- **R2.** `domain/findings.py` as designed.
- **R3.** `ACTIONS` gains, last, `finding_handled`, `finding_ignored`, `finding_reopened`; `KINDS` gains, last, `finding`.
- **R4.** The three repository functions as designed, exported from `finances.db.repositories`.
- **R5.** `InsightsReport.closed` and `find_finding` as designed.
- **R6.** `ClosedRow` and `closed_rows`, formatted as `finding_rows` formats, with the status.
- **R7.** The commands and the `fin insights` table as designed.
- **R8.** The two routes, the page's values, and the notices as designed; the given template diff.
- **R9.** Apply the given diff to `tests/support.py` and the five earlier test files. No other earlier test changes.

## Given migration

```python
"""Create finding_statuses: findings a person handled (that month) or ignored (every month)."""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finding_statuses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("month", sa.Date(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_finding_statuses"),
    )


def downgrade() -> None:
    op.drop_table("finding_statuses")
```

## Given template diff

```text
diff --git a/src/finances/web/templates/insights.html b/src/finances/web/templates/insights.html
index 825310c..67f3592 100644
--- a/src/finances/web/templates/insights.html
+++ b/src/finances/web/templates/insights.html
@@ -25,15 +25,25 @@
 <h2>Findings</h2>
 {% if report.findings %}
 <table>
-<thead><tr><th>Severity</th><th>Type</th><th>About</th><th class="amount">Saves a month</th><th>Detail</th></tr></thead>
+<thead><tr><th>Severity</th><th>Type</th><th>About</th><th class="amount">Saves a month</th><th>Detail</th><th></th></tr></thead>
 <tbody>
-{% for row in report.findings %}<tr><td>{{ row.severity }}</td><td>{{ row.type }}</td><td>{% if row.type in ("spike", "subscription_overlap") %}<a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;category={{ row.about|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.about }}</a>{% elif row.type in ("frequent_small", "price_increase", "duplicate", "large_first_charge") %}<a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;merchant={{ row.about|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.about }}</a>{% else %}{{ row.about }}{% endif %}</td><td class="{{ row.saves|amount_class }}">{{ row.saves }}</td><td>{{ row.detail }}</td></tr>
+{% for row in report.findings %}<tr><td>{{ row.severity }}</td><td>{{ row.type }}</td><td>{% if row.type in ("spike", "subscription_overlap") %}<a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;category={{ row.about|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.about }}</a>{% elif row.type in ("frequent_small", "price_increase", "duplicate", "large_first_charge") %}<a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;merchant={{ row.about|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.about }}</a>{% else %}{{ row.about }}{% endif %}</td><td class="{{ row.saves|amount_class }}">{{ row.saves }}</td><td>{{ row.detail }}</td><td><form method="post" action="/findings/status" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="type" value="{{ row.type }}"><input type="hidden" name="about" value="{{ row.about }}"><input type="hidden" name="month" value="{{ report.month }}"><input type="hidden" name="status" value="handled"><button type="submit">Handled</button></form> <form method="post" action="/findings/status" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="type" value="{{ row.type }}"><input type="hidden" name="about" value="{{ row.about }}"><input type="hidden" name="month" value="{{ report.month }}"><input type="hidden" name="status" value="ignored"><button type="submit">Ignore</button></form></td></tr>
 {% endfor %}</tbody>
 </table>
 <p class="summary">{{ report.findings_summary }}</p>
 {% else %}
 <p class="empty">No findings.</p>
 {% endif %}
+{% if report.closed %}
+<h3>Handled or ignored</h3>
+<p class="hint">Handled covers that month only; ignored covers the same type and subject in every month.</p>
+<table>
+<thead><tr><th>Severity</th><th>Type</th><th>About</th><th class="amount">Saves a month</th><th>Detail</th><th>Status</th><th></th></tr></thead>
+<tbody>
+{% for row in report.closed %}<tr><td>{{ row.severity }}</td><td>{{ row.type }}</td><td>{{ row.about }}</td><td class="{{ row.saves|amount_class }}">{{ row.saves }}</td><td>{{ row.detail }}</td><td>{{ row.status }}</td><td><form method="post" action="/findings/reopen" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="type" value="{{ row.type }}"><input type="hidden" name="about" value="{{ row.about }}"><input type="hidden" name="month" value="{{ report.month }}"><button type="submit">Reopen</button></form></td></tr>
+{% endfor %}</tbody>
+</table>
+{% endif %}
 </section>
 <section class="card">
 <h2>Recurring charges</h2>
```

## Given diff to earlier tests

`tests/support.py` gains `add_findings_data`, the data of `test_cli_insights.py` plus one June interest charge, for the CLI and web tests. The Findings table's new button column, the new actions and kind, the new routes, and the new repository area. With the template diff applied, `test_web_insights.py` passes before any route changes.

```text
diff --git a/tests/e2e/test_cli_audit.py b/tests/e2e/test_cli_audit.py
index e002902..0c67d31 100644
--- a/tests/e2e/test_cli_audit.py
+++ b/tests/e2e/test_cli_audit.py
@@ -62,7 +62,7 @@ UNKNOWN = (
     "transfer_unpaired, statement_imported, backup_deleted, backup_restored, proposal"
     "_accepted, proposal_declined, alias_added, alias_deleted, tag_added, tag_removed, "
     "note_set, note_cleared, split_set, split_cleared, share_set, share_cleared, settlement_a"
-    "dded, settlement_deleted, category_tax_set"
+    "dded, settlement_deleted, category_tax_set, finding_handled, finding_ignored, finding_reopened"
 )
 
 
diff --git a/tests/integration/test_web_insights.py b/tests/integration/test_web_insights.py
index 6e90681..f679038 100644
--- a/tests/integration/test_web_insights.py
+++ b/tests/integration/test_web_insights.py
@@ -12,7 +12,8 @@ from finances.db.repositories import create_account, create_rule
 from finances.web.app import create_app
 from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts
 
-FINDINGS = ["Severity", "Type", "About", "Saves a month", "Detail"]
+FINDINGS = ["Severity", "Type", "About", "Saves a month", "Detail", ""]
+BUTTONS = "Handled Ignore"
 RECURRING = ["Merchant", "Every", "Amount", "Monthly", "Count", "Last", "Next"]
 MERCHANTS = ["Merchant", "Visits", "Spent", "Average", "Baseline", "Change", "Weekend"]
 
@@ -102,13 +103,14 @@ def test_a_month(home: TestClient) -> None:
     found = Page(response.text)
     assert table(found, FINDINGS) == [
         FINDINGS,
-        ["high", "interest", "", "$23.45", "Interest charged: $23.45."],
+        ["high", "interest", "", "$23.45", "Interest charged: $23.45.", BUTTONS],
         [
             "medium",
             "spike",
             "Dining",
             "$140.00",
             "Dining: $200.00 this month, against $60.00 a month before.",
+            BUTTONS,
         ],
         [
             "medium",
@@ -116,6 +118,7 @@ def test_a_month(home: TestClient) -> None:
             "QUUX STREAMING",
             "$2.00",
             "QUUX STREAMING went from $15.99 to $17.99.",
+            BUTTONS,
         ],
         [
             "low",
@@ -123,6 +126,7 @@ def test_a_month(home: TestClient) -> None:
             "ACME COFFEE",
             "$20.00",
             "ACME COFFEE: 8 visits averaging $5.00.",
+            BUTTONS,
         ],
         [
             "low",
@@ -131,6 +135,7 @@ def test_a_month(home: TestClient) -> None:
             "$8.25",
             "Subscriptions & Digital: QUUX STREAMING ($17.99), BAZ VIDEO ($9.99),"
             " QUUX CLOUD ($8.25).",
+            BUTTONS,
         ],
     ]
     assert table(found, RECURRING) == [
@@ -164,6 +169,7 @@ def test_a_yearly_plan_charged_before_the_window_still_overlaps(home: TestClient
             "Subscriptions & Digital",
             "$8.25",
             "Subscriptions & Digital: QUUX STREAMING ($15.99), QUUX CLOUD ($8.25).",
+            BUTTONS,
         ]
     ]
 
diff --git a/tests/support.py b/tests/support.py
index a0b78f4..640105d 100644
--- a/tests/support.py
+++ b/tests/support.py
@@ -4,12 +4,16 @@ New tests import these instead of copying them. Tests written before Phase 13c k
 copies.
 """
 
+from datetime import date
 from html.parser import HTMLParser
 
 from fastapi.testclient import TestClient
 from typer.testing import CliRunner
 
 from finances.cli.main import app
+from finances.db.engine import get_engine, session_scope
+from finances.db.orm import TransactionRow
+from finances.db.repositories import create_account
 
 CLI_NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
 WEB_NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"
@@ -149,6 +153,49 @@ def texts(found: Page, kind: str) -> list[str]:
     return [text for name, text in found.paragraphs if name == kind]
 
 
+def add_findings_data() -> None:
+    """February to June 2026 on one card, into a migrated database. May has five findings:
+    interest, a Dining spike, a QUUX STREAMING price rise, ACME COFFEE eight times, and two
+    video subscriptions; June has one: interest charged again."""
+    rows = [
+        (date(2026, 2, 3), -6000, "ACME DINER"),
+        (date(2026, 3, 17), -6000, "ACME DINER"),
+        (date(2026, 4, 9), -6000, "ACME DINER"),
+        (date(2026, 5, 22), -20000, "ACME DINER"),
+        (date(2026, 2, 5), -1599, "QUUX STREAMING"),
+        (date(2026, 3, 5), -1599, "QUUX STREAMING"),
+        (date(2026, 4, 5), -1599, "QUUX STREAMING"),
+        (date(2026, 5, 5), -1799, "QUUX STREAMING"),
+        (date(2026, 3, 12), -999, "BAZ VIDEO"),
+        (date(2026, 4, 12), -999, "BAZ VIDEO"),
+        (date(2026, 5, 12), -999, "BAZ VIDEO"),
+        (date(2026, 5, 28), -2345, "PURCHASE INTEREST CHARGE"),
+        (date(2026, 6, 28), -1000, "PURCHASE INTEREST CHARGE"),
+    ] + [(date(2026, 5, day), -500, "ACME COFFEE") for day in (2, 3, 6, 9, 10, 13, 16, 17)]
+    engine = get_engine()
+    with session_scope(engine) as session:
+        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
+        for number, (day, cents, description) in enumerate(rows, start=1):
+            session.add(
+                TransactionRow(
+                    account_id=card.id,
+                    posted_date=day,
+                    amount_cents=cents,
+                    description=description,
+                    source="statement",
+                    fingerprint=f"t{number:02d}".ljust(64, "0"),
+                )
+            )
+    engine.dispose()
+    for pattern, category in (
+        ("ACME DINER", "Dining"),
+        ("QUUX STREAMING", "Subscriptions & Digital"),
+        ("BAZ VIDEO", "Subscriptions & Digital"),
+        ("ACME COFFEE", "Coffee & Dessert"),
+    ):
+        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
+
+
 # Every MCP tool, and the ones that write (proposals and the advice log only).
 MCP_TOOLS = [
     "data_coverage",
diff --git a/tests/unit/test_audit_rules.py b/tests/unit/test_audit_rules.py
index 59e33e5..6eb79dd 100644
--- a/tests/unit/test_audit_rules.py
+++ b/tests/unit/test_audit_rules.py
@@ -43,6 +43,9 @@ def test_the_lists() -> None:
         "settlement_added",
         "settlement_deleted",
         "category_tax_set",
+        "finding_handled",
+        "finding_ignored",
+        "finding_reopened",
     )
     assert KINDS == (
         "account",
@@ -56,6 +59,7 @@ def test_the_lists() -> None:
         "proposal",
         "alias",
         "settlement",
+        "finding",
     )
     assert AUDIT_TEXT_LIMIT == 200
 
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index b4819a0..912d786 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -90,6 +90,11 @@ HOMES = {
         "record_sync_failure",
         "set_feed_account_ignored",
     ],
+    "findings": [
+        "list_finding_statuses",
+        "reopen_finding",
+        "set_finding_status",
+    ],
     "category_changes": [
         "propose_category_change",
     ],
@@ -197,7 +202,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 135
+    assert len(expected) == 138
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 8f75cc6..8adac2d 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -79,6 +79,8 @@ ROUTES = {
     ("GET", "/export/year"),
     ("GET", "/export/spending"),
     ("GET", "/insights"),
+    ("POST", "/findings/status"),
+    ("POST", "/findings/reopen"),
     ("GET", "/ahead"),
     ("GET", "/transfers"),
     ("POST", "/transfers/find"),
```

## Given tests

37 tests in four files. Do not change them.

`tests/integration/test_migration_0025.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import FindingStatusRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("type", "VARCHAR(30)", False),
    ("subject", "VARCHAR(100)", False),
    ("month", "DATE", True),
    ("status", "VARCHAR(10)", False),
    ("set_at", "DATETIME", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0025_follows_0024() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0025")
    assert script.down_revision == "0024"


def test_the_table_and_its_row_class(url: str) -> None:
    command.upgrade(make_config(url), "0025")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [
        (c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("finding_statuses")
    ]
    primary = found.get_pk_constraint("finding_statuses")
    others = (
        found.get_unique_constraints("finding_statuses"),
        found.get_foreign_keys("finding_statuses"),
    )
    engine.dispose()
    assert shown == COLUMNS
    assert (primary["name"], primary["constrained_columns"]) == ("pk_finding_statuses", ["id"])
    assert others == ([], [])
    orm = [(c.name, str(c.type), c.nullable) for c in FindingStatusRow.__table__.columns]
    assert orm == COLUMNS
    assert FindingStatusRow.__tablename__ == "finding_statuses"


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0025")
    command.downgrade(config, "0024")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "finding_statuses" not in names
    command.upgrade(config, "0025")
```

`tests/unit/test_finding_rules.py`

```python
from datetime import UTC, date, datetime

import pytest

from finances.domain.findings import (
    FINDING_STATUSES,
    HANDLED,
    IGNORED,
    ClosedFinding,
    FindingStatus,
    finding_text,
    split_findings,
    status_of,
)
from finances.domain.insights import Finding

MAY = date(2026, 5, 1)
JUNE = date(2026, 6, 1)
AT = datetime(2026, 6, 2, 9, 0, tzinfo=UTC)
SPIKE = Finding("spike", "medium", MAY, "Dining", 14000, "Dining: up.")
INTEREST = Finding("interest", "high", MAY, "", 2345, "Interest charged: $23.45.")
COFFEE = Finding("frequent_small", "low", MAY, "ACME COFFEE", 2000, "ACME COFFEE: 8 visits.")


def handled(type: str, subject: str, month: date, id: int = 1) -> FindingStatus:
    return FindingStatus(id, type, subject, month, HANDLED, AT)


def ignored(type: str, subject: str, id: int = 1) -> FindingStatus:
    return FindingStatus(id, type, subject, None, IGNORED, AT)


def test_the_statuses() -> None:
    assert (HANDLED, IGNORED, FINDING_STATUSES) == ("handled", "ignored", ("handled", "ignored"))


@pytest.mark.parametrize(
    ("type", "subject", "month", "text"),
    [
        ("spike", "Dining", MAY, "spike for Dining in 2026-05"),
        ("interest", "", JUNE, "interest in 2026-06"),
        ("spike", "Dining", None, "spike for Dining in every month"),
    ],
)
def test_the_text(type: str, subject: str, month: date | None, text: str) -> None:
    assert finding_text(type, subject, month) == text


@pytest.mark.parametrize(
    ("statuses", "found"),
    [
        ([], None),
        ([handled("spike", "Dining", MAY)], "handled"),
        ([handled("spike", "Dining", JUNE)], None),
        ([handled("spike", "Coffee & Dessert", MAY)], None),
        ([handled("price_increase", "Dining", MAY)], None),
        ([handled("spike", "dining", MAY)], "handled"),
        ([ignored("spike", "Dining")], "ignored"),
        ([handled("spike", "Dining", MAY, 1), ignored("spike", "Dining", 2)], "ignored"),
    ],
)
def test_the_status_of_a_finding(statuses: list[FindingStatus], found: str | None) -> None:
    assert status_of(SPIKE, statuses) == found


def test_an_empty_subject_matches_only_an_empty_one() -> None:
    assert status_of(INTEREST, [ignored("interest", "")]) == "ignored"
    assert status_of(INTEREST, [ignored("interest", "Dining")]) is None


def test_splitting_keeps_the_order() -> None:
    statuses = [handled("frequent_small", "ACME COFFEE", MAY, 1), ignored("interest", "", 2)]
    assert split_findings([INTEREST, SPIKE, COFFEE], statuses) == (
        [SPIKE],
        [ClosedFinding(INTEREST, "ignored"), ClosedFinding(COFFEE, "handled")],
    )
    assert split_findings([SPIKE], []) == ([SPIKE], [])
```

`tests/e2e/test_cli_findings.py`

```python
import pytest

from finances.config import Settings
from tests.support import (
    CLI_NOT_MIGRATED,
    add_findings_data,
    failed_cleanly,
    plain_lines,
    run,
    table_rows,
)

MAY = ("--month", "2026-05")
JUNE = ("--month", "2026-06")
OPEN = ["Severity", "Type", "About", "Saves a month", "Detail"]
CLOSED = ["Severity", "Type", "About", "Saves a month", "Detail", "Status"]
INTEREST = ["high", "interest", "", "$23.45", "Interest charged: $23.45."]
SPIKE = [
    "medium",
    "spike",
    "Dining",
    "$140.00",
    "Dining: $200.00 this month, against $60.00 a month before.",
]
PRICE = [
    "medium",
    "price_increase",
    "QUUX STREAMING",
    "$2.00",
    "QUUX STREAMING went from $15.99 to $17.99.",
]
COFFEE = [
    "low",
    "frequent_small",
    "ACME COFFEE",
    "$20.00",
    "ACME COFFEE: 8 visits averaging $5.00.",
]
OVERLAP = [
    "low",
    "subscription_overlap",
    "Subscriptions & Digital",
    "$9.99",
    "Subscriptions & Digital: QUUX STREAMING ($17.99), BAZ VIDEO ($9.99).",
]
JUNE_INTEREST = ["high", "interest", "", "$10.00", "Interest charged: $10.00."]
TYPES = (
    "type must be one of: spike, frequent_small, subscription_overlap, price_increase, interest, "
    "fees, over_budget, duplicate, large_first_charge"
)


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    add_findings_data()
    return tmp_settings


def test_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("findings", "handle", "--type", "interest", *MAY)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_handling_a_finding_moves_it_below(money: Settings) -> None:
    result = run("findings", "handle", "--type", "spike", "--about", "dining", *MAY)
    assert (result.exit_code, result.stdout) == (
        0,
        "Marked handled: spike for Dining in 2026-05.\n",
    )
    shown = run("insights", *MAY).stdout
    assert table_rows(shown) == [
        OPEN,
        INTEREST,
        PRICE,
        COFFEE,
        OVERLAP,
        CLOSED,
        [*SPIKE, "handled"],
    ]
    assert plain_lines(shown) == [
        "Insights for 2026-05.",
        "Findings: 4. Could save up to $55.44 a month.",
        "Handled or ignored:",
    ]


def test_handled_holds_for_that_month_only(money: Settings) -> None:
    assert run("findings", "handle", "--type", "interest", *MAY).exit_code == 0
    shown = run("insights", *JUNE).stdout
    assert table_rows(shown) == [OPEN, JUNE_INTEREST]
    assert "Handled or ignored:" not in plain_lines(shown)


def test_ignored_holds_for_every_month(money: Settings) -> None:
    result = run("findings", "ignore", "--type", "interest", *MAY)
    assert (result.exit_code, result.stdout) == (0, "Ignoring: interest in every month.\n")
    shown = run("insights", *JUNE).stdout
    assert table_rows(shown) == [CLOSED, [*JUNE_INTEREST, "ignored"]]
    assert plain_lines(shown) == ["Insights for 2026-06.", "No findings.", "Handled or ignored:"]


def test_reopening_a_finding(money: Settings) -> None:
    run("findings", "ignore", "--type", "interest", *MAY)
    result = run("findings", "reopen", "--type", "interest", *JUNE)
    assert (result.exit_code, result.stdout) == (0, "Reopened: interest in 2026-06.\n")
    assert table_rows(run("insights", *MAY).stdout)[:2] == [OPEN, INTEREST]
    assert "Handled or ignored:" not in plain_lines(run("insights", *MAY).stdout)


def test_reopening_clears_the_month_and_every_month(money: Settings) -> None:
    run("findings", "handle", "--type", "spike", "--about", "Dining", *MAY)
    run("findings", "reopen", "--type", "spike", "--about", "Dining", *MAY)
    run("findings", "ignore", "--type", "spike", "--about", "Dining", *MAY)
    assert run("findings", "reopen", "--type", "spike", "--about", "DINING", *MAY).exit_code == 0
    assert "Handled or ignored:" not in plain_lines(run("insights", *MAY).stdout)


def test_history_records_each_change(money: Settings) -> None:
    run("findings", "handle", "--type", "spike", "--about", "Dining", *MAY)
    run("findings", "ignore", "--type", "interest", *MAY)
    run("findings", "reopen", "--type", "interest", *MAY)
    rows = table_rows(run("audit").stdout)
    assert [row[1:] for row in rows[1:4]] == [
        ["person", "finding_reopened", "finding 2", "interest in every month", ""],
        ["person", "finding_ignored", "finding 2", "", "interest in every month"],
        ["person", "finding_handled", "finding 1", "", "spike for Dining in 2026-05"],
    ]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("handle", "--type", "nope", *MAY), TYPES),
        (
            ("handle", "--type", "spike", "--about", "Groceries", *MAY),
            "no such finding: spike for Groceries in 2026-05",
        ),
        (
            ("ignore", "--type", "interest", "--month", "2026-04"),
            "no such finding: interest in 2026-04",
        ),
        (
            ("handle", "--type", "interest", "--month", "2026-13"),
            "month must be a year and month, like 2026-05",
        ),
        (("reopen", "--type", "interest", *MAY), "this finding is open"),
    ],
)
def test_a_refusal(money: Settings, args: tuple, message: str) -> None:
    assert failed_cleanly(run("findings", *args), message)


@pytest.mark.parametrize(
    ("first", "then", "message"),
    [
        ("handle", "handle", "this finding is already handled"),
        ("ignore", "handle", "this finding is already ignored"),
    ],
)
def test_a_finding_with_a_status_is_refused(
    money: Settings, first: str, then: str, message: str
) -> None:
    assert run("findings", first, "--type", "interest", *MAY).exit_code == 0
    assert failed_cleanly(run("findings", then, "--type", "interest", *MAY), message)
```

`tests/integration/test_web_findings.py`

```python
import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, add_findings_data, page, post, texts

CLOSED = ["Severity", "Type", "About", "Saves a month", "Detail", "Status", ""]
SPIKE = [
    "medium",
    "spike",
    "Dining",
    "$140.00",
    "Dining: $200.00 this month, against $60.00 a month before.",
]
JUNE_INTEREST = ["high", "interest", "", "$10.00", "Interest charged: $10.00."]


@pytest.fixture
def home(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    add_findings_data()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/insights")
    return client


def closed(found: Page) -> list[list[str]]:
    """The rows of the Handled or ignored table, without its heading."""
    if CLOSED not in found.rows:
        return []
    rows = found.rows[found.rows.index(CLOSED) + 1 :]
    end = next((i for i, row in enumerate(rows) if row[-1:] != ["Reopen"]), len(rows))
    return rows[:end]


def fields(form: dict) -> dict:
    return {name: value for name, (_, value) in form["inputs"].items() if name != "csrf"}


def test_two_buttons_beside_each_open_finding(home: TestClient) -> None:
    found = page(home, "/insights?month=2026-05")
    forms = found.all("/findings/status")
    assert len(forms) == 10
    assert [fields(form) for form in forms[:4]] == [
        {"type": "interest", "about": "", "month": "2026-05", "status": "handled"},
        {"type": "interest", "about": "", "month": "2026-05", "status": "ignored"},
        {"type": "spike", "about": "Dining", "month": "2026-05", "status": "handled"},
        {"type": "spike", "about": "Dining", "month": "2026-05", "status": "ignored"},
    ]
    assert forms[0]["inputs"]["csrf"] == ("hidden", home.cookies["fin_csrf"])
    assert (closed(found), found.all("/findings/reopen")) == ([], [])


def test_handling_a_finding_on_the_page(home: TestClient) -> None:
    response = post(
        home, "/findings/status", type="spike", about="Dining", month="2026-05", status="handled"
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/insights?month=2026-05&notice=finding-handled",
    )
    found = page(home, response.headers["location"])
    assert texts(found, "notice") == ["Finding marked handled."]
    assert closed(found) == [[*SPIKE, "handled", "Reopen"]]
    assert "Findings: 4. Could save up to $55.44 a month." in texts(found, "summary")
    assert [fields(form) for form in found.all("/findings/reopen")] == [
        {"type": "spike", "about": "Dining", "month": "2026-05"}
    ]
    assert len(found.all("/findings/status")) == 8


def test_ignoring_a_finding_holds_in_every_month(home: TestClient) -> None:
    response = post(
        home, "/findings/status", type="interest", about="", month="2026-05", status="ignored"
    )
    assert response.headers["location"] == "/insights?month=2026-05&notice=finding-ignored"
    assert texts(page(home, response.headers["location"]), "notice") == [
        "Finding ignored in every month."
    ]
    june = page(home, "/insights?month=2026-06")
    assert closed(june) == [[*JUNE_INTEREST, "ignored", "Reopen"]]
    assert "No findings." in texts(june, "empty")


def test_reopening_a_finding_on_the_page(home: TestClient) -> None:
    post(home, "/findings/status", type="interest", about="", month="2026-05", status="ignored")
    response = post(home, "/findings/reopen", type="interest", about="", month="2026-06")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/insights?month=2026-06&notice=finding-reopened",
    )
    found = page(home, response.headers["location"])
    assert texts(found, "notice") == ["Finding reopened."]
    assert closed(found) == []


@pytest.mark.parametrize(
    ("path", "form", "message"),
    [
        (
            "/findings/status",
            {"type": "spike", "about": "Groceries", "month": "2026-05", "status": "handled"},
            "no such finding: spike for Groceries in 2026-05",
        ),
        (
            "/findings/status",
            {"type": "spike", "about": "Dining", "month": "2026-05", "status": "done"},
            "status must be one of: handled, ignored",
        ),
        (
            "/findings/reopen",
            {"type": "interest", "about": "", "month": "2026-05"},
            "this finding is open",
        ),
    ],
)
def test_a_refusal_shows_the_page_with_its_message(
    home: TestClient, path: str, form: dict, message: str
) -> None:
    response = post(home, path, **form)
    assert (response.status_code, texts(Page(response.text), "error")) == (400, [message])
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_findings_more.py` (section core, or web for the page cases):

- `set_finding_status` stores month None for an ignored finding and the finding's month for a handled one, and refuses `status: done`;
- `reopen_finding` with June leaves a handled status of May in place;
- `list_finding_statuses` is ordered by id;
- a subject longer than 100 characters is cut to 100 when stored;
- the dashboard's top findings and its summary leave out a handled finding (`add_findings_data`, interest handled in May: the top three start with the spike);
- `get_insights` for May, with the spike handled, lists four findings;
- `POST /findings/status` with an empty month uses this month (the web clock patched, as the dashboard tests patch it);
- History through the web: who is `person`.

## Rules for this phase

- Earlier tests stay unchanged except the given diff.
- `domain/findings.py` imports nothing from the project outside `finances.domain`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first migrations,core,cli,web`;
- the given test files above, 37 tests; at least N + 37 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/support.py` and the five files of the given diff;
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/domain/findings.py,*/finances/domain/audit.py,*/finances/db/orm.py,*/finances/db/repositories/findings.py,*/finances/analysis/insights.py,*/finances/views/insights.py,*/finances/cli/findings.py,*/finances/cli/reports.py,*/finances/cli/main.py,*/finances/web/routes/reports.py,*/finances/web/render.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 45a: findings a person handled or ignored (YYYY-MM-DD)`.
