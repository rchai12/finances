# Phase 16d: new SimpleFIN accounts

## Goal

When the household connects a new bank or card in SimpleFIN, the app notices it and offers to set it up in one click.

Today the next sync receives the new account, reports it as `not mapped`, and stores nothing; the only way to find it is to open a link's SimpleFIN accounts page and look for an empty "Mapped to". After this phase:

- every sync **remembers each SimpleFIN account it receives**, mapped or not, in a new table;
- `fin sync run` (and so the daily log) and the Sync now page say **how many new accounts each link has**;
- the SimpleFIN page has a **New SimpleFIN accounts** section with, for each one, a Create and map form **already filled in** with a guessed name, institution, type, last four digits, and owner, a Map form with **an account the household already has preselected** when it looks like the same one, and a **Don't track** button. Accounts not tracked are listed with **Track again**;
- a sync also runs **every link that has a seen account**, not only links with a mapping, so a freshly linked subscription with nothing mapped yet still has its accounts noticed.

Nothing is created without a click. The guesses only fill the form: SimpleFIN does not say an account's type or owner, and a card already added for its statements must not be created a second time.

## Read first

- `AGENTS.md` (text that fits its column; `web` and `cli` are thin), `docs/architecture.md`
- `docs/phases/phase-16b-web-setup.md` (R9 to R14: link, map, create and map, Sync now)
- `src/finances/sync/runner.py`, `src/finances/cli/sync.py` (`run_command`), `src/finances/web/app.py`, `src/finances/web/templates/sync.html`, `src/finances/web/templates/sync_run.html`
- `src/finances/db/migrations/versions/0006_people.py` and `tests/integration/test_migration_0006.py` (the pattern for a migration and its test)

## Starting state

- Phase 16c is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1877` when Phase 16c is the last phase built.
- The newest migration is `0006`.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0007_feed_seen_accounts.py` | new: given below |
| `src/finances/db/orm.py` | `FeedSeenAccountRow`, `to_seen_feed_account` |
| `src/finances/domain/models.py` | `SeenFeedAccount` |
| `src/finances/domain/feed_setup.py` | new: `TEXT_LIMIT`, `NO_NAME`, `AccountGuess`, `guess_account`, `guess_owner`, `suggest_existing`, `new_accounts` |
| `src/finances/db/repositories.py` | `record_seen_feed_account`, `list_new_feed_accounts`, `set_feed_account_ignored`, `list_feed_links` |
| `src/finances/sync/runner.py` | `run_sync` records what it receives (R9) |
| `src/finances/cli/sync.py` | `fin sync run`: the links it runs and the new-accounts line (R10, R11) |
| `src/finances/web/app.py` | two notices, the new section's context, `/sync/ignore`, `/sync/track`, `owner` and `next` on the mapping forms, the Sync now notice (R12 to R18) |
| `src/finances/web/templates/sync.html`, `src/finances/web/templates/sync_run.html` | replaced: given, do not change |
| `src/finances/web/static/app.css` | one line added (R19) |
| the five test files under "Given tests" | new: given, do not change |
| `docs/progress.md` | one new entry |

You may add private helpers inside the listed modules. Do not change any other production file or any existing test.

## Out of scope

- Creating or mapping an account without a click, or on a schedule.
- Fetching from SimpleFIN when a page is opened. The section uses what the last sync recorded; the live page of a link's accounts stays as it is and records nothing (a `GET` never changes data).
- Editing or deleting accounts, people, owners, or mappings.
- A link-to-person setting. The owner guess uses the link's name only.
- Recording seen accounts from `fin sync accounts`, the live accounts page, or `fin sync link`.

## Dependencies

None new.

## Design

```python
# src/finances/domain/models.py
@dataclass(frozen=True)
class SeenFeedAccount:
    # An aggregator account a sync has delivered under a link, mapped or not.
    id: int
    link: str
    provider_account_id: str
    name: str
    institution: str
    first_seen: date
    last_seen: date
    ignored: bool
```

```python
# src/finances/domain/feed_setup.py  (imports only finances.domain.models)
TEXT_LIMIT = 100
NO_NAME = "New account"


@dataclass(frozen=True)
class AccountGuess:
    name: str
    institution: str
    type: AccountType
    last4: str | None


def guess_account(name: str, institution: str) -> AccountGuess: ...
def guess_owner(link: str, people: list[str]) -> str | None: ...
def suggest_existing(guess: AccountGuess, candidates: list[tuple[str, str | None]]) -> str | None: ...
def new_accounts(count: int) -> str: ...
```

```python
# src/finances/db/repositories.py
def record_seen_feed_account(
    session: Session, link: str, provider_account_id: str, name: str, institution: str, day: date
) -> None: ...
def list_new_feed_accounts(
    session: Session, link: str | None = None, *, ignored: bool = False
) -> list[SeenFeedAccount]: ...
def set_feed_account_ignored(
    session: Session, link: str, provider_account_id: str, ignored: bool
) -> None: ...
def list_feed_links(session: Session) -> list[str]: ...
```

`FeedSeenAccountRow` maps the table of the migration below: `id` the primary key; `link` `String(50)`; `provider_account_id` `String(200)`; `name` and `institution` `String(100)`; `first_seen` and `last_seen` `Date`; `ignored` `Boolean` with the Python default `False`; all not null; the unique constraint `uq_feed_seen_accounts_link_provider_account` on (`link`, `provider_account_id`). `to_seen_feed_account(row)` returns the `SeenFeedAccount`.

The migration, in full:

```python
"""Create the feed_seen_accounts table: every SimpleFIN account a sync has delivered."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_seen_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("link", sa.String(50), nullable=False),
        sa.Column("provider_account_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("institution", sa.String(100), nullable=False),
        sa.Column("first_seen", sa.Date(), nullable=False),
        sa.Column("last_seen", sa.Date(), nullable=False),
        sa.Column("ignored", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_feed_seen_accounts"),
        sa.UniqueConstraint(
            "link", "provider_account_id", name="uq_feed_seen_accounts_link_provider_account"
        ),
    )


def downgrade() -> None:
    op.drop_table("feed_seen_accounts")
```

Messages and notices, in full:

| Where | Text |
|---|---|
| `set_feed_account_ignored`, no such seen account | `SimpleFIN account not found` |
| `NOTICES["ignored"]` | `That SimpleFIN account will not be tracked.` |
| `NOTICES["tracked"]` | `That SimpleFIN account is offered for setup again.` |
| `fin sync run`, per link | `SimpleFIN (LINK): COUNT to set up (open the SimpleFIN page, or run: fin sync accounts --link LINK)` |
| Sync now page, per link | `LINK: COUNT to set up.` |

