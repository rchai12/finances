# Phase 16j: accounts and bulk categorizing

## Goal

The household renames and closes accounts and categorizes many transactions at once, in the browser and the terminal. After this phase:

- an **account can be renamed, closed, and reopened**; a closed account leaves balances, net worth, coverage, and the account choices, and its transactions are kept and still count for the days they happened;
- **several transactions can be categorized at once**: on the Transactions page a checkbox in each row's date cell, **Select all shown** (a link), a category choice, and **Set category** or **Leave to the rules**; in the terminal, `--id` may be given several times.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-16f-editing-categories-and-rules.md` (built just before)
- `src/finances/db/repositories.py`: `create_account`, `get_account_by_name`, `set_category_by_hand`, `clear_category_by_hand`, `_leaf_category`
- `src/finances/cli/accounts.py`, `src/finances/cli/categories.py` (`set_category_command`)
- `src/finances/web/app.py`: the Accounts and Transactions routes, `_search_query`
- `tests/support.py`

## Starting state

N is the passed count in Phase 16f's progress entry (`Tests: ... -> N`).

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/repositories.py` | new: `rename_account`, `set_account_active`, `set_categories_by_hand`, `clear_categories_by_hand` (R1 to R3) |
| `src/finances/cli/accounts.py` | `fin accounts rename`, `deactivate`, `activate` (R4) |
| `src/finances/cli/categories.py` | `fin transactions set-category` with several ids (R5) |
| `src/finances/web/app.py` | five notices, the routes of Part 3 (R6 to R8) |
| `src/finances/web/templates/accounts.html`, `transactions.html` | replaced: given |
| `tests/e2e/test_cli_accounts_and_bulk.py`, `tests/integration/test_web_accounts_and_bulk.py` | new: given |
| `tests/integration/test_account_and_bulk_repositories.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Changing an account's type, institution, last four digits, or currency; deleting an account; anything about SimpleFIN mappings when an account closes (sync continues as before).
- Applying a category to every transaction a filter matches without choosing them; JavaScript.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/db/repositories.py
def rename_account(session: Session, account_id: int, new_name: str) -> Account: ...
def set_account_active(session: Session, account_id: int, active: bool) -> Account: ...
def set_categories_by_hand(session: Session, transaction_ids: Iterable[int], category: str) -> tuple[int, Category]: ...  # (how many, category)
def clear_categories_by_hand(session: Session, transaction_ids: Iterable[int]) -> int: ...
```

None of these commit; the caller does.

Messages, in full (each a `ValueError` or the existing `AccountExistsError`):

| Where | When | Message |
|---|---|---|
| accounts | no account has that name | the existing `account not found` |
| rename account | name empty, too long, or another account's (ignoring case) | the existing messages of `create_account` |
| web close or reopen | `active` not `true` or `false` | `choose Close or Reopen` |
| bulk | no ids | `choose at least one transaction` |
| bulk | more than 1000 distinct ids | `at most 1000 transactions at once` |
| bulk | an id that is not a whole number, or no such transaction | the existing `transaction not found` |
| bulk, set | the category | the existing `_leaf_category` messages |
| web bulk | `action` not `set` or `clear` | `choose Set category or Leave to the rules` |

## Requirements

### Part 1: repositories

- **R1.** `rename_account` strips the new name, applies `create_account`'s name checks (another account with the name, ignoring case; the account's own name in another case is allowed), and renames it.
- **R2.** `set_account_active` sets `is_active` and returns the account.
- **R3.** `set_categories_by_hand` and `clear_categories_by_hand` take the distinct ids in the order given, refuse an empty set and more than 1000, check that every transaction exists (and, for set, the category) before changing any, then set each by hand or remove each assignment. They return how many distinct transactions they changed. The caller of `clear_categories_by_hand` runs `categorize`.

### Part 2: the terminal

Every command checks the schema first and uses one session.

- **R4.** `fin accounts rename --account NAME --to NEW` prints `Renamed account "OLD" to "NEW".`; `fin accounts deactivate --account NAME` prints `Account "NAME" is closed.`; `fin accounts activate --account NAME` prints `Account "NAME" is open again.`
- **R5.** `fin transactions set-category` takes `--id` one or more times. With one distinct id its output is unchanged. With several: `N transactions: CATEGORY, set by hand.`, or `N transactions: category left to the rules.` followed by the categorize line.

### Part 3: the web

Every `POST` runs the existing checks (origin, form token, database) and answers `303` with `notice=KEY`. Notices, in full: `account-renamed` `Account renamed.`; `account-closed` `Account closed.`; `account-reopened` `Account reopened.`; `bulk-set` `Category set by hand on the chosen transactions.`; `bulk-cleared` `The chosen transactions were left to the rules, and the rules were run again.`

- **R6.** The Accounts page gains `rename_form` (`account`, `to`). `POST /accounts/rename` (`account`, `to`) and `POST /accounts/active` (`account`, `active`) find the account by name, then call R1 or R2; done: `/accounts?notice=account-renamed`, `account-closed`, or `account-reopened`; refused: the Accounts page with status `400` (the rename form holding what was sent).
- **R7.** `GET /transactions` also passes `back` (the page's own filter fields that were sent and are not empty, in the order of its fields, URL-encoded), `select_all_query` (`back` plus `&select=all`, or `select=all` when `back` is empty), and `select_all` (the `select` field is `all`).
- **R8.** `POST /transactions/bulk` (`id` any number of times, `category`, `action`, `back`) reads `back` keeping only the page's filter fields; checks the ids (whole numbers), then `action`; then calls `set_categories_by_hand`, or `clear_categories_by_hand` and `categorize`, in one session. Done: `/transactions?BACK&notice=bulk-set` (or `bulk-cleared`), or `/transactions?notice=...` when `back` keeps nothing. Refused: the Transactions page for `back`'s filters, with status `400` and the message; nothing changes.
- **R9.** The given templates are used as shown (the checkbox sits inside each row's date cell, so the table's columns, and the earlier tests that read them, do not change); the routes hold no rule.

## Given templates

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
{% for row in rows %}<tr><td>{{ row.name }}</td><td>{{ row.institution }}</td><td>{{ row.type }}</td><td>{{ row.last4 }}</td><td>{{ row.active }}</td><td>{{ row.owner }}</td></tr>
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
{% for id, row, category in rows %}<tr><td><input type="checkbox" name="id" value="{{ id }}"{% if select_all %} checked{% endif %}> <a href="/transactions/{{ id }}">{{ row.date }}</a></td><td>{{ row.account }}</td><td>{{ row.description }}</td><td>{{ category }}</td><td class="amount">{{ row.amount }}</td><td>{{ row.card }}</td><td>{{ row.section }}</td><td>{{ row.person }}</td></tr>
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

## Given tests

29 tests in two files, both importing from `tests/support.py`.

`tests/e2e/test_cli_accounts_and_bulk.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, list_categories, list_category_assignments
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, run, table_rows

