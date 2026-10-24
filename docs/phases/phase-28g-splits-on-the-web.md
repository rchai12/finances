# Phase 28g: splits on the web

## Goal

28e's splits reach the browser, which finishes Phase 28. After this phase:

- a split transaction's page shows its parts in a table with a button to remove the split, and no longer offers to set one category for the whole;
- a transaction that is not split has a Split card: a box with one part per line (`12.00 Groceries`, as `fin transactions split` takes them), so a split is made in the browser;
- the Transactions page marks each part's row with a `part 1`, `part 2` badge beside its category, as it marks refunds.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-28e-splits-in-reports.md`
- `src/finances/domain/splits.py` (`parse_part`), `src/finances/db/repositories/splits.py` (`split_by_sizes`, `clear_split`, `splits_for`)
- `src/finances/analysis/search.py` (`FoundTransaction`, `search_transactions`), `src/finances/views/transactions.py` (`found_rows`, `part_lines`)
- `src/finances/web/routes/transactions.py` (`_transaction_page`, the tag and note routes of 28f), `src/finances/web/render.py` (`NOTICES`), `src/finances/web/templates/transactions_one.html`, `transactions.html`

## Starting state

N is `3657` when Phase 28f is the last phase built. The newest migration is `0019`; this phase adds none. `found_rows` gives four values per row today; the given Transactions template takes five, so every earlier test that shows a row of that page fails until R7 is built (70 of them, all for that one reason). With today's Transactions template, every earlier integration and end-to-end test passes against the given transaction page (2036). `found_rows` has two callers: the Transactions page and the account page (`web/routes/accounts.py`, whose `account.html` unpacks its rows too); the given diff changes both templates. **Amended after the first build:** the first version of this spec left `account.html` out, so five account-page tests failed with the new rows; the given diff now unpacks the fifth value there and ignores it.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/templates/transactions_one.html`, `transactions.html`, `account.html` | the given diff (R1, R7) |
| `src/finances/web/routes/transactions.py` | the page's new context, two routes (R1 to R4) |
| `src/finances/web/render.py` | two notices (R5) |
| `src/finances/domain/splits.py` | `parse_parts` (R6) |
| `src/finances/analysis/search.py`, `src/finances/views/transactions.py` | `FoundTransaction.part`, `found_rows` (R7) |
| `tests/unit/test_web_split.py` | the given diff (R8) |
| `tests/unit/test_split_lines.py`, `tests/integration/test_web_splits.py` | new: given |
| `tests/integration/test_web_splits_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Editing one part in place (remove the split and make another); a category select per part; splits in the bulk form.
- Changing the detail table at the top of a transaction's page (its Category and Set rows stay as 28d leaves them).
- A part badge anywhere but the Transactions page; splits in an MCP tool.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/splits.py (critical)
def parse_parts(text: str) -> list[tuple[int, str]]: ...
# parse_part of each line (str.splitlines) that is not blank after stripping, in order

# src/finances/analysis/search.py
@dataclass(frozen=True)
class FoundTransaction:
    transaction: Transaction
    flow: Flow
    part: int | None = None  # the part's position for a part of a split transaction, else None

# src/finances/views/transactions.py
def found_rows(
    found: list[FoundTransaction], names: dict[int, str]
) -> list[tuple[int, TransactionRow, str, bool, int | None]]: ...
# 28e's four values, then the item's part
```

New routes on the transactions router; each starts with `refused(request, csrf)`, then `_known_transaction` (an unknown id gives `_missing_transaction`, 404), as 28f's routes do:

| Route | Fields | Calls | On success | On a `ValueError` |
|---|---|---|---|---|
| `POST /transactions/{transaction_id}/split` | `csrf`, `parts` | `split_by_sizes(session, id, parse_parts(parts))` | 303 to `/transactions/{id}?notice=split-saved` | the transaction's page, 400, the error, `split_form` the typed text |
| `POST /transactions/{transaction_id}/split/clear` | `csrf` | `clear_split(session, id)`, then `categorize(session)` | 303 to `...?notice=split-removed` | the transaction's page, 400, the error |

New context of a transaction's page, on every render:

| Name | Value |
|---|---|
| `parts` | `part_lines` of its parts from `splits_for`, with the categories' names; `[]` when it is not split |
| `split_form` | the text typed into the Split box after a refusal, else `""` |

