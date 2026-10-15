# Phase 16f: editing and bulk

## Goal

The household fixes its set-up without starting over, in the browser and the terminal. After this phase:

- a **category or group can be renamed**; a **category can be deleted**, and when transactions or rules still use it they **move to another category first** (the household chooses which); a **group can be deleted when it has no categories**;
- a **rule can be edited** (pattern, match, priority, category), and the rules run again, as when one is added;
- an **account can be renamed, closed, and reopened**; a closed account leaves balances, net worth, coverage, and the account choices, and its transactions are kept;
- **several transactions can be categorized at once**: on the Transactions page a checkbox in each row's date cell, **Select all shown**, a category choice, and **Set category** or **Leave to the rules**; in the terminal, `--id` may be given several times.

Everything goes through new repository functions that both the web and the terminal call.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/db/repositories.py`: `create_category`, `_leaf_category`, `create_rule`, `delete_rule`, `set_category_by_hand`, `clear_category_by_hand`, `create_account`, `get_account_by_name`
- `src/finances/cli/categories.py`, `src/finances/cli/accounts.py`
- `src/finances/web/app.py`: the Categories, Accounts, and Transactions routes; `_priority`, `_id`, `_search_query`
- `tests/support.py`

## Starting state

N is `2652` when Phase 24b is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/repositories.py` | new functions (R1 to R6) |
| `src/finances/cli/categories.py` | `fin categories rename`, `fin categories delete`, `fin rules edit`, `fin transactions set-category` with several ids (R7 to R9) |
| `src/finances/cli/accounts.py` | `fin accounts rename`, `deactivate`, `activate` (R10) |
| `src/finances/web/app.py` | eight notices, the routes of Part 3, the Transactions page's selection (R11 to R16) |
| `src/finances/web/templates/categories.html`, `accounts.html`, `transactions.html` | replaced: given |
| `src/finances/web/templates/rule_edit.html` | new: given |
| `tests/e2e/test_cli_editing.py`, `tests/integration/test_web_editing.py` | new: given |
| `tests/integration/test_editing_repositories.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Moving a category to another group, merging groups, changing a category's kind (transfer, income, sensitive).
- Changing an account's type, institution, last four digits, or currency; deleting an account; anything about SimpleFIN mappings when an account closes (sync continues as before).
- Undo, history, or a confirmation page for these edits; JavaScript (Select all shown is a link).

## Dependencies

None new. No migration.

## Design

```python
# src/finances/db/repositories.py
@dataclass(frozen=True)
class CategoryDeletion:
    name: str            # the deleted category's or group's name
    was_group: bool
    moved_to: str | None  # the category's name its uses moved to, or None
    transactions: int     # assignments moved
    rules: int            # rules moved


