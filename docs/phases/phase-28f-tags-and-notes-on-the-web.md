# Phase 28f: tags and notes on the web

## Goal

28c's tags and notes reach the browser. After this phase:

- a transaction's page shows its tags (each a link to the transactions carrying it, each with a Remove button), a form to add a tag, its note, and a form to save or remove the note;
- the Transactions page has a Tag filter, a choice of every tag in use, so search, the bulk form's way back, and select-all keep it;
- search (`search_transactions`) takes a tag, so anything built on it can filter by one.

Splits on the web (28g) come next.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-28c-tags-and-notes.md`
- `src/finances/db/repositories/tags.py`, `src/finances/domain/tags.py` (`normalize_tag`)
- `src/finances/analysis/search.py` (`TransactionQuery`, `search_transactions`)
- `src/finances/web/routes/transactions.py` (`_SEARCH_FIELDS`, `_FILTER_FIELDS`, `_transactions_page`, `_transaction_page`, `set_category`, `_known_transaction`, `_missing_transaction`), `src/finances/web/render.py` (`NOTICES`), `src/finances/web/templates/transactions.html`, `transactions_one.html`

## Starting state

N is `3640` when Phase 28e is the last phase built. The newest migration is `0019`; this phase adds none. `tags_for` reads with one `IN` over the ids it is given, so it is for a page's transactions, not for a whole search. The given template diff was checked against every earlier integration and end-to-end test, with the new context values below filled in: all 2019 pass unchanged.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/templates/transactions_one.html`, `transactions.html` | the given diff (R1, R6) |
| `src/finances/web/routes/transactions.py` | the two pages' new context, the tag field, three routes (R1 to R4, R6) |
| `src/finances/web/render.py` | four notices (R5) |
| `src/finances/db/repositories/tags.py`, `src/finances/db/repositories/__init__.py` | `tagged_with` (R7) |
| `src/finances/analysis/search.py` | `TransactionQuery.tag` (R8) |
| `tests/unit/test_web_split.py`, `tests/unit/test_repositories_split.py` | the given diff (R9) |
| `tests/integration/test_web_tags_and_notes.py` | new: given |
| `tests/integration/test_web_tags_and_notes_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- A Tags or Note column on the Transactions page, or a tag in any table earlier tests read; tags or notes in an MCP tool, `fin transactions list`, or a report.
- Tagging from the bulk form; renaming or merging tags.
- Splits on the web (28g).

## Dependencies

None new. No migration.

## Design

```python
# src/finances/db/repositories/tags.py
def tagged_with(session: Session, tag: str) -> set[int]: ...
# the ids of the transactions that carry the tag, normalized with normalize_tag (its refusal)

# src/finances/analysis/search.py
@dataclass(frozen=True)
class TransactionQuery:
    ...              # the fields of today, unchanged and in order
    tag: str = ""    # only transactions carrying this tag; "" for any
```

New routes on the transactions router; each starts with `refused(request, csrf)`, then `_known_transaction` (an unknown id gives `_missing_transaction`, 404), as `set_category` does:

| Route | Fields | Calls | On success | On a `ValueError` |
|---|---|---|---|---|
| `POST /transactions/{transaction_id}/tags/add` | `csrf`, `tag` | `add_tags(session, [id], tag)` | 303 to `/transactions/{id}?notice=tag-added` | the transaction's page, 400, the error |
| `POST /transactions/{transaction_id}/tags/remove` | `csrf`, `tag` | `remove_tags(session, [id], tag)` | 303 to `...?notice=tag-removed` | the same |
| `POST /transactions/{transaction_id}/note` | `csrf`, `text` | `set_note(session, id, text)` | 303 to `...?notice=note-saved`, or `...?notice=note-removed` when it returns None | the same |

New context:

| Page | Name | Value |
|---|---|---|
| a transaction's page | `tags` | its tags, from `tags_for(session, [id])`, `[]` when none |
| a transaction's page | `note` | `note_of(session, id)` |
| the Transactions page | `tag_choices` | each tag in use, from `list_tags`, by tag |

## Requirements

### A transaction's page

- **R1.** Apply the given template diff exactly. `_transaction_page` supplies `tags` and `note` on every render, the 400 renders included.
- **R2.** `POST /transactions/{transaction_id}/tags/add` and `/tags/remove` as designed.
- **R3.** `POST /transactions/{transaction_id}/note` as designed: an empty text removes the note.
- **R4.** GET on each of the three new paths answers 405.
- **R5.** `NOTICES` gains `"tag-added": "Tag added."`, `"tag-removed": "Tag removed."`, `"note-saved": "Note saved."`, `"note-removed": "Note removed."`.

### The tag filter

- **R6.** `"tag"` is the last of `_SEARCH_FIELDS`, so it is a filter field, sent to `TransactionQuery`, kept in the bulk form's `back` and the select-all link, and in `chosen`. `_transactions_page` supplies `tag_choices` on every render.
- **R7.** `tagged_with` as designed, in one query over `transaction_tags` (no `IN` over a list of ids), re-exported from `finances.db.repositories`.
- **R8.** `search_transactions`, when `query.tag` is not blank after stripping, finds only transactions in `tagged_with(session, query.tag)`; each part of a split transaction that carries the tag is found as 28e says. A tag that `normalize_tag` refuses is refused with its message, as the other filters refuse a bad value, so the page answers 400. A blank tag filters nothing.
- **R9.** Apply the given diff to the two earlier test files. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/templates/` (do not change).