LINE = "Categorized 4 transactions: {} changed, {} without a category."


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """Card: 1 and 2 coffee, 3 groceries; checking: 4 a paycheck. Rule 1 ACME COFFEE to
    Coffee & Dessert, rule 2 FOOBAR to Groceries; 4 is set to Dining by hand."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        for number, (account, cents, description) in enumerate(
            (
                (card, -450, "SQ *ACME COFFEE"),
                (card, -500, "ACME COFFEE #12"),
                (card, -2599, "FOOBAR GROCERY #77"),
                (checking, 300000, "PAYCHECK EXAMPLE CORP"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    assert (
        run("rules", "add", "--pattern", "ACME COFFEE", "--category", "Coffee & Dessert").exit_code
        == 0
    )
    assert run("rules", "add", "--pattern", "FOOBAR", "--category", "Groceries").exit_code == 0
    assert run("transactions", "set-category", "--id", "4", "--category", "Dining").exit_code == 0
    return tmp_settings


def categories_of() -> dict[int, str]:
    """Each categorized transaction's category name."""
    engine = get_engine()
    with session_scope(engine) as session:
        names = {category.id: category.name for category in list_categories(session)}
        found = {
            transaction_id: names[assignment.category_id]
            for transaction_id, assignment in list_category_assignments(session).items()
        }
    engine.dispose()
    return found


@pytest.mark.parametrize(
    "args",
    [
        ("accounts", "rename", "--account", "Test Card", "--to", "Family Card"),
        ("accounts", "deactivate", "--account", "Test Card"),
        ("accounts", "activate", "--account", "Test Card"),
    ],
)
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


# Accounts


def test_rename_close_and_reopen_an_account(money: Settings) -> None:
    result = run("accounts", "rename", "--account", "test card", "--to", " Family Card ")
    assert (result.exit_code, result.stdout) == (
        0,
        'Renamed account "Test Card" to "Family Card".\n',
    )
    assert run("accounts", "deactivate", "--account", "family card").stdout == (
        'Account "Family Card" is closed.\n'
    )
    assert [row[0] for row in table_rows(run("accounts", "list").stdout)[1:]] == ["Test Checking"]
    assert run("accounts", "activate", "--account", "Family Card").stdout == (
        'Account "Family Card" is open again.\n'
    )
    assert [row[0] for row in table_rows(run("accounts", "list").stdout)[1:]] == [
        "Family Card",
        "Test Checking",
    ]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("rename", "--account", "Nope", "--to", "Other"), "account not found"),
        (
            ("rename", "--account", "Test Card", "--to", "test checking"),
            "an account with this name already exists",
        ),
        (("rename", "--account", "Test Card", "--to", "  "), "account name must not be empty"),
        (
            ("rename", "--account", "Test Card", "--to", "N" * 101),
            "account name must be at most 100 characters",
        ),
        (("deactivate", "--account", "Nope"), "account not found"),
        (("activate", "--account", "Nope"), "account not found"),
    ],
)
def test_a_refused_account_change(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("accounts", *args), message)


