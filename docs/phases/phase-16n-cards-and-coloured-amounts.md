# Phase 16n: cards and coloured amounts

## Goal

The second half of the look the owner chose from the mock-up (16m was the first). After this phase every section of every page (each `<h2>` and what follows it) sits in its own card, one shade lighter than the page, and money in a table is coloured by its sign: below zero in red, a gain written with `+` in green, everything else plain. Spent and income columns stay plain, since green on spending would mislead.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-16m-layered-dark-look.md`; `src/finances/web/static/app.css`; `src/finances/web/render.py` (`_TEMPLATES`); `src/finances/views/format.py`
- every template in `src/finances/web/templates/`

## Starting state

N is `3060` when Phase 16m is the last phase built.

No earlier test reads the raw markup of a section or an amount cell (the architect searched), and the test page readers ignore `<section>` and `class`. The architect ran the whole suite with every page post-processed into cards and coloured cells: all passed.

## Scope

| Path | What changes |
|---|---|
| `src/finances/views/format.py` | `amount_class` (R1) |
| `src/finances/web/render.py` | the filter (R2) |
| `src/finances/web/templates/*.html` | cells (R3) and cards (R4) |
| `src/finances/web/static/app.css` | the given diff (R5) |
| `tests/integration/test_web_cards.py`, `tests/unit/test_web_cards_style.py` | new: given |
| `tests/integration/test_web_cards_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- New colours for headers, badges, stat tiles, or chart series; colouring amounts in paragraphs (only table cells).
- Any change to what a page shows: no text, column, row, link, or form changes.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/views/format.py
def amount_class(text: str) -> str: ...  # "amount neg", "amount pos", or "amount"
```

## Requirements

- **R1.** `amount_class(text)` is `"amount neg"` when the text starts with `-$`, `"amount pos"` when it starts with `+$`, and `"amount"` otherwise (also for `-15%`, `+20%`, `81%`, `$0.00`, and the empty text). It reads the formatted text only.
- **R2.** `render.py` registers it as the Jinja filter `amount_class` on `_TEMPLATES.env`.
- **R3.** Every amount cell `<td class="amount">{{ EXPR }}</td>` in the templates (each holds one expression) becomes `<td class="{{ EXPR|amount_class }}">{{ EXPR }}</td>`. Heading cells (`<th class="amount">`) do not change.
- **R4.** In every template, each `<h2>` opens a `<section class="card">`: the `<h2>` is its first child, and the card holds everything after it up to the next `<h2>` at the same level, or to the end of the Jinja branch or block it is in. A card opens and closes inside the same `{% if %}` branch or `{% for %}` body. Content before a page's first `<h2>` stays outside the cards, and nothing after the first card stands outside one (a trailing link goes into the last card). Where an existing `<section>` already starts with the `<h2>` (`sync_accounts.html`'s `<section class="map">`), it becomes `<section class="map card">` instead of gaining a wrapper. `<section class="map">` blocks that start with an `<h3>` (`sync.html`) stay as they are, inside their card.
- **R5.** `app.css` gets the given diff, exactly: the card, the darker table inside a card, banners inside a card, and the two money colours. 16m's style tests keep passing.
- **R6.** Every earlier test passes unchanged.

## Given tests

28 tests in two files. The page tests render 17 pages from synthetic data and check where every `<h2>` sits and the class of every amount cell; `_today` is replaced after the app is created.

`tests/integration/test_web_cards.py`

```python
from datetime import date
from html.parser import HTMLParser

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
    set_budget,
)
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_PORT

TODAY = date(2026, 5, 25)
WITH_SECTIONS = [
    "/",
    "/accounts",
    "/account?name=Test%20Card",
    "/people",
    "/transactions/1",
    "/statements",
    "/categories",
    "/transfers",
    "/reports",
    "/insights",
    "/budgets",
    "/ahead",
    "/ahead?account=Test%20Checking",
    "/sync",
    "/backups",
]
EVERY_PAGE = [*WITH_SECTIONS, "/transactions", "/categories/rules/1"]
VOID = {"input", "br", "meta", "link", "img", "hr"}


class Layout(HTMLParser):
    """Where each h2 sits, and what stands loose in main once the cards begin."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.in_main = False
        self.sections: list[list] = []
        self.cards = 0
        self.problems: list[str] = []
        self.amounts: list[tuple[set[str], str]] = []
        self.cell: tuple[set[str], list[str]] | None = None
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = set((dict(attrs).get("class") or "").split())
        if tag == "main":
            self.in_main = True
            return
        if not self.in_main:
            return
        if tag == "td" and "amount" in classes:
            self.cell = (classes, [])
        if tag == "h2":
            top = self.sections[-1] if self.sections else None
            if top is None or "card" not in top[0] or top[1]:
                self.problems.append("an h2 that does not open a card")
        elif not self.sections and self.cards and tag not in VOID and "card" not in classes:
            self.problems.append(f"a <{tag}> outside the cards")
        if self.sections:
            self.sections[-1][1] = True
        if tag == "section":
            self.sections.append([classes, False])
            if "card" in classes:
                self.cards += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self.in_main = False
        elif tag == "section" and self.sections:
            self.sections.pop()
        elif tag == "td" and self.cell is not None:
            self.amounts.append((self.cell[0], "".join(self.cell[1]).strip()))
            self.cell = None

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell[1].append(data)


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return found


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """A card, checking, and savings in April and May 2026: purchases, a refund, pay, a card
    payment that pairs, a move to savings with two possible matches, a budget, an owner."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        set_account_owner(session, card.id, create_person(session, "Pat Example").id)
        add_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.STATEMENT)
        add_balance_snapshot(session, checking.id, date(2026, 4, 30), 310000, DataSource.STATEMENT)
        rows = [
            (card, date(2026, 4, 12), -3000, "FOOBAR GROCERY"),
            (checking, date(2026, 4, 15), 300000, "PAYCHECK EXAMPLE CORP"),
            (card, date(2026, 5, 3), -1500, "BAZ BOOKS"),
            (card, date(2026, 5, 4), 1500, "BAZ BOOKS REFUND"),
            (checking, date(2026, 5, 5), -2000, "TRANSFER TO SAVINGS"),
            (savings, date(2026, 5, 5), 2000, "TRANSFER FROM CHECKING"),
            (savings, date(2026, 5, 6), 2000, "TRANSFER FROM CHECKING"),
            (checking, date(2026, 5, 10), -50000, "PAYMENT TO TEST CARD"),
            (card, date(2026, 5, 11), 50000, "PAYMENT THANK YOU"),
            (card, date(2026, 5, 10), -20000, "FOOBAR GROCERY"),
            (card, date(2026, 5, 20), -3500, "LATE FEE"),
        ] + [(card, date(2026, 5, day), -500, "ACME COFFEE") for day in (1, 2, 4, 6, 8, 11, 13, 15)]
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
        for pattern, category in (("FOOBAR", "Groceries"), ("PAYCHECK", "Paycheck")):
            create_rule(session, pattern, category)
        categorize(session)
        pair_transfers(session)
        set_budget(session, "Groceries", 15000)
    engine.dispose()
    return client


@pytest.mark.parametrize("path", WITH_SECTIONS)
def test_every_section_is_a_card(home: TestClient, path: str) -> None:
    response = home.get(path)
    assert response.status_code == 200
    found = Layout(response.text)
    assert found.problems == []
    assert found.cards >= 1


def test_amounts_are_coloured_by_sign(home: TestClient) -> None:
    wrong = []
    seen = set()
    for path in EVERY_PAGE:
        for classes, text in Layout(home.get(path).text).amounts:
            tone = "neg" if text.startswith("-$") else "pos" if text.startswith("+$") else None
            expected = {"amount"} | ({tone} if tone else set())
            seen.add(tone)
            if classes != expected:
                wrong.append((path, text, sorted(classes)))
    assert wrong == []
    assert seen == {"neg", "pos", None}
```

`tests/unit/test_web_cards_style.py`

```python
import re
from pathlib import Path

import pytest

import finances.web
from finances.views.format import amount_class

CSS = (Path(finances.web.__file__).parent / "static" / "app.css").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("text", "classes"),
    [
        ("-$12.00", "amount neg"),
        ("+$189.64", "amount pos"),
        ("$3,000.00", "amount"),
        ("$0.00", "amount"),
        ("", "amount"),
        ("-15%", "amount"),
        ("+20%", "amount"),
        ("81%", "amount"),
    ],
)
def test_the_class_of_an_amount_cell(text: str, classes: str) -> None:
    assert amount_class(text) == classes


@pytest.mark.parametrize(
    ("selector", "declaration"),
    [
        ("section.card", "background: var(--surface)"),
        ("section.card table", "background: var(--bg)"),
        ("td.amount.neg", "color: var(--bad)"),
        ("td.amount.pos", "color: var(--good)"),
    ],
)
def test_the_cards_and_colours_come_from_the_stylesheet(selector: str, declaration: str) -> None:
    plain = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    rules = {name.strip(): body for name, body in re.findall(r"([^{}]+)\{([^}]*)\}", plain)}
    assert declaration in rules[selector]
```

## Given diff

```text
diff --git a/src/finances/web/static/app.css b/src/finances/web/static/app.css
index 287ee89..4b6b0ca 100644
--- a/src/finances/web/static/app.css
+++ b/src/finances/web/static/app.css
@@ -66,3 +66,11 @@ p { margin: .35rem 0; }
 ul.links li { margin: .3rem 0; }
 section.map { border-top: 1px solid var(--line); margin-top: 1rem; }
 .chart { max-width: 32rem; margin: .5rem 0 1rem; padding: .75rem; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
+
+/* Cards around each section; money below zero in red, a gain in green. */
+section.card { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: .25rem 1rem .75rem; margin: 1rem 0; }
+section.card > h2 { margin-top: .75rem; }
+section.card table { background: var(--bg); }
+section.card .notice, section.card .error, section.card .attention { background: var(--bg); }
+td.amount.neg { color: var(--bad); }
+td.amount.pos { color: var(--good); }
```

## Tests to write

`tests/integration/test_web_cards_more.py`: the SimpleFIN accounts page of a link with one unmapped account (its section is `map card`, no card inside a card); the error page and the not-migrated page have no card; a page in its empty state (no accounts) still puts every `<h2>` in a card; the Ahead page's detail with nothing expected.

## Rules for this phase

- Templates only gain wrappers and classes: every text, row, link, and form stays as it is.
- No inline style; no script.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_web_cards.py tests/unit/test_web_cards_style.py`, 28 tests; at least N + 28 passed in all;
- `git diff --stat HEAD -- tests`: nothing (earlier tests unchanged);
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.views.format --cov=finances.web.render --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the search `git grep -n '<td class="amount">' -- src/finances/web/templates`: no output (no amount cell left without the filter).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16n: cards and coloured amounts (YYYY-MM-DD)`.
