# Phase 41a: adding a group

## Goal

The first part of Phase 41 (the agent proposing new categories and groups). Today no one can add a group: the groups are the ones the first migration seeded, and `create_category` only puts a category into one of them. With the owner's choices (2026-10-25), a person adds a group in the terminal and on the Categories page:

```
fin categories add-group --name "Pets"
fin categories add-group --name "Side Gigs" --income --sensitive
```

- a group is spending (the default), transfer, or income, never transfer and income together; it may also be sensitive;
- its flags are set once, when it is added; its categories copy them, as `create_category` already does;
- a group starts empty; `fin categories add` and the existing form put categories in it, and the existing delete removes an empty group;
- an empty group shows in `fin categories list` and on the Categories page, as one line with no category.

Phase 41b uses the same `create_group` when a person accepts the agent's proposed group.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat; this is the first phase with sections and the new coverage command)
- `src/finances/db/repositories/categories.py` (`create_category`: its checks, its order, and its `record_change`), `src/finances/cli/categories.py` (`add_category_command`), `src/finances/web/routes/categories.py` (`add_category`, `_categories_page`), `src/finances/views/categories.py` (`category_lines`, `_kind`), `src/finances/web/render.py` (`NOTICES`)

## Starting state

N is `4069` when Phase 40 is the last phase built. **Sections: core, web, cli.** Categories and groups share one table and one namespace: a name is taken whether a category or a group holds it. A group is a row with no parent; its `is_transfer`, `is_income`, and `is_sensitive` decide how its categories count. History already records groups under the category actions (`category_renamed` and `category_deleted` act on groups too). No migration.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/repositories/categories.py` | `create_group` (R1, R2) |
| `src/finances/db/repositories/__init__.py` | export it (R1) |
| `src/finances/views/categories.py` | `category_lines` lists an empty group (R5) |
| `src/finances/cli/categories.py` | `fin categories add-group` (R3) |
| `src/finances/web/routes/categories.py` | `POST /categories/groups/add`; `group_form` and `group_kinds` on the page (R4) |
| `src/finances/web/render.py` | the notice `group-added` (R4) |
| `src/finances/web/templates/categories.html` | the given diff (R4) |
| `tests/unit/test_web_split.py`, `tests/unit/test_repositories_split.py` | the given diff (R6) |
| `tests/e2e/test_cli_groups.py`, `tests/integration/test_web_groups.py` | new: given |
| `tests/integration/test_groups_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

Each module stays under the 400 lines the split tests allow (`repositories/categories.py` is at 358 today, `web/routes/categories.py` at 345).

## Out of scope

- Changing a group's flags after it is added; adding a group's first category with it; a tax flag on a group (tax stays per category).
- The agent's proposals (41b) and the Review page (41c).

## Dependencies

None new.

## Design

```python
# src/finances/db/repositories/categories.py
def create_group(
    session: Session, name: str, *, transfer: bool = False, income: bool = False,
    sensitive: bool = False,
) -> Category: ...
# The caller commits.
```

| Check, in this order | Refusal |
|---|---|
| the name, stripped, is 1 to `CATEGORY_NAME_LIMIT` characters | `ValueError("a group name must be 1 to 50 characters")` (the limit from `finances.domain.text`) |
| not both `transfer` and `income` | `ValueError("a group is for transfers or for income, not both")` |
| no category or group has the name | `CategoryExistsError("a category with this name already exists")` |

The new row has no parent, the three flags as given, and `is_tax` false. It is recorded with `record_change(session, action="category_added", kind="category", record_id=<its id>, after=<its name>)`, as `create_category` records a category.

| Front end | Behaviour |
|---|---|
| `fin categories add-group --name NAME [--transfer] [--income] [--sensitive]` | prints `Added group "NAME".`, or with flags `Added group "NAME" (FLAGS).`, where FLAGS are the words `transfer`, `income`, `sensitive` that apply, in that order, joined by `, `; a refusal prints its message through `fail` (exit 1); an unmigrated database gives the usual message |
| `POST /categories/groups/add` (`name`, `kind`, `sensitive`) | `kind` is `spending`, `transfer`, or `income` (else 400 with `a group's kind must be spending, transfer, or income`, checked before `create_group`); `sensitive` is on when the field is `on`; success: 303 to `/categories?notice=group-added`, whose notice is `Group added.`; a refusal: the Categories page, 400, the error, the form kept |
| `_categories_page` | gains `group_form` (default `{"name": "", "kind": "spending", "sensitive": False}`) and `group_kinds` (`["spending", "transfer", "income"]`) |
| `category_lines` | a group with no categories gives one line: the group's name, an empty category, and the group's own kind text (`_kind` of the group); groups keep their order |

