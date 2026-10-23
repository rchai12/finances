# Phase 19b: the review queue on the web

## Goal

What `fin review` does in the terminal (19a), a person can do in the browser. After this phase:

- a **Review** page (`/review`, in the menu after History) lists the agent's open proposals with the transaction, its category now, the proposal, the agent's reason, and whether it is out of date; a checkbox on each row and two buttons, **Accept chosen** and **Decline chosen**, decide every chosen proposal in one transaction (all or none), through the same repository functions as `fin review`;
- the same page shows the agent's latest notes (read-only);
- the Categories page's uncategorized table gains a **Suggested** column: the category the agent proposes for that transaction, linking to the Review page, when a proposal is open and not out of date.

Nothing new is stored; no migration. Transfer and rule proposals are 19c.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-19a-proposals-and-advice.md`; `src/finances/analysis/review.py`, `src/finances/views/review.py`, `src/finances/db/repositories/proposals.py`
- `src/finances/web/routes/categories.py`, `src/finances/web/routes/history.py` (a recent router), `src/finances/web/forms.py` (`refused`), `src/finances/web/render.py` (`NOTICES`, `_done`), `src/finances/web/app.py` (the router list)

## Starting state

N is `3397` when Phase 19a is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/analysis/review.py` | `open_suggestions` (R1) |
| `src/finances/views/review.py` | `AdviceRow`, `advice_rows` (R2) |
| `src/finances/web/routes/review.py`, `src/finances/web/app.py` | the page and its form (R3, R4) |
| `src/finances/web/render.py` | two notices (R4) |
| `src/finances/web/routes/categories.py` | `suggestions` (R5) |
| `src/finances/web/templates/review.html` | new: given |
| `src/finances/web/templates/categories.html`, `layout.html` | the given diff (R5, R6) |
| `tests/integration/test_web_categories.py`, `tests/unit/test_web_split.py` | the given diff (R7) |
| `tests/integration/test_web_review.py` | new: given |
| `tests/integration/test_web_review_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- A dashboard block or a count of open proposals in the menu; decided proposals on the page; editing notes.
- Transfer and rule proposals (19c); any change to the MCP tools or to `fin review`.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/analysis/review.py
def open_suggestions(session: Session) -> dict[int, str]: ...

# src/finances/views/review.py
@dataclass(frozen=True)
class AdviceRow:
    when: str       # "YYYY-MM-DD HH:MM" (UTC)
    subject: str
    text: str

def advice_rows(notes: list[Advice]) -> list[AdviceRow]: ...

# src/finances/web/routes/review.py
NONE_CHOSEN = "choose at least one proposal"

@router.get("/review")
def review(request: Request) -> Response: ...

@router.post("/review")
async def decide(request: Request) -> Response: ...

# src/finances/web/render.py, NOTICES
"proposals-accepted": "Proposals accepted, as your choice."
"proposals-declined": "Proposals declined. The agent will not propose them again."
```

## Requirements

- **R1.** `open_suggestions` maps each transaction with an **open** category proposal that is **not out of date** (`proposal_out_of_date`) to the proposed category.
- **R2.** `advice_rows` formats each note (`created_at` as `YYYY-MM-DD HH:MM`, the subject, the text).
- **R3.** `GET /review` stops with the not-migrated page as the others do, and renders the given `review.html` with `rows` (`review_rows(review_items(session))`), `notes` (`advice_rows(list_advice(session, limit=20))`), and `error`, in one reading session.
- **R4.** `POST /review` reads the form (`csrf`, `decision`, and every `id`), checks it with `refused` (bad token or origin: 403 as elsewhere), and refuses with status 400 and `NONE_CHOSEN` when `decision` is neither `accept` nor `decline`, no `id` was sent, or an `id` is not written with the digits 0 to 9 only. Otherwise it applies `accept_proposal` or `decline_proposal` to each id in order **in one session**; a `ValueError` re-renders the page with status 400 and its message, and nothing is decided (the session rolls back). On success it redirects (303) to `/review?notice=proposals-accepted` or `proposals-declined`.
- **R5.** The Categories page passes `suggestions`, `open_suggestions` keyed by the transaction id as text; the given template diff shows it in the new **Suggested** column of the uncategorized table, linked to `/review`.
- **R6.** Apply the given diff to `layout.html`: **Review** joins the menu after History. The router is a new area `review`, registered after `history` in `create_app`.
- **R7.** Apply the given diff to two earlier test files: the Categories test reads the uncategorized table with its sixth column, and the web's route and area lists gain `/review`. No other earlier test changes.

