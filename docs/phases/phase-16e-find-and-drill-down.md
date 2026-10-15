# Phase 16e: find and drill down

## Goal

The household finds any transaction and sees what lies behind every number. After this phase:

- the Transactions page has a **Search** box (words in the description), a **Category** choice (or Uncategorized), a **Merchant** box, and a **Category** column;
- it also accepts `group`, `bank`, `card`, and `kind` (spending, income, transfer, unsorted_in, pending) from links, keeps them on the form, names them in a line with **Clear all filters**;
- its **From** and **To** now mean the day bought when the statement gives one (as every report does), otherwise the day posted;
- every **spending line** on the Reports page, every **merchant**, **recurring charge**, and **finding about a category or merchant** on the Insights page links to exactly the transactions behind it.

A drill-down shows the same transactions the line counted because both are built from the same flows (Phase 12a). `fin transactions list` does not change.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/analysis/spending.py` (`load_flows`), `src/finances/domain/spending.py`, `src/finances/analysis/people.py`, `src/finances/views/transactions.py`
- `src/finances/web/app.py`: `GET /transactions` and `_find`, `GET /reports`, `GET /insights`
- `tests/support.py` and `docs/testing.md` rule 8

## Starting state

N is `2533` when Phase 13c is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/spending.py` | new: `PENDING`, `KINDS` (R1) |
| `src/finances/db/repositories.py` | new: `list_transactions_by_day` (R2) |
| `src/finances/analysis/spending.py` | new: `flows_for`; `load_flows` uses it (R3) |
| `src/finances/analysis/search.py` | new (R4, R5) |
| `src/finances/views/transactions.py` | new: `found_rows` (R6) |
| `src/finances/web/app.py` | `GET /transactions` (R7, R8); the Reports and Insights pages pass their dates (R9) |
| `src/finances/web/templates/transactions.html`, `reports.html`, `insights.html` | replaced: given |
| `tests/integration/test_web_search.py` | new: given |
| `tests/integration/test_web_pages.py` | the Category column: given change (below) |
| `tests/integration/test_transaction_search.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- `fin transactions list` and its options; any change to how reports count.
- Saving searches, sorting by column, paging beyond `limit`, exporting, full-text indexes.
- Links from the months table or the balances (a month already opens its spending).

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/spending.py
PENDING = "pending"  # the kind of a pending transaction; flow_kind never returns it
KINDS = (SPENDING, INCOME, TRANSFER, UNSORTED_IN, PENDING)

# src/finances/db/repositories.py
def list_transactions_by_day(session: Session, start: date | None, end: date | None) -> list[Transaction]: ...

# src/finances/analysis/spending.py
def flows_for(session: Session, transactions: Iterable[Transaction]) -> list[Flow]: ...

# src/finances/analysis/search.py
@dataclass(frozen=True)
class TransactionQuery:
    text: str = ""
    account: str = ""
    person: str = ""      # a person's name, "joint", or "unassigned"
    category: str = ""    # a category's name, or "Uncategorized"
    group: str = ""
    merchant: str = ""
    bank: str = ""
    card: str = ""        # last four digits, or "No card"
    kind: str = ""        # one of KINDS
    start: date | None = None
    end: date | None = None
    limit: int = 50


@dataclass(frozen=True)
class FoundTransaction:
    transaction: Transaction
    flow: Flow


def search_transactions(session: Session, query: TransactionQuery) -> list[FoundTransaction]: ...

# src/finances/views/transactions.py
def found_rows(found: list[FoundTransaction], names: dict[int, str]) -> list[tuple[int, TransactionRow, str]]: ...
```

Messages, in full. Each is a `ValueError`; the page shows it with status `400` and no rows.

| Order | When | Message |
|---|---|---|
| 1, 2 | `from`, `to` not a date | the existing `from must be a date as YYYY-MM-DD`, `to must be a date as YYYY-MM-DD` |
| 3 | `limit` | the existing `limit must be a whole number from 1 to 1000` |
| 4 | `kind` given and not exactly one of `KINDS` | `kind must be one of: spending, income, transfer, unsorted_in, pending` |
| 5 | `account` given and no account has that name | the existing `account not found` |
| 6 | `person` given, not `joint` or `unassigned`, and no person has that name | the existing `person not found` |

