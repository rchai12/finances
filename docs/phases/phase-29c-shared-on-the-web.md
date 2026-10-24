# Phase 29c: shared expenses on the web

## Goal

29a and 29b reach the browser, which finishes Phase 29. After this phase:

- a Shared page (in the menu, after People) shows who owes whom, the shared transactions, and the settlements, each with a Delete button, and a form to record a settlement (today unless another date is chosen);
- a transaction's page has a Shared card: the share and a Stop sharing button when it is shared, otherwise a form to share it (who owes, who paid, their share, half when left blank).

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-29a-shared-expenses-stored.md`, `docs/phases/phase-29b-shared-in-the-terminal.md`
- `src/finances/db/repositories/shared.py`, `src/finances/analysis/shared.py`, `src/finances/views/shared.py`
- `src/finances/web/routes/budgets.py` (a page with money forms and `web_app._today()`), `src/finances/web/routes/transactions.py` (`_transaction_page`, `_known_transaction`, `_missing_transaction`), `src/finances/web/helpers.py` (`_day`, `_id`), `src/finances/web/render.py` (`NOTICES`), `src/finances/web/app.py` (how routers are included)

## Starting state

N is `3736` when Phase 29b is the last phase built. The newest migration is `0020`; this phase adds none. `web/routes/transactions.py` is 355 lines, so the two share routes go in the new `shared` router and `transactions.py` gains only the page's context. The given templates were checked against every earlier integration and end-to-end test with the new context values filled in: all 2082 pass unchanged.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/templates/shared.html` (new), `transactions_one.html`, `layout.html` | the given diff (R1, R5, R9) |
| `src/finances/web/routes/shared.py` (new), `src/finances/web/app.py` | the `shared` router: five routes (R2 to R4, R6, R7) |
| `src/finances/web/routes/transactions.py` | the transaction page's new context and its `share_form` parameter (R5) |
| `src/finances/web/render.py` | four notices (R8) |
| `src/finances/db/repositories/shared.py`, `src/finances/db/repositories/__init__.py` | `share_of` (R5) |
| `tests/unit/test_web_split.py`, `tests/unit/test_repositories_split.py` | the given diff (R10) |
| `tests/integration/test_web_shared.py` | new: given |
| `tests/integration/test_web_shared_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Shares on the Transactions page or any other table; an MCP tool for shares; a filter on the Shared page.
- Editing a settlement or a share in place (delete or stop sharing, then add again).
- Any change to 29a's rules or 29b's commands.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/db/repositories/shared.py
def share_of(session: Session, transaction_id: int) -> Share | None: ...
```

The `shared` router (`src/finances/web/routes/shared.py`, included in `create_app` as the other areas are). Every POST starts with `refused(request, csrf)`:

| Route | Fields | Calls | On success | On a `ValueError` |
|---|---|---|---|---|
| `GET /shared` | none | the page | 200 | |
| `POST /shared/settle` | `csrf`, `payer`, `payee`, `amount`, `day` | `parse_money(amount)`, then `_day(day, "date")` (today when blank), then `record_settlement` | 303 to `/shared?notice=settled` | the Shared page, 400, the error, `settle_form` the typed values |
| `POST /shared/settlements/delete` | `csrf`, `settlement` | `_id(settlement)` (None is `settlement not found`), `delete_settlement` | 303 to `/shared?notice=settlement-deleted` | the Shared page, 400, the error |
| `POST /transactions/{transaction_id}/share` | `csrf`, `debtor`, `payer`, `share` | `_known_transaction` (else `_missing_transaction`, 404); `parse_money(share)` when not blank; `share_transaction(session, id, debtor, payer=payer, size_cents=...)` | 303 to `/transactions/{id}?notice=share-saved` | `_transaction_page(..., error, 400, share_form=the typed values)` |
| `POST /transactions/{transaction_id}/share/clear` | `csrf` | `_known_transaction`; `unshare_transaction` | 303 to `/transactions/{id}?notice=share-removed` | `_transaction_page(..., error, 400)` |

