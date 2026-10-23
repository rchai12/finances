# Phase 28b: aliases on the web and the rule preview

## Goal

After this phase:

- the Categories page lists the merchant aliases of 28a, with a form to merge one merchant into another and a button to remove each alias; each change runs the rules again, as the page's rule forms do;
- before saving a rule, a person can **preview** it: how many transactions it would put in its category, and the newest ten of them with the category each has now. The preview is in the terminal (`fin rules preview`) and on the web (a Preview button on the rule form, on the Categories page and on a transaction's page). A preview writes nothing.

The preview counts what the rules will really do: it skips categories set by hand, sees the merged merchant name of 28a, and loses ties to older rules, as a new rule does.

Phase 19e (the agent's alias proposals) comes next, then 28c (tags and notes).

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-28a-merchant-aliases.md`
- `src/finances/db/repositories/categories.py` (`create_rule`, `_leaf_category`), `src/finances/db/repositories/aliases.py`
- `src/finances/categorize/service.py` (`categorize`), `src/finances/domain/rules.py` (`pick_rule_for`), `src/finances/domain/merchants.py` (`merchant_name`, `merchant_names`)
- `src/finances/views/categories.py` (`uncategorized_lines`, `alias_rows`), `src/finances/cli/categories.py` (`add_rule_command`)
- `src/finances/web/routes/categories.py` (`_categories_page`, `add_rule`, `_priority`), `src/finances/web/render.py` (`NOTICES`), `src/finances/web/templates/categories.html`, `rule_form.html`

## Starting state

N is `3507` when Phase 28a is the last phase built. The newest migration is `0016`; this phase adds none. The rule form `rule_form.html` is included by `categories.html` and by `transactions_one.html`. The given template diff was checked against every earlier integration and end-to-end test, with the new context values below filled in: all 1918 pass unchanged.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/templates/categories.html`, `rule_form.html` | the given diff (R1, R8) |
| `src/finances/web/routes/categories.py` | the page's new context, three routes (R1 to R3, R8) |
| `src/finances/web/render.py` | two notices (R3) |
| `src/finances/db/repositories/categories.py`, `src/finances/db/repositories/__init__.py` | `check_rule` (R4) |
| `src/finances/categorize/service.py` | `PREVIEW_EXAMPLES`, `RuleChange`, `RulePreview`, `preview_rule` (R5) |
| `src/finances/views/categories.py` | `PreviewLine`, `preview_lines`, `preview_text`, `preview_more` (R6) |
| `src/finances/cli/categories.py` | `fin rules preview` (R7) |
| `tests/unit/test_repositories_split.py` | the given diff (R9) |
| `tests/integration/test_web_aliases_and_preview.py`, `tests/e2e/test_cli_rule_preview.py` | new: given |
| `tests/integration/test_rule_preview.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- A preview on the rule edit page, or of editing or deleting a rule; a preview of an alias.
- Keeping the transaction page after a preview made there: the preview always shows the Categories page.
- Any change to `fin aliases`, to 28a's alias rules, or to the uncategorized lists.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/db/repositories/categories.py
def check_rule(
    session: Session, pattern: str, category: str, match: str = "contains"
) -> tuple[str, Category]: ...
# the normalized pattern and the category, or create_rule's ValueError

# src/finances/categorize/service.py
PREVIEW_EXAMPLES = 10

@dataclass(frozen=True)
class RuleChange:
    transaction: Transaction
    account: str      # the account's name
    merchant: str     # merchant_name of the description: the merged name
    now: str | None   # the category it has now, None when it has none

@dataclass(frozen=True)
class RulePreview:
    category: str               # the category's own name
    changes: int                # how many transactions the rule would put in it
    examples: list[RuleChange]  # the newest PREVIEW_EXAMPLES of them

def preview_rule(
    session: Session, pattern: str, category: str, *, match: str = "contains", priority: int = 0
) -> RulePreview: ...

# src/finances/views/categories.py
@dataclass(frozen=True)
class PreviewLine:
    id: str
    date: str
    account: str
    merchant: str
    amount: str
    now: str  # "" when it has no category

def preview_lines(preview: RulePreview) -> list[PreviewLine]: ...
def preview_text(preview: RulePreview) -> str: ...
def preview_more(preview: RulePreview) -> str | None: ...
```

New routes on the categories router:

| Route | Fields | On success | On a `ValueError` |
|---|---|---|---|
| `POST /categories/aliases/add` | `csrf`, `source`, `target` | 303 to `/categories?notice=merchant-merged` | the Categories page, 400, the error, `alias_form` the typed values |
| `POST /categories/aliases/delete` | `csrf`, `source` | 303 to `/categories?notice=merchant-unmerged` | the Categories page, 400, the error, `alias_form` empty |
| `POST /categories/rules/preview` | `csrf`, `pattern`, `match`, `priority`, `category`, `back` | the Categories page, 200, `rule_form` the typed values, `preview` filled | the Categories page, 400, the error, `rule_form` the typed values, `preview` None |

Each starts with `refused(request, csrf)`, as the page's other forms do.

New context of `_categories_page`, for every render of the page:

| Name | Value |
|---|---|
| `aliases` | `alias_rows(list_aliases(session))` |
| `alias_form` | `{"source": ..., "target": ...}`, both `""` by default |
| `preview` | None, or `{"text": preview_text(p), "rows": preview_lines(p), "more": preview_more(p)}` |

## Requirements

### Aliases on the web

- **R1.** Apply the given template diff exactly. `_categories_page` supplies the three context values above on every render.
- **R2.** `POST /categories/aliases/add` calls `add_alias`, then `categorize(session)`, in one session, as `add_rule` does. A refusal stores nothing and does not run the rules.
- **R3.** `POST /categories/aliases/delete` calls `delete_alias`, then `categorize(session)`, in one session. `NOTICES` gains `"merchant-merged": "Merchants merged, and the rules were run again."` and `"merchant-unmerged": "Merchant alias removed, and the rules were run again."`.

### The preview

- **R4.** `check_rule` makes `create_rule`'s four checks, in its order and with its messages (the pattern's length, the match, the category, a rule with this match and pattern), and returns the normalized pattern and the category. `create_rule` calls it; its behaviour is unchanged. It is re-exported from `finances.db.repositories`.
- **R5.** `preview_rule` calls `check_rule` first, so it refuses exactly what `create_rule` would. It then imagines the rule added: a `CategoryRule` whose id is one more than the highest rule id (1 when there are none), with the normalized pattern, the match, the priority, and the category. Over the transactions `categorize` goes over (`list_transaction_descriptions`), skipping those whose category was set by hand, a transaction **counts** when `pick_rule_for(merchant_names(description, aliases), rules + [the new rule])` is the new rule and the transaction's current category is not the rule's category. `changes` is how many count; `examples` are the newest `PREVIEW_EXAMPLES` of them, by posted date, then id, both descending. `preview_rule` writes nothing.
- **R6.** `preview_text` is `This rule would put 3 transactions in Dining.`, with `1 transaction` for one and `no transactions` for none, and the category's own name. `preview_lines` gives one line per example (`format_cents` for the amount, `""` for no category). `preview_more` is `Showing the 10 newest.` (the number of examples) when `changes` is more than the number of examples, otherwise None.
- **R7.** `fin rules preview` on `rules_app`, with `--pattern` and `--category` required, `--match` (default `contains`) and `--priority` (default 0) as `fin rules add` has them. It calls `require_current_schema()`, prints `preview_text`, then, when there are examples, a table with headings `ID`, `Date`, `Account`, `Merchant`, `Amount`, `Now` by `print_rows`, then `preview_more` when it is not None. A refusal is `fail(message)`.
- **R8.** `POST /categories/rules/preview` reads the priority with `_priority` (its refusal included), calls `preview_rule`, and renders the page as the table above says. `back` is accepted and not used. The rule form's Preview button is in the given diff.
- **R9.** Apply the given diff to `tests/unit/test_repositories_split.py`. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/templates/` (do not change).

```text
diff --git a/src/finances/web/templates/categories.html b/src/finances/web/templates/categories.html
index 48d99c7..96717ea 100644
--- a/src/finances/web/templates/categories.html
+++ b/src/finances/web/templates/categories.html
@@ -35,6 +35,18 @@
 <section class="card">
 <h2>Add a rule</h2>
 {% with back = "" %}{% include "rule_form.html" %}{% endwith %}
+{% if preview %}
+<p class="preview">{{ preview.text }}</p>
+{% if preview.rows %}
+<table>
+<thead><tr><th>ID</th><th>Date</th><th>Account</th><th>Merchant</th><th class="amount">Amount</th><th>Now</th></tr></thead>
+<tbody>
+{% for row in preview.rows %}<tr><td><a href="/transactions/{{ row.id }}">{{ row.id }}</a></td><td>{{ row.date }}</td><td>{{ row.account }}</td><td>{{ row.merchant }}</td><td class="{{ row.amount|amount_class }}">{{ row.amount }}</td><td>{{ row.now }}</td></tr>
+{% endfor %}</tbody>
+</table>
+{% endif %}
+{% if preview.more %}<p class="hint">{{ preview.more }}</p>{% endif %}
+{% endif %}
 </section>
 <section class="card">
 <h2>Categories</h2>
@@ -104,4 +116,24 @@
   <button type="submit">Delete</button>
 </form>
 </section>
+<section class="card">
+<h2>Merchant aliases</h2>
+<p class="hint">Merge one merchant into another so reports count them as one; a rule matches either name. Adding or deleting an alias runs the rules again.</p>
+{% if aliases %}
+<table>
+<thead><tr><th>From</th><th>To</th><th></th></tr></thead>
+<tbody>
+{% for row in aliases %}<tr><td>{{ row.source }}</td><td>{{ row.target }}</td><td><form method="post" action="/categories/aliases/delete" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="source" value="{{ row.source }}"><button type="submit">Delete</button></form></td></tr>
+{% endfor %}</tbody>
+</table>
+{% else %}
+<p class="empty">No merchant aliases.</p>
+{% endif %}
+<form method="post" action="/categories/aliases/add" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <label>Merchant <input name="source" required maxlength="100" value="{{ alias_form.source }}"></label>
+  <label>Merge into <input name="target" required maxlength="100" value="{{ alias_form.target }}"></label>
+  <button type="submit">Merge</button>
+</form>
+</section>
 {% endblock %}
diff --git a/src/finances/web/templates/rule_form.html b/src/finances/web/templates/rule_form.html
index 8acca9d..67fd826 100644
--- a/src/finances/web/templates/rule_form.html
+++ b/src/finances/web/templates/rule_form.html
@@ -13,4 +13,5 @@
     {% with selected = rule_form.category %}{% include "category_select.html" %}{% endwith %}
   </label>
   <button type="submit">Add rule</button>
+  <button type="submit" formaction="/categories/rules/preview">Preview</button>
 </form>
```

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index a1fc465..d86899a 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -114,6 +114,7 @@ HOMES = {
         "CategoryDeletion",
         "CategoryExistsError",
         "create_category",
+        "check_rule",
         "create_rule",
         "delete_category",
         "delete_rule",
@@ -149,7 +150,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 103
+    assert len(expected) == 104
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

12 tests in two files. Do not change them. Two of them (`test_no_aliases_yet`, `test_both_rule_forms_offer_a_preview`) pass once the given templates and R1's context are in.

`tests/integration/test_web_aliases_and_preview.py`

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
    list_rules,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

PREVIEW_HEADINGS = ["ID", "Date", "Account", "Merchant", "Amount", "Now"]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Card: 1 ACME CAFE, 2 and 3 ACME COFFEE, 4 FOOBAR GROCERY; rule 1 puts ACME COFFEE in
    Coffee & Dessert, so 2 and 3 are categorized and 1 and 4 are not."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            (
                (-450, "ACME CAFE"),
                (-500, "ACME COFFEE"),
                (-700, "SQ *ACME COFFEE 12345"),
                (-2599, "FOOBAR GROCERY #77"),
            ),
            start=1,
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
        create_rule(session, "ACME COFFEE", "Coffee & Dessert")
        categorize(session)
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


def rule_count() -> int:
    engine = get_engine()
    with session_scope(engine) as session:
        found = len(list_rules(session))
    engine.dispose()
    return found


def test_no_aliases_yet(home: TestClient) -> None:
    found = page(home, "/categories")
    assert texts(found, "empty") == ["No merchant aliases."]
    assert sorted(found.find("/categories/aliases/add")["inputs"]) == ["csrf", "source", "target"]


def test_merging_on_the_page(home: TestClient) -> None:
    response = post(home, "/categories/aliases/add", source=" acme  cafe ", target="acme coffee")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/categories?notice=merchant-merged",
    )
    found = page(home, "/categories?notice=merchant-merged")
    assert texts(found, "notice") == ["Merchants merged, and the rules were run again."]
    assert found.rows[-2:] == [["From", "To", ""], ["ACME CAFE", "ACME COFFEE", "Delete"]]
    assert found.find("/categories/aliases/delete")["inputs"]["source"] == ("hidden", "ACME CAFE")
    assert categories_of() == {1: "Coffee & Dessert", 2: "Coffee & Dessert", 3: "Coffee & Dessert"}


def test_unmerging_on_the_page(home: TestClient) -> None:
    post(home, "/categories/aliases/add", source="ACME CAFE", target="ACME COFFEE")
    response = post(home, "/categories/aliases/delete", source="ACME CAFE")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/categories?notice=merchant-unmerged",
    )
    found = page(home, "/categories?notice=merchant-unmerged")
    assert texts(found, "notice") == ["Merchant alias removed, and the rules were run again."]
    assert texts(found, "empty") == ["No merchant aliases."]
    assert categories_of() == {2: "Coffee & Dessert", 3: "Coffee & Dessert"}


@pytest.mark.parametrize(
    ("path", "fields", "message"),
    [
        (
            "/categories/aliases/add",
            {"source": "ACME CAFE", "target": "Acme Cafe"},
            "a merchant cannot be merged into itself",
        ),
        ("/categories/aliases/delete", {"source": "BAZ CAFE"}, "alias not found"),
    ],
)
def test_a_refused_alias(home: TestClient, path: str, fields: dict, message: str) -> None:
    response = post(home, path, **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == [message]
    assert found.find("/categories/aliases/add")["inputs"]["source"] == (
        "text",
        fields["source"] if path.endswith("add") else "",
    )


def test_previewing_a_rule(home: TestClient) -> None:
    response = post(
        home,
        "/categories/rules/preview",
        pattern="acme",
        match="contains",
        priority="5",
        category="Dining",
    )
    assert response.status_code == 200
    found = Page(response.text)
    assert texts(found, "preview") == ["This rule would put 3 transactions in Dining."]
    start = found.rows.index(PREVIEW_HEADINGS)
    assert found.rows[start + 1 : start + 4] == [
        ["3", "2026-05-03", "Test Card", "ACME COFFEE", "-$7.00", "Coffee & Dessert"],
        ["2", "2026-05-02", "Test Card", "ACME COFFEE", "-$5.00", "Coffee & Dessert"],
        ["1", "2026-05-01", "Test Card", "ACME CAFE", "-$4.50", ""],
    ]
    inputs = found.find("/categories/rules/add")["inputs"]
    assert (inputs["pattern"], inputs["priority"]) == (("text", "acme"), ("text", "5"))
    assert rule_count() == 1
    assert categories_of() == {2: "Coffee & Dessert", 3: "Coffee & Dessert"}


def test_a_refused_preview(home: TestClient) -> None:
    response = post(
        home,
        "/categories/rules/preview",
        pattern="acme coffee",
        match="contains",
        priority="",
        category="Dining",
    )
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == ["a rule with this pattern and match already exists"]
    assert texts(found, "preview") == []


def test_both_rule_forms_offer_a_preview(home: TestClient) -> None:
    for path in ("/categories", "/transactions/1"):
        assert 'formaction="/categories/rules/preview">Preview</button>' in home.get(path).text
```

`tests/e2e/test_cli_rule_preview.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import failed_cleanly, plain_lines, run, table_rows

HEADINGS = ["ID", "Date", "Account", "Merchant", "Amount", "Now"]


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """Eleven ACME CAFE purchases (1 to 11, May 1 to 11) and FOOBAR GROCERY (12, May 12) on a
    card. No rules."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [(-450, "ACME CAFE")] * 11 + [(-3000, "FOOBAR GROCERY")]
        for number, (cents, description) in enumerate(rows, start=1):
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
    engine.dispose()
    return tmp_settings


def test_a_preview_shows_the_ten_newest(card: Settings) -> None:
    result = run("rules", "preview", "--pattern", "acme", "--category", "Dining")
    assert result.exit_code == 0
    assert plain_lines(result.stdout) == [
        "This rule would put 11 transactions in Dining.",
        "Showing the 10 newest.",
    ]
    assert table_rows(result.stdout) == [
        HEADINGS,
        ["11", "2026-05-11", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["10", "2026-05-10", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["9", "2026-05-09", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["8", "2026-05-08", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["7", "2026-05-07", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["6", "2026-05-06", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["5", "2026-05-05", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["4", "2026-05-04", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["3", "2026-05-03", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["2", "2026-05-02", "Test Card", "ACME CAFE", "-$4.50", ""],
    ]
    assert run("rules", "list").stdout == "No rules.\n"


def test_one_transaction(card: Settings) -> None:
    result = run(
        "rules",
        "preview",
        "--pattern",
        "foobar grocery",
        "--match",
        "equals",
        "--category",
        "Groceries",
    )
    assert plain_lines(result.stdout) == ["This rule would put 1 transaction in Groceries."]
    assert table_rows(result.stdout) == [
        HEADINGS,
        ["12", "2026-05-12", "Test Card", "FOOBAR GROCERY", "-$30.00", ""],
    ]


def test_no_transactions(card: Settings) -> None:
    result = run("rules", "preview", "--pattern", "TEA", "--category", "dining")
    assert (result.exit_code, result.stdout) == (
        0,
        "This rule would put no transactions in Dining.\n",
    )


def test_a_refused_preview(card: Settings) -> None:
    result = run("rules", "preview", "--pattern", "acme", "--match", "like", "--category", "Dining")
    assert failed_cleanly(result, "match must be one of: contains, starts_with, equals")
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_rule_preview.py`:

- `check_rule("  acme  coffee ", "dining")` returns `("ACME COFFEE", <the Dining category>)`; each of its four refusals once;
- a transaction whose category was set by hand and that the rule matches does not count;
- with `contains "ACME COFFEE" -> Dining` in place, a preview of `contains "ACME" -> Dining` at priority 5 does not count the ACME COFFEE purchases: the rule wins but changes nothing;
- with `contains "ACME COFFEE" -> Coffee & Dessert` in place, `contains "ACME" -> Dining` at priority 0 does not count an ACME COFFEE purchase (the older rule wins the tie), and at priority 1 it does;
- with the alias `ACME CAFE -> ACME COFFEE`, `equals "ACME COFFEE"` counts an `ACME CAFE` purchase, and the example's merchant is `ACME COFFEE`;
- two counted transactions on the same day come newest id first;
- a preview changes nothing: the rules and the audit trail are the same after it; and on the same data, `create_rule` then `categorize` reports `changed` equal to the preview's `changes`;
- on the web, a preview with priority `x` answers 400 with `priority must be a whole number`.

## Rules for this phase

- `preview_rule` decides by `pick_rule_for` and `merchant_names`, the functions `categorize` uses; no route, command, or view picks a rule or names a merchant.
- The routes and the command parse fields, call one function, and render or print; every text comes from `views` or `NOTICES`.
- Messages are constant and echo no merchant name or pattern.
- Earlier tests stay unchanged except the given diff; keep `web/routes/categories.py` under 400 lines.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 12 tests; at least N + 12 passed in all;
- `git diff --stat HEAD -- tests` lists only the file of the given diff;
- `git grep -n "pick_rule\|merchant_names\|rule_matches" -- src/finances/web src/finances/cli src/finances/views` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.db.repositories --cov=finances.categorize.service --cov=finances.views.categories --cov=finances.cli.categories --cov=finances.web.routes.categories --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 28b: aliases on the web and the rule preview (YYYY-MM-DD)`.