## Given template and diffs

`src/finances/web/templates/review.html` (new; do not change)

```html
{% extends "layout.html" %}
{% block title %}Review · Finances{% endblock %}
{% block content %}
<h1>Review</h1>
{% include "messages.html" %}
<section class="card">
<h2>The agent's proposals</h2>
{% if rows %}
<form method="post" action="/review" class="bulk">
<input type="hidden" name="csrf" value="{{ csrf }}">
<table>
<thead><tr><th>ID</th><th>Date</th><th>Account</th><th>Description</th><th class="amount">Amount</th><th>Now</th><th>Proposed</th><th>Reason</th><th>State</th></tr></thead>
<tbody>
{% for row in rows %}<tr><td><input type="checkbox" name="id" value="{{ row.id }}"> {{ row.id }}</td><td>{{ row.date }}</td><td>{{ row.account }}</td><td>{{ row.description }}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{{ row.now }}</td><td>{{ row.proposed }}</td><td>{{ row.reason }}</td><td>{{ row.state }}</td></tr>
{% endfor %}</tbody>
</table>
<p class="fields"><button type="submit" name="decision" value="accept">Accept chosen</button> <button type="submit" name="decision" value="decline">Decline chosen</button></p>
</form>
<p class="hint">Accepting sets the category as your choice. Declining changes nothing, and the agent will not propose the same again. An out of date proposal can only be declined.</p>
{% else %}
<p class="empty">No open proposals.</p>
{% endif %}
</section>
<section class="card">
<h2>The agent's notes</h2>
{% if notes %}
<table>
<thead><tr><th>When (UTC)</th><th>Subject</th><th>Note</th></tr></thead>
<tbody>
{% for row in notes %}<tr><td>{{ row.when }}</td><td>{{ row.subject }}</td><td>{{ row.text }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No notes yet.</p>
{% endif %}
</section>
{% endblock %}
```

`categories.html` and `layout.html`:

```text
diff --git a/src/finances/web/templates/categories.html b/src/finances/web/templates/categories.html
index 44634f6..48d99c7 100644
--- a/src/finances/web/templates/categories.html
+++ b/src/finances/web/templates/categories.html
@@ -7,9 +7,9 @@
 <h2>Uncategorized</h2>
 {% if uncategorized %}
 <table>
-<thead><tr><th>ID</th><th>Date</th><th>Account</th><th>Merchant</th><th class="amount">Amount</th></tr></thead>
+<thead><tr><th>ID</th><th>Date</th><th>Account</th><th>Merchant</th><th class="amount">Amount</th><th>Suggested</th></tr></thead>
 <tbody>
-{% for row in uncategorized %}<tr><td><a href="/transactions/{{ row.id }}">{{ row.id }}</a></td><td>{{ row.date }}</td><td>{{ row.account }}</td><td>{{ row.merchant }}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td></tr>
+{% for row in uncategorized %}<tr><td><a href="/transactions/{{ row.id }}">{{ row.id }}</a></td><td>{{ row.date }}</td><td>{{ row.account }}</td><td>{{ row.merchant }}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{% if row.id in suggestions %}<a href="/review">{{ suggestions[row.id] }}</a>{% endif %}</td></tr>
 {% endfor %}</tbody>
 </table>
 {% if card_note %}<p class="hint">{{ card_note }}</p>{% endif %}
diff --git a/src/finances/web/templates/layout.html b/src/finances/web/templates/layout.html
index 5833cce..595353f 100644
--- a/src/finances/web/templates/layout.html
+++ b/src/finances/web/templates/layout.html
@@ -24,6 +24,7 @@
   <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
   <a href="/backups"{% if section == "backups" %} aria-current="page"{% endif %}>Backups</a>
   <a href="/history"{% if section == "history" %} aria-current="page"{% endif %}>History</a>
+  <a href="/review"{% if section == "review" %} aria-current="page"{% endif %}>Review</a>
   <form method="post" action="/sync/run" class="nav-sync"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit">Sync now</button></form>
 </nav>
 <main>
```