Context:

| Page | Name | Value |
|---|---|---|
| Shared | `owed` | `owed_text` of each line of `owed_report` |
| Shared | `shares` | `share_rows(list_shares(session))` |
| Shared | `settlements` | `settlement_rows(list_settlements(session))` |
| Shared | `people` | every person's name, by `list_people` |
| Shared | `settle_form` | `{"payer", "payee", "amount", "day"}`: empty, with `day` today (`web_app._today()`, ISO), unless a refusal keeps the typed values |
| a transaction's | `share` | `share_text(share_of(...))`, or None |
| a transaction's | `people` | every person's name, by `list_people` |
| a transaction's | `share_form` | `{"debtor", "payer", "share"}`, all `""` unless a refusal keeps the typed values |

## Requirements

### The Shared page

- **R1.** Apply the given template diff exactly (`shared.html` new; the Shared card in `transactions_one.html`; the Shared link in `layout.html`). `GET /shared` checks the schema as the other pages do and renders `shared` with the context above.
- **R2.** `POST /shared/settle` as designed: the money is read before the date, a blank date is today through `web_app._today()` (looked up when the request runs, so a test can replace it), and every refusal of `parse_money`, `_day`, and `record_settlement` reaches the page.
- **R3.** `POST /shared/settlements/delete` as designed.
- **R4.** GET on each of the four new POST paths answers 405.

### A transaction's page

- **R5.** `_transaction_page` gains `share_form: dict[str, str] | None = None` and supplies `share`, `people`, and `share_form` on every render, the 400 renders included. `share_of` returns the transaction's share or None, and is re-exported from `finances.db.repositories`.
- **R6.** `POST /transactions/{transaction_id}/share` as designed: a blank `payer` lets 29a find who paid, a blank `share` is half.
- **R7.** `POST /transactions/{transaction_id}/share/clear` as designed.
- **R8.** `NOTICES` gains `"settled": "Settlement recorded."`, `"settlement-deleted": "Settlement deleted."`, `"share-saved": "Share saved."`, `"share-removed": "Share removed."`.
- **R9.** The menu's Shared link marks itself `aria-current="page"` on the Shared page (the given `layout.html`, with the page's section `shared`).
- **R10.** Apply the given diff to the two earlier test files. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/templates/` (do not change).

```text
diff --git a/src/finances/web/templates/layout.html b/src/finances/web/templates/layout.html
index 595353f..a858d07 100644
--- a/src/finances/web/templates/layout.html
+++ b/src/finances/web/templates/layout.html
@@ -13,6 +13,7 @@
   <a href="/"{% if section == "dashboard" %} aria-current="page"{% endif %}>Home</a>
   <a href="/accounts"{% if section == "accounts" %} aria-current="page"{% endif %}>Accounts</a>
   <a href="/people"{% if section == "people" %} aria-current="page"{% endif %}>People</a>
+  <a href="/shared"{% if section == "shared" %} aria-current="page"{% endif %}>Shared</a>
   <a href="/transactions"{% if section == "transactions" %} aria-current="page"{% endif %}>Transactions</a>
   <a href="/statements"{% if section == "statements" %} aria-current="page"{% endif %}>Statements</a>
   <a href="/categories"{% if section == "categories" %} aria-current="page"{% endif %}>Categories</a>