def rename_category(session: Session, name: str, new_name: str) -> tuple[str, Category]: ...  # (old name, renamed)
def delete_category(session: Session, name: str, move_to: str = "") -> CategoryDeletion: ...
def edit_rule(
    session: Session,
    rule_id: int,
    *,
    pattern: str | None = None,
    match: str | None = None,
    priority: int | None = None,
    category: str | None = None,
) -> CategoryRule: ...
def rename_account(session: Session, account_id: int, new_name: str) -> Account: ...
def set_account_active(session: Session, account_id: int, active: bool) -> Account: ...
def set_categories_by_hand(session: Session, transaction_ids: Iterable[int], category: str) -> tuple[int, Category]: ...  # (how many, category)
def clear_categories_by_hand(session: Session, transaction_ids: Iterable[int]) -> int: ...
```

None of these commit; the caller does.

Messages, in full. Each is a `ValueError` (or the existing `CategoryExistsError` / `AccountExistsError`); the terminal prints `Error: <message>` with exit code 1, the web shows it on the page with status `400`.

| Where | When | Message |
|---|---|---|
| rename, delete | no group or category has that name | the existing `category not found` |
| rename | the new name's length | the existing `a category name must be 1 to 50 characters` |
| rename | another group or category has the new name (ignoring case) | the existing `a category with this name already exists` |
| delete | a group that still has categories | `a group can be deleted only when it has no categories` |
| delete | `move_to` names the category being deleted | `a category cannot be moved to itself` |
| delete | `move_to` unknown or a group | the existing `category not found`, `rules and transactions take a category, not a group` |
| delete | the category is used and `move_to` is empty | `NAME is in use (transactions: T, rules: R); choose a category to move them to` |
| edit rule | unknown id | the existing `rule not found` |
| edit rule | pattern, match, category, another rule with the same pattern and match | the existing messages of `create_rule`, checked in its order |
| `fin rules edit` | none of the four options | `give at least one of --pattern, --match, --priority, --category` |
| accounts | no account has that name | the existing `account not found` |
| rename account | name empty, too long, or another account's (ignoring case) | the existing messages of `create_account` |
| web close or reopen | `active` not `true` or `false` | `choose Close or Reopen` |
| bulk | no ids | `choose at least one transaction` |
| bulk | more than 1000 distinct ids | `at most 1000 transactions at once` |
| bulk | an id that is not a whole number, or no such transaction | the existing `transaction not found` |
| web bulk | `action` not `set` or `clear` | `choose Set category or Leave to the rules` |

## Requirements

### Part 1: repositories

- **R1.** `rename_category` finds the group or category by name (ignoring case and outer spaces), strips the new name, checks its length, then that no **other** row has it (a change of case of its own name is allowed), and renames it. It returns the old stored name and the renamed category.
- **R2.** `delete_category` finds the row. A group: refused while it has categories, otherwise deleted (`move_to` is ignored). A category: when `move_to` is not empty, it must be another category (`_leaf_category`, then the itself check); the counts of its assignments and rules are taken; when either is above zero and `move_to` is empty, it is refused with the in-use message; otherwise every assignment and rule pointing at it is moved to `move_to` (an assignment keeps its source and rule), and the category is deleted.
- **R3.** `edit_rule` finds the rule, takes each argument that is `None` from the rule as it is, and checks the result as `create_rule` does, except that the rule itself does not count as a duplicate. It stores and returns the rule. The caller runs `categorize`.
- **R4.** `rename_account` strips the new name, applies `create_account`'s name checks (another account with the name, ignoring case; the account's own name in another case is allowed), and renames it.
- **R5.** `set_account_active` sets `is_active` and returns the account.
- **R6.** `set_categories_by_hand` and `clear_categories_by_hand` take the distinct ids in the order given, refuse an empty set and more than 1000, check that every transaction exists (and, for set, the category with `_leaf_category`) before changing any, then set each by hand or remove each assignment. They return how many transactions changed hands (the distinct ids). The caller of `clear_categories_by_hand` runs `categorize`.

### Part 2: the terminal

Every command checks the schema first, as the others do, and uses one session.

- **R7.** `fin categories rename --name NAME --to NEW` prints `Renamed "OLD" to "NEW".` (stored names). `fin categories delete --name NAME [--move-to OTHER]` prints `Deleted category "NAME".`, or `Deleted group "NAME".`, or, when something moved, `Deleted category "NAME"; moved its transactions (T) and rules (R) to "OTHER".`
- **R8.** `fin rules edit --id N [--pattern P] [--match M] [--priority N] [--category C]` refuses no options as above, then prints `Changed rule N: MATCH "PATTERN" -> CATEGORY.` and the categorize line, as `fin rules add` does.
- **R9.** `fin transactions set-category` takes `--id` one or more times. With one distinct id its output is unchanged. With several: `N transactions: CATEGORY, set by hand.`, or `N transactions: category left to the rules.` followed by the categorize line.
- **R10.** `fin accounts rename --account NAME --to NEW` prints `Renamed account "OLD" to "NEW".`; `fin accounts deactivate --account NAME` prints `Account "NAME" is closed.`; `fin accounts activate --account NAME` prints `Account "NAME" is open again.`

### Part 3: the web

Every `POST` runs the existing checks (origin, form token, database) and answers `303` with `notice=KEY`. Notices, in full: `category-renamed` `Category renamed.`; `category-deleted` `Category deleted.`; `rule-changed` `Rule changed, and the rules were run again.`; `account-renamed` `Account renamed.`; `account-closed` `Account closed.`; `account-reopened` `Account reopened.`; `bulk-set` `Category set by hand on the chosen transactions.`; `bulk-cleared` `The chosen transactions were left to the rules, and the rules were run again.`

- **R11.** The Categories page gains `rename_form` (`name`, `to`) and `delete_form` (`name`, `move_to`), each empty unless a refused form is shown again. `POST /categories/rename` (`name`, `to`) and `POST /categories/delete` (`name`, `move_to`) call R1 and R2; done: `/categories?notice=category-renamed` or `category-deleted`; refused: the Categories page with that form holding what was sent.
- **R12.** `GET /categories/rules/{id}` renders `rule_edit.html` with `rule_id`, `rule_form` (the rule's pattern, match, priority as text, and category name), `matches`, and `choices`. `POST /categories/rules/{id}` (`pattern`, `match`, `priority`, `category`) reads the priority as `POST /categories/rules/add` does, then calls `edit_rule` with all four and `categorize`, in one session; done: `/categories?notice=rule-changed`; refused: the edit page with status `400` holding what was sent. An id that is not a whole number, or no such rule, answers `404` with `error.html` and `rule not found`, on both routes. These routes are registered after `/categories/rules/add` and `/categories/rules/delete`.
- **R13.** The Accounts page gains `rename_form` (`account`, `to`). `POST /accounts/rename` (`account`, `to`) and `POST /accounts/active` (`account`, `active`) find the account by name, then call R4 or R5; done: `/accounts?notice=account-renamed`, `account-closed`, or `account-reopened`; refused: the Accounts page with status `400` (the rename form holding what was sent).
- **R14.** `GET /transactions` also passes `back` (the page's own filter fields that were sent and are not empty, in the order of its fields, URL-encoded), `select_all_query` (`back` plus `&select=all`, or `select=all` when `back` is empty), and `select_all` (the `select` field is `all`).
- **R15.** `POST /transactions/bulk` (`id` any number of times, `category`, `action`, `back`) reads `back` keeping only the page's filter fields; checks the ids (whole numbers), then `action`; then calls `set_categories_by_hand`, or `clear_categories_by_hand` and `categorize`, in one session. Done: `/transactions?BACK&notice=bulk-set` (or `bulk-cleared`), or `/transactions?notice=...` when `back` keeps nothing. Refused: the Transactions page for `back`'s filters, with status `400` and the message; nothing changes.
- **R16.** The given templates are used as shown; the route holds no rule (names, counts, and checks come from the repositories).

## Given templates

Replace the three templates and add the fourth, exactly as shown.

`src/finances/web/templates/categories.html`

```html
{% extends "layout.html" %}
{% block title %}Categories · Finances{% endblock %}
{% block content %}
<h1>Categories</h1>
{% include "messages.html" %}
<h2>Uncategorized</h2>
{% if uncategorized %}
<table>
<thead><tr><th>ID</th><th>Date</th><th>Account</th><th>Merchant</th><th class="amount">Amount</th></tr></thead>
<tbody>
{% for row in uncategorized %}<tr><td><a href="/transactions/{{ row.id }}">{{ row.id }}</a></td><td>{{ row.date }}</td><td>{{ row.account }}</td><td>{{ row.merchant }}</td><td class="amount">{{ row.amount }}</td></tr>
{% endfor %}</tbody>
</table>
{% if uncategorized|length >= limit %}<p class="hint">Showing the {{ limit }} latest. Open one to set its category, or add a rule below.</p>{% endif %}
{% else %}
<p class="empty">No uncategorized transactions.</p>
{% endif %}
<h2>Rules</h2>
<p class="hint">The highest priority wins; a category set by hand is never changed. Adding, editing, or deleting a rule runs the rules again over every transaction. Open a rule's ID to edit it.</p>
{% if rules %}
<table>
<thead><tr><th>ID</th><th>Priority</th><th>Match</th><th>Pattern</th><th>Category</th><th></th></tr></thead>
<tbody>
{% for row in rules %}<tr><td><a href="/categories/rules/{{ row.id }}" title="Edit this rule">{{ row.id }}</a></td><td>{{ row.priority }}</td><td>{{ row.match }}</td><td>{{ row.pattern }}</td><td>{{ row.category }}</td><td><form method="post" action="/categories/rules/delete" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="rule" value="{{ row.id }}"><button type="submit">Delete</button></form></td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No rules.</p>
{% endif %}
<h2>Add a rule</h2>
{% with back = "" %}{% include "rule_form.html" %}{% endwith %}
<h2>Categories</h2>
<table>
<thead><tr><th>Group</th><th>Category</th><th>Kind</th></tr></thead>
<tbody>
{% for row in tree %}<tr><td>{{ row.group }}</td><td>{{ row.category }}</td><td>{{ row.kind }}</td></tr>
{% endfor %}</tbody>
</table>
<h2>Add a category</h2>
<form method="post" action="/categories/add" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Name <input name="name" required maxlength="50" value="{{ category_form.name }}"></label>
  <label>Group
    <select name="group">
      {% for group in groups %}<option value="{{ group }}"{% if group == category_form.group %} selected{% endif %}>{{ group }}</option>
      {% endfor %}
    </select>
  </label>
  <button type="submit">Add category</button>