`COUNT` is `new_accounts(n)`: `1 new account` or `N new accounts`.

## Requirements

### Part 1: guessing (`domain/feed_setup.py`)

- **R1.** `guess_account(name, institution)`:
  - `name` and `institution` are **tidied**: whitespace runs made one space, outer spaces removed, cut to `TEXT_LIMIT` characters, trailing spaces removed. An empty tidied name becomes `NO_NAME`; an empty institution stays empty.
  - The **type** comes from whole words of the tidied name, ignoring case, checked in this order: `checking` or `chk` gives `checking`; `saving`, `savings`, or `money market` gives `savings`; `card`, `credit card`, `visa`, `mastercard`, `amex`, `american express`, or `discover` gives `credit_card`; otherwise `other`. Whole words: `Cardinal` and `Visas` match nothing.
  - **last4** is the name's last run of ASCII digits when that run is exactly four digits long, otherwise `None`. `Card 4400 0000 0000 5555` gives `5555`; `Checking 0001234567` gives `None`.
- **R2.** `guess_owner(link, people)` returns the first person whose name, without outer spaces and ignoring case, equals the link name, without outer spaces and ignoring case; otherwise `None`. It returns the name as given.
- **R3.** `suggest_existing(guess, candidates)`, where each candidate is (account name, last4 or `None`): when `guess.last4` is not `None` and exactly one candidate has that last4, that candidate's name; otherwise the first candidate whose name equals `guess.name` ignoring case; otherwise `None`.
- **R4.** `new_accounts(count)` returns `1 new account` for 1, and `COUNT new accounts` otherwise.

### Part 2: remembering what a sync sees

- **R5.** `record_seen_feed_account(...)` keeps one row per (`link`, `provider_account_id`). A new one gets `first_seen` and `last_seen` set to `day` and `ignored` false. An existing one gets the new name and institution, and `last_seen` becomes the later of its value and `day`; `first_seen` and `ignored` stay. Name and institution are stored with whitespace runs made one space, cut to 100 characters, and trailing spaces removed (the AGENTS.md rule: text from the feed is cut to fit). The caller commits.
- **R6.** `list_new_feed_accounts(session, link=None, *, ignored=False)` returns the seen accounts that have **no mapping under their own link** (an account mapped under another link still counts as new) and whose `ignored` equals the argument, only those of `link` when one is given, ordered by link, then `first_seen`, then id.
- **R7.** `set_feed_account_ignored(session, link, provider_account_id, ignored)` sets the flag, and raises `ValueError("SimpleFIN account not found")` when there is no such seen account.
- **R8.** `list_feed_links(session)` returns the sorted, distinct links that have a mapping or a seen account.
- **R9.** `run_sync` records every account of SimpleFIN's answer with `record_seen_feed_account(session, link, account id, name, institution, today)` right after the answer is read, before it applies anything. Its result is unchanged.

### Part 3: the command

- **R10.** `fin sync run` without `--link` runs the links of `list_feed_links`, so a link with only seen accounts is synced too. `No mapped accounts.` is still printed when that list is empty.
- **R11.** After the table, and **before** SimpleFIN's messages, `fin sync run` prints one line for each link that ran (no error), in the order they ran, that has new accounts (`list_new_feed_accounts` for the link, not ignored), in the form of the table above. Links with no new accounts print nothing. The exit code is unchanged.

### Part 4: the web pages