diff --git a/src/finances/web/templates/shared.html b/src/finances/web/templates/shared.html
new file mode 100644
index 0000000..f5cbdfb
--- /dev/null
+++ b/src/finances/web/templates/shared.html
@@ -0,0 +1,59 @@
+{% extends "layout.html" %}
+{% block title %}Shared · Finances{% endblock %}
+{% block content %}
+<h1>Shared</h1>
+{% include "messages.html" %}
+<section class="card">
+<h2>Who owes whom</h2>
+{% for line in owed %}<p class="owed">{{ line }}</p>
+{% else %}<p class="owed">Nobody owes anybody.</p>
+{% endfor %}
+</section>
+<section class="card">
+<h2>Shared transactions</h2>
+{% if shares %}
+<table>
+<thead><tr><th>ID</th><th>Paid by</th><th>Owes</th><th class="amount">Owed</th></tr></thead>
+<tbody>
+{% for row in shares %}<tr><td><a href="/transactions/{{ row.id }}">{{ row.id }}</a></td><td>{{ row.paid_by }}</td><td>{{ row.owes }}</td><td class="{{ row.owed|amount_class }}">{{ row.owed }}</td></tr>
+{% endfor %}</tbody>
+</table>
+{% else %}
+<p class="empty">No shared transactions. Share one from its page.</p>
+{% endif %}
+</section>
+<section class="card">
+<h2>Settlements</h2>
+{% if settlements %}
+<table>
+<thead><tr><th>ID</th><th>Date</th><th>From</th><th>To</th><th class="amount">Amount</th><th></th></tr></thead>
+<tbody>
+{% for row in settlements %}<tr><td>{{ row.id }}</td><td>{{ row.date }}</td><td>{{ row.payer }}</td><td>{{ row.payee }}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td><form method="post" action="/shared/settlements/delete" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="settlement" value="{{ row.id }}"><button type="submit">Delete</button></form></td></tr>
+{% endfor %}</tbody>
+</table>
+{% else %}
+<p class="empty">No settlements.</p>
+{% endif %}
+</section>
+<section class="card">
+<h2>Record a settlement</h2>
+<form method="post" action="/shared/settle" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <label>From
+    <select name="payer">
+      {% for name in people %}<option value="{{ name }}"{% if name == settle_form.payer %} selected{% endif %}>{{ name }}</option>
+      {% endfor %}
+    </select>
+  </label>
+  <label>To
+    <select name="payee">
+      {% for name in people %}<option value="{{ name }}"{% if name == settle_form.payee %} selected{% endif %}>{{ name }}</option>
+      {% endfor %}
+    </select>
+  </label>
+  <label>Amount <input name="amount" required inputmode="decimal" value="{{ settle_form.amount }}"></label>
+  <label>Date <input type="date" name="day" value="{{ settle_form.day }}"></label>
+  <button type="submit">Record</button>
+</form>
+</section>
+{% endblock %}
diff --git a/src/finances/web/templates/transactions_one.html b/src/finances/web/templates/transactions_one.html
index 242ed8a..40be83c 100644
--- a/src/finances/web/templates/transactions_one.html
+++ b/src/finances/web/templates/transactions_one.html
@@ -83,6 +83,34 @@
 {% endif %}
 </section>
 <section class="card">
+<h2>Shared</h2>
+{% if share %}<p class="share">{{ share }}</p>
+<form method="post" action="/transactions/{{ detail.id }}/share/clear" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <button type="submit">Stop sharing</button>
+</form>
+{% else %}
+<form method="post" action="/transactions/{{ detail.id }}/share" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <label>Owed by
+    <select name="debtor">
+      {% for name in people %}<option value="{{ name }}"{% if name == share_form.debtor %} selected{% endif %}>{{ name }}</option>
+      {% endfor %}
+    </select>
+  </label>
+  <label>Paid by
+    <select name="payer">
+      <option value=""{% if not share_form.payer %} selected{% endif %}>The card's or account's person</option>
+      {% for name in people %}<option value="{{ name }}"{% if name == share_form.payer %} selected{% endif %}>{{ name }}</option>
+      {% endfor %}
+    </select>
+  </label>
+  <label>Their share <input name="share" inputmode="decimal" placeholder="half" value="{{ share_form.share }}"></label>
+  <button type="submit">Share</button>
+</form>
+{% endif %}
+</section>
+<section class="card">
 <h2>Tags</h2>
 {% if tags %}<p class="tags">{% for tag in tags %}<a href="/transactions?tag={{ tag|urlencode }}">{{ tag }}</a>{% if not loop.last %}, {% endif %}{% endfor %}</p>
 {% for tag in tags %}<form method="post" action="/transactions/{{ detail.id }}/tags/remove" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="tag" value="{{ tag }}"><button type="submit">Remove {{ tag }}</button></form>