## Requirements

- **R1.** `create_group` as designed, exported from `finances.db.repositories`.
- **R2.** Its checks in the order of the table; a refusal adds nothing and records nothing.
- **R3.** `fin categories add-group` as designed.
- **R4.** The form and route as designed; apply the given template diff exactly.
- **R5.** `category_lines` lists an empty group as designed; a group with categories is listed as today.
- **R6.** Apply the given diffs to the two split tests. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/templates/` (do not change). It was checked against every earlier test, unit tests included, with `group_form` and `group_kinds` at their defaults: all pass unchanged.

```text
diff --git a/src/finances/web/templates/categories.html b/src/finances/web/templates/categories.html
index a6f8ea2..22b7b5f 100644
--- a/src/finances/web/templates/categories.html
+++ b/src/finances/web/templates/categories.html
@@ -58,6 +58,22 @@
 </table>
 </section>
 <section class="card">
+<h2>Add a group</h2>
+<p class="hint">A group's kind decides how its categories count: spending, money moved between your own accounts, or income. It is set once, when the group is added.</p>
+<form method="post" action="/categories/groups/add" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <label>Name <input name="name" required maxlength="50" value="{{ group_form.name }}"></label>
+  <label>Kind
+    <select name="kind">
+      {% for kind in group_kinds %}<option value="{{ kind }}"{% if kind == group_form.kind %} selected{% endif %}>{{ kind }}</option>
+      {% endfor %}
+    </select>
+  </label>
+  <label><input type="checkbox" name="sensitive" value="on"{% if group_form.sensitive %} checked{% endif %}> Sensitive</label>
+  <button type="submit">Add group</button>
+</form>
+</section>
+<section class="card">
 <h2>Add a category</h2>
 <form method="post" action="/categories/add" class="fields">
   <input type="hidden" name="csrf" value="{{ csrf }}">
```

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index a450936..c4f84e2 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -116,6 +116,7 @@ HOMES = {
         "CategoryDeletion",
         "CategoryExistsError",
         "create_category",
+        "create_group",
         "check_rule",
         "create_rule",
         "delete_category",
@@ -177,7 +178,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 125
+    assert len(expected) == 126
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 5322200..14860a5 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -62,6 +62,7 @@ ROUTES = {
     ("POST", "/statements/upload"),
     ("GET", "/categories"),
     ("POST", "/categories/add"),
+    ("POST", "/categories/groups/add"),
     ("POST", "/categories/rules/add"),
     ("POST", "/categories/rules/preview"),
     ("POST", "/categories/rules/delete"),
```

## Given tests

16 tests in two files. Do not change them.

`tests/e2e/test_cli_groups.py`

```python
import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import get_category_by_name
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, run, table_rows

BOTH = "a group is for transfers or for income, not both"
TAKEN = "a category with this name already exists"


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    upgrade_to_head()
    return tmp_settings


def flags(name: str) -> tuple[bool, bool, bool, bool, bool]:
    """Whether the row is a group, and its transfer, income, sensitive, and tax flags."""
    engine = get_engine()
    with session_scope(engine) as session:
        found = get_category_by_name(session, name)
    engine.dispose()
    assert found is not None
    return (
        found.group_id is None,
        found.is_transfer,
        found.is_income,
        found.is_sensitive,
        found.is_tax,
    )


def test_a_spending_group(migrated: Settings) -> None:
    result = run("categories", "add-group", "--name", "Pets")
    assert (result.exit_code, result.output) == (0, 'Added group "Pets".\n')
    assert flags("Pets") == (True, False, False, False, False)


def test_a_group_with_flags(migrated: Settings) -> None:
    result = run("categories", "add-group", "--name", "Side Gigs", "--income", "--sensitive")
    assert (result.exit_code, result.output) == (
        0,
        'Added group "Side Gigs" (income, sensitive).\n',
    )
    assert flags("Side Gigs") == (True, False, True, True, False)


def test_a_category_takes_its_new_groups_flags(migrated: Settings) -> None:
    run("categories", "add-group", "--name", "Between Banks", "--transfer")
    result = run("categories", "add", "--name", "Wire Out", "--group", "Between Banks")
    assert (result.exit_code, result.output) == (0, 'Added category "Wire Out" to Between Banks.\n')
    assert flags("Wire Out") == (False, True, False, False, False)


def test_an_empty_group_is_listed(migrated: Settings) -> None:
    run("categories", "add-group", "--name", "Pets", "--sensitive")
    rows = table_rows(run("categories", "list").output)
    assert ["Pets", "", "sensitive"] in rows
    run("categories", "add", "--name", "Dog Food", "--group", "Pets")
    rows = table_rows(run("categories", "list").output)
    assert ["Pets", "Dog Food", "sensitive"] in rows
    assert ["Pets", "", "sensitive"] not in rows


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--name", "Moves", "--transfer", "--income"], BOTH),
        (["--name", "Food"], TAKEN),
        (["--name", "Groceries"], TAKEN),
        (["--name", "x" * 51], "a group name must be 1 to 50 characters"),
        (["--name", "   "], "a group name must be 1 to 50 characters"),
    ],
)
def test_a_refused_group(migrated: Settings, arguments: list[str], message: str) -> None:
    assert failed_cleanly(run("categories", "add-group", *arguments), message)


def test_both_kinds_are_refused_before_a_taken_name(migrated: Settings) -> None:
    result = run("categories", "add-group", "--name", "Food", "--transfer", "--income")
    assert failed_cleanly(result, BOTH)


def test_add_group_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("categories", "add-group", "--name", "Pets")
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)
```