## Requirements

### Part 1: the search

- **R1.** `domain/spending.py` gains `PENDING` and `KINDS` as above. Nothing else there changes.
- **R2.** `list_transactions_by_day` returns every transaction, pending included, whose day (`transaction_date` when set, otherwise `posted_date`) is on or after `start` and on or before `end` (each bound only when given), ordered by posted date, latest first, then by id, highest first. It uses `func.coalesce`.
- **R3.** `flows_for` builds one `Flow` per transaction, in the order given, exactly as `load_flows` does today, except that a pending transaction's `kind` is `PENDING`. `load_flows` becomes `flows_for` over `list_transactions_between`; its results do not change.
- **R4.** `search_transactions` checks messages 4 to 6 in order, then takes `flows_for(list_transactions_by_day(start, end))` and keeps each transaction whose flow matches every field that is not empty (after stripping spaces): `text` is contained in the description, ignoring case; `account`, `category`, `group`, `merchant`, `bank`, `card` equal the flow's label ignoring case; `person` equals the flow's person ignoring case, with `joint` meaning `Joint` and `unassigned` meaning `Unassigned`; `kind` equals the flow's kind. It returns at most `limit` of them, in the repository's order.
- **R5.** A drill-down matches its line: for any month and grouping, `search_transactions` with that month's dates, the grouping's field set to a line's label, `kind` `spending`, and `limit` 1000 returns exactly the flows that line counted.
- **R6.** `found_rows` gives each found transaction as `(id, transaction_row(transaction, person, names), category)`, where `person` is `None` when the flow's person is `Unassigned` (so the Person cell stays empty, as today) and `category` is the flow's category, or empty when it is `Uncategorized`.

### Part 2: the pages

