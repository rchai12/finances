# Phase 16i: account pages

## Goal

Every account has its own page, and every account name opens it. After this phase:

- `/account?name=NAME` shows the account: its details and newest balance, its cards, its **spending by group** for a month (each group opening exactly its transactions), its **spent and income for the last 12 months**, its **balance history**, and its **latest 50 transactions** with a link to search and filter them on the Transactions page;
- `&card=DIGITS` shows the same page for one card of the account (an account with several cardholders), and `&month=YYYY-MM` chooses the month;
- an account's name opens its page on the Accounts page, the balances of the Reports page, the Account column of the Transactions page, and From and To on the Transfers page; the Transactions page's card digits open the account page for that card.

The figures follow the rules of Phases 12a and 12b, for this account (and card) only. Charts come in Phase 16k, which turns these tables into charts beside them.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/analysis/spending.py` (`load_flows`), `src/finances/domain/spending.py`, `src/finances/analysis/search.py`, `src/finances/analysis/people.py` (`load_attribution`)
- `src/finances/views/transactions.py` (`found_rows`), `src/finances/views/balances.py` (how a balance's source is named)
- `src/finances/web/app.py`: `_today`, `_render` (its `section`), the transaction page's 404

## Starting state

N is `2798` when Phase 16h is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/repositories.py` | new: `list_balance_snapshots` (R1) |
| `src/finances/analysis/account_page.py` | new (R2) |
| `src/finances/views/account_page.py` | new (R3) |
| `src/finances/web/app.py` | `GET /account` (R4) |
| `src/finances/web/templates/account.html` | new: given |
| `src/finances/web/templates/accounts.html`, `reports.html`, `transactions.html`, `transfers.html` | replaced: given (links only) |
| `tests/integration/test_web_account_page.py` | new: given |
| `tests/integration/test_account_page_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Charts, the chart library, and the security policy (16k).
- Editing anything from this page (Phase 16j's forms stay where they are); a page per card outside its account.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/db/repositories.py
def list_balance_snapshots(session: Session, account_id: int) -> list[BalanceSnapshot]: ...  # newest first

# src/finances/analysis/account_page.py
@dataclass(frozen=True)
class AccountMonth:
    start: date
    spent_cents: int
    income_cents: int


@dataclass(frozen=True)
class AccountPage:
    account: Account
    owner: str | None            # a person's name, JOINT, or None
    card: str                    # the chosen card's digits, or ""
    cards: list[str]             # the account's card digits, sorted
    spending: list[SpendingLine] # by group, for the chosen month
    months: list[AccountMonth]   # 12 months ending with today's, oldest first
    balances: list[BalanceSnapshot]
    latest: list[FoundTransaction]


def account_page(
    session: Session, account: Account, card: str, start: date, end: date, today: date
) -> AccountPage: ...

# src/finances/views/account_page.py
@dataclass(frozen=True)
class AccountMonthRow:
    month: str   # YYYY-MM
    spent: str
    income: str


@dataclass(frozen=True)
class BalanceHistoryRow:
    date: str
    balance: str
    source: str  # "statement" or "SimpleFIN"


def account_detail_rows(page: AccountPage) -> list[tuple[str, str]]: ...
def group_rows(page: AccountPage) -> list[SpendingRow]: ...
def account_month_rows(page: AccountPage) -> list[AccountMonthRow]: ...
def balance_history_rows(page: AccountPage) -> list[BalanceHistoryRow]: ...
```

New message, in full: `card not found` (a `ValueError`; the page answers `404` with `error.html`, as it does for `account not found`).

## Requirements