Earlier tests:

```text
diff --git a/tests/integration/test_web_categories.py b/tests/integration/test_web_categories.py
index 61aa0c6..1be0baa 100644
--- a/tests/integration/test_web_categories.py
+++ b/tests/integration/test_web_categories.py
@@ -161,13 +161,13 @@ def page(client: TestClient, path: str) -> Page:
 
 
 def uncategorized_ids(client: TestClient) -> list[str]:
-    """The ids in the Uncategorized table, which is the page's first and has five columns."""
+    """The ids in the Uncategorized table, which is the page's first and has six columns."""
     rows = page(client, "/categories").rows
-    if rows[0] != ["ID", "Date", "Account", "Merchant", "Amount"]:
+    if rows[0] != ["ID", "Date", "Account", "Merchant", "Amount", "Suggested"]:
         return []
     ids = []
     for row in rows[1:]:
-        if len(row) != 5:
+        if len(row) != 6 or row[0] == "ID":
             break
         ids.append(row[0])
     return ids
@@ -193,8 +193,8 @@ def test_the_menu_has_categories(home: TestClient) -> None:
 def test_the_categories_page(home: TestClient) -> None:
     found = page(home, "/categories")
     assert found.rows[:2] == [
-        ["ID", "Date", "Account", "Merchant", "Amount"],
-        ["4", "2026-05-04", "Test Card", "PAYCHECK EXAMPLE CORP", "$3,000.00"],
+        ["ID", "Date", "Account", "Merchant", "Amount", "Suggested"],
+        ["4", "2026-05-04", "Test Card", "PAYCHECK EXAMPLE CORP", "$3,000.00", ""],
     ]
     assert [f"/transactions/{n}" for n in (4, 3, 2, 1)] == [
         link for link in found.links if link.startswith("/transactions/")
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 117b375..b142e1d 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -20,6 +20,7 @@ AREAS = [
     "home",
     "people",
     "reports",
+    "review",
     "statements",
     "sync",
     "transactions",
@@ -78,6 +79,8 @@ ROUTES = {
     ("GET", "/backups/restore"),
     ("POST", "/backups/restore"),
     ("GET", "/history"),
+    ("GET", "/review"),
+    ("POST", "/review"),
 }
 
 
```

## Given tests

12 tests in one file.

`tests/integration/test_web_review.py`

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
    list_category_assignments,
    list_proposals,
    log_advice,
    propose_category,
    set_category_by_hand,
)
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

HEADINGS = ["ID", "Date", "Account", "Description", "Amount", "Now", "Proposed", "Reason", "State"]
NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    return found