## Requirements

### A transaction's page

- **R1.** Apply the given template diff exactly. `_transaction_page` supplies `parts` and `split_form` on every render, the 400 renders included.
- **R2.** `POST /transactions/{transaction_id}/split` as designed: the text is read with `parse_parts`, so every refusal of `parse_part` and `split_by_sizes` (28e) and of `set_split` (28d) reaches the page.
- **R3.** `POST /transactions/{transaction_id}/split/clear` as designed, the rules run in the same session.
- **R4.** GET on each of the two new paths answers 405.
- **R5.** `NOTICES` gains `"split-saved": "Split saved."` and `"split-removed": "Split removed, and the rules were run again."`.

### The rule and the Transactions page

- **R6.** `parse_parts` as designed; it is covered 100% by `tests/unit/test_split_lines.py`, and `domain/splits.py` stays critical.
- **R7.** `search_transactions` sets `part` to each part's position on the items it gives for a split transaction, and leaves it None otherwise. `found_rows` gives it as each row's fifth value; the account page takes the five values and shows no badge (the given diff). Nothing else in search, its rows, or the `list_transactions` tool changes.
- **R8.** Apply the given diff to `tests/unit/test_web_split.py`. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/templates/` (do not change).

```text
diff --git a/src/finances/web/templates/account.html b/src/finances/web/templates/account.html
index cc8ed0b..d11ee75 100644
--- a/src/finances/web/templates/account.html
+++ b/src/finances/web/templates/account.html
@@ -64,7 +64,7 @@
 <table>
 <thead><tr><th>Date</th><th>Description</th><th>Category</th><th class="amount">Amount</th><th>Card</th><th>Person</th></tr></thead>
 <tbody>
-{% for id, row, category, refund in transactions %}<tr><td><a href="/transactions/{{ id }}">{{ row.date }}</a></td><td>{{ row.description }}</td><td>{{ category }}{% if refund %} <span class="badge">refund</span>{% endif %}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{{ row.card }}</td><td>{{ row.person }}</td></tr>
+{% for id, row, category, refund, part in transactions %}<tr><td><a href="/transactions/{{ id }}">{{ row.date }}</a></td><td>{{ row.description }}</td><td>{{ category }}{% if refund %} <span class="badge">refund</span>{% endif %}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{{ row.card }}</td><td>{{ row.person }}</td></tr>
 {% endfor %}</tbody>
 </table>
 {% else %}
diff --git a/src/finances/web/templates/transactions.html b/src/finances/web/templates/transactions.html
index 7a69459..ee5bd9e 100644
--- a/src/finances/web/templates/transactions.html
+++ b/src/finances/web/templates/transactions.html
@@ -55,7 +55,7 @@
 <table>
 <thead><tr><th>Date</th><th>Account</th><th>Description</th><th>Category</th><th class="amount">Amount</th><th>Card</th><th>Section</th><th>Person</th></tr></thead>
 <tbody>
-{% for id, row, category, refund in rows %}<tr><td><input type="checkbox" name="id" value="{{ id }}"{% if select_all %} checked{% endif %}> <a href="/transactions/{{ id }}">{{ row.date }}</a></td><td><a href="/account?name={{ row.account|urlencode }}">{{ row.account }}</a></td><td>{{ row.description }}</td><td>{{ category }}{% if refund %} <span class="badge">refund</span>{% endif %}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{% if row.card %}<a href="/account?name={{ row.account|urlencode }}&amp;card={{ row.card[-4:] }}">{{ row.card }}</a>{% endif %}</td><td>{{ row.section }}</td><td>{{ row.person }}</td></tr>
+{% for id, row, category, refund, part in rows %}<tr><td><input type="checkbox" name="id" value="{{ id }}"{% if select_all %} checked{% endif %}> <a href="/transactions/{{ id }}">{{ row.date }}</a></td><td><a href="/account?name={{ row.account|urlencode }}">{{ row.account }}</a></td><td>{{ row.description }}</td><td>{{ category }}{% if refund %} <span class="badge">refund</span>{% endif %}{% if part %} <span class="badge">part {{ part }}</span>{% endif %}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{% if row.card %}<a href="/account?name={{ row.account|urlencode }}&amp;card={{ row.card[-4:] }}">{{ row.card }}</a>{% endif %}</td><td>{{ row.section }}</td><td>{{ row.person }}</td></tr>
 {% endfor %}</tbody>
 </table>
 <p class="fields">