# Several transactions at once


def test_set_and_clear_several_transactions(money: Settings) -> None:
    result = run(
        "transactions",
        "set-category",
        "--id",
        "1",
        "--id",
        "3",
        "--id",
        "1",
        "--category",
        "dining",
    )
    assert (result.exit_code, result.stdout) == (0, "2 transactions: Dining, set by hand.\n")
    assert categories_of() == {1: "Dining", 2: "Coffee & Dessert", 3: "Dining", 4: "Dining"}
    result = run("transactions", "set-category", "--id", "1", "--id", "3", "--clear")
    assert (
        result.stdout == "2 transactions: category left to the rules.\n" + LINE.format(2, 0) + "\n"
    )
    assert categories_of() == {
        1: "Coffee & Dessert",
        2: "Coffee & Dessert",
        3: "Groceries",
        4: "Dining",
    }


def test_an_unknown_id_changes_none_of_them(money: Settings) -> None:
    result = run("transactions", "set-category", "--id", "99", "--id", "1", "--category", "Dining")
    assert failed_cleanly(result, "transaction not found")
    assert categories_of()[1] == "Coffee & Dessert"
```

`tests/integration/test_web_accounts_and_bulk.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_rule,
    list_categories,
    list_category_assignments,
    set_category_by_hand,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post