```text
diff --git a/src/finances/web/templates/transactions.html b/src/finances/web/templates/transactions.html
index bc53169..7a69459 100644
--- a/src/finances/web/templates/transactions.html
+++ b/src/finances/web/templates/transactions.html
@@ -31,6 +31,13 @@
       {% endfor %}
     </select>
   </label>
+  <label>Tag
+    <select name="tag">
+      <option value=""{% if not chosen.tag %} selected{% endif %}>Any tag</option>
+      {% for tag in tag_choices %}<option value="{{ tag }}"{% if tag == chosen.tag %} selected{% endif %}>{{ tag }}</option>
+      {% endfor %}
+    </select>
+  </label>
   <label>Merchant <input name="merchant" value="{{ chosen.merchant }}"></label>
   <label>From <input type="date" name="from" value="{{ chosen['from'] }}"></label>
   <label>To <input type="date" name="to" value="{{ chosen['to'] }}"></label>
diff --git a/src/finances/web/templates/transactions_one.html b/src/finances/web/templates/transactions_one.html
index ac292fb..8304bce 100644
--- a/src/finances/web/templates/transactions_one.html
+++ b/src/finances/web/templates/transactions_one.html
@@ -58,6 +58,28 @@
 {% endif %}
 </section>
 <section class="card">
+<h2>Tags</h2>
+{% if tags %}<p class="tags">{% for tag in tags %}<a href="/transactions?tag={{ tag|urlencode }}">{{ tag }}</a>{% if not loop.last %}, {% endif %}{% endfor %}</p>
+{% for tag in tags %}<form method="post" action="/transactions/{{ detail.id }}/tags/remove" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="tag" value="{{ tag }}"><button type="submit">Remove {{ tag }}</button></form>
+{% endfor %}
+{% else %}<p class="tags">No tags.</p>
+{% endif %}
+<form method="post" action="/transactions/{{ detail.id }}/tags/add" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <label>Tag <input name="tag" required maxlength="30"></label>
+  <button type="submit">Add tag</button>
+</form>
+</section>
+<section class="card">
+<h2>Note</h2>
+{% if note %}<p class="note">{{ note }}</p>{% endif %}
+<form method="post" action="/transactions/{{ detail.id }}/note" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <label>Note <textarea name="text" maxlength="500">{{ note or "" }}</textarea></label>
+  <button type="submit">Save note</button>
+</form>
+</section>
+<section class="card">
 <h2>Make a rule from this merchant</h2>
 {% with back = detail.id %}{% include "rule_form.html" %}{% endwith %}
 </section>
```

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 4b2917a..2900f8d 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -142,6 +142,7 @@ HOMES = {
         "note_of",
         "remove_tags",
         "set_note",
+        "tagged_with",
         "tags_for",
     ],
     "transfers": [
@@ -165,7 +166,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 115
+    assert len(expected) == 116
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 3db51c7..40aab3b 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -45,6 +45,9 @@ ROUTES = {
     ("GET", "/transactions/{transaction_id}"),
     ("POST", "/transactions/{transaction_id}/category"),
     ("POST", "/transactions/{transaction_id}/category/clear"),
+    ("POST", "/transactions/{transaction_id}/tags/add"),
+    ("POST", "/transactions/{transaction_id}/tags/remove"),
+    ("POST", "/transactions/{transaction_id}/note"),
     ("GET", "/statements"),
     ("POST", "/statements/upload"),
     ("GET", "/categories"),
```

## Given tests

9 tests in one file. Do not change them. One (`test_a_transaction_with_neither`) passes once the given template is in, since it renders `No tags.` when no tags are given.

`tests/integration/test_web_tags_and_notes.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import add_tags, create_account, set_note
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Card: 1 ACME COFFEE tagged tax and trip with a note, 2 FOOBAR GROCERY tagged trip,
    3 BAZ CAFE with neither."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-450, "ACME COFFEE"), (-2599, "FOOBAR GROCERY"), (-500, "BAZ CAFE")), start=1
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
        add_tags(session, [1, 2], "trip")
        add_tags(session, [1], "tax")
        set_note(session, 1, "split with a friend")
    engine.dispose()
    client.get("/transactions")
    return client


def test_a_transaction_with_tags_and_a_note(home: TestClient) -> None:
    found = page(home, "/transactions/1")
    assert texts(found, "tags") == ["tax, trip"]
    assert "/transactions?tag=trip" in found.links
    assert [form["inputs"]["tag"] for form in found.all("/transactions/1/tags/remove")] == [
        ("hidden", "tax"),
        ("hidden", "trip"),
    ]
    assert texts(found, "note") == ["split with a friend"]
    assert sorted(found.find("/transactions/1/tags/add")["inputs"]) == ["csrf", "tag"]


def test_a_transaction_with_neither(home: TestClient) -> None:
    found = page(home, "/transactions/3")
    assert (texts(found, "tags"), texts(found, "note")) == (["No tags."], [])


def test_adding_and_removing_a_tag(home: TestClient) -> None:
    added = post(home, "/transactions/3/tags/add", tag=" Work  Trip ")
    assert (added.status_code, added.headers["location"]) == (
        303,
        "/transactions/3?notice=tag-added",
    )
    found = page(home, "/transactions/3?notice=tag-added")
    assert (texts(found, "notice"), texts(found, "tags")) == (["Tag added."], ["work trip"])
    removed = post(home, "/transactions/1/tags/remove", tag="TRIP")
    assert (removed.status_code, removed.headers["location"]) == (
        303,
        "/transactions/1?notice=tag-removed",
    )
    found = page(home, "/transactions/1?notice=tag-removed")
    assert (texts(found, "notice"), texts(found, "tags")) == (["Tag removed."], ["tax"])


def test_saving_and_removing_the_note(home: TestClient) -> None:
    saved = post(home, "/transactions/3/note", text="  paid back  ")
    assert (saved.status_code, saved.headers["location"]) == (
        303,
        "/transactions/3?notice=note-saved",
    )
    found = page(home, "/transactions/3?notice=note-saved")
    assert (texts(found, "notice"), texts(found, "note")) == (["Note saved."], ["paid back"])
    removed = post(home, "/transactions/3/note", text="")
    assert (removed.status_code, removed.headers["location"]) == (
        303,
        "/transactions/3?notice=note-removed",
    )
    found = page(home, "/transactions/3?notice=note-removed")
    assert (texts(found, "notice"), texts(found, "note")) == (["Note removed."], [])


@pytest.mark.parametrize(
    ("path", "fields", "status", "message"),
    [
        ("/transactions/1/tags/add", {"tag": "   "}, 400, "a tag must be 1 to 30 characters"),
        ("/transactions/1/note", {"text": "x" * 501}, 400, "a note is at most 500 characters"),
        ("/transactions/99/tags/remove", {"tag": "trip"}, 404, "transaction not found"),
    ],
)
def test_a_refused_form(
    home: TestClient, path: str, fields: dict, status: int, message: str
) -> None:
    response = post(home, path, **fields)
    assert response.status_code == status
    assert texts(Page(response.text), "error") == [message]


def test_the_tag_filter(home: TestClient) -> None:
    found = page(home, "/transactions?tag=TRIP")
    assert [row[2] for row in found.rows[1:]] == ["FOOBAR GROCERY", "ACME COFFEE"]
    assert found.find("/transactions")["selects"]["tag"] == [
        ("", False),
        ("tax", False),
        ("trip", False),
    ]
    assert found.find("/transactions/bulk")["inputs"]["back"] == ("hidden", "tag=TRIP")
    chosen = page(home, "/transactions?tag=trip").find("/transactions")["selects"]["tag"]
    assert chosen == [("", False), ("tax", False), ("trip", True)]


def test_a_tag_filter_that_is_refused(home: TestClient) -> None:
    response = home.get("/transactions?tag=" + "x" * 31)
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["a tag must be 1 to 30 characters"]
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_web_tags_and_notes_more.py`:

- GET on each of the three new paths answers 405;
- a refused tag on a transaction's page keeps its tags and note on the 400 page (R1's context on every render);
- `tagged_with("  TRIP ")` finds the transactions tagged `trip`, and `tagged_with("")` is refused with `normalize_tag`'s message;
- `search_transactions(TransactionQuery(tag="trip", category="Dining"))` finds only transactions with both; a split transaction tagged `trip` is found once per part;
- the select-all link on `/transactions?tag=trip` keeps `tag=trip`;
- a form posted without a valid form token is refused, as on the other forms.

## Rules for this phase

- The routes parse fields, call one repository function, and redirect or render; every text comes from `NOTICES`, the templates, or the repository's messages.
- Messages are constant and echo no tag, note, or description.
- Keep `web/routes/transactions.py` under 400 lines; earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 9 tests; at least N + 9 passed in all;
- `git diff --stat HEAD -- tests` lists only the two files of the given diff;
- `git grep -n "TransactionTagRow\|TransactionNoteRow" -- src/finances/web src/finances/analysis src/finances/views` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.db.repositories --cov=finances.analysis.search --cov=finances.web.routes.transactions --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 28f: tags and notes on the web (YYYY-MM-DD)`.