```

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index f3efa6f..c6c1175 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -135,6 +135,7 @@ HOMES = {
         "list_settlements",
         "list_shares",
         "record_settlement",
+        "share_of",
         "share_transaction",
         "unshare_transaction",
     ],
@@ -174,7 +175,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 122
+    assert len(expected) == 123
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 18fe728..56e9277 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -21,6 +21,7 @@ AREAS = [
     "people",
     "reports",
     "review",
+    "shared",
     "statements",
     "sync",
     "transactions",
@@ -50,6 +51,11 @@ ROUTES = {
     ("POST", "/transactions/{transaction_id}/note"),
     ("POST", "/transactions/{transaction_id}/split"),
     ("POST", "/transactions/{transaction_id}/split/clear"),
+    ("GET", "/shared"),
+    ("POST", "/shared/settle"),
+    ("POST", "/shared/settlements/delete"),
+    ("POST", "/transactions/{transaction_id}/share"),
+    ("POST", "/transactions/{transaction_id}/share/clear"),
     ("GET", "/statements"),
     ("POST", "/statements/upload"),
     ("GET", "/categories"),
```

## Given tests

10 tests in one file. Do not change them.

`tests/integration/test_web_shared.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    record_settlement,
    set_account_owner,
    share_transaction,
)
from finances.domain.shared import SIZE
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 6, 1))
    return found


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Sam and Alex; a card owned by Sam with a purchase of -$20.01 (1), shared with Alex, and
    a refund of $6.00 (2); Alex paid Sam $4.00 on 2026-05-20."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        sam = create_person(session, "Sam")
        create_person(session, "Alex")
        account = create_account(session, "Test Card", "Test Bank", "credit_card")
        set_account_owner(session, account.id, sam.id)
        for number, (day, cents) in enumerate(((1, -2001), (3, 600)), start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description="FOOBAR GROCERY",
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        share_transaction(session, 1, "Alex")
        record_settlement(session, "Alex", "Sam", 400, date(2026, 5, 20))
    engine.dispose()
    client.get("/shared")
    return client


def test_the_shared_page(home: TestClient) -> None:
    response = home.get("/shared")
    assert response.status_code == 200
    assert 'href="/shared" aria-current="page">Shared</a>' in response.text
    found = Page(response.text)
    assert texts(found, "owed") == ["Alex owes Sam $6.00."]
    assert found.rows == [
        ["ID", "Paid by", "Owes", "Owed"],
        ["1", "Sam", "Alex", "$10.00"],
        ["ID", "Date", "From", "To", "Amount", ""],
        ["1", "2026-05-20", "Alex", "Sam", "$4.00", "Delete"],
    ]
    form = found.find("/shared/settle")
    assert form["selects"]["payer"] == [("Alex", False), ("Sam", False)]
    assert form["inputs"]["day"] == ("date", "2026-06-01")
    assert 'href="/shared">Shared</a>' in home.get("/people").text


def test_settling_on_the_page(home: TestClient) -> None:
    response = post(
        home, "/shared/settle", payer="Alex", payee="Sam", amount="2.00", day="2026-05-25"
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/shared?notice=settled",
    )
    found = page(home, "/shared?notice=settled")
    assert texts(found, "notice") == ["Settlement recorded."]
    assert texts(found, "owed") == ["Alex owes Sam $4.00."]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"payee": "Sam", "amount": "x", "day": ""}, "invalid money text"),
        ({"payee": "Alex", "amount": "1.00", "day": ""}, "a person cannot pay themselves"),
        (
            {"payee": "Sam", "amount": "1.00", "day": "2026-13-01"},
            "date must be a date as YYYY-MM-DD",
        ),
    ],
)
def test_a_refused_settlement(home: TestClient, fields: dict, message: str) -> None:
    response = post(home, "/shared/settle", payer="Alex", **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == [message]
    assert found.find("/shared/settle")["inputs"]["amount"] == ("text", fields["amount"])


def test_deleting_a_settlement(home: TestClient) -> None:
    response = post(home, "/shared/settlements/delete", settlement="1")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/shared?notice=settlement-deleted",
    )
    found = page(home, "/shared?notice=settlement-deleted")
    assert texts(found, "notice") == ["Settlement deleted."]
    assert texts(found, "owed") == ["Alex owes Sam $10.00."]
    refused = post(home, "/shared/settlements/delete", settlement="9")
    assert refused.status_code == 400
    assert texts(Page(refused.text), "error") == ["settlement not found"]


def test_a_shared_transactions_page(home: TestClient) -> None:
    found = page(home, "/transactions/1")
    assert texts(found, "share") == ["Transaction 1: Alex owes Sam $10.00."]
    assert sorted(found.find("/transactions/1/share/clear")["inputs"]) == ["csrf"]
    assert found.all("/transactions/1/share") == []


def test_sharing_and_unsharing_on_a_transactions_page(home: TestClient) -> None:
    form = page(home, "/transactions/2").find("/transactions/2/share")
    assert form["selects"]["payer"] == [("", True), ("Alex", False), ("Sam", False)]
    shared = post(home, "/transactions/2/share", debtor="Alex", payer="", share="2.00")
    assert (shared.status_code, shared.headers["location"]) == (
        303,
        "/transactions/2?notice=share-saved",
    )
    found = page(home, "/transactions/2?notice=share-saved")
    assert texts(found, "notice") == ["Share saved."]
    assert texts(found, "share") == ["Transaction 2: Sam owes Alex $2.00."]
    removed = post(home, "/transactions/1/share/clear")
    assert (removed.status_code, removed.headers["location"]) == (
        303,
        "/transactions/1?notice=share-removed",
    )
    assert texts(page(home, "/transactions/1?notice=share-removed"), "notice") == ["Share removed."]
    assert texts(page(home, "/shared"), "owed") == ["Sam owes Alex $6.00."]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"debtor": "Sam", "payer": "", "share": ""}, "a person cannot owe themselves"),
        ({"debtor": "Alex", "payer": "", "share": "30"}, SIZE),
    ],
)
def test_a_refused_share(home: TestClient, fields: dict, message: str) -> None:
    response = post(home, "/transactions/2/share", **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == [message]
    assert found.find("/transactions/2/share")["inputs"]["share"] == ("text", fields["share"])
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_web_shared_more.py`:

