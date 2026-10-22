# Phase 35b: refunds on transactions

## Goal

A refund can be told apart where transactions are listed. After this phase:

- the Transactions page and an account's page show a `refund` badge next to a refund's category, and the Transactions page links to **Only refunds** (`/transactions?kind=refund`);
- a refund's own page names the purchase it most likely returns, and that purchase's page names its refunds, each linking to the other;
- uncategorized money in on a credit card is flagged under the uncategorized list (`fin uncategorized` and the Categories page) as a likely refund or card payment.

Nothing is stored and no figure changes; 35a already shows refunds in the reports. The refund filter is on the web only: the terminal's `fin transactions list` has no kinds today.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/roadmap.md`, Phase 35; `docs/phases/phase-35a-spent-refunds-net.md`
- `src/finances/domain/spending.py`, `src/finances/analysis/search.py`, `src/finances/analysis/spending.py` (`flows_for`), `src/finances/views/transactions.py` (`found_rows`), `src/finances/views/categories.py` (`uncategorized_lines`), `src/finances/web/routes/transactions.py` (`_transaction_page`), `src/finances/web/routes/categories.py`, `src/finances/web/routes/accounts.py`, `src/finances/cli/categories.py` (`uncategorized_command`)

## Starting state

N is `3111` when Phase 35a is the last phase built.