</form>
<h2>Rename a category or group</h2>
<form method="post" action="/categories/rename" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Category or group
    <select name="name" required>
      <option value=""{% if not rename_form.name %} selected{% endif %}>Choose</option>
      {% for group, names in choices %}<optgroup label="{{ group }}">
        <option value="{{ group }}"{% if group == rename_form.name %} selected{% endif %}>{{ group }} (the group)</option>
        {% for name in names %}<option value="{{ name }}"{% if name == rename_form.name %} selected{% endif %}>{{ name }}</option>
        {% endfor %}</optgroup>
      {% endfor %}
    </select>
  </label>
  <label>New name <input name="to" required maxlength="50" value="{{ rename_form.to }}"></label>
  <button type="submit">Rename</button>
</form>
<h2>Delete a category or group</h2>
<p class="hint">A category in use is deleted only after its transactions and rules move to another category. A group can be deleted when it has no categories.</p>
<form method="post" action="/categories/delete" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Category or group
    <select name="name" required>
      <option value=""{% if not delete_form.name %} selected{% endif %}>Choose</option>
      {% for group, names in choices %}<optgroup label="{{ group }}">
        <option value="{{ group }}"{% if group == delete_form.name %} selected{% endif %}>{{ group }} (the group)</option>
        {% for name in names %}<option value="{{ name }}"{% if name == delete_form.name %} selected{% endif %}>{{ name }}</option>
        {% endfor %}</optgroup>
      {% endfor %}
    </select>
  </label>
  <label>Move its transactions and rules to
    <select name="move_to">
      <option value=""{% if not delete_form.move_to %} selected{% endif %}>Do not move</option>
      {% for group, names in choices %}<optgroup label="{{ group }}">
        {% for name in names %}<option value="{{ name }}"{% if name == delete_form.move_to %} selected{% endif %}>{{ name }}</option>
        {% endfor %}</optgroup>
      {% endfor %}
    </select>
  </label>
  <button type="submit">Delete</button>