- **R1.** `list_balance_snapshots` returns the account's snapshots, latest `as_of_date` first, then highest id first.
- **R2.** `account_page` refuses a `card` that is not empty and not among the account's card digits (`card not found`). It loads Phase 12a's flows once, from the first of the 12 months to the later of `end` and today's month's end, keeps those whose `account` is the account's name (and whose `card` is `card` when one is chosen), and builds: `spending` from `spending_lines(..., "group")` over the days `start` to `end`; `months` from `summarize` per month (`months_ending(today, 12)`); `owner` from `load_attribution(session).owner(account.id)`; `cards` from the account's transactions' `card_last4`, distinct and sorted; `balances` from `list_balance_snapshots`; `latest` from `search_transactions(TransactionQuery(account=name, card=card, limit=50))`.
- **R3.** `account_detail_rows` gives, in order: `Name`, `Institution`, `Type` (the type's value), `Last 4` (or empty), `Owner` (the name, `Joint`, or empty), `Status` (`open` or `closed`), and `Balance`: `$X on DATE (SOURCE)` from the newest snapshot, SOURCE `statement` or `SimpleFIN`, or `No balance yet`. The row functions format money with `format_cents` and dates in ISO.
- **R4.** `GET /account` reads `name`, `card`, and `month` as text. It checks the database as the other pages do; finds the account by name (`get_account_by_name`; none or empty answers `404` with `error.html`, `account not found`, and a link back to `/accounts`); reads `month` with `month_range` (empty means the month of `_today()`; a bad month renders the page with status `400`, the message as `error`, and no spending); then calls `account_page` (`card not found` answers `404` as above). It renders `account.html` with `section` `accounts` (so the menu marks Accounts), `name` (stored), `card`, `cards`, `detail`, `month_label` and `month_text` (the month as `YYYY-MM`, and as sent), `start` and `end` (ISO), `spending` (`group_rows`), `months`, `balances`, `transactions` (`found_rows(page.latest, ...)`), and `error`.
- **R5.** The given templates are used as shown; the links inside cells keep every table's columns and text. One read session; the route holds no rule.

## Given templates

`src/finances/web/templates/account.html`

```html
{% extends "layout.html" %}
{% block title %}{{ name }} · Finances{% endblock %}
{% block content %}
<h1>{{ name }}{% if card %} · card ending {{ card }}{% endif %}</h1>
{% include "messages.html" %}
<p><a href="/accounts">All accounts</a>{% if card %} · <a href="/account?name={{ name|urlencode }}">All cards of this account</a>{% endif %}</p>
<table class="detail">
<tbody>
{% for label, value in detail %}<tr><th>{{ label }}</th><td>{{ value }}</td></tr>
{% endfor %}</tbody>
</table>
{% if cards %}<p class="cards">Cards: {% for digits in cards %}<a href="/account?name={{ name|urlencode }}&amp;card={{ digits }}">{{ digits }}</a>{% if not loop.last %}, {% endif %}{% endfor %}</p>{% endif %}
<h2>Spending in {{ month_label }}</h2>
<form method="get" action="/account" class="fields">
  <input type="hidden" name="name" value="{{ name }}">
  {% if card %}<input type="hidden" name="card" value="{{ card }}">{% endif %}
  <label>Month <input type="month" name="month" value="{{ month_text }}"></label>
  <button type="submit">Show</button>
</form>
{% if spending %}
<table>
<thead><tr><th>Group</th><th class="amount">Spent</th><th class="amount">Count</th></tr></thead>
<tbody>
{% for row in spending %}<tr><td><a href="/transactions?account={{ name|urlencode }}{% if card %}&amp;card={{ card }}{% endif %}&amp;from={{ start }}&amp;to={{ end }}&amp;group={{ row.label|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.label }}</a></td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.count }}</td></tr>
{% endfor %}</tbody>
</table>
{% elif not error %}
<p class="empty">No spending in {{ month_label }}.</p>
{% endif %}
<h2>Months</h2>
<table>
<thead><tr><th>Month</th><th class="amount">Spent</th><th class="amount">Income</th></tr></thead>
<tbody>
{% for row in months %}<tr><td><a href="/account?name={{ name|urlencode }}{% if card %}&amp;card={{ card }}{% endif %}&amp;month={{ row.month }}">{{ row.month }}</a></td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.income }}</td></tr>
{% endfor %}</tbody>
</table>
<h2>Balance history</h2>
{% if balances %}
<table>
<thead><tr><th>Date</th><th class="amount">Balance</th><th>From</th></tr></thead>
<tbody>
{% for row in balances %}<tr><td>{{ row.date }}</td><td class="amount">{{ row.balance }}</td><td>{{ row.source }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No balances yet.</p>
{% endif %}
<h2>Latest transactions</h2>
<p><a href="/transactions?account={{ name|urlencode }}{% if card %}&amp;card={{ card }}{% endif %}">Search and filter this account's transactions</a></p>
{% if transactions %}
<table>
<thead><tr><th>Date</th><th>Description</th><th>Category</th><th class="amount">Amount</th><th>Card</th><th>Person</th></tr></thead>
<tbody>
{% for id, row, category in transactions %}<tr><td><a href="/transactions/{{ id }}">{{ row.date }}</a></td><td>{{ row.description }}</td><td>{{ category }}</td><td class="amount">{{ row.amount }}</td><td>{{ row.card }}</td><td>{{ row.person }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No transactions.</p>
{% endif %}
{% endblock %}
```

`src/finances/web/templates/accounts.html`

```html
{% extends "layout.html" %}
{% block title %}Accounts · Finances{% endblock %}
{% block content %}
<h1>Accounts</h1>
{% include "messages.html" %}
{% if closed %}<p><a href="/accounts">Hide closed accounts</a></p>{% else %}<p><a href="/accounts?closed=true">Show closed accounts</a></p>{% endif %}
{% if rows %}
<table>
<thead><tr><th>Name</th><th>Institution</th><th>Type</th><th>Last 4</th><th>Active</th><th>Owner</th></tr></thead>
<tbody>
{% for row in rows %}<tr><td><a href="/account?name={{ row.name|urlencode }}">{{ row.name }}</a></td><td>{{ row.institution }}</td><td>{{ row.type }}</td><td>{{ row.last4 }}</td><td>{{ row.active }}</td><td>{{ row.owner }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No accounts.</p>
{% endif %}
<h2>Add an account</h2>
<form method="post" action="/accounts/add" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Name <input name="name" required maxlength="100" value="{{ form.name }}"></label>
  <label>Institution <input name="institution" required maxlength="100" value="{{ form.institution }}"></label>
  <label>Type
    <select name="type">
      {% for kind in types %}<option value="{{ kind }}"{% if kind == form.type %} selected{% endif %}>{{ kind }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Last 4 digits <input name="last4" maxlength="4" inputmode="numeric" value="{{ form.last4 }}"></label>
  <button type="submit">Add account</button>
</form>
{% if every_account %}
<h2>Set an owner</h2>
<form method="post" action="/accounts/owner" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Account
    <select name="account">
      {% for name in every_account %}<option value="{{ name }}">{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Owner
    <select name="owner">
      {% for name in people %}<option value="{{ name }}">{{ name }}</option>
      {% endfor %}
      <option value="joint">Joint</option>
    </select>
  </label>
  <button type="submit">Save owner</button>
</form>
{% endif %}
{% if every_account %}
<h2>Rename an account</h2>
<form method="post" action="/accounts/rename" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Account
    <select name="account">
      {% for name in every_account %}<option value="{{ name }}"{% if name == rename_form.account %} selected{% endif %}>{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <label>New name <input name="to" required maxlength="100" value="{{ rename_form.to }}"></label>
  <button type="submit">Rename</button>
</form>
<h2>Close or reopen an account</h2>
<p class="hint">A closed account is left out of balances, net worth, coverage, and the account choices; its transactions are kept and still count for the days they happened.</p>
<form method="post" action="/accounts/active" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Account
    <select name="account">
      {% for name in every_account %}<option value="{{ name }}">{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <button type="submit" name="active" value="false">Close</button>
  <button type="submit" name="active" value="true">Reopen</button>
</form>
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
{% for row in balances %}<tr><td><a href="/account?name={{ row.account|urlencode }}">{{ row.account }}</a></td><td>{{ row.type }}</td><td class="amount">{{ row.balance }}</td><td>{{ row.as_of }}</td><td>{{ row.source }}</td></tr>
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

`src/finances/web/templates/transactions.html`

```html
{% extends "layout.html" %}
{% block title %}Transactions · Finances{% endblock %}
{% block content %}
<h1>Transactions</h1>
{% include "messages.html" %}
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
{% if rows %}
<p class="selection"><a href="/transactions?{{ select_all_query }}">Select all shown</a> <a href="/transactions?{{ back }}">Clear the selection</a></p>
<form method="post" action="/transactions/bulk" class="bulk">
<input type="hidden" name="csrf" value="{{ csrf }}">
<input type="hidden" name="back" value="{{ back }}">
<table>
<thead><tr><th>Date</th><th>Account</th><th>Description</th><th>Category</th><th class="amount">Amount</th><th>Card</th><th>Section</th><th>Person</th></tr></thead>
<tbody>
{% for id, row, category in rows %}<tr><td><input type="checkbox" name="id" value="{{ id }}"{% if select_all %} checked{% endif %}> <a href="/transactions/{{ id }}">{{ row.date }}</a></td><td><a href="/account?name={{ row.account|urlencode }}">{{ row.account }}</a></td><td>{{ row.description }}</td><td>{{ category }}</td><td class="amount">{{ row.amount }}</td><td>{% if row.card %}<a href="/account?name={{ row.account|urlencode }}&amp;card={{ row.card[-4:] }}">{{ row.card }}</a>{% endif %}</td><td>{{ row.section }}</td><td>{{ row.person }}</td></tr>
{% endfor %}</tbody>
</table>
<p class="fields">
  <label>Category for the chosen
    {% with choices = choices.categories, selected = "" %}{% include "category_select.html" %}{% endwith %}
  </label>
  <button type="submit" name="action" value="set">Set category</button>
  <button type="submit" name="action" value="clear" formnovalidate>Leave to the rules</button>
</p>
</form>
{% elif not error %}
<p class="empty">No transactions.</p>
{% endif %}
{% endblock %}
```

`src/finances/web/templates/transfers.html`

```html
{% extends "layout.html" %}
{% block title %}Transfers · Finances{% endblock %}
{% block content %}
<h1>Transfers</h1>
{% include "messages.html" %}
<p class="hint">Money that leaves one of your accounts and arrives in another, the same amount within {{ max_days }} days, is a transfer. When there is only one match it is paired by itself; the rest wait here for you.</p>
<form method="post" action="/transfers/find" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <button type="submit">Find transfers</button>
</form>
<h2>Waiting for review</h2>
{% if suggestions %}
<table>
<thead><tr><th>Out</th><th>Out date</th><th>From</th><th>In</th><th>In date</th><th>To</th><th class="amount">Amount</th><th></th></tr></thead>
<tbody>
{% for row in suggestions %}<tr><td><a href="/transactions/{{ row.out_id }}">{{ row.out_id }}</a></td><td>{{ row.out_date }}</td><td><a href="/account?name={{ row.from_account|urlencode }}">{{ row.from_account }}</a></td><td><a href="/transactions/{{ row.in_id }}">{{ row.in_id }}</a></td><td>{{ row.in_date }}</td><td><a href="/account?name={{ row.to_account|urlencode }}">{{ row.to_account }}</a></td><td class="amount">{{ row.amount }}</td><td><form method="post" action="/transfers/confirm" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="out" value="{{ row.out_id }}"><input type="hidden" name="in" value="{{ row.in_id }}"><button type="submit">Transfer</button></form> <form method="post" action="/transfers/reject" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="out" value="{{ row.out_id }}"><input type="hidden" name="in" value="{{ row.in_id }}"><button type="submit">Not a transfer</button></form></td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No transfers wait for review.</p>
{% endif %}
<h2>Transfers</h2>
{% if pairs %}
<table>
<thead><tr><th>Pair</th><th>Date</th><th>From</th><th>To</th><th class="amount">Amount</th><th>Out</th><th>In</th><th>How</th><th></th></tr></thead>
<tbody>
{% for row in pairs %}<tr><td>{{ row.pair }}</td><td>{{ row.date }}</td><td><a href="/account?name={{ row.from_account|urlencode }}">{{ row.from_account }}</a></td><td><a href="/account?name={{ row.to_account|urlencode }}">{{ row.to_account }}</a></td><td class="amount">{{ row.amount }}</td><td><a href="/transactions/{{ row.out_id }}">{{ row.out_id }}</a></td><td><a href="/transactions/{{ row.in_id }}">{{ row.in_id }}</a></td><td>{{ row.how }}</td><td><form method="post" action="/transfers/unpair" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="pair" value="{{ row.pair }}"><button type="submit">Unpair</button></form></td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No transfers.</p>
{% endif %}
{% endblock %}
```

## Given tests

`tests/integration/test_web_account_page.py` (11 tests). It sets `finances.web.app._today` to 25 May 2026. Its spending and month figures come from Phase 12a's `load_flows`, `spending_lines`, and `summarize` on its data, filtered to the account and card.

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
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_person,
    create_rule,
    set_account_owner,
)
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

TODAY = date(2026, 5, 25)
CARD = "/account?name=Test%20Card"
SPENDING = ["Group", "Spent", "Count"]
MONTHS = ["Month", "Spent", "Income"]
BALANCES = ["Date", "Balance", "From"]
LATEST = ["Date", "Description", "Category", "Amount", "Card", "Person"]
DETAIL = [
    ["Name", "Test Card"],
    ["Institution", "Test Bank"],
    ["Type", "credit_card"],
    ["Last 4", "9999"],
    ["Owner", "Pat Example"],
    ["Status", "open"],
    ["Balance", "-$612.34 on 2026-05-20 (SimpleFIN)"],
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Test Card (Pat's) with cards 1111 and 2222, three balances, and a payment from Test
    Checking that pairs as a transfer; Test Checking has a utility bill of its own."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card", last4="9999")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        pat = create_person(session, "Pat Example")
        set_account_owner(session, card.id, pat.id)
        add_balance_snapshot(session, card.id, date(2026, 3, 31), -40000, DataSource.STATEMENT)
        add_balance_snapshot(session, card.id, date(2026, 4, 30), -45000, DataSource.STATEMENT)
        add_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.AGGREGATOR)
        rows = [
            (card, date(2026, 4, 12), -3000, "FOOBAR GROCERY", "1111"),
            (card, date(2026, 5, 3), -1500, "BAZ BOOKS", "2222"),
            (card, date(2026, 5, 10), -20000, "FOOBAR GROCERY", "1111"),
            (card, date(2026, 5, 12), -500, "ACME COFFEE", "2222"),
            (card, date(2026, 5, 15), 599, "FOOBAR GROCERY", "1111"),
            (checking, date(2026, 5, 5), -12000, "ACME UTILITY", None),
            (card, date(2026, 5, 20), -3500, "LATE FEE", None),
            (checking, date(2026, 5, 20), -50000, "PAYMENT TO TEST CARD", None),
            (card, date(2026, 5, 21), 50000, "PAYMENT THANK YOU", None),
        ]
        for number, (account, day, cents, description, last4) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    card_last4=last4,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for pattern, category in (
            ("FOOBAR", "Groceries"),
            ("ACME COFFEE", "Coffee & Dessert"),
            ("ACME UTILITY", "Utilities & Internet"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        pair_transfers(session)
    engine.dispose()
    return client


def table(found: Page, heading: list[str]) -> list[list[str]]:
    start = found.rows.index(heading)
    end = start + 1
    while end < len(found.rows) and len(found.rows[end]) == len(heading):
        if found.rows[end] in (SPENDING, MONTHS, BALANCES, LATEST):
            break
        end += 1
    return found.rows[start:end]


def test_every_account_name_and_card_opens_the_account_page(home: TestClient) -> None:
    assert CARD in page(home, "/accounts").links
    assert CARD in page(home, "/reports?month=2026-05").links
    transactions = page(home, "/transactions").links
    assert CARD in transactions and f"{CARD}&card=1111" in transactions
    assert "/account?name=Test%20Checking" in page(home, "/transfers").links


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get(CARD)
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_the_account_page(home: TestClient) -> None:
    response = home.get(CARD)
    assert response.status_code == 200
    assert 'href="/accounts" aria-current="page">Accounts</a>' in response.text
    found = Page(response.text)
    assert found.rows[:7] == DETAIL
    assert texts(found, "cards") == ["Cards: 1111, 2222"]
    assert table(found, SPENDING) == [
        SPENDING,
        ["Food", "$199.01", "3"],
        ["Uncategorized", "$50.00", "2"],
    ]
    months = table(found, MONTHS)
    assert len(months) == 13
    assert months[1] == ["2025-06", "$0.00", "$0.00"]
    assert months[-2:] == [["2026-04", "$30.00", "$0.00"], ["2026-05", "$249.01", "$0.00"]]
    assert table(found, BALANCES) == [
        BALANCES,
        ["2026-05-20", "-$612.34", "SimpleFIN"],
        ["2026-04-30", "-$450.00", "statement"],
        ["2026-03-31", "-$400.00", "statement"],
    ]
    assert table(found, LATEST) == [
        LATEST,
        ["2026-05-21", "PAYMENT THANK YOU", "", "$500.00", "", "Pat Example"],
        ["2026-05-20", "LATE FEE", "", "-$35.00", "", "Pat Example"],
        ["2026-05-15", "FOOBAR GROCERY", "Groceries", "$5.99", "••1111", "Pat Example"],
        ["2026-05-12", "ACME COFFEE", "Coffee & Dessert", "-$5.00", "••2222", "Pat Example"],
        ["2026-05-10", "FOOBAR GROCERY", "Groceries", "-$200.00", "••1111", "Pat Example"],
        ["2026-05-03", "BAZ BOOKS", "", "-$15.00", "••2222", "Pat Example"],
        ["2026-04-12", "FOOBAR GROCERY", "Groceries", "-$30.00", "••1111", "Pat Example"],
    ]
    for link in (
        "/transactions?account=Test%20Card&from=2026-05-01&to=2026-05-31&group=Food&kind=spending&limit=1000",
        f"{CARD}&month=2026-04",
        f"{CARD}&card=1111",
        "/transactions?account=Test%20Card",
    ):
        assert link in found.links, link


def test_one_card_of_the_account(home: TestClient) -> None:
    found = page(home, f"{CARD}&card=2222")
    assert "<h1>Test Card · card ending 2222</h1>" in home.get(f"{CARD}&card=2222").text
    assert found.rows[:7] == DETAIL
    assert table(found, SPENDING) == [
        SPENDING,
        ["Uncategorized", "$15.00", "1"],
        ["Food", "$5.00", "1"],
    ]
    assert table(found, MONTHS)[-1] == ["2026-05", "$20.00", "$0.00"]
    assert [row[1] for row in table(found, LATEST)[1:]] == ["ACME COFFEE", "BAZ BOOKS"]
    assert f"{CARD}" in found.links


def test_a_group_line_opens_exactly_its_transactions(home: TestClient) -> None:
    for query, count in (("", 3), ("&card=1111", 2)):
        found = page(home, f"{CARD}{query}")
        food = next(link for link in found.links if "group=Food" in link)
        assert len(page(home, food).rows) - 1 == count, food


def test_another_month(home: TestClient) -> None:
    found = page(home, f"{CARD}&month=2026-04")
    assert table(found, SPENDING) == [SPENDING, ["Food", "$30.00", "1"]]
    assert found.find("/account")["inputs"]["month"] == ("month", "2026-04")
    assert table(found, MONTHS)[-1] == ["2026-05", "$249.01", "$0.00"]
    found = page(home, f"{CARD}&month=2026-02")
    assert ("empty", "No spending in 2026-02.") in found.paragraphs


@pytest.mark.parametrize(
    ("query", "status", "message"),
    [
        ("/account?name=Nope", 404, "account not found"),
        ("/account", 404, "account not found"),
        (f"{CARD}&card=3333", 404, "card not found"),
        (f"{CARD}&card=12", 404, "card not found"),
        (f"{CARD}&month=2026-13", 400, "month must be a year and month, like 2026-05"),
    ],
)
def test_refused(home: TestClient, query: str, status: int, message: str) -> None:
    response = home.get(query)
    assert response.status_code == status
    assert ("error", message) in Page(response.text).paragraphs
```

## Tests to write

`tests/integration/test_account_page_more.py`:

- `list_balance_snapshots` with a statement and a SimpleFIN snapshot on the same day (higher id first);
- a closed account's page (`Status` `closed`); an account with no card digits (no Cards line); a joint account (`Owner` `Joint`);
- a month in which the account has income (a refund is not income; an income category is);
- a `month` later than today's month (the flows reach its end).

## Rules for this phase

- **No JavaScript** yet (16k). **Thin**, as R5.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_web_account_page.py`, 11 tests;
- also `.venv/bin/python -m pytest tests/integration/test_web_pages.py tests/integration/test_web_search.py tests/integration/test_web_transfers.py tests/integration/test_web_reports.py tests/integration/test_web_accounts_and_bulk.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.analysis --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|timedelta|sum\(" -- src/finances/web` and `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16i: account pages (YYYY-MM-DD)`.