- **R12.** The SimpleFIN page (`GET /sync`) gets, besides what it has:
  - `new_accounts`: for each of `list_new_feed_accounts(session)`, a dict with `link`, `feed_account` (the SimpleFIN id), `name` and `institution` (as stored), `guess` (a dict of `name`, `institution`, `type` as its text value, and `last4` as text, empty when `None`, from `guess_account`), `owner` (`guess_owner` over the people's names, or empty), and `suggestion` (`suggest_existing`, or empty);
  - `ignored_accounts`: for each of `list_new_feed_accounts(session, ignored=True)`, a dict with `link`, `feed_account`, `name`, `institution`;
  - `people`: the people's names in `list_people` order; `types`: `ACCOUNT_TYPES`;
  - `unmapped`: the names of the active accounts, in `list_accounts` order, that have no mapping under any link. These are also the `candidates` for `suggest_existing`, with their last4.
- **R13.** `POST /sync/create` takes an optional `owner` field: empty leaves the new account without an owner; `joint` in any case and without outer spaces makes it Joint; otherwise a person found by `get_person_by_name`, or the refusal `person not found`. The owner is set in the same session as the account and its mapping, so a refused owner creates and maps nothing.
- **R14.** `POST /sync/create` and `POST /sync/map` take an optional `next` field: `sync` sends a done form to `/sync?notice=mapped`; anything else keeps the Phase 16b redirect to `/sync/accounts?link=LINK&notice=mapped`.
- **R15.** `POST /sync/ignore` and `POST /sync/track`, each with `link` and `feed_account` (outer spaces removed), run the form checks of Phase 16b (origin, token, database), then `set_feed_account_ignored` with true or false. Done: `/sync?notice=ignored` or `/sync?notice=tracked`. A `ValueError` shows `error.html` with its message and the back link to `/sync`, status `400`. `GET` on either answers `405`.
- **R16.** `NOTICES` gains `ignored` and `tracked` with the texts above.
- **R17.** `POST /sync/run` runs the links of `list_feed_links`, and its page gets `waiting`: for each link that ran (no error) with new accounts, in the order run, the text `LINK: COUNT to set up.`
- **R18.** The new section and the run notice are in the given templates; the routes only supply the values of R12 and R17.
- **R19.** `src/finances/web/static/app.css` gains, at its end, the line `h3 { font-size: 1rem; margin-bottom: .4rem; }`.

### Part 5: the code

- **R20.** `domain/feed_setup.py` imports nothing from the project but `finances.domain.models`. The web and the command call the functions of Parts 1 and 2; neither holds a guessing rule or a query.

## Given templates

Replace these two files exactly as shown. The new section comes right after the page's messages; the Phase 16b tables and forms are unchanged.

`src/finances/web/templates/sync.html`

```html
{% extends "layout.html" %}
{% block title %}SimpleFIN · Finances{% endblock %}
{% block content %}
<h1>SimpleFIN</h1>
{% include "messages.html" %}
{% if new_accounts %}
<h2>New SimpleFIN accounts</h2>
<p class="hint">The last sync found these accounts. Set each one up below: check the guesses, then create it, map it to an account you already have, or stop tracking it.</p>
{% for item in new_accounts %}
<section class="map">
<h3>{{ item.institution }}: {{ item.name }} <span class="hint">link {{ item.link }}</span></h3>
{% if item.suggestion %}<p class="notice">This looks like {{ item.suggestion }}, which you already have. Map it instead of creating a second one.</p>{% endif %}
<form method="post" action="/sync/create" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <input type="hidden" name="link" value="{{ item.link }}">
  <input type="hidden" name="feed_account" value="{{ item.feed_account }}">
  <input type="hidden" name="next" value="sync">
  <label>Account name <input name="account" required maxlength="100" value="{{ item.guess.name }}"></label>
  <label>Institution <input name="institution" required maxlength="100" value="{{ item.guess.institution }}"></label>
  <label>Type
    <select name="type">
      {% for kind in types %}<option value="{{ kind }}"{% if kind == item.guess.type %} selected{% endif %}>{{ kind }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Last 4 digits <input name="last4" maxlength="4" inputmode="numeric" value="{{ item.guess.last4 }}"></label>
  <label>Owner
    <select name="owner">
      <option value="">No owner yet</option>
      {% for name in people %}<option value="{{ name }}"{% if name == item.owner %} selected{% endif %}>{{ name }}</option>
      {% endfor %}
      <option value="joint">Joint</option>
    </select>
  </label>
  <button type="submit">Create and map</button>
</form>
{% if unmapped %}
<form method="post" action="/sync/map" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <input type="hidden" name="link" value="{{ item.link }}">
  <input type="hidden" name="feed_account" value="{{ item.feed_account }}">
  <input type="hidden" name="next" value="sync">
  <label>Or map to
    <select name="account">
      {% if not item.suggestion %}<option value="">Choose an account</option>
      {% endif %}{% for name in unmapped %}<option value="{{ name }}"{% if name == item.suggestion %} selected{% endif %}>{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <button type="submit">Map</button>
</form>
{% endif %}
<form method="post" action="/sync/ignore" class="inline">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <input type="hidden" name="link" value="{{ item.link }}">
  <input type="hidden" name="feed_account" value="{{ item.feed_account }}">
  <button type="submit">Don't track</button>
</form>
</section>
{% endfor %}
{% endif %}
{% if rows %}
<table>
<thead><tr><th>Link</th><th>Account</th><th>SimpleFIN account</th><th>Keychain</th><th>Last pull</th><th>Balance date</th><th class="amount">Drift</th></tr></thead>
<tbody>
{% for row in rows %}<tr><td>{{ row.link }}</td><td>{{ row.account }}</td><td>{{ row.feed_account }}</td><td>{{ row.keychain }}</td><td>{{ row.last_pull }}</td><td>{{ row.balance_date }}</td><td class="amount">{{ row.drift }}</td></tr>
{% endfor %}</tbody>
</table>
<form method="post" action="/sync/run">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <button type="submit">Sync now</button>
</form>
{% else %}
<p class="empty">No mapped accounts.</p>
{% endif %}
{% if links %}
<h2>Links</h2>
<ul class="links">
{% for name in links %}<li>{{ name }}
  <a href="/sync/accounts?link={{ name }}">SimpleFIN accounts</a>
  <form method="post" action="/sync/unlink" class="inline">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <input type="hidden" name="link" value="{{ name }}">
    <button type="submit">Unlink</button>
  </form>
</li>
{% endfor %}</ul>
{% endif %}
{% if ignored_accounts %}
<h2>Not tracked</h2>
<ul class="links">
{% for item in ignored_accounts %}<li>{{ item.institution }}: {{ item.name }} <span class="hint">link {{ item.link }}</span>
  <form method="post" action="/sync/track" class="inline">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <input type="hidden" name="link" value="{{ item.link }}">
    <input type="hidden" name="feed_account" value="{{ item.feed_account }}">
    <button type="submit">Track again</button>
  </form>
</li>
{% endfor %}</ul>
{% endif %}
<h2>Link a SimpleFIN subscription</h2>
<p class="hint">Create a setup token in your SimpleFIN account and paste it here. It is used once; the access it gives is kept in this Mac's Keychain.</p>
<form method="post" action="/sync/link" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Link name <input name="link" required maxlength="30" pattern="[a-z][a-z0-9-]{0,29}" value="{{ form.link }}"></label>
  <label>Setup token <input type="password" name="token" required autocomplete="off"></label>
  <label class="check"><input type="checkbox" name="replace" value="on"> Replace an existing link</label>
  <button type="submit">Link</button>
</form>
<h2>Open a link's accounts</h2>
<form method="get" action="/sync/accounts" class="fields">
  <label>Link name <input name="link" required maxlength="30"></label>
  <button type="submit">Show accounts</button>
</form>
{% endblock %}
```

`src/finances/web/templates/sync_run.html`

```html
{% extends "layout.html" %}
{% block title %}Sync · Finances{% endblock %}
{% block content %}
<h1>Sync</h1>
<p><a href="/sync">Back to SimpleFIN</a></p>
{% if not ran %}<p class="empty">No mapped accounts.</p>{% endif %}
{% for message in errors %}<p class="error">{{ message }}</p>
{% endfor %}
{% if rows %}
<table>
<thead><tr><th>Link</th><th>Account</th><th>SimpleFIN account</th><th>New</th><th>Changed</th><th>Removed</th><th>Same</th><th class="amount">Drift</th><th>Problem</th></tr></thead>
<tbody>
{% for row in rows %}<tr><td>{{ row.link }}</td><td>{{ row.account }}</td><td>{{ row.feed_account }}</td><td>{{ row.new }}</td><td>{{ row.changed }}</td><td>{{ row.removed }}</td><td>{{ row.same }}</td><td class="amount">{{ row.drift }}</td><td>{{ row.problem }}</td></tr>
{% endfor %}</tbody>
</table>
{% endif %}
{% for message in messages %}<p class="notice">SimpleFIN {{ message }}</p>
{% endfor %}
{% for message in waiting %}<p class="notice">New SimpleFIN accounts: {{ message }} <a href="/sync">Set them up</a></p>
{% endfor %}
{% endblock %}
```

## Given tests

Create these five files exactly as shown and do not change them. If one fails, the production code is wrong. Together they reach every line and branch of the code this phase adds, so there are no tests for you to write.

`tests/unit/test_feed_setup.py`

```python
import pytest

from finances.domain.feed_setup import (
    NO_NAME,
    TEXT_LIMIT,
    AccountGuess,
    guess_account,
    guess_owner,
    new_accounts,
    suggest_existing,
)
from finances.domain.models import AccountType

CHECKING, SAVINGS, CARD, OTHER = (
    AccountType.CHECKING,
    AccountType.SAVINGS,
    AccountType.CREDIT_CARD,
    AccountType.OTHER,
)


def test_the_limits() -> None:
    assert (TEXT_LIMIT, NO_NAME) == (100, "New account")


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("Everyday Checking", CHECKING),
        ("PROBE CHK 0001", CHECKING),
        ("High Yield Savings", SAVINGS),
        ("Online Saving", SAVINGS),
        ("Money Market Account", SAVINGS),
        ("Probe Visa Signature", CARD),
        ("Cash Rewards Mastercard", CARD),
        ("Platinum Card", CARD),
        ("AMEX Gold", CARD),
        ("American Express Blue", CARD),
        ("Discover It", CARD),
        ("Probe Credit Card", CARD),
        ("Credit Union Checking", CHECKING),
        ("Savings Card Plus", SAVINGS),
        ("Brokerage", OTHER),
        ("Cardinal Fund", OTHER),
        ("Checkingplus", OTHER),
        ("Visas", OTHER),
        ("", OTHER),
    ],
)
def test_the_type_comes_from_words_in_the_name(name: str, kind: AccountType) -> None:
    assert guess_account(name, "Probe Bank").type == kind


@pytest.mark.parametrize(
    ("name", "last4"),
    [
        ("Probe Visa ...1234", "1234"),
        ("Probe Visa (5678)", "5678"),
        ("Card ending in 0042", "0042"),
        ("Card 4400 0000 0000 5555", "5555"),
        ("Checking 0001234567", None),
        ("Savings 123", None),
        ("Card 1234 x", "1234"),
        ("Account 2024 Plan 77", None),
        ("No digits", None),
        ("Card ١٢٣٤", None),
    ],
)
def test_the_last_four_digits_come_from_the_last_run_of_digits(
    name: str, last4: str | None
) -> None:
    assert guess_account(name, "Probe Bank").last4 == last4


def test_the_name_and_institution_are_tidied_and_cut() -> None:
    guess = guess_account("  Probe   Visa\tSignature  ", "  Probe\n Bank ")
    assert guess == AccountGuess("Probe Visa Signature", "Probe Bank", CARD, None)
    long = guess_account("N" * 99 + " MORE", "I" * 150)
    assert (long.name, long.institution) == ("N" * 99, "I" * 100)


def test_a_missing_name_gets_a_placeholder() -> None:
    assert guess_account("   ", "").name == NO_NAME
    assert guess_account("", "").institution == ""


@pytest.mark.parametrize(
    ("link", "people", "owner"),
    [
        ("kim", ["Alex", "Kim"], "Kim"),
        ("KIM", ["kim"], "kim"),
        ("alex", ["Kim"], None),
        ("default", [], None),
        ("kim", [" Kim "], " Kim "),
    ],
)
def test_the_owner_is_the_person_named_like_the_link(
    link: str, people: list[str], owner: str | None
) -> None:
    assert guess_owner(link, people) == owner


def guess(name: str = "Probe Visa", last4: str | None = "1234") -> AccountGuess:
    return AccountGuess(name, "Probe Bank", CARD, last4)


def test_an_account_with_the_same_last_four_digits_is_suggested() -> None:
    candidates = [("Old Card", "9999"), ("Statement Card", "1234"), ("Probe Visa", None)]
    assert suggest_existing(guess(), candidates) == "Statement Card"


def test_two_with_the_same_digits_fall_back_to_the_name() -> None:
    candidates = [("A", "1234"), ("probe visa", "1234")]
    assert suggest_existing(guess(), candidates) == "probe visa"
    assert suggest_existing(guess(), [("A", "1234"), ("B", "1234")]) is None


def test_without_digits_the_name_decides() -> None:
    assert suggest_existing(guess(last4=None), [("PROBE VISA", "1234")]) == "PROBE VISA"
    assert suggest_existing(guess(last4=None), [("Other", None)]) is None
    assert suggest_existing(guess(), []) is None


@pytest.mark.parametrize(
    ("count", "text"), [(1, "1 new account"), (2, "2 new accounts"), (0, "0 new accounts")]
)
def test_counting_new_accounts(count: int, text: str) -> None:
    assert new_accounts(count) == text
```

`tests/integration/test_migration_0007.py`

```python
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import Base, FeedSeenAccountRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0007_feed_seen_accounts.py"
COLUMNS = [
    ("id", "INTEGER", False),
    ("link", "VARCHAR(50)", False),
    ("provider_account_id", "VARCHAR(200)", False),
    ("name", "VARCHAR(100)", False),
    ("institution", "VARCHAR(100)", False),
    ("first_seen", "DATE", False),
    ("last_seen", "DATE", False),
    ("ignored", "BOOLEAN", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def table_names(url: str) -> list[str]:
    engine = get_engine(url)
    names = sorted(inspect(engine).get_table_names())
    engine.dispose()
    return names


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def at_0007(url: str) -> str:
    command.upgrade(make_config(url), "0007")
    return url


def test_0007_follows_0006(url: str) -> None:
    script = ScriptDirectory.from_config(make_config(url)).get_revision("0007")
    assert script.down_revision == "0006"


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


def test_columns_keys_and_constraints(at_0007: str) -> None:
    engine = get_engine(at_0007)
    found = inspect(engine)
    columns = [
        (column["name"], str(column["type"]), column["nullable"])
        for column in found.get_columns("feed_seen_accounts")
    ]
    primary = found.get_pk_constraint("feed_seen_accounts")
    uniques = [
        (item["name"], item["column_names"])
        for item in found.get_unique_constraints("feed_seen_accounts")
    ]
    foreign = found.get_foreign_keys("feed_seen_accounts")
    engine.dispose()
    assert columns == COLUMNS
    assert (primary["name"], primary["constrained_columns"]) == ("pk_feed_seen_accounts", ["id"])
    assert uniques == [
        ("uq_feed_seen_accounts_link_provider_account", ["link", "provider_account_id"])
    ]
    assert foreign == []


def test_the_orm_class_matches_the_migrated_table(at_0007: str) -> None:
    table = Base.metadata.tables["feed_seen_accounts"]
    assert FeedSeenAccountRow.__table__ is table
    assert [(column.name, str(column.type), column.nullable) for column in table.columns] == COLUMNS


def test_one_row_per_link_and_aggregator_account(at_0007: str) -> None:
    engine = get_engine(at_0007)
    insert = (
        "INSERT INTO feed_seen_accounts (link, provider_account_id, name, institution,"
        " first_seen, last_seen, ignored) VALUES (:link, 'ACT-1', 'Probe', 'Probe Bank',"
        " '2026-05-01', '2026-05-01', 0)"
    )
    with session_scope(engine) as session:
        session.execute(text(insert), {"link": "alex"})
        session.execute(text(insert), {"link": "sam"})
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.execute(text(insert), {"link": "alex"})
    with session_scope(engine) as session:
        row = session.get(FeedSeenAccountRow, 1)
        assert (row.first_seen, row.ignored) == (date(2026, 5, 1), False)
    engine.dispose()


def test_downgrade_removes_only_the_table(at_0007: str) -> None:
    before = table_names(at_0007)
    command.downgrade(make_config(at_0007), "0006")
    assert table_names(at_0007) == sorted(set(before) - {"feed_seen_accounts"})
```

`tests/integration/test_seen_feed_accounts.py`

```python
import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine, select

from finances.db.engine import session_scope
from finances.db.orm import FeedSeenAccountRow
from finances.db.repositories import (
    create_account,
    list_feed_links,
    list_new_feed_accounts,
    map_feed_account,
    record_seen_feed_account,
    set_feed_account_ignored,
)
from finances.domain.models import SeenFeedAccount
from finances.sync.runner import run_sync

MAY_1 = date(2026, 5, 1)
MAY_9 = date(2026, 5, 9)


def seen(engine: Engine, link: str | None = None, ignored: bool = False) -> list[tuple]:
    with session_scope(engine) as session:
        return [
            (item.link, item.provider_account_id, item.name, item.institution)
            for item in list_new_feed_accounts(session, link, ignored=ignored)
        ]


def test_a_new_account_is_recorded(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "Probe Visa", "Probe Bank", MAY_1)
        assert list_new_feed_accounts(session) == [
            SeenFeedAccount(1, "kim", "ACT-1", "Probe Visa", "Probe Bank", MAY_1, MAY_1, False)
        ]


def test_seeing_it_again_updates_the_name_and_the_last_day(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "Old Name", "Old Bank", MAY_1)
        record_seen_feed_account(session, "kim", "ACT-1", "New  Name", " New Bank ", MAY_9)
        record_seen_feed_account(session, "kim", "ACT-1", "Newer", "Newer Bank", MAY_1)
        (item,) = list_new_feed_accounts(session)
    assert (item.name, item.institution, item.first_seen, item.last_seen) == (
        "Newer",
        "Newer Bank",
        MAY_1,
        MAY_9,
    )


def test_long_text_is_cut_to_fit(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "N" * 99 + "  X" * 40, "I" * 300, MAY_1)
        row = session.scalars(select(FeedSeenAccountRow)).one()
        assert (row.name, row.institution) == ("N" * 99, "I" * 100)


def test_a_mapped_account_is_not_new_under_its_link(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        made = create_account(session, "Probe Card", "Probe Bank", "credit_card")
        map_feed_account(session, made.id, "ACT-1", "kim")
        for link, feed_id in (("kim", "ACT-1"), ("kim", "ACT-2"), ("sam", "ACT-1")):
            record_seen_feed_account(session, link, feed_id, f"{link} {feed_id}", "Probe", MAY_1)
    assert seen(db_engine) == [
        ("kim", "ACT-2", "kim ACT-2", "Probe"),
        ("sam", "ACT-1", "sam ACT-1", "Probe"),
    ]
    assert seen(db_engine, "sam") == [("sam", "ACT-1", "sam ACT-1", "Probe")]


def test_new_accounts_come_by_link_then_first_day_then_id(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "sam", "S-1", "S one", "Probe", MAY_1)
        record_seen_feed_account(session, "kim", "K-late", "K late", "Probe", MAY_9)
        record_seen_feed_account(session, "kim", "K-b", "K b", "Probe", MAY_1)
        record_seen_feed_account(session, "kim", "K-a", "K a", "Probe", MAY_1)
    assert [item[1] for item in seen(db_engine)] == ["K-b", "K-a", "K-late", "S-1"]


def test_an_account_not_tracked_leaves_the_new_list_and_can_come_back(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "Probe", "Probe Bank", MAY_1)
        record_seen_feed_account(session, "kim", "ACT-2", "Other", "Probe Bank", MAY_1)
        set_feed_account_ignored(session, "kim", "ACT-1", True)
    assert [item[1] for item in seen(db_engine)] == ["ACT-2"]
    assert [item[1] for item in seen(db_engine, ignored=True)] == ["ACT-1"]
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "Probe", "Probe Bank", MAY_9)
    assert [item[1] for item in seen(db_engine, ignored=True)] == ["ACT-1"]
    with session_scope(db_engine) as session:
        set_feed_account_ignored(session, "kim", "ACT-1", False)
    assert [item[1] for item in seen(db_engine)] == ["ACT-1", "ACT-2"]


@pytest.mark.parametrize(("link", "feed_id"), [("sam", "ACT-1"), ("kim", "ACT-9")])
def test_an_unknown_account_cannot_be_ignored(db_engine: Engine, link: str, feed_id: str) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "Probe", "Probe Bank", MAY_1)
        with pytest.raises(ValueError, match="^SimpleFIN account not found$"):
            set_feed_account_ignored(session, link, feed_id, True)


def test_links_to_sync_have_a_mapping_or_a_seen_account(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        assert list_feed_links(session) == []
        made = create_account(session, "Probe Card", "Probe Bank", "credit_card")
        map_feed_account(session, made.id, "sam", "sam")
        record_seen_feed_account(session, "kim", "ACT-1", "Probe", "Probe Bank", MAY_1)
        record_seen_feed_account(session, "sam", "ACT-2", "Probe", "Probe Bank", MAY_1)
        assert list_feed_links(session) == ["kim", "sam"]


def test_a_sync_records_every_account_it_delivers(db_engine: Engine) -> None:
    stamp = int(datetime(2026, 5, 9, 12, tzinfo=UTC).timestamp())
    body = {
        "errlist": [],
        "connections": [{"conn_id": "C", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": feed_id,
                "name": name,
                "conn_id": "C",
                "currency": "USD",
                "balance": "-1.00",
                "balance-date": stamp,
                "transactions": [],
            }
            for feed_id, name in (("ACT-1", "Mapped Card"), ("ACT-2", "Probe Visa 9876"))
        ],
    }
    with session_scope(db_engine) as session:
        made = create_account(session, "Probe Card", "Probe Bank", "credit_card")
        map_feed_account(session, made.id, "ACT-1", "kim")
    with session_scope(db_engine) as session:
        report = run_sync(
            session,
            "https://u:p@bridge.simplefin.org/simplefin",
            today=MAY_9,
            transport=lambda *_: (200, json.dumps(body).encode()),
            link="kim",
        )
    assert [item.problem for item in report.accounts] == [None, "not mapped"]
    assert seen(db_engine) == [("kim", "ACT-2", "Probe Visa 9876", "Probe Bank")]
    with session_scope(db_engine) as session:
        rows = session.scalars(select(FeedSeenAccountRow).order_by(FeedSeenAccountRow.id)).all()
        assert [(row.provider_account_id, row.last_seen) for row in rows] == [
            ("ACT-1", MAY_9),
            ("ACT-2", MAY_9),
        ]
```

`tests/e2e/test_cli_sync_new_accounts.py`

```python
import base64
import json
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import set_feed_account_ignored
from finances.sync import transport

runner = CliRunner(env={"COLUMNS": "200"})
SERVICE = "finances-simplefin"
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"
HINT = "(open the SimpleFIN page, or run: fin sync accounts --link {})"


def run(*args: str):
    return runner.invoke(app, list(args))


def key(access: str) -> str:
    user, password = access.split("//")[1].split("@")[0].split(":")
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


class Bridge:
    """A fake SimpleFIN Bridge: each access URL has its list of accounts."""

    def __init__(self) -> None:
        self.answers: dict[str, list[tuple[str, str]]] = {}
        self.asked: list[str] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.asked.append(headers["Authorization"])
        noon = int(datetime.now(UTC).replace(hour=12, minute=0, second=0).timestamp())
        accounts = [
            {
                "id": feed_id,
                "name": name,
                "conn_id": "C",
                "currency": "USD",
                "balance": "-1.00",
                "balance-date": noon,
                "transactions": [],
            }
            for feed_id, name in self.answers[headers["Authorization"]]
        ]
        body = {
            "errlist": [{"code": "con.auth", "msg": "Probe note"}],
            "connections": [{"conn_id": "C", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
            "accounts": accounts,
        }
        return 200, json.dumps(body).encode()


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch, keychain) -> Bridge:
    fake = Bridge()
    monkeypatch.setattr(transport, "urllib_transport", fake)
    keychain.passwords[(SERVICE, "alex")] = ALEX
    keychain.passwords[(SERVICE, "sam")] = SAM
    return fake


@pytest.fixture
def mapped(tmp_settings: Settings, bridge: Bridge) -> Bridge:
    """Alex's link maps ACT-1 to Test Card."""
    assert run("db", "upgrade").exit_code == 0
    details = ["--institution", "Probe Bank", "--type", "credit_card", "--last4", "1111"]
    assert run("accounts", "add", "--name", "Test Card", *details).exit_code == 0
    made = run("sync", "map", "--account", "Test Card", "--feed-account", "ACT-1", "--link", "alex")
    assert made.exit_code == 0
    return bridge


def tail(output: str) -> list[str]:
    """The lines after the table."""
    lines = output.splitlines()
    return lines[max(index for index, line in enumerate(lines) if line.startswith("└")) + 1 :]


def test_a_sync_names_the_new_accounts_before_simplefins_messages(mapped: Bridge) -> None:
    mapped.answers[key(ALEX)] = [("ACT-1", "Card"), ("ACT-2", "Visa 9876"), ("ACT-3", "Savings")]
    result = run("sync", "run")
    assert result.exit_code == 0
    assert tail(result.stdout) == [
        "SimpleFIN (alex): 2 new accounts to set up " + HINT.format("alex"),
        "SimpleFIN (alex): Probe note",
    ]


def test_one_new_account(mapped: Bridge) -> None:
    mapped.answers[key(ALEX)] = [("ACT-1", "Card"), ("ACT-2", "Visa 9876")]
    assert tail(run("sync", "run").stdout)[0] == (
        "SimpleFIN (alex): 1 new account to set up " + HINT.format("alex")
    )


def test_no_line_when_everything_is_mapped_or_not_tracked(mapped: Bridge) -> None:
    mapped.answers[key(ALEX)] = [("ACT-1", "Card")]
    assert tail(run("sync", "run").stdout) == ["SimpleFIN (alex): Probe note"]
    mapped.answers[key(ALEX)] = [("ACT-1", "Card"), ("ACT-2", "Visa 9876")]
    run("sync", "run")
    engine = get_engine()
    with session_scope(engine) as session:
        set_feed_account_ignored(session, "alex", "ACT-2", True)
    engine.dispose()
    assert tail(run("sync", "run").stdout) == ["SimpleFIN (alex): Probe note"]


def test_a_link_with_only_new_accounts_is_synced_too(mapped: Bridge) -> None:
    mapped.answers[key(ALEX)] = [("ACT-1", "Card")]
    mapped.answers[key(SAM)] = [("SAM-1", "Sam Checking")]
    first = run("sync", "run")
    assert key(SAM) not in mapped.asked
    assert "sam" not in first.stdout
    assert run("sync", "run", "--link", "sam").exit_code == 0
    mapped.asked.clear()
    result = run("sync", "run")
    assert sorted(set(mapped.asked)) == sorted({key(ALEX), key(SAM)})
    assert "SimpleFIN (sam): 1 new account to set up " + HINT.format("sam") in result.stdout


def test_only_links_that_ran_are_counted(mapped: Bridge) -> None:
    mapped.answers[key(ALEX)] = [("ACT-1", "Card"), ("ACT-2", "Visa 9876")]
    mapped.answers[key(SAM)] = [("SAM-1", "Sam Checking")]
    run("sync", "run", "--link", "sam")
    result = run("sync", "run", "--link", "alex")
    assert "SimpleFIN (alex): 1 new account" in result.stdout
    assert "SimpleFIN (sam)" not in result.stdout
```

`tests/integration/test_web_new_accounts.py`

```python
import json
from datetime import UTC, date, datetime
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AccountRow
from finances.db.repositories import (
    create_account,
    create_person,
    map_feed_account,
    record_seen_feed_account,
)
from finances.sync import transport
from finances.web.app import create_app

PORT = 8765
DAY = date(2026, 5, 9)


class Page(HTMLParser):
    """The parts of a page the tests read: table rows, paragraphs, and forms."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.paragraphs: list[tuple[str, str]] = []
        self.forms: list[dict] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.paragraph: str | None = None
        self.text: list[str] = []
        self.form: dict | None = None
        self.select: str | None = None
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "p":
            self.paragraph = values.get("class", "")
            self.text = []
        elif tag == "form":
            self.form = {
                "action": values.get("action", ""),
                "method": values.get("method", "get"),
                "inputs": {},
                "selects": {},
            }
            self.forms.append(self.form)
        elif tag == "input" and self.form is not None:
            self.form["inputs"][values.get("name", "")] = (
                values.get("type", "text"),
                values.get("value", ""),
            )
        elif tag == "select" and self.form is not None:
            self.select = values.get("name", "")
            self.form["selects"][self.select] = []
        elif tag == "option" and self.form is not None and self.select is not None:
            self.form["selects"][self.select].append(
                (values.get("value", ""), "selected" in values)
            )

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "p" and self.paragraph is not None:
            self.paragraphs.append((self.paragraph, "".join(self.text).strip()))
            self.paragraph = None
        elif tag == "form":
            self.form = None
        elif tag == "select":
            self.select = None

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
        if self.paragraph is not None:
            self.text.append(data)

    def find(self, action: str) -> dict:
        found = [form for form in self.forms if form["action"] == action]
        assert len(found) == 1, action
        return found[0]


class SeenPage(Page):
    """Also the text of each h3 heading."""

    def __init__(self, html: str) -> None:
        self.headings: list[str] = []
        self.heading: list[str] | None = None
        super().__init__(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h3":
            self.heading = []
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self.heading is not None:
            self.headings.append(" ".join("".join(self.heading).split()))
            self.heading = None
        super().handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.heading is not None:
            self.heading.append(data)
        super().handle_data(data)

    def all(self, action: str) -> list[dict]:
        return [form for form in self.forms if form["action"] == action]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Kim's link maps ACT-1 to Test Card; Test Savings ends in 4321 and is not mapped."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Probe Bank", "credit_card", last4="1111")
        map_feed_account(session, card.id, "ACT-1", "kim")
        create_account(session, "Test Savings", "Probe Bank", "savings", last4="4321")
        old = create_account(session, "Test Old", "Probe Bank", "other")
        session.get(AccountRow, old.id).is_active = False
        create_person(session, "Alex")
        create_person(session, "Kim")
    engine.dispose()
    client.get("/sync")
    return client


def see(link: str, feed_id: str, name: str, institution: str = "Probe Bank") -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        record_seen_feed_account(session, link, feed_id, name, institution, DAY)
    engine.dispose()


def post(client: TestClient, path: str, **fields: str):
    return client.post(
        path, data={"csrf": client.cookies["fin_csrf"], **fields}, follow_redirects=False
    )


def sync_page(client: TestClient) -> SeenPage:
    return SeenPage(client.get("/sync").text)


def selected(form: dict, name: str) -> list[str]:
    return [value for value, chosen in form["selects"][name] if chosen]


def accounts(client: TestClient) -> list[list[str]]:
    return Page(client.get("/accounts?closed=true").text).rows[1:]


def test_no_section_without_new_accounts(home: TestClient) -> None:
    page = sync_page(home)
    assert page.headings == []
    assert page.all("/sync/create") == page.all("/sync/ignore") == []
    see("kim", "ACT-1", "Mapped already")
    assert sync_page(home).headings == []


def test_each_new_account_is_offered_with_its_guesses(home: TestClient) -> None:
    see("kim", "ACT-2", "  Probe   Visa ...9876 ")
    see("sam", "SAM-1", "Everyday Checking", "Other Bank")
    page = sync_page(home)
    assert page.headings == [
        "Probe Bank: Probe Visa ...9876 link kim",
        "Other Bank: Everyday Checking link sam",
    ]
    first, second = page.all("/sync/create")
    assert {name: first["inputs"][name] for name in ("link", "feed_account", "next")} == {
        "link": ("hidden", "kim"),
        "feed_account": ("hidden", "ACT-2"),
        "next": ("hidden", "sync"),
    }
    assert first["inputs"]["account"] == ("text", "Probe Visa ...9876")
    assert first["inputs"]["institution"] == ("text", "Probe Bank")
    assert first["inputs"]["last4"] == ("text", "9876")
    assert selected(first, "type") == ["credit_card"]
    assert [value for value, _ in first["selects"]["owner"]] == ["", "Alex", "Kim", "joint"]
    assert selected(first, "owner") == ["Kim"]
    assert selected(second, "type") == ["checking"]
    assert second["inputs"]["last4"] == ("text", "")
    assert selected(second, "owner") == []


def test_an_existing_account_with_the_same_digits_is_suggested(home: TestClient) -> None:
    see("kim", "ACT-3", "High Yield Savings 4321")
    page = sync_page(home)
    assert (
        "notice",
        "This looks like Test Savings, which you already have."
        " Map it instead of creating a second one.",
    ) in page.paragraphs
    (mapping,) = page.all("/sync/map")
    assert mapping["selects"]["account"] == [("Test Savings", True)]
    assert mapping["inputs"]["next"] == ("hidden", "sync")


def test_without_a_suggestion_the_list_starts_empty(home: TestClient) -> None:
    see("kim", "ACT-4", "Brokerage")
    page = sync_page(home)
    assert not any(kind == "notice" for kind, _ in page.paragraphs)
    (mapping,) = page.all("/sync/map")
    assert mapping["selects"]["account"] == [("", False), ("Test Savings", False)]


def test_no_map_form_when_every_open_account_is_mapped(home: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        map_feed_account(session, 2, "SAV-1", "sam")
    engine.dispose()
    see("kim", "ACT-4", "Brokerage")
    page = sync_page(home)
    assert page.all("/sync/map") == []
    assert len(page.all("/sync/create")) == 1


def test_text_from_simplefin_is_escaped(home: TestClient) -> None:
    see("kim", "ACT-5", "<b>Bold</b> Card")
    html = home.get("/sync").text
    assert "&lt;b&gt;Bold&lt;/b&gt; Card" in html
    assert "<b>Bold</b>" not in html


@pytest.mark.parametrize(
    ("owner", "shown"), [("Kim", "Kim"), ("kim", "Kim"), ("joint", "Joint"), ("", "")]
)
def test_create_and_map_with_an_owner(home: TestClient, owner: str, shown: str) -> None:
    see("kim", "ACT-2", "Probe Visa 9876")
    response = post(
        home,
        "/sync/create",
        link="kim",
        feed_account="ACT-2",
        account="Kim Visa",
        institution="Probe Bank",
        type="credit_card",
        last4="9876",
        owner=owner,
        next="sync",
    )
    assert (response.status_code, response.headers["location"]) == (303, "/sync?notice=mapped")
    assert ["Kim Visa", "Probe Bank", "credit_card", "••9876", "yes", shown] in accounts(home)
    page = SeenPage(home.get("/sync?notice=mapped").text)
    assert page.headings == []
    assert ("notice", "Account mapped.") in page.paragraphs


def test_an_unknown_owner_creates_nothing(home: TestClient) -> None:
    see("kim", "ACT-2", "Probe Visa 9876")
    response = post(
        home,
        "/sync/create",
        link="kim",
        feed_account="ACT-2",
        account="Kim Visa",
        institution="Probe Bank",
        type="credit_card",
        owner="Nobody",
        next="sync",
    )
    assert response.status_code == 400
    assert ("error", "person not found") in Page(response.text).paragraphs
    assert "Kim Visa" not in [row[0] for row in accounts(home)]
    assert sync_page(home).headings == ["Probe Bank: Probe Visa 9876 link kim"]


def test_map_to_the_suggested_account(home: TestClient) -> None:
    see("kim", "ACT-3", "High Yield Savings 4321")
    response = post(
        home, "/sync/map", link="kim", feed_account="ACT-3", account="Test Savings", next="sync"
    )
    assert (response.status_code, response.headers["location"]) == (303, "/sync?notice=mapped")
    rows = sync_page(home).rows
    assert ["kim", "Test Savings", "ACT-3"] == rows[2][:3]


def test_mapping_without_next_still_goes_to_the_links_accounts(home: TestClient) -> None:
    see("kim", "ACT-3", "High Yield Savings 4321")
    response = post(home, "/sync/map", link="kim", feed_account="ACT-3", account="Test Savings")
    assert response.headers["location"] == "/sync/accounts?link=kim&notice=mapped"


def test_dont_track_and_track_again(home: TestClient) -> None:
    see("kim", "ACT-4", "Brokerage")
    response = post(home, "/sync/ignore", link="kim", feed_account="ACT-4")
    assert (response.status_code, response.headers["location"]) == (303, "/sync?notice=ignored")
    page = SeenPage(home.get(response.headers["location"]).text)
    assert ("notice", "That SimpleFIN account will not be tracked.") in page.paragraphs
    assert page.headings == []
    (again,) = page.all("/sync/track")
    assert (again["inputs"]["link"], again["inputs"]["feed_account"]) == (
        ("hidden", "kim"),
        ("hidden", "ACT-4"),
    )
    response = post(home, "/sync/track", link="kim", feed_account=" ACT-4 ")
    assert (response.status_code, response.headers["location"]) == (303, "/sync?notice=tracked")
    page = SeenPage(home.get(response.headers["location"]).text)
    assert ("notice", "That SimpleFIN account is offered for setup again.") in page.paragraphs
    assert page.headings == ["Probe Bank: Brokerage link kim"]
    assert page.all("/sync/track") == []


@pytest.mark.parametrize("path", ["/sync/ignore", "/sync/track"])
def test_tracking_an_unknown_account_is_refused(home: TestClient, path: str) -> None:
    response = post(home, path, link="kim", feed_account="ACT-404")
    assert response.status_code == 400
    assert ("error", "SimpleFIN account not found") in Page(response.text).paragraphs


@pytest.mark.parametrize("path", ["/sync/ignore", "/sync/track"])
def test_tracking_needs_the_form_token_and_a_post(home: TestClient, path: str) -> None:
    see("kim", "ACT-4", "Brokerage")
    response = home.post(path, data={"link": "kim", "feed_account": "ACT-4"})
    assert (response.status_code, response.text) == (403, "Bad form token")
    assert home.get(path).status_code == 405
    assert sync_page(home).headings == ["Probe Bank: Brokerage link kim"]


def test_sync_now_says_how_many_accounts_are_new(home: TestClient, keychain, monkeypatch) -> None:
    keychain.passwords[("finances-simplefin", "kim")] = "https://u:p@bridge.simplefin.org/x"
    noon = int(datetime.now(UTC).replace(hour=12, minute=0, second=0).timestamp())
    body = {
        "errlist": [],
        "connections": [{"conn_id": "C", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": feed_id,
                "name": name,
                "conn_id": "C",
                "currency": "USD",
                "balance": "1.00",
                "balance-date": noon,
                "transactions": [],
            }
            for feed_id, name in (("ACT-1", "Card"), ("ACT-2", "Visa"), ("ACT-3", "Savings"))
        ],
    }
    monkeypatch.setattr(transport, "urllib_transport", lambda *_: (200, json.dumps(body).encode()))
    html = post(home, "/sync/run").text
    page = SeenPage(html)
    assert ("notice", "New SimpleFIN accounts: kim: 2 new accounts to set up. Set them up") in (
        page.paragraphs
    )
    assert '<a href="/sync">Set them up</a>' in html
    post(home, "/sync/ignore", link="kim", feed_account="ACT-2")
    post(home, "/sync/ignore", link="kim", feed_account="ACT-3")
    page = SeenPage(post(home, "/sync/run").text)
    assert not any(text.startswith("New SimpleFIN") for _, text in page.paragraphs)


def test_sync_now_also_runs_a_link_with_only_new_accounts(
    home: TestClient, keychain, monkeypatch
) -> None:
    keychain.passwords[("finances-simplefin", "kim")] = "https://kim:k@bridge.simplefin.org/x"
    keychain.passwords[("finances-simplefin", "sam")] = "https://sam:s@bridge.simplefin.org/x"
    see("sam", "SAM-1", "Sam Checking")
    asked = []
    empty = {"errlist": [], "connections": [], "accounts": []}

    def bridge(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        asked.append(headers["Authorization"])
        return 200, json.dumps(empty).encode()

    monkeypatch.setattr(transport, "urllib_transport", bridge)
    assert post(home, "/sync/run").status_code == 200
    assert len(set(asked)) == 2
```

## Rules for this phase

- **One migration, never edited later.** `0007` follows `0006`. No other schema change.
- **Text fits its column** (AGENTS.md): SimpleFIN's names are cut, never refused.
- **Thin layers.** Guessing lives in `domain/feed_setup.py`, queries in `db/repositories.py`.
- **No new calls to SimpleFIN.** Only a sync contacts it, as before.
- **Messages carry no data** beyond the link name and a count.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.
- Do not run `fin` against the real database in `data/`, the real Keychain, or SimpleFIN; the owner does that after verification, starting with `fin db upgrade`.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, no warnings summary, at least N + 84 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_feed_setup.py tests/integration/test_migration_0007.py tests/integration/test_seen_feed_accounts.py tests/e2e/test_cli_sync_new_accounts.py tests/integration/test_web_new_accounts.py --no-cov` | exactly `84 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the three searches below | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.cli --cov=finances.sync --cov=finances.db --cov=finances.domain --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "select\(|finances\.db\.orm|session\.(add|execute|delete)|keyring|mastercard|money market|american express" -- src/finances/web/app.py src/finances/cli/sync.py`

`git grep -n --untracked -E "^ *(from|import) finances\.(db|sync|web|cli|ingest|analysis)" -- src/finances/domain`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 16d: new SimpleFIN accounts (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. In your final message, give the output line of each acceptance command, and for each of R1 to R20 the name of a test that covers it.
