# Phase 16f: editing categories and rules

## Goal

The household fixes its categories and rules without starting over, in the browser and the terminal. After this phase:

- a **category or group can be renamed**;
- a **category can be deleted**; when transactions or rules still use it, they **move to another category first** (the household chooses which); a **group can be deleted when it has no categories**;
- a **rule can be edited** (pattern, match, priority, category), and the rules run again, as when one is added.

Renaming, closing, and reopening accounts and categorizing several transactions at once are Phase 16j.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/db/repositories.py`: `create_category`, `_category_row`, `_leaf_category`, `create_rule`, `delete_rule`
- `src/finances/cli/categories.py`
- `src/finances/web/app.py`: the Categories routes, `_categories_page`, `_priority`, `_id`
- `tests/support.py`

## Starting state

N is `2652` when Phase 24b is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/repositories.py` | new: `CategoryDeletion`, `rename_category`, `delete_category`, `edit_rule` (R1 to R3) |
| `src/finances/cli/categories.py` | `fin categories rename`, `fin categories delete`, `fin rules edit` (R4, R5) |
| `src/finances/web/app.py` | three notices, the routes of Part 3 (R6, R7) |
| `src/finances/web/templates/categories.html` | replaced: given |
| `src/finances/web/templates/rule_edit.html` | new: given |
| `tests/e2e/test_cli_category_editing.py`, `tests/integration/test_web_category_editing.py` | new: given |
| `tests/integration/test_category_editing_repositories.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Accounts and bulk categorizing (16j).
- Moving a category to another group, merging groups, changing a category's kind (transfer, income, sensitive).
- Undo, history, or a confirmation page for these edits; JavaScript.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/db/repositories.py
@dataclass(frozen=True)
class CategoryDeletion:
    name: str             # the deleted category's or group's name
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
```

None of these commit; the caller does.

Messages, in full. Each is a `ValueError` (or the existing `CategoryExistsError`); the terminal prints `Error: <message>` with exit code 1, the web shows it with status `400`.

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

## Requirements

### Part 1: repositories

- **R1.** `rename_category` finds the group or category by name (ignoring case and outer spaces), strips the new name, checks its length, then that no **other** row has it (a change of case of its own name is allowed), and renames it. It returns the old stored name and the renamed category.
- **R2.** `delete_category` finds the row. A group: refused while it has categories, otherwise deleted (`move_to` is ignored). A category: when `move_to` is not empty, it must be another category (`_leaf_category`, then the itself check); the counts of its assignments and rules are taken; when either is above zero and `move_to` is empty, it is refused with the in-use message; otherwise every assignment and rule pointing at it is moved to `move_to` (an assignment keeps its source and rule), and the category is deleted.
- **R3.** `edit_rule` finds the rule, takes each argument that is `None` from the rule as it is, and checks the result as `create_rule` does, except that the rule itself does not count as a duplicate. It stores and returns the rule. The caller runs `categorize`.

### Part 2: the terminal

Every command checks the schema first and uses one session.

- **R4.** `fin categories rename --name NAME --to NEW` prints `Renamed "OLD" to "NEW".` (stored names). `fin categories delete --name NAME [--move-to OTHER]` prints `Deleted category "NAME".`, or `Deleted group "NAME".`, or, when something moved, `Deleted category "NAME"; moved its transactions (T) and rules (R) to "OTHER".`
- **R5.** `fin rules edit --id N [--pattern P] [--match M] [--priority N] [--category C]` refuses no options as above, then prints `Changed rule N: MATCH "PATTERN" -> CATEGORY.` and the categorize line, as `fin rules add` does.

### Part 3: the web

Every `POST` runs the existing checks (origin, form token, database) and answers `303` with `notice=KEY`. Notices, in full: `category-renamed` `Category renamed.`; `category-deleted` `Category deleted.`; `rule-changed` `Rule changed, and the rules were run again.`

- **R6.** The Categories page gains `rename_form` (`name`, `to`) and `delete_form` (`name`, `move_to`), each empty unless a refused form is shown again. `POST /categories/rename` (`name`, `to`) and `POST /categories/delete` (`name`, `move_to`) call R1 and R2; done: `/categories?notice=category-renamed` or `category-deleted`; refused: the Categories page with that form holding what was sent.
- **R7.** `GET /categories/rules/{id}` renders `rule_edit.html` with `rule_id`, `rule_form` (the rule's pattern, match, priority as text, and category name), `matches`, and `choices`. `POST /categories/rules/{id}` (`pattern`, `match`, `priority`, `category`) reads the priority as `POST /categories/rules/add` does, then calls `edit_rule` with all four and `categorize`, in one session; done: `/categories?notice=rule-changed`; refused: the edit page with status `400` holding what was sent. An id that is not a whole number, or no such rule, answers `404` with `error.html` and `rule not found`, on both routes. These routes are registered after `/categories/rules/add` and `/categories/rules/delete`.
- **R8.** The given templates are used as shown (a rule's ID on the Categories page links to its edit page, so the rules table keeps its columns); the routes hold no rule.

## Given templates

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

## Given tests

32 tests in two files, both importing from `tests/support.py`.

`tests/e2e/test_cli_category_editing.py`

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
```

`tests/integration/test_web_category_editing.py`

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

POSTS = ["/categories/rename", "/categories/delete", "/categories/rules/2"]


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
```

## Tests to write

`tests/integration/test_category_editing_repositories.py`:

- `rename_category` of a group keeps its categories under it; a change of case of its own name;
- `delete_category` keeps a moved assignment's source (`MANUAL` stays `MANUAL`, a rule's stays the rule's); a category with no uses and a `move_to`; a group with a `move_to` (ignored);
- `edit_rule` with only `priority` keeps the rest.

## Rules for this phase

- **Thin.** Commands and routes call the repository functions and `categorize`; no query or rule in `cli/` or `web/`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/e2e/test_cli_category_editing.py tests/integration/test_web_category_editing.py`, 32 tests;
- also `.venv/bin/python -m pytest tests/integration/test_web_categories.py tests/e2e/test_cli_categories.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.cli.categories --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|update\(" -- src/finances/web src/finances/cli/categories.py` and `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16f: editing categories and rules (YYYY-MM-DD)`.