- **R7.** `GET /transactions` reads `text`, `account`, `person`, `category`, `merchant`, `group`, `bank`, `card`, `kind`, `from`, `to`, and `limit` as text; checks messages 1 to 3 as today, then calls `search_transactions` once. It renders the given template with `chosen` (every field as sent; `limit` defaulting to 50 as today), `choices` (`accounts` and `people` as today, and `categories` from `category_choices`), `special` as today, `kept` (those of `group`, `bank`, `card`, `kind` that are not empty, in that order), `rows` (`found_rows`), and `error`.
- **R8.** The page otherwise behaves as today (its existing tests pass, with the given change for the new column).
- **R9.** The Reports page's `spending` gains `start` and `end` (ISO dates of the range), and the Insights page's `report` gains `start` and `end` (the month's first and last day, ISO). The given templates build the links from them.

## Given templates

Replace the three templates exactly as shown.

`src/finances/web/templates/transactions.html`

```html
{% extends "layout.html" %}
{% block title %}Transactions · Finances{% endblock %}
{% block content %}
<h1>Transactions</h1>
<form method="get" action="/transactions" class="filters">
  <label>Search <input type="search" name="text" value="{{ chosen.text }}"></label>
  <label>Account
    <select name="account">
      <option value=""{% if not chosen.account %} selected{% endif %}>All accounts</option>
      {% for name in choices.accounts %}<option value="{{ name }}"{% if name == chosen.account %} selected{% endif %}>{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Person
    <select name="person">
      <option value=""{% if not chosen.person %} selected{% endif %}>Everyone</option>
      {% for name in choices.people %}<option value="{{ name }}"{% if name == chosen.person %} selected{% endif %}>{{ name }}</option>
      {% endfor %}
      <option value="{{ special[0] }}"{% if chosen.person == special[0] %} selected{% endif %}>Joint</option>
      <option value="{{ special[1] }}"{% if chosen.person == special[1] %} selected{% endif %}>Unassigned</option>
    </select>
  </label>
  <label>Category
    <select name="category">
      <option value=""{% if not chosen.category %} selected{% endif %}>Any category</option>
      <option value="Uncategorized"{% if chosen.category == "Uncategorized" %} selected{% endif %}>Uncategorized</option>
      {% for group, names in choices.categories %}<optgroup label="{{ group }}">
        {% for name in names %}<option value="{{ name }}"{% if name == chosen.category %} selected{% endif %}>{{ name }}</option>
        {% endfor %}</optgroup>
      {% endfor %}
    </select>
  </label>
  <label>Merchant <input name="merchant" value="{{ chosen.merchant }}"></label>
  <label>From <input type="date" name="from" value="{{ chosen['from'] }}"></label>
  <label>To <input type="date" name="to" value="{{ chosen['to'] }}"></label>
  <label>Rows <input type="number" name="limit" min="1" max="1000" value="{{ chosen.limit }}"></label>
  {% for key in kept %}<input type="hidden" name="{{ key }}" value="{{ chosen[key] }}">
  {% endfor %}<button type="submit">Show</button>
</form>
{% if kept %}<p class="hint">Also filtered by: {% for key in kept %}{{ key }} {{ chosen[key] }}{% if not loop.last %}, {% endif %}{% endfor %}. <a href="/transactions">Clear all filters</a></p>{% endif %}
{% if error %}<p class="error">{{ error }}</p>
{% elif rows %}
<table>
<thead><tr><th>Date</th><th>Account</th><th>Description</th><th>Category</th><th class="amount">Amount</th><th>Card</th><th>Section</th><th>Person</th></tr></thead>
<tbody>
{% for id, row, category in rows %}<tr><td><a href="/transactions/{{ id }}">{{ row.date }}</a></td><td>{{ row.account }}</td><td>{{ row.description }}</td><td>{{ category }}</td><td class="amount">{{ row.amount }}</td><td>{{ row.card }}</td><td>{{ row.section }}</td><td>{{ row.person }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No transactions.</p>
{% endif %}
{% endblock %}
```

`src/finances/web/templates/reports.html`

```html
{% extends "layout.html" %}
{% block title %}Reports · Finances{% endblock %}
{% block content %}
<h1>Reports</h1>
{% include "messages.html" %}
<h2>Balances</h2>
{% if balances %}
<table>
<thead><tr><th>Account</th><th>Type</th><th class="amount">Balance</th><th>As of</th><th>From</th></tr></thead>
<tbody>
{% for row in balances %}<tr><td>{{ row.account }}</td><td>{{ row.type }}</td><td class="amount">{{ row.balance }}</td><td>{{ row.as_of }}</td><td>{{ row.source }}</td></tr>
{% endfor %}</tbody>
</table>
{% for line in balance_summary %}<p class="summary">{{ line }}</p>
{% endfor %}
{% else %}
<p class="empty">No accounts.</p>
{% endif %}
<h2>Months</h2>
{% if months %}
<table>
<thead><tr><th>Month</th><th class="amount">Spent</th><th class="amount">Income</th><th class="amount">Change</th><th>Covered</th></tr></thead>
<tbody>
{% for row in months %}<tr><td><a href="/reports?month={{ row.month }}">{{ row.month }}</a></td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.income }}</td><td class="amount">{{ row.change }}</td><td>{{ row.covered }}</td></tr>
{% endfor %}</tbody>
</table>
{% for line in month_notes %}<p class="hint">{{ line }}</p>
{% endfor %}
{% endif %}
<h2>Spending</h2>
<form method="get" action="/reports" class="fields">
  <label>Month <input type="month" name="month" value="{{ form.month }}"></label>
  <label>or from <input type="date" name="from" value="{{ form.start }}"></label>
  <label>to <input type="date" name="to" value="{{ form.end }}"></label>
  <label>By
    <select name="by">
      {% for item in bys %}<option value="{{ item }}"{% if item == form.by %} selected{% endif %}>{{ item }}</option>
      {% endfor %}
    </select>
  </label>
  <button type="submit">Show</button>
</form>
{% if spending %}
<p class="summary">{{ spending.heading }}</p>
{% if spending.rows %}
<table>
<thead><tr><th>{{ spending.by|capitalize }}</th><th class="amount">Spent</th><th class="amount">Count</th></tr></thead>
<tbody>
{% for row in spending.rows %}<tr><td><a href="/transactions?from={{ spending.start }}&amp;to={{ spending.end }}&amp;{{ spending.by }}={{ row.label|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.label }}</a></td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.count }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No spending.</p>
{% endif %}
{% for line in spending.summary %}<p class="summary">{{ line }}</p>
{% endfor %}
{% endif %}
{% endblock %}
```

`src/finances/web/templates/insights.html`

```html
{% extends "layout.html" %}
{% block title %}Insights · Finances{% endblock %}
{% block content %}
<h1>Insights</h1>
{% include "messages.html" %}
<form method="get" action="/insights" class="fields">
  <label>Month <input type="month" name="month" value="{{ form.month }}"></label>
  <button type="submit">Show</button>
</form>
{% if report %}
<p class="summary">{{ report.heading }}</p>
<h2>Findings</h2>
{% if report.findings %}
<table>
<thead><tr><th>Severity</th><th>Type</th><th>About</th><th class="amount">Saves a month</th><th>Detail</th></tr></thead>
<tbody>
{% for row in report.findings %}<tr><td>{{ row.severity }}</td><td>{{ row.type }}</td><td>{% if row.type in ("spike", "subscription_overlap") %}<a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;category={{ row.about|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.about }}</a>{% elif row.type in ("frequent_small", "price_increase") %}<a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;merchant={{ row.about|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.about }}</a>{% else %}{{ row.about }}{% endif %}</td><td class="amount">{{ row.saves }}</td><td>{{ row.detail }}</td></tr>
{% endfor %}</tbody>
</table>
<p class="summary">{{ report.findings_summary }}</p>
{% else %}
<p class="empty">No findings.</p>
{% endif %}
<h2>Recurring charges</h2>
{% if report.recurring %}
<table>
<thead><tr><th>Merchant</th><th>Every</th><th class="amount">Amount</th><th class="amount">Monthly</th><th class="amount">Count</th><th>Last</th><th>Next</th></tr></thead>
<tbody>
{% for row in report.recurring %}<tr><td><a href="/transactions?merchant={{ row.merchant|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.merchant }}</a></td><td>{{ row.every }}</td><td class="amount">{{ row.amount }}</td><td class="amount">{{ row.monthly }}</td><td class="amount">{{ row.count }}</td><td>{{ row.last }}</td><td>{{ row.next }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No recurring charges.</p>
{% endif %}
<p class="summary">{{ report.recurring_summary }}</p>
<h2>Merchants</h2>
{% if report.merchants %}
<table>
<thead><tr><th>Merchant</th><th class="amount">Visits</th><th class="amount">Spent</th><th class="amount">Average</th><th class="amount">Baseline</th><th class="amount">Change</th><th class="amount">Weekend</th></tr></thead>
<tbody>
{% for row in report.merchants %}<tr><td><a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;merchant={{ row.merchant|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.merchant }}</a></td><td class="amount">{{ row.visits }}</td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.average }}</td><td class="amount">{{ row.baseline }}</td><td class="amount">{{ row.change }}</td><td class="amount">{{ row.weekend }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No spending.</p>
{% endif %}
{% endif %}
{% endblock %}
```

## Given tests

`tests/integration/test_web_search.py` (28 tests). `test_every_line_opens_exactly_its_transactions` checks R5 for all seven groupings.

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_person, create_rule, set_account_owner
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, texts

HEADINGS = ["Date", "Account", "Description", "Category", "Amount", "Card", "Section", "Person"]
MAY = "from=2026-05-01&to=2026-05-31"
SNACK_DAYS = [
    "2026-05-08",
    "2026-05-07",
    "2026-05-06",
    "2026-05-05",
    "2026-05-04",
    "2026-05-03",
    "2026-05-02",
    "2026-05-01",
]
KINDS = "kind must be one of: spending, income, transfer, unsorted_in, pending"


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The data of tests/e2e/test_cli_spending.py (transactions 1 to 12), plus eight snacks
    from checking on 1 to 8 May (13 to 20). Rules run and transfers are paired."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        pat = create_person(session, "Pat Example")
        set_account_owner(session, card.id, pat.id)
        rows = [
            # account, posted, bought, cents, description, card digits, pending
            (card, date(2026, 5, 2), None, -450, "SQ *ACME COFFEE", "1111", False),
            (card, date(2026, 5, 3), None, -2599, "FOOBAR GROCERY #77", "1111", False),
            (card, date(2026, 5, 10), None, 599, "FOOBAR GROCERY #77", "1111", False),
            (card, date(2026, 6, 1), date(2026, 5, 31), -1250, "ACME COFFEE #12", None, False),
            (card, date(2026, 5, 1), date(2026, 4, 30), -800, "BAZ BOOKS", None, False),
            (checking, date(2026, 5, 20), None, -50000, "PAYMENT TO TEST CARD", None, False),
            (card, date(2026, 5, 21), None, 50000, "PAYMENT THANK YOU", None, False),
            (checking, date(2026, 5, 15), None, 300000, "PAYCHECK EXAMPLE CORP", None, False),
            (checking, date(2026, 5, 16), None, 2500, "VENMO CASHOUT", None, False),
            (card, date(2026, 5, 18), None, -999, "QUUX STREAMING", None, True),
            (checking, date(2026, 5, 25), None, -12000, "ACME UTILITY", None, False),
            (card, date(2026, 5, 12), None, -1500, "BAZ BOOKS", None, False),
        ] + [
            (checking, date(2026, 5, day), None, -300, "QUUX SNACKS", None, False)
            for day in range(1, 9)
        ]
        for number, (account, posted, bought, cents, description, last4, pending) in enumerate(
            rows, start=1
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=posted,
                    transaction_date=bought,
                    amount_cents=cents,
                    description=description,
                    card_last4=last4,
                    is_pending=pending,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for pattern, category in (
            ("ACME COFFEE", "Coffee & Dessert"),
            ("FOOBAR GROCERY", "Groceries"),
            ("PAYCHECK", "Paycheck"),
            ("ACME UTILITY", "Utilities & Internet"),
            ("QUUX SNACKS", "Groceries"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        pair_transfers(session)
    engine.dispose()
    return client


def days(client: TestClient, query: str) -> list[str]:
    return [row[0] for row in page(client, f"/transactions?{query}").rows[1:]]


def links(found: Page) -> list[str]:
    return [link for link in found.links if link.startswith("/transactions?")]


# The Transactions page


def test_the_category_column_and_the_filters(home: TestClient) -> None:
    found = page(home, "/transactions?text=acme")
    assert found.rows == [
        HEADINGS,
        [
            "2026-06-01",
            "Test Card",
            "ACME COFFEE #12",
            "Coffee & Dessert",
            "-$12.50",
            "",
            "",
            "Pat Example",
        ],
        [
            "2026-05-25",
            "Test Checking",
            "ACME UTILITY",
            "Utilities & Internet",
            "-$120.00",
            "",
            "",
            "",
        ],
        [
            "2026-05-02",
            "Test Card",
            "SQ *ACME COFFEE",
            "Coffee & Dessert",
            "-$4.50",
            "••1111",
            "",
            "Pat Example",
        ],
    ]
    form = found.find("/transactions")
    assert form["inputs"]["text"] == ("search", "acme")
    assert form["inputs"]["merchant"] == ("text", "")
    options = form["selects"]["category"]
    assert options[:2] == [("", True), ("Uncategorized", False)]
    assert ("Coffee & Dessert", False) in options and ("Food", False) not in options
    assert len(options) == 36


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("kind=transfer", ["2026-05-21", "2026-05-20"]),
        ("kind=income", ["2026-05-15"]),
        ("kind=unsorted_in", ["2026-05-16"]),
        ("kind=pending", ["2026-05-18"]),
        ("merchant=foobar+grocery", ["2026-05-10", "2026-05-03"]),
        ("merchant=acme", []),
        ("card=1111", ["2026-05-10", "2026-05-03", "2026-05-02"]),
        (
            "category=uncategorized",
            ["2026-05-21", "2026-05-20", "2026-05-18", "2026-05-16", "2026-05-12", "2026-05-01"],
        ),
        ("bank=test+bank&text=payment", ["2026-05-20"]),
        (
            "group=Food&kind=spending&from=2026-05-02&to=2026-05-12",
            [
                "2026-05-10",
                "2026-05-08",
                "2026-05-07",
                "2026-05-06",
                "2026-05-05",
                "2026-05-04",
                "2026-05-03",
                "2026-05-03",
                "2026-05-02",
                "2026-05-02",
            ],
        ),
        ("from=2026-05-31&to=2026-05-31", ["2026-06-01"]),
        ("from=2026-04-30&to=2026-04-30", ["2026-05-01"]),
        ("person=unassigned&kind=spending&limit=2", ["2026-05-25", "2026-05-08"]),
        ("text=SNACKS&account=test+checking", SNACK_DAYS),
    ],
)
def test_filters(home: TestClient, query: str, expected: list[str]) -> None:
    assert days(home, query) == expected


def test_link_filters_are_kept_and_named(home: TestClient) -> None:
    found = page(home, "/transactions?group=Food&bank=Example+Card+Co&card=&kind=spending")
    form = found.find("/transactions")
    assert form["inputs"]["group"] == ("hidden", "Food")
    assert form["inputs"]["bank"] == ("hidden", "Example Card Co")
    assert form["inputs"]["kind"] == ("hidden", "spending")
    assert "card" not in form["inputs"]
    assert texts(found, "hint") == [
        "Also filtered by: group Food, bank Example Card Co, kind spending. Clear all filters"
    ]
    assert "/transactions" in found.links
    assert texts(page(home, "/transactions"), "hint") == []


@pytest.mark.parametrize("kind", ["spend", "SPENDING ", "all"])
def test_a_kind_that_is_not_one(home: TestClient, kind: str) -> None:
    response = home.get(f"/transactions?kind={kind}")
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", KINDS) in found.paragraphs
    assert found.rows == []
    assert found.find("/transactions")["inputs"]["kind"] == ("hidden", kind)


# Drilling down


def test_a_spending_line_opens_its_transactions(home: TestClient) -> None:
    found = page(home, "/reports?month=2026-05")
    assert links(found) == [
        f"/transactions?{MAY}&category=Utilities%20%26%20Internet&kind=spending&limit=1000",
        f"/transactions?{MAY}&category=Groceries&kind=spending&limit=1000",
        f"/transactions?{MAY}&category=Coffee%20%26%20Dessert&kind=spending&limit=1000",
        f"/transactions?{MAY}&category=Uncategorized&kind=spending&limit=1000",
    ]
    shown = page(home, links(found)[2])
    assert [(row[0], row[2]) for row in shown.rows[1:]] == [
        ("2026-06-01", "ACME COFFEE #12"),
        ("2026-05-02", "SQ *ACME COFFEE"),
    ]
    assert days(home, links(found)[3].removeprefix("/transactions?")) == ["2026-05-12"]


@pytest.mark.parametrize(
    "by", ["category", "group", "merchant", "person", "account", "bank", "card"]
)
def test_every_line_opens_exactly_its_transactions(home: TestClient, by: str) -> None:
    found = page(home, f"/reports?month=2026-05&by={by}")
    spending = found.rows[found.rows.index([by.capitalize(), "Spent", "Count"]) + 1 :]
    assert len(links(found)) == len(spending) > 0
    for link, row in zip(links(found), spending, strict=True):
        assert len(page(home, link).rows) - 1 == int(row[2]), (link, row)


def test_insights_open_their_transactions(home: TestClient) -> None:
    found = page(home, "/insights?month=2026-05")
    assert f"/transactions?{MAY}&merchant=QUUX%20SNACKS&kind=spending&limit=1000" in links(found)
    assert f"/transactions?{MAY}&merchant=ACME%20COFFEE&kind=spending&limit=1000" in links(found)
    finding = Page(home.get("/insights?month=2026-05").text).rows[1]
    assert finding[:3] == ["low", "frequent_small", "QUUX SNACKS"]
    assert links(found)[0] == f"/transactions?{MAY}&merchant=QUUX%20SNACKS&kind=spending&limit=1000"
    assert days(home, links(found)[0].removeprefix("/transactions?")) == SNACK_DAYS
```

The change to `tests/integration/test_web_pages.py`, exactly this diff (the new column is empty for its uncategorized rows):

```diff
diff --git a/tests/integration/test_web_pages.py b/tests/integration/test_web_pages.py
index 9db3d25..e12c701 100644
--- a/tests/integration/test_web_pages.py
+++ b/tests/integration/test_web_pages.py
@@ -200,17 +200,26 @@ def test_people_with_none(tmp_settings: Settings, client: TestClient) -> None:
     assert ("empty", "No people.") in Page(client.get("/people").text).paragraphs
 
 
-TRANSACTION_HEADINGS = ["Date", "Account", "Description", "Amount", "Card", "Section", "Person"]
+TRANSACTION_HEADINGS = [
+    "Date",
+    "Account",
+    "Description",
+    "Category",
+    "Amount",
+    "Card",
+    "Section",
+    "Person",
+]
 
 
 def test_transactions(household: TestClient) -> None:
     page = Page(household.get("/transactions").text)
     assert page.rows == [
         TRANSACTION_HEADINGS,
-        ["2026-05-08", "Test <Card>", "ACME <i>8</i>", "-$8.00", "••2222", "purchases", "Sam"],
-        ["2026-05-07", "Test Checking", "ACME <i>7</i>", "-$7.00", "", "purchases", "Joint"],
-        ["2026-05-06", "Test <Card>", "ACME <i>6</i>", "-$6.00", "", "purchases", "Alex"],
-        ["2026-05-05", "Test Savings", "ACME <i>5</i>", "$10.00", "", "", ""],
+        ["2026-05-08", "Test <Card>", "ACME <i>8</i>", "", "-$8.00", "••2222", "purchases", "Sam"],
+        ["2026-05-07", "Test Checking", "ACME <i>7</i>", "", "-$7.00", "", "purchases", "Joint"],
+        ["2026-05-06", "Test <Card>", "ACME <i>6</i>", "", "-$6.00", "", "purchases", "Alex"],
+        ["2026-05-05", "Test Savings", "ACME <i>5</i>", "", "$10.00", "", "", ""],
     ]
     assert page.options["account"] == [
         ("", "All accounts", True),
```

## Tests to write

`tests/integration/test_transaction_search.py` (import helpers from `tests/support.py` where they apply):

- `search_transactions`: messages 4 to 6 and their order; fields with surrounding spaces; `Joint` and a person's name in another case; an account given in another case; `limit` cutting after the filters;
- `list_transactions_by_day`: no bounds, one bound, pending included, the order;
- `flows_for` marks a pending transaction `PENDING`, and `load_flows` over a month gives the same flows as before (a month with a pending transaction, a transfer, and income).

## Rules for this phase

- **Thin.** The route reads fields and calls `search_transactions`, `found_rows`, and the existing helpers; matching and labels live in `analysis` and `views`.
- **No JavaScript.**

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_web_search.py`, 28 tests;
- also `.venv/bin/python -m pytest tests/integration/test_web_pages.py tests/integration/test_web_reports.py tests/integration/test_web_insights.py tests/e2e/test_cli_spending.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.analysis --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|casefold|flow_kind|clean_merchant" -- src/finances/web` and `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16e: find and drill down (YYYY-MM-DD)`.