A refund is a flow of kind `SPENDING` above zero (35a). Money in with no category has the kind `UNSORTED_IN` and is never a refund.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/spending.py` | `REFUND`, `SEARCH_KINDS`, `is_refund` (R1) |
| `src/finances/domain/refunds.py` | new (R2) |
| `src/finances/analysis/search.py` | the `refund` kind (R3) |
| `src/finances/analysis/refunds.py` | new (R5) |
| `src/finances/views/transactions.py` | `found_rows` (R4) |
| `src/finances/views/categories.py` | `card_credits_note` (R7) |
| `src/finances/web/routes/transactions.py`, `src/finances/web/routes/categories.py` | context (R6, R7) |
| `src/finances/cli/categories.py` | the note (R7) |
| `src/finances/web/templates/*.html`, `src/finances/web/static/app.css` | the given diff (R8) |
| three earlier test files | the given diff (R9) |
| `tests/unit/test_refunds.py`, `tests/integration/test_web_refunds_found.py`, `tests/e2e/test_cli_card_credits.py` | new: given |
| `tests/integration/test_refunds_found_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Storing a refund's match, or letting a person confirm or reject it; matching across accounts or merchants.
- A kind option in the terminal; a Kind column; any change to totals, reports, budgets, insights, or transfers.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/spending.py
REFUND = "refund"
SEARCH_KINDS = (*KINDS, REFUND)  # what the search's kind accepts; KINDS does not change

def is_refund(flow: Flow) -> bool: ...  # kind SPENDING and amount above zero

# src/finances/domain/refunds.py  (standard library and finances.domain only)
REFUND_WINDOW_DAYS = 90

@dataclass(frozen=True)
class Purchase:
    id: int
    day: date
    amount_cents: int

def likely_purchase(day: date, cents: int, purchases: list[Purchase]) -> int | None: ...

# src/finances/analysis/refunds.py
@dataclass(frozen=True)
class RefundFacts:
    is_refund: bool
    purchase: Transaction | None   # for a refund: its likely purchase
    refunds: list[Transaction]     # for a purchase: the refunds matched to it, oldest first

def refund_facts(session: Session, transaction_id: int) -> RefundFacts: ...

# src/finances/views/categories.py
CARD_CREDITS = (
    "Money in on a card: {count}, likely a refund or a card payment."
    " Set a category, or pair it on the Transfers page."
)

def card_credits_note(session: Session, limit: int) -> str | None: ...
```

## Requirements

### Part 1: the rules (pure)

- **R1.** `is_refund(flow)` is true exactly when the flow's kind is `SPENDING` and its amount is above zero. `REFUND` and `SEARCH_KINDS` are as above; `KINDS` and every flow's kind do not change.
- **R2.** `likely_purchase(day, cents, purchases)` keeps the purchases below zero whose amount covers the refund (`-amount_cents >= cents`) and whose day is from `day - 90 days` to `day`, both included, and returns the id of the latest of them by day, the highest id among those on that day; `None` when none fits. The caller passes only purchases of the same account and the same cleaned merchant.

### Part 2: finding and matching

- **R3.** The search's `kind` accepts every value of `SEARCH_KINDS`; `refund` keeps the transactions whose flow `is_refund`. Any other value is refused with `kind must be one of: ` followed by `SEARCH_KINDS` joined with `, `.
- **R4.** `found_rows` returns `(id, row, category, refund)` for each transaction, `refund` being `is_refund` of its flow.
- **R5.** `refund_facts` reads the transaction and the flows of its account within 90 days on each side that are of kind `SPENDING` with the same cleaned merchant (pending transactions are never in it, by their kind). For a refund, `purchase` is the transaction `likely_purchase` names among those flows below zero (by each flow's day, as the search uses it). For a purchase (below zero), `refunds` are the refunds from its day to 90 days after whose `likely_purchase` is this purchase, oldest first. Any other transaction gets `RefundFacts(False, None, [])`.

### Part 3: what people see

- **R6.** A transaction's page adds to its context `refund`: `None` unless the transaction is a refund, else `{"amount": <its amount as shown>, "purchase": None or {"id": ..., "date": <ISO day>, "amount": format_cents(...)}}`; and `refunded`: a list of `{"id", "date", "amount"}` for `RefundFacts.refunds`. One reading session.
- **R7.** `card_credits_note(session, limit)` counts the transactions in `list_uncategorized(session, limit)` that are above zero on an account of type `credit_card` (open or closed), and returns `CARD_CREDITS` with that count, or `None` for none. `fin uncategorized` prints it on its own line after the table; the Categories page passes it as `card_note`.
- **R8.** Apply the given diff to the templates and `app.css`, exactly: the badge after a refund's category on the Transactions page and an account's page, the **Only refunds** link, the Refund and Refunds sections of a transaction's page (each a 16n card), the note on the Categories page, and a `.badge` rule from 16m's tokens.
- **R9.** Apply the given diff to three earlier test files: the kind message gains `refund`, and the account page's refund row reads `Groceries refund`. No other earlier test changes.

## Given tests

27 tests in three files. Five of them already pass on today's code and guard what must stay absent (no refund section where none applies; no note without money in on a card).

`tests/unit/test_refunds.py`

```python
from datetime import date

import pytest

from finances.domain.refunds import REFUND_WINDOW_DAYS, Purchase, likely_purchase
from finances.domain.spending import (
    INCOME,
    KINDS,
    REFUND,
    SEARCH_KINDS,
    SPENDING,
    TRANSFER,
    UNSORTED_IN,
    Flow,
    is_refund,
)

DAY = date(2026, 6, 12)


def flow(cents: int, kind: str) -> Flow:
    return Flow(cents, DAY, kind, "Groceries", "Food", "FOOBAR GROCERY", "", "Test Card", "", "")


@pytest.mark.parametrize(
    ("cents", "kind", "refund"),
    [
        (599, SPENDING, True),
        (-599, SPENDING, False),
        (599, INCOME, False),
        (599, TRANSFER, False),
        (599, UNSORTED_IN, False),
    ],
)
def test_a_refund_is_money_back_on_spending(cents: int, kind: str, refund: bool) -> None:
    assert is_refund(flow(cents, kind)) is refund


def test_refund_is_a_kind_to_search_by_but_not_a_flow_kind() -> None:
    assert SEARCH_KINDS == (*KINDS, REFUND)
    assert REFUND == "refund" and REFUND not in KINDS
    assert REFUND_WINDOW_DAYS == 90


@pytest.mark.parametrize(
    ("purchases", "found"),
    [
        ([Purchase(1, date(2026, 4, 1), -1000), Purchase(2, date(2026, 5, 10), -2599)], 2),
        ([Purchase(1, date(2026, 5, 10), -500)], None),
        ([Purchase(1, date(2026, 6, 13), -2599)], None),
        ([Purchase(1, DAY, -599)], 1),
        ([Purchase(1, date(2026, 3, 14), -599)], 1),
        ([Purchase(1, date(2026, 3, 13), -599)], None),
        ([Purchase(3, date(2026, 5, 10), -700), Purchase(5, date(2026, 5, 10), -700)], 5),
        ([Purchase(1, date(2026, 5, 10), 2599)], None),
        ([], None),
    ],
    ids=[
        "the latest that fits",
        "smaller than the refund",
        "after the refund",
        "the same day",
        "90 days before",
        "91 days before",
        "a tie goes to the newest",
        "money in is no purchase",
        "nothing",
    ],
)
def test_the_likely_purchase(purchases: list[Purchase], found: int | None) -> None:
    assert likely_purchase(DAY, 599, purchases) == found
```

`tests/integration/test_web_refunds_found.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule
from finances.web.app import create_app
from tests.support import WEB_PORT, page, texts

HEADINGS = ["Date", "Account", "Description", "Category", "Amount", "Card", "Section", "Person"]
CARD_NOTE = (
    "Money in on a card: 1, likely a refund or a card payment."
    " Set a category, or pair it on the Transfers page."
)


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def refunds(client: TestClient) -> TestClient:
    """On the card: groceries in April and May, $5.99 of May's refunded in June, groceries
    again after the refund, a book refund with no purchase, and a credit with no category.
    On checking: a deposit with no category. Ids follow the rows."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        rows = [
            (card, date(2026, 4, 1), -1000, "FOOBAR GROCERY"),
            (card, date(2026, 5, 10), -2599, "FOOBAR GROCERY"),
            (card, date(2026, 6, 12), 599, "FOOBAR GROCERY"),
            (card, date(2026, 6, 1), 1500, "BAZ BOOKS"),
            (card, date(2026, 6, 5), 2500, "QUUX CREDIT"),
            (checking, date(2026, 6, 1), 300000, "ACME DEPOSIT"),
            (card, date(2026, 6, 15), -800, "FOOBAR GROCERY"),
        ]
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        create_rule(session, "FOOBAR", "Groceries")
        create_rule(session, "BAZ BOOKS", "Education")
        categorize(session)
    engine.dispose()
    return client


def test_refunds_carry_a_label(refunds: TestClient) -> None:
    found = page(refunds, "/transactions")
    assert [row[2:5] for row in found.rows] == [
        HEADINGS[2:5],
        ["FOOBAR GROCERY", "Groceries", "-$8.00"],
        ["FOOBAR GROCERY", "Groceries refund", "$5.99"],
        ["QUUX CREDIT", "", "$25.00"],
        ["ACME DEPOSIT", "", "$3,000.00"],
        ["BAZ BOOKS", "Education refund", "$15.00"],
        ["FOOBAR GROCERY", "Groceries", "-$25.99"],
        ["FOOBAR GROCERY", "Groceries", "-$10.00"],
    ]
    assert "/transactions?kind=refund" in found.links


def test_only_refunds(refunds: TestClient) -> None:
    found = page(refunds, "/transactions?kind=refund")
    assert [row[2:5] for row in found.rows[1:]] == [
        ["FOOBAR GROCERY", "Groceries refund", "$5.99"],
        ["BAZ BOOKS", "Education refund", "$15.00"],
    ]
    assert "Also filtered by: kind refund. Clear all filters" in texts(found, "hint")


def test_a_refund_names_its_likely_purchase(refunds: TestClient) -> None:
    found = page(refunds, "/transactions/3")
    assert "Likely returns the purchase of 2026-05-10 for -$25.99." in texts(found, "summary")
    assert "/transactions/2" in found.links


def test_the_purchase_names_its_refund(refunds: TestClient) -> None:
    found = page(refunds, "/transactions/2")
    assert "Refunded $5.99 on 2026-06-12." in texts(found, "summary")
    assert "/transactions/3" in found.links


@pytest.mark.parametrize("transaction_id", [1, 5, 6, 7])
def test_no_refund_section_where_none_applies(refunds: TestClient, transaction_id: int) -> None:
    html = refunds.get(f"/transactions/{transaction_id}").text
    assert "<h2>Refund</h2>" not in html and "<h2>Refunds</h2>" not in html


def test_a_refund_with_no_purchase(refunds: TestClient) -> None:
    found = page(refunds, "/transactions/4")
    assert texts(found, "empty") == [
        "No purchase of at least $15.00 from this merchant on this account in the 90 days before."
    ]


def test_money_in_on_a_card_without_a_category(refunds: TestClient) -> None:
    assert CARD_NOTE in texts(page(refunds, "/categories"), "hint")
```

`tests/e2e/test_cli_card_credits.py`

```python
from datetime import date

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import plain_lines, run, table_rows


def test_uncategorized_money_in_on_a_card_is_flagged(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        rows = [
            (card, date(2026, 6, 5), 2500, "QUUX CREDIT"),
            (card, date(2026, 6, 6), 1200, "BAZ CREDIT"),
            (card, date(2026, 6, 7), -900, "BAZ BOX"),
            (checking, date(2026, 6, 1), 300000, "ACME DEPOSIT"),
        ]
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    result = run("uncategorized")
    assert table_rows(result.stdout)[0] == ["ID", "Date", "Account", "Merchant", "Amount"]
    assert plain_lines(result.stdout) == [
        "Money in on a card: 2, likely a refund or a card payment."
        " Set a category, or pair it on the Transfers page."
    ]


def test_no_flag_without_money_in_on_a_card(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        session.add(
            TransactionRow(
                account_id=checking.id,
                posted_date=date(2026, 6, 1),
                amount_cents=300000,
                description="ACME DEPOSIT",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
    engine.dispose()
    assert plain_lines(run("uncategorized").stdout) == []
```

## Given diffs

Templates and stylesheet:

```text
diff --git a/src/finances/web/static/app.css b/src/finances/web/static/app.css
index 4b6b0ca..17bd907 100644
--- a/src/finances/web/static/app.css
+++ b/src/finances/web/static/app.css
@@ -74,3 +74,4 @@ section.card table { background: var(--bg); }
 section.card .notice, section.card .error, section.card .attention { background: var(--bg); }
 td.amount.neg { color: var(--bad); }
 td.amount.pos { color: var(--good); }
+.badge { display: inline-block; margin-left: .35rem; padding: 0 .45rem; border-radius: 999px; font-size: .72rem; font-weight: 600; background: var(--accent-tint); color: var(--accent); }
diff --git a/src/finances/web/templates/account.html b/src/finances/web/templates/account.html
index a8d5eab..cc8ed0b 100644
--- a/src/finances/web/templates/account.html
+++ b/src/finances/web/templates/account.html
@@ -64,7 +64,7 @@
 <table>
 <thead><tr><th>Date</th><th>Description</th><th>Category</th><th class="amount">Amount</th><th>Card</th><th>Person</th></tr></thead>
 <tbody>
-{% for id, row, category in transactions %}<tr><td><a href="/transactions/{{ id }}">{{ row.date }}</a></td><td>{{ row.description }}</td><td>{{ category }}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{{ row.card }}</td><td>{{ row.person }}</td></tr>
+{% for id, row, category, refund in transactions %}<tr><td><a href="/transactions/{{ id }}">{{ row.date }}</a></td><td>{{ row.description }}</td><td>{{ category }}{% if refund %} <span class="badge">refund</span>{% endif %}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{{ row.card }}</td><td>{{ row.person }}</td></tr>
 {% endfor %}</tbody>
 </table>
 {% else %}
diff --git a/src/finances/web/templates/categories.html b/src/finances/web/templates/categories.html
index 1b7efb1..44634f6 100644
--- a/src/finances/web/templates/categories.html
+++ b/src/finances/web/templates/categories.html
@@ -12,6 +12,7 @@
 {% for row in uncategorized %}<tr><td><a href="/transactions/{{ row.id }}">{{ row.id }}</a></td><td>{{ row.date }}</td><td>{{ row.account }}</td><td>{{ row.merchant }}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td></tr>
 {% endfor %}</tbody>
 </table>
+{% if card_note %}<p class="hint">{{ card_note }}</p>{% endif %}
 {% if uncategorized|length >= limit %}<p class="hint">Showing the {{ limit }} latest. Open one to set its category, or add a rule below.</p>{% endif %}
 {% else %}
 <p class="empty">No uncategorized transactions.</p>
diff --git a/src/finances/web/templates/transactions.html b/src/finances/web/templates/transactions.html
index 31d8f7a..bc53169 100644
--- a/src/finances/web/templates/transactions.html
+++ b/src/finances/web/templates/transactions.html
@@ -38,6 +38,7 @@
   {% for key in kept %}<input type="hidden" name="{{ key }}" value="{{ chosen[key] }}">
   {% endfor %}<button type="submit">Show</button>
 </form>
+<p class="quick"><a href="/transactions?kind=refund">Only refunds</a></p>
 {% if kept %}<p class="hint">Also filtered by: {% for key in kept %}{{ key }} {{ chosen[key] }}{% if not loop.last %}, {% endif %}{% endfor %}. <a href="/transactions">Clear all filters</a></p>{% endif %}
 {% if rows %}
 <p class="selection"><a href="/transactions?{{ select_all_query }}">Select all shown</a> <a href="/transactions?{{ back }}">Clear the selection</a></p>
@@ -47,7 +48,7 @@
 <table>
 <thead><tr><th>Date</th><th>Account</th><th>Description</th><th>Category</th><th class="amount">Amount</th><th>Card</th><th>Section</th><th>Person</th></tr></thead>
 <tbody>
-{% for id, row, category in rows %}<tr><td><input type="checkbox" name="id" value="{{ id }}"{% if select_all %} checked{% endif %}> <a href="/transactions/{{ id }}">{{ row.date }}</a></td><td><a href="/account?name={{ row.account|urlencode }}">{{ row.account }}</a></td><td>{{ row.description }}</td><td>{{ category }}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{% if row.card %}<a href="/account?name={{ row.account|urlencode }}&amp;card={{ row.card[-4:] }}">{{ row.card }}</a>{% endif %}</td><td>{{ row.section }}</td><td>{{ row.person }}</td></tr>
+{% for id, row, category, refund in rows %}<tr><td><input type="checkbox" name="id" value="{{ id }}"{% if select_all %} checked{% endif %}> <a href="/transactions/{{ id }}">{{ row.date }}</a></td><td><a href="/account?name={{ row.account|urlencode }}">{{ row.account }}</a></td><td>{{ row.description }}</td><td>{{ category }}{% if refund %} <span class="badge">refund</span>{% endif %}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{% if row.card %}<a href="/account?name={{ row.account|urlencode }}&amp;card={{ row.card[-4:] }}">{{ row.card }}</a>{% endif %}</td><td>{{ row.section }}</td><td>{{ row.person }}</td></tr>
 {% endfor %}</tbody>
 </table>
 <p class="fields">
diff --git a/src/finances/web/templates/transactions_one.html b/src/finances/web/templates/transactions_one.html
index f3fef63..ac292fb 100644
--- a/src/finances/web/templates/transactions_one.html
+++ b/src/finances/web/templates/transactions_one.html
@@ -16,6 +16,19 @@
 <tr><th>Set</th><td>{{ detail.set_by }}</td></tr>
 </tbody>
 </table>
+{% if refund %}
+<section class="card">
+<h2>Refund</h2>
+{% if refund.purchase %}<p class="summary">Likely returns the purchase of <a href="/transactions/{{ refund.purchase.id }}">{{ refund.purchase.date }}</a> for {{ refund.purchase.amount }}.</p>
+{% else %}<p class="empty">No purchase of at least {{ refund.amount }} from this merchant on this account in the 90 days before.</p>
+{% endif %}</section>
+{% endif %}
+{% if refunded %}
+<section class="card">
+<h2>Refunds</h2>
+{% for item in refunded %}<p class="summary">Refunded <a href="/transactions/{{ item.id }}">{{ item.amount }} on {{ item.date }}</a>.</p>
+{% endfor %}</section>
+{% endif %}
 {% if transfer %}
 <section class="card">
 <h2>Transfer</h2>
```

Earlier tests:

```text
diff --git a/tests/integration/test_transaction_search.py b/tests/integration/test_transaction_search.py
index 8ba3a85..98ce2b0 100644
--- a/tests/integration/test_transaction_search.py
+++ b/tests/integration/test_transaction_search.py
@@ -30,7 +30,7 @@ from finances.domain.spending import (
 )
 
 CHECKING, CARD, SHARED = 1, 2, 3
-KIND_MESSAGE = "kind must be one of: spending, income, transfer, unsorted_in, pending"
+KIND_MESSAGE = "kind must be one of: spending, income, transfer, unsorted_in, pending, refund"
 
 
 @pytest.fixture
diff --git a/tests/integration/test_web_account_page.py b/tests/integration/test_web_account_page.py
index a426bc0..ed8e5f7 100644
--- a/tests/integration/test_web_account_page.py
+++ b/tests/integration/test_web_account_page.py
@@ -143,7 +143,7 @@ def test_the_account_page(home: TestClient) -> None:
         LATEST,
         ["2026-05-21", "PAYMENT THANK YOU", "", "$500.00", "", "Pat Example"],
         ["2026-05-20", "LATE FEE", "", "-$35.00", "", "Pat Example"],
-        ["2026-05-15", "FOOBAR GROCERY", "Groceries", "$5.99", "••1111", "Pat Example"],
+        ["2026-05-15", "FOOBAR GROCERY", "Groceries refund", "$5.99", "••1111", "Pat Example"],
         ["2026-05-12", "ACME COFFEE", "Coffee & Dessert", "-$5.00", "••2222", "Pat Example"],
         ["2026-05-10", "FOOBAR GROCERY", "Groceries", "-$200.00", "••1111", "Pat Example"],
         ["2026-05-03", "BAZ BOOKS", "", "-$15.00", "••2222", "Pat Example"],
diff --git a/tests/integration/test_web_search.py b/tests/integration/test_web_search.py
index f9f3e7a..efd297e 100644
--- a/tests/integration/test_web_search.py
+++ b/tests/integration/test_web_search.py
@@ -25,7 +25,7 @@ SNACK_DAYS = [
     "2026-05-02",
     "2026-05-01",
 ]
-KINDS = "kind must be one of: spending, income, transfer, unsorted_in, pending"
+KINDS = "kind must be one of: spending, income, transfer, unsorted_in, pending, refund"
 
 
 @pytest.fixture
```

## Tests to write

`tests/integration/test_refunds_found_more.py`: a refund on a closed account's purchase still matches; two refunds of one purchase both listed on it, oldest first; a refund on another account of the same merchant never matches; a pending charge is never a purchase; `/account?name=...` shows the badge; `kind=refund` together with a category filter.

## Rules for this phase

- `domain/refunds.py` imports only the standard library and `finances.domain`.
- Nothing is written to the database; refunds and matches are worked out when a page or command asks.
- Messages hold no description or amount beyond what the page already shows.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_refunds.py tests/integration/test_web_refunds_found.py tests/e2e/test_cli_card_credits.py`, 27 tests; at least N + 27 passed in all;
- `git diff --stat HEAD -- tests` lists only the three files of the earlier-tests diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.spending --cov=finances.domain.refunds --cov=finances.analysis.search --cov=finances.analysis.refunds --cov=finances.views.transactions --cov=finances.views.categories --cov=finances.web.routes.transactions --cov=finances.web.routes.categories --cov=finances.cli.categories --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the search `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain`: no output.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 35b: refunds on transactions (YYYY-MM-DD)`.