@pytest.fixture
def review(client: TestClient) -> TestClient:
    """Three proposals (one per transaction); the third's transaction was then set by hand, so
    it is out of date. One note."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, description in ((1, "ACME COFFEE"), (2, "BAZ CAFE"), (3, "FOOBAR GROCERY")):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=-500,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
        propose_category(session, 2, "Dining", "BAZ CAFE serves lunch")
        propose_category(session, 3, "Groceries", "FOOBAR is a grocer")
        set_category_by_hand(session, 3, "Dining")
        log_advice(session, "Suggested a coffee budget.", "budgets")
    engine.dispose()
    client.get("/review")
    return client


def decide(client: TestClient, decision: str, *ids: str):
    data = {"csrf": client.cookies["fin_csrf"], "decision": decision, "id": list(ids)}
    return client.post("/review", data=data, follow_redirects=False)


def state() -> dict[int, str]:
    engine = get_engine()
    with session_scope(engine) as session:
        found = {item.id: item.status for item in list_proposals(session)}
    engine.dispose()
    return found


def test_the_review_page(review: TestClient) -> None:
    response = review.get("/review")
    assert response.status_code == 200
    assert 'href="/review" aria-current="page">Review</a>' in response.text
    found = Page(response.text)
    assert found.rows == [
        HEADINGS,
        [
            "3",
            "2026-05-03",
            "Test Card",
            "FOOBAR GROCERY",
            "-$5.00",
            "Dining",
            "Groceries",
            "FOOBAR is a grocer",
            "out of date",
        ],
        [
            "2",
            "2026-05-02",
            "Test Card",
            "BAZ CAFE",
            "-$5.00",
            "",
            "Dining",
            "BAZ CAFE serves lunch",
            "open",
        ],
        [
            "1",
            "2026-05-01",
            "Test Card",
            "ACME COFFEE",
            "-$5.00",
            "",
            "Coffee & Dessert",
            "ACME is a coffee shop",
            "open",
        ],
        ["When (UTC)", "Subject", "Note"],
        ["2026-05-25 12:00", "budgets", "Suggested a coffee budget."],
    ]
    form = found.find("/review")
    assert form["method"] == "post"
    assert form["inputs"]["id"][0] == "checkbox"


def test_accepting_several(review: TestClient) -> None:
    response = decide(review, "accept", "1", "2")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/review?notice=proposals-accepted",
    )
    assert ("notice", "Proposals accepted, as your choice.") in page(
        review, response.headers["location"]
    ).paragraphs
    assert state() == {3: "open", 2: "accepted", 1: "accepted"}
    engine = get_engine()
    with session_scope(engine) as session:
        assert {key: value.source for key, value in list_category_assignments(session).items()} == {
            1: "manual",
            2: "manual",
            3: "manual",
        }
    engine.dispose()


def test_declining_an_out_of_date_one(review: TestClient) -> None:
    response = decide(review, "decline", "3")
    assert response.headers["location"] == "/review?notice=proposals-declined"
    assert ("notice", "Proposals declined. The agent will not propose them again.") in page(
        review, response.headers["location"]
    ).paragraphs
    assert state()[3] == "declined"


def test_all_or_none(review: TestClient) -> None:
    response = decide(review, "accept", "1", "3")
    assert response.status_code == 400
    assert ("error", "proposal 3 is out of date: the transaction was decided since") in Page(
        response.text
    ).paragraphs
    assert state() == {3: "open", 2: "open", 1: "open"}


@pytest.mark.parametrize(
    ("decision", "ids"),
    [("accept", ()), ("approve", ("1",)), ("accept", ("one",)), ("accept", ("١",))],
)
def test_nothing_chosen_or_a_bad_form(review: TestClient, decision: str, ids: tuple) -> None:
    response = decide(review, decision, *ids)
    assert response.status_code == 400
    assert ("error", "choose at least one proposal") in Page(response.text).paragraphs
    assert set(state().values()) == {"open"}


def test_the_form_token_is_checked(review: TestClient) -> None:
    response = review.post(
        "/review", data={"decision": "accept", "id": "1"}, follow_redirects=False
    )
    assert (response.status_code, response.text) == (403, "Bad form token")


def test_the_suggestions_beside_uncategorized_transactions(review: TestClient) -> None:
    found = page(review, "/categories")
    assert found.rows[:3] == [
        ["ID", "Date", "Account", "Merchant", "Amount", "Suggested"],
        ["2", "2026-05-02", "Test Card", "BAZ CAFE", "-$5.00", "Dining"],
        ["1", "2026-05-01", "Test Card", "ACME COFFEE", "-$5.00", "Coffee & Dessert"],
    ]
    assert found.links.count("/review") == 3


def test_nothing_yet(client: TestClient) -> None:
    upgrade_to_head()
    assert texts(page(client, "/review"), "empty") == ["No open proposals.", "No notes yet."]


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/review")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs
```

## Tests to write

`tests/integration/test_web_review_more.py`: `open_suggestions` leaves out an open proposal whose transaction was set by hand, or deleted; a proposal declined on the page cannot be proposed again through the repository; the Suggested column is empty for a transaction whose proposal was declined; the notes table shows at most 20, newest first; the Review link is current only on its page.

## Rules for this phase

- Deciding goes through `accept_proposal` and `decline_proposal` only; the route holds no rule of its own beyond reading its form.
- One session per decision, so a refusal leaves every chosen proposal as it was.
- The page is behind the same form token and origin checks as every other form.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file: `tests/integration/test_web_review.py`, 12 tests; at least N + 12 passed in all;
- `git diff --stat HEAD -- tests` lists only the two files of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.review --cov=finances.views.review --cov=finances.web.routes.review --cov=finances.web.routes.categories --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 19b: the review queue on the web (YYYY-MM-DD)`.