POSTS = ["/accounts/rename", "/accounts/active", "/transactions/bulk"]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Card: 1 and 2 coffee, 3 groceries; checking 4 a
    paycheck set to Dining by hand; rule 1 ACME COFFEE, rule 2 FOOBAR."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        for number, (account, cents, description) in enumerate(
            (
                (card, -450, "SQ *ACME COFFEE"),
                (card, -500, "ACME COFFEE #12"),
                (card, -2599, "FOOBAR GROCERY #77"),
                (checking, 300000, "PAYCHECK EXAMPLE CORP"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        create_rule(session, "ACME COFFEE", "Coffee & Dessert")
        create_rule(session, "FOOBAR", "Groceries")
        categorize(session)
        set_category_by_hand(session, 4, "Dining")
    engine.dispose()
    client.get("/categories")
    return client


def categories_of() -> dict[int, str]:
    engine = get_engine()
    with session_scope(engine) as session:
        names = {category.id: category.name for category in list_categories(session)}
        found = {
            transaction_id: names[assignment.category_id]
            for transaction_id, assignment in list_category_assignments(session).items()
        }
    engine.dispose()
    return found


def bulk(client: TestClient, **fields) -> object:
    return client.post(
        "/transactions/bulk",
        data={"csrf": client.cookies["fin_csrf"], **fields},
        follow_redirects=False,
    )


def redirected(response, location: str) -> bool:
    return (response.status_code, response.headers.get("location")) == (303, location)


@pytest.mark.parametrize("path", POSTS)
def test_a_form_without_the_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


# Accounts


def test_rename_close_and_reopen_an_account(home: TestClient) -> None:
    response = post(home, "/accounts/rename", account="Test Card", to="Family Card")
    assert redirected(response, "/accounts?notice=account-renamed")
    found = page(home, response.headers["location"])
    assert ("notice", "Account renamed.") in found.paragraphs
    assert [row[0] for row in found.rows[1:]] == ["Family Card", "Test Checking"]
    response = post(home, "/accounts/active", account="Family Card", active="false")
    assert redirected(response, "/accounts?notice=account-closed")
    found = page(home, response.headers["location"])
    assert ("notice", "Account closed.") in found.paragraphs
    assert [row[0] for row in found.rows[1:]] == ["Test Checking"]
    response = post(home, "/accounts/active", account="Family Card", active="true")
    assert redirected(response, "/accounts?notice=account-reopened")
    assert ("notice", "Account reopened.") in page(home, response.headers["location"]).paragraphs


@pytest.mark.parametrize(
    ("path", "fields", "message"),
    [
        (
            "/accounts/rename",
            {"account": "Test Card", "to": "Test Checking"},
            "an account with this name already exists",
        ),
        ("/accounts/rename", {"account": "Nope", "to": "Other"}, "account not found"),
        ("/accounts/active", {"account": "Test Card", "active": "maybe"}, "choose Close or Reopen"),
        ("/accounts/active", {"account": "Nope", "active": "false"}, "account not found"),
    ],
)
def test_a_refused_account_change(home: TestClient, path: str, fields: dict, message: str) -> None:
    response = post(home, path, **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", message) in found.paragraphs
    assert [row[0] for row in found.rows[1:]] == ["Test Card", "Test Checking"]


def test_a_refused_rename_keeps_the_new_name(home: TestClient) -> None:
    response = post(home, "/accounts/rename", account="Test Checking", to="Test Card")
    assert Page(response.text).find("/accounts/rename")["inputs"]["to"] == ("text", "Test Card")


# Several transactions at once


def test_every_row_has_a_checkbox_and_select_all_checks_them(home: TestClient) -> None:
    html = home.get("/transactions?text=acme").text
    assert 'name="id" value="2">' in html and 'name="id" value="1">' in html
    assert "checked" not in html.split('action="/transactions/bulk"')[1]
    found = Page(html)
    assert found.rows[1][0] == "2026-05-02"
    assert found.find("/transactions/bulk")["inputs"]["back"] == ("hidden", "text=acme")
    assert "/transactions?text=acme&select=all" in found.links
    html = home.get("/transactions?text=acme&select=all").text
    assert 'name="id" value="2" checked>' in html and 'name="id" value="1" checked>' in html
    assert Page(html).find("/transactions/bulk")["inputs"]["back"] == ("hidden", "text=acme")
    assert "/transactions?text=acme" in Page(html).links


def test_set_and_clear_several_transactions(home: TestClient) -> None:
    response = bulk(
        home,
        id=["1", "2"],
        category="Dining",
        action="set",
        back="text=acme&notice=x&evil=1&select=all",
    )
    assert redirected(response, "/transactions?text=acme&notice=bulk-set")
    found = page(home, response.headers["location"])
    assert ("notice", "Category set by hand on the chosen transactions.") in found.paragraphs
    assert [row[3] for row in found.rows[1:]] == ["Dining", "Dining"]
    response = bulk(home, id=["1", "2"], category="", action="clear", back="")
    assert redirected(response, "/transactions?notice=bulk-cleared")
    assert (
        "notice",
        "The chosen transactions were left to the rules, and the rules were run again.",
    ) in page(home, response.headers["location"]).paragraphs
    assert categories_of() == {
        1: "Coffee & Dessert",
        2: "Coffee & Dessert",
        3: "Groceries",
        4: "Dining",
    }


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"category": "Dining", "action": "set"}, "choose at least one transaction"),
        ({"id": ["1", "x"], "category": "Dining", "action": "set"}, "transaction not found"),
        ({"id": ["1", "99"], "category": "Dining", "action": "set"}, "transaction not found"),
        ({"id": ["1"], "category": "", "action": "set"}, "category not found"),
        (
            {"id": ["1"], "category": "Food", "action": "set"},
            "rules and transactions take a category, not a group",
        ),
        (
            {"id": ["1"], "category": "Dining", "action": "drop"},
            "choose Set category or Leave to the rules",
        ),
    ],
)
def test_a_refused_bulk_change(home: TestClient, fields: dict, message: str) -> None:
    response = bulk(home, back="text=acme", **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", message) in found.paragraphs
    assert "<h1>Transactions</h1>" in response.text
    assert [row[0] for row in found.rows[1:]] == ["2026-05-02", "2026-05-01"]
    assert categories_of()[1] == "Coffee & Dessert"
```

## Tests to write

`tests/integration/test_account_and_bulk_repositories.py`:

- `rename_account` to its own name in another case;
- `set_categories_by_hand` with 1001 distinct ids, and with repeated ids (counted once); the web refuses 1001 ids the same way;
- a closed account is left out of `fin balances` and still counts in `fin spending`.

## Rules for this phase

- **Thin.** Commands and routes call the repository functions and `categorize`; no query or rule in `cli/` or `web/`.
- **No JavaScript.**

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/e2e/test_cli_accounts_and_bulk.py tests/integration/test_web_accounts_and_bulk.py`, 29 tests;
- also `.venv/bin/python -m pytest tests/integration/test_web_pages.py tests/integration/test_web_search.py tests/integration/test_web_forms.py tests/e2e/test_cli_categories.py --no-cov`: all pass (the replaced templates keep the earlier pages);
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.cli.categories --cov=finances.cli.accounts --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|update\(" -- src/finances/web src/finances/cli/categories.py src/finances/cli/accounts.py` and `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16j: accounts and bulk categorizing (YYYY-MM-DD)`.