diff --git a/src/finances/web/templates/transactions_one.html b/src/finances/web/templates/transactions_one.html
index 8304bce..242ed8a 100644
--- a/src/finances/web/templates/transactions_one.html
+++ b/src/finances/web/templates/transactions_one.html
@@ -41,6 +41,7 @@
 </form>
 </section>
 {% endif %}
+{% if not parts %}
 <section class="card">
 <h2>Set the category</h2>
 <form method="post" action="/transactions/{{ detail.id }}/category" class="fields">
@@ -57,6 +58,30 @@
 </form>
 {% endif %}
 </section>
+{% endif %}
+<section class="card">
+{% if parts %}
+<h2>Parts</h2>
+<table>
+<thead><tr><th>Part</th><th class="amount">Amount</th><th>Category</th></tr></thead>
+<tbody>
+{% for line in parts %}<tr><td>{{ line.part }}</td><td class="{{ line.amount|amount_class }}">{{ line.amount }}</td><td>{{ line.category }}</td></tr>
+{% endfor %}</tbody>
+</table>
+<form method="post" action="/transactions/{{ detail.id }}/split/clear" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <button type="submit">Remove the split</button>
+</form>
+{% else %}
+<h2>Split</h2>
+<p class="hint">One part per line: its size and its category, such as 12.00 Groceries. The sizes add up to the amount.</p>
+<form method="post" action="/transactions/{{ detail.id }}/split" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <label>Parts <textarea name="parts" rows="4">{{ split_form }}</textarea></label>
+  <button type="submit">Split</button>
+</form>
+{% endif %}
+</section>
 <section class="card">
 <h2>Tags</h2>
 {% if tags %}<p class="tags">{% for tag in tags %}<a href="/transactions?tag={{ tag|urlencode }}">{{ tag }}</a>{% if not loop.last %}, {% endif %}{% endfor %}</p>
```

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 40aab3b..18fe728 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -48,6 +48,8 @@ ROUTES = {
     ("POST", "/transactions/{transaction_id}/tags/add"),
     ("POST", "/transactions/{transaction_id}/tags/remove"),
     ("POST", "/transactions/{transaction_id}/note"),
+    ("POST", "/transactions/{transaction_id}/split"),
+    ("POST", "/transactions/{transaction_id}/split/clear"),
     ("GET", "/statements"),
     ("POST", "/statements/upload"),
     ("GET", "/categories"),
```

## Given tests

13 tests in two files. Do not change them.

`tests/unit/test_split_lines.py`

```python
import pytest

from finances.domain.splits import parse_parts


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("12.00 Groceries\n8.00 Home & Garden", [(1200, "Groceries"), (800, "Home & Garden")]),
        ("\n  12.00 Groceries  \r\n\n 8 Dining\n", [(1200, "Groceries"), (800, "Dining")]),
        ("", []),
    ],
)
def test_one_part_per_line(text: str, parts: list[tuple[int, str]]) -> None:
    assert parse_parts(text) == parts


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("12.00 Groceries\n8.00", "a part is a size and a category, such as 12.00 Groceries"),
        ("12.00 Groceries\neight Dining", "invalid money text"),
    ],
)
def test_a_line_that_is_refused(text: str, message: str) -> None:
    with pytest.raises(ValueError) as raised:
        parse_parts(text)
    assert str(raised.value) == message
```