</form>
{% endblock %}
```

`src/finances/web/templates/rule_edit.html`

```html
{% extends "layout.html" %}
{% block title %}Rule {{ rule_id }} · Finances{% endblock %}
{% block content %}
<h1>Rule {{ rule_id }}</h1>
{% include "messages.html" %}
<p><a href="/categories">Back to categories</a></p>
<p class="hint">Saving runs the rules again over every transaction; a category set by hand is never changed.</p>
<form method="post" action="/categories/rules/{{ rule_id }}" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Pattern <input name="pattern" required maxlength="100" value="{{ rule_form.pattern }}"></label>
  <label>Match
    <select name="match">
      {% for item in matches %}<option value="{{ item }}"{% if item == rule_form.match %} selected{% endif %}>{{ item }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Priority <input name="priority" inputmode="numeric" value="{{ rule_form.priority }}"></label>
  <label>Category
    {% with selected = rule_form.category %}{% include "category_select.html" %}{% endwith %}
  </label>
  <button type="submit">Save rule</button>
</form>
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

The checkbox sits inside each row's date cell, so the table's columns, and the earlier tests that read them, do not change.

## Given tests

61 tests in two files, both importing from `tests/support.py`.

`tests/e2e/test_cli_editing.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, list_categories, list_category_assignments
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, plain_lines, run, table_rows

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
        ("categories", "rename", "--name", "Dining", "--to", "Eating out"),
        ("categories", "delete", "--name", "Gaming"),
        ("rules", "edit", "--id", "1", "--priority", "2"),
        ("accounts", "rename", "--account", "Test Card", "--to", "Family Card"),
        ("accounts", "deactivate", "--account", "Test Card"),
        ("accounts", "activate", "--account", "Test Card"),
    ],
)
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


# Categories


def test_rename_a_category_and_a_group(money: Settings) -> None:
    result = run("categories", "rename", "--name", "coffee & dessert", "--to", " Coffee ")
    assert (result.exit_code, result.stdout) == (0, 'Renamed "Coffee & Dessert" to "Coffee".\n')
    assert table_rows(run("rules", "list").stdout)[1][4] == "Coffee"
    assert categories_of()[1] == "Coffee"
    result = run("categories", "rename", "--name", "food", "--to", "Eating")
    assert result.stdout == 'Renamed "Food" to "Eating".\n'
    assert ["Eating", "Dining", ""] in table_rows(run("categories", "list").stdout)
    assert run("categories", "rename", "--name", "dining", "--to", "DINING").stdout == (
        'Renamed "Dining" to "DINING".\n'
    )


@pytest.mark.parametrize(
    ("name", "to", "message"),
    [
        ("Nope", "Other", "category not found"),
        ("Dining", "groceries", "a category with this name already exists"),
        ("Dining", "food", "a category with this name already exists"),
        ("Dining", "  ", "a category name must be 1 to 50 characters"),
        ("Dining", "N" * 51, "a category name must be 1 to 50 characters"),
    ],
)
def test_a_refused_rename(money: Settings, name: str, to: str, message: str) -> None:
    assert failed_cleanly(run("categories", "rename", "--name", name, "--to", to), message)


def test_delete_an_unused_category_and_an_empty_group(money: Settings) -> None:
    assert run("categories", "delete", "--name", "gaming").stdout == 'Deleted category "Gaming".\n'
    result = run("categories", "delete", "--name", "Subscriptions & Digital")
    assert result.stdout == 'Deleted category "Subscriptions & Digital".\n'
    assert run("categories", "delete", "--name", "subscriptions").stdout == (
        'Deleted group "Subscriptions".\n'
    )
    names = [row[1] for row in table_rows(run("categories", "list").stdout)[1:]]
    assert "Gaming" not in names and "Subscriptions & Digital" not in names
    assert "Subscriptions" not in [row[0] for row in table_rows(run("categories", "list").stdout)]


def test_a_category_in_use_moves_before_it_goes(money: Settings) -> None:
    assert failed_cleanly(
        run("categories", "delete", "--name", "Coffee & Dessert"),
        "Coffee & Dessert is in use (transactions: 2, rules: 1); choose a category to move them to",
    )
    result = run("categories", "delete", "--name", "Coffee & Dessert", "--move-to", "dining")
    assert (result.exit_code, result.stdout) == (
        0,
        'Deleted category "Coffee & Dessert"; moved its transactions (2) and rules (1)'
        ' to "Dining".\n',
    )
    assert categories_of() == {1: "Dining", 2: "Dining", 3: "Groceries", 4: "Dining"}
    assert table_rows(run("rules", "list").stdout)[1] == [
        "1",
        "0",
        "contains",
        "ACME COFFEE",
        "Dining",
    ]
    assert run("categorize").stdout == LINE.format(0, 0) + "\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--name", "Nope"), "category not found"),
        (("--name", "Food"), "a group can be deleted only when it has no categories"),
        (("--name", "Dining", "--move-to", "dining"), "a category cannot be moved to itself"),
        (
            ("--name", "Dining", "--move-to", "Food"),
            "rules and transactions take a category, not a group",
        ),
        (("--name", "Dining", "--move-to", "Nope"), "category not found"),
    ],
)
def test_a_refused_delete(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("categories", "delete", *args), message)
    assert categories_of()[4] == "Dining"


# Rules


def test_edit_a_rule_and_the_rules_run_again(money: Settings) -> None:
    result = run("rules", "edit", "--id", "2", "--category", "dining")
    assert (result.exit_code, result.stdout) == (
        0,
        'Changed rule 2: contains "FOOBAR" -> Dining.\n' + LINE.format(1, 0) + "\n",
    )
    assert categories_of()[3] == "Dining"
    result = run("rules", "edit", "--id", "2", "--priority", "7", "--pattern", " foobar ")
    assert (
        result.stdout == 'Changed rule 2: contains "FOOBAR" -> Dining.\n' + LINE.format(0, 0) + "\n"
    )
    assert table_rows(run("rules", "list").stdout)[1] == ["2", "7", "contains", "FOOBAR", "Dining"]
    result = run("rules", "edit", "--id", "2", "--match", "equals", "--pattern", "FOOBAR GROCERY")
    assert plain_lines(result.stdout) == [
        'Changed rule 2: equals "FOOBAR GROCERY" -> Dining.',
        LINE.format(0, 0),
    ]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--id", "9", "--priority", "1"), "rule not found"),
        (
            (
                "--id",
                "2",
            ),
            "give at least one of --pattern, --match, --priority, --category",
        ),
        (
            ("--id", "2", "--pattern", "acme coffee"),
            "a rule with this pattern and match already exists",
        ),
        (("--id", "2", "--match", "regex"), "match must be one of: contains, starts_with, equals"),
        (
            ("--id", "2", "--category", "Food"),
            "rules and transactions take a category, not a group",
        ),
    ],
)
def test_a_refused_rule_edit(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("rules", "edit", *args), message)
    assert table_rows(run("rules", "list").stdout)[2] == [
        "2",
        "0",
        "contains",
        "FOOBAR",
        "Groceries",
    ]


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

`tests/integration/test_web_editing.py`

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

POSTS = [
    "/categories/rename",
    "/categories/delete",
    "/categories/rules/2",
    "/accounts/rename",
    "/accounts/active",
    "/transactions/bulk",
]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The data of tests/e2e/test_cli_editing.py: card 1 and 2 coffee, 3 groceries; checking 4 a
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


# Categories and rules


def test_rename_a_category(home: TestClient) -> None:
    response = post(home, "/categories/rename", name="Coffee & Dessert", to="Coffee")
    assert redirected(response, "/categories?notice=category-renamed")
    found = page(home, response.headers["location"])
    assert ("notice", "Category renamed.") in found.paragraphs
    assert ["Food", "Coffee", ""] in found.rows
    options = found.find("/categories/rename")["selects"]["name"]
    assert ("Food", False) in options and ("Coffee", False) in options


def test_a_refused_rename_keeps_the_form(home: TestClient) -> None:
    response = post(home, "/categories/rename", name="Dining", to="Groceries")
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", "a category with this name already exists") in found.paragraphs
    form = found.find("/categories/rename")
    assert ("Dining", True) in form["selects"]["name"]
    assert form["inputs"]["to"] == ("text", "Groceries")


def test_delete_a_category_after_moving_what_uses_it(home: TestClient) -> None:
    response = post(home, "/categories/delete", name="Coffee & Dessert", move_to="")
    assert response.status_code == 400
    found = Page(response.text)
    assert (
        "error",
        "Coffee & Dessert is in use (transactions: 2, rules: 1); choose a category to move them to",
    ) in found.paragraphs
    assert ("Coffee & Dessert", True) in found.find("/categories/delete")["selects"]["name"]
    response = post(home, "/categories/delete", name="Coffee & Dessert", move_to="Dining")
    assert redirected(response, "/categories?notice=category-deleted")
    found = page(home, response.headers["location"])
    assert ("notice", "Category deleted.") in found.paragraphs
    assert ["Food", "Coffee & Dessert", ""] not in found.rows
    assert categories_of() == {1: "Dining", 2: "Dining", 3: "Groceries", 4: "Dining"}


def test_edit_a_rule(home: TestClient) -> None:
    assert "/categories/rules/2" in page(home, "/categories").links
    found = page(home, "/categories/rules/2")
    form = found.find("/categories/rules/2")
    assert (form["inputs"]["pattern"], form["inputs"]["priority"]) == (
        ("text", "FOOBAR"),
        ("text", "0"),
    )
    assert ("contains", True) in form["selects"]["match"]
    assert ("Groceries", True) in form["selects"]["category"]
    response = post(
        home,
        "/categories/rules/2",
        pattern="FOOBAR",
        match="contains",
        priority="3",
        category="Dining",
    )
    assert redirected(response, "/categories?notice=rule-changed")
    found = page(home, response.headers["location"])
    assert ("notice", "Rule changed, and the rules were run again.") in found.paragraphs
    assert ["2", "3", "contains", "FOOBAR", "Dining", "Delete"] in found.rows
    assert categories_of()[3] == "Dining"


@pytest.mark.parametrize("path", ["/categories/rules/9", "/categories/rules/x"])
def test_an_unknown_rule(home: TestClient, path: str) -> None:
    for response in (
        home.get(path),
        post(home, path, pattern="X", match="contains", priority="0", category="Dining"),
    ):
        assert response.status_code == 404
        assert ("error", "rule not found") in Page(response.text).paragraphs


def test_a_refused_rule_edit_keeps_what_was_typed(home: TestClient) -> None:
    response = post(
        home,
        "/categories/rules/2",
        pattern="BAZ",
        match="contains",
        priority="x",
        category="Dining",
    )
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", "priority must be a whole number") in found.paragraphs
    form = found.find("/categories/rules/2")
    assert (form["inputs"]["pattern"], form["inputs"]["priority"]) == (
        ("text", "BAZ"),
        ("text", "x"),
    )
    assert categories_of()[3] == "Groceries"


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

`tests/integration/test_editing_repositories.py`:

- `rename_category` of a group keeps its categories under it; a change of case of its own name;
- `delete_category` keeps a moved assignment's source (`MANUAL` stays `MANUAL`, a rule's stays the rule's); a category with no uses and a `move_to`; a group with a `move_to` (ignored);
- `edit_rule` with only `priority` keeps the rest;
- `rename_account` to its own name in another case;
- `set_categories_by_hand` with 1001 distinct ids, and with repeated ids (counted once); the web refuses 1001 ids the same way;
- a closed account is left out of `fin balances` and the Accounts page's choices of open accounts, and its transactions still count in `fin spending`.

## Rules for this phase

- **Thin.** Commands and routes call the repository functions and `categorize`; no query or rule in `cli/` or `web/`.
- **No JavaScript.**

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/e2e/test_cli_editing.py tests/integration/test_web_editing.py`, 61 tests;
- also `.venv/bin/python -m pytest tests/integration/test_web_pages.py tests/integration/test_web_categories.py tests/integration/test_web_search.py tests/e2e/test_cli_categories.py --no-cov`: all pass (the replaced templates keep the earlier pages);
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.cli.categories --cov=finances.cli.accounts --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|update\(" -- src/finances/web src/finances/cli/categories.py src/finances/cli/accounts.py` and `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16f: editing and bulk (YYYY-MM-DD)`.