- GET on each of the four new POST paths answers 405; `/shared` on a database that is not migrated answers as the other pages do;
- a settlement with a blank date is recorded on the day `finances.web.app._today` gives, replaced after the app is created;
- a refused share keeps the transaction's tags, note, and Shared form on the 400 page (R5's context on every render); stopping a share that is not there answers 400 with `the transaction is not shared`;
- a joint purchase shared with `payer` Sam is stored, and with `payer` blank answers 400 with the joint message;
- a share posted with `share` blank owes half (`Transaction 2: Sam owes Alex $3.00.` for the $6.00 refund);
- a share on transaction 99 answers 404;
- the Shared page with no shares and no settlements shows `Nobody owes anybody.` and both empty paragraphs;
- a form posted without a valid form token is refused, as on the other forms.

## Rules for this phase

- Money is integer cents: amounts are typed as sizes and read with `parse_money`; the routes do no arithmetic and every text comes from `views/shared.py`, `NOTICES`, or the templates.
- Messages are 29a's, `parse_money`'s, or `_day`'s, constant and echoing nothing typed.
- Keep every module under `src/finances/web/routes/` under 400 lines; earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 10 tests; at least N + 10 passed in all;
- `git diff --stat HEAD -- tests` lists only the two files of the given diff;
- `git grep -n "half_share\|signed_share\|balances(\|SharedExpenseRow\|SettlementRow" -- src/finances/web` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web.routes.shared --cov=finances.web.routes.transactions --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 29c: shared expenses on the web (YYYY-MM-DD)`.