`tests/integration/test_web_groups.py`

```python
import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import get_category_by_name
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

KIND = "a group's kind must be spending, transfer, or income"


@pytest.fixture
def home(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/categories")
    return client


def group_flags(name: str) -> tuple[bool, bool, bool] | None:
    engine = get_engine()
    with session_scope(engine) as session:
        found = get_category_by_name(session, name)
    engine.dispose()
    if found is None:
        return None
    assert found.group_id is None
    return found.is_transfer, found.is_income, found.is_sensitive


def test_the_form(home: TestClient) -> None:
    form = page(home, "/categories").find("/categories/groups/add")
    assert form["inputs"]["sensitive"] == ("checkbox", "on")
    assert form["selects"]["kind"] == [("spending", True), ("transfer", False), ("income", False)]


def test_adding_a_group(home: TestClient) -> None:
    response = post(home, "/categories/groups/add", name="Pets", kind="spending")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/categories?notice=group-added",
    )
    found = page(home, response.headers["location"])
    assert texts(found, "notice") == ["Group added."]
    groups = [name for name, _ in found.find("/categories/add")["selects"]["group"]]
    assert "Pets" in groups
    assert group_flags("Pets") == (False, False, False)


def test_adding_an_income_group_that_is_sensitive(home: TestClient) -> None:
    post(home, "/categories/groups/add", name="Side Gigs", kind="income", sensitive="on")
    assert group_flags("Side Gigs") == (False, True, True)


def test_an_unknown_kind_is_refused_and_the_form_kept(home: TestClient) -> None:
    response = post(home, "/categories/groups/add", name="Pets", kind="savings", sensitive="on")
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == [KIND]
    form = found.find("/categories/groups/add")
    assert form["inputs"]["name"][1] == "Pets"
    assert group_flags("Pets") is None


def test_a_taken_name_is_refused(home: TestClient) -> None:
    response = post(home, "/categories/groups/add", name="Dining", kind="spending")
    assert (response.status_code, texts(Page(response.text), "error")) == (
        400,
        ["a category with this name already exists"],
    )
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_groups_more.py` (section core):

- `create_group` records one `category_added` change with the group's name, and a refused one records none;
- a name with outer spaces (`"  Pets  "`) is stored stripped;
- a name that differs from a group only in case (`food`) is refused as taken: names are compared ignoring case, as `_category_row` does;
- `category_lines` for a tree with an empty transfer group gives `(group, "", "transfer")`;
- a new group can be deleted while empty, and `fin categories list` no longer shows it;
- the web form with `kind=transfer` and `sensitive=on` stores a transfer group that is sensitive.

## Rules for this phase

- The front ends only read their input and call `create_group`; the rules live in the repository.
- Earlier tests stay unchanged except the given diffs.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first core,web,cli`;
- the given test files above, 16 tests; at least N + 16 passed in all;
- `git diff --stat HEAD -- tests` lists only the two split tests;
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/db/repositories/categories.py,*/finances/cli/categories.py,*/finances/web/routes/categories.py,*/finances/views/categories.py,*/finances/web/render.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 41a: adding a group (YYYY-MM-DD)`.