`tests/integration/test_web_splits.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule, set_split
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

PART_HEADINGS = ["Part", "Amount", "Category"]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Card: 1 FOOBAR GROCERY -$20.00 with no category, 2 ACME COFFEE -$5.00 put in Coffee &
    Dessert by a rule, 3 BAZ CAFE -$10.00 split into Dining -$6.00 and Groceries -$4.00."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-2000, "FOOBAR GROCERY"), (-500, "ACME COFFEE"), (-1000, "BAZ CAFE")), start=1
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
        create_rule(session, "ACME", "Coffee & Dessert")
        categorize(session)
        set_split(session, 3, [(-600, "Dining"), (-400, "Groceries")])
    engine.dispose()
    client.get("/transactions")
    return client


def parts_of(found: Page) -> list[list[str]]:
    start = found.rows.index(PART_HEADINGS)
    return [row for row in found.rows[start + 1 :] if len(row) == 3]


def test_a_split_transactions_page(home: TestClient) -> None:
    found = page(home, "/transactions/3")
    assert parts_of(found) == [["1", "-$6.00", "Dining"], ["2", "-$4.00", "Groceries"]]
    assert sorted(found.find("/transactions/3/split/clear")["inputs"]) == ["csrf"]
    assert (found.all("/transactions/3/split"), found.all("/transactions/3/category")) == ([], [])


def test_a_page_that_is_not_split(home: TestClient) -> None:
    found = page(home, "/transactions/1")
    assert PART_HEADINGS not in found.rows
    assert sorted(found.find("/transactions/1/split")["inputs"]) == ["csrf"]
    assert len(found.all("/transactions/1/category")) == 1


def test_splitting_on_the_page(home: TestClient) -> None:
    response = post(home, "/transactions/1/split", parts="12.00 groceries\n$8 Home & Garden")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/1?notice=split-saved",
    )
    found = page(home, "/transactions/1?notice=split-saved")
    assert texts(found, "notice") == ["Split saved."]
    assert parts_of(found) == [["1", "-$12.00", "Groceries"], ["2", "-$8.00", "Home & Garden"]]


def test_a_refused_split_keeps_what_was_typed(home: TestClient) -> None:
    response = post(home, "/transactions/1/split", parts="12.00 Groceries\n9.00 Dining")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["the parts must add up to the transaction"]
    assert ">12.00 Groceries\n9.00 Dining</textarea>" in response.text


def test_removing_the_split(home: TestClient) -> None:
    response = post(home, "/transactions/3/split/clear")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/3?notice=split-removed",
    )
    found = page(home, "/transactions/3?notice=split-removed")
    assert texts(found, "notice") == ["Split removed, and the rules were run again."]
    assert len(found.all("/transactions/3/split")) == 1


@pytest.mark.parametrize(
    ("path", "fields", "status", "message"),
    [
        ("/transactions/1/split/clear", {}, 400, "the transaction is not split"),
        (
            "/transactions/99/split",
            {"parts": "1.00 Dining\n1.00 Dining"},
            404,
            "transaction not found",
        ),
    ],
)
def test_a_refused_form(
    home: TestClient, path: str, fields: dict, status: int, message: str
) -> None:
    response = post(home, path, **fields)
    assert response.status_code == status
    assert texts(Page(response.text), "error") == [message]


def test_parts_on_the_transactions_page(home: TestClient) -> None:
    found = page(home, "/transactions")
    assert [(row[2], row[3], row[4]) for row in found.rows[1:]] == [
        ("BAZ CAFE", "Dining part 1", "-$6.00"),
        ("BAZ CAFE", "Groceries part 2", "-$4.00"),
        ("ACME COFFEE", "Coffee & Dessert", "-$5.00"),
        ("FOOBAR GROCERY", "", "-$20.00"),
    ]
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_web_splits_more.py`:

- GET on each of the two new paths answers 405;
- parts that do not add up, posted to a transaction that is already split, answer 400, and that page still shows its parts table (R1's context on every render);
- splitting a pending transaction on the page gives `a pending transaction cannot be split`, and a size of `0` gives `each part's size must be more than zero`;
- removing a split whose merchant a rule matches puts the transaction back in the rule's category (the rules ran);
- `search_transactions` gives `part` 1 and 2 for a two-part split and None for a transaction that is not split;
- a form posted without a valid form token is refused, as on the other forms.

## Rules for this phase

- Money is integer cents; sizes are typed without a sign, as in the terminal.
- The routes parse fields, call the repository and `categorize`, and redirect or render; reading the box's lines is `parse_parts`, in the critical module, not in the route.
- Messages are constant and echo no amount, description, or category.
- Keep `web/routes/transactions.py` under 400 lines; earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 13 tests; at least N + 13 passed in all;
- `git diff --stat HEAD -- tests` lists only the file of the given diff;
- `git grep -n "splitlines\|parse_part(" -- src/finances/web` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.splits --cov=finances.analysis.search --cov=finances.views.transactions --cov=finances.web.routes.transactions --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 28g: splits on the web (YYYY-MM-DD)`.
