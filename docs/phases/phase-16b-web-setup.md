# Phase 16b: the web interface, setup forms

## Goal

Let the household set up and run the finances from the web page instead of the terminal. After this phase, the site that `fin web serve` starts has forms and buttons to:

- **add an account** (name, institution, type, last four digits);
- **set an account's owner**: a person, or Joint;
- **add a person**, and **add a cardholder name** for a person (the name a statement prints on a shared card);
- **link a SimpleFIN subscription** by pasting its setup token, once per person's subscription;
- **map each SimpleFIN account** to an account from a list, or **create the account and map it** in one step;
- **sync now**, every link at once, and see what each account received;
- **unlink** a subscription, which forgets its access in the Keychain.

Every one of these does what an existing command does (`fin accounts add`, `fin accounts set-owner`, `fin people add`, `fin people alias`, `fin sync link`, `fin sync accounts`, `fin sync map`, `fin sync run`, `fin sync unlink`) by calling the same functions. The commands stay as they are.

**Why every form carries a token.** Phase 16a made the site answer only requests addressed to it by name. A page on another site can still make the household's browser *send a form* to `127.0.0.1`. So every request that changes something must carry a random token that only pages from this site know (R2, R3), and is refused when the browser says it came from another site. Requests that change something are `POST` only; a link or a `GET` never changes anything.

**Why the setup token never comes back.** A SimpleFIN setup token can be claimed once, and the access URL it gives reads every account. The token is typed into a password field, sent once, and never put back into a page, a log, or an error. The access URL goes straight to the Keychain, as `fin sync link` does.

This phase also makes the one function that sends HTTP requests ignore proxy settings in the environment (R18), which fixes the follow-up recorded for Phase 17c: under `HTTPS_PROXY` the network guard's own test failed.

## Read first

- `AGENTS.md`: "Privacy rules" (rules 1 and 4), "Architecture rules" (`web` is thin)
- `docs/phases/phase-16a-web-foundation.md`: the pages, the host check, and the headers this phase builds on
- `src/finances/web/app.py`, `src/finances/cli/accounts.py`, `src/finances/cli/people.py`, `src/finances/cli/sync.py`: the forms do what these do
- `src/finances/sync/runner.py`, `src/finances/sync/links.py`, `src/finances/sync/transport.py`
- `tests/integration/test_web_pages.py`: its tests must keep passing unchanged

## Starting state

- Phase 16a is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1620` when Phase 16a is the last phase built.
- `finances.web` and `finances.sync` are at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `pyproject.toml` | one dependency added (below) |
| `src/finances/sync/transport.py` | the opener ignores proxy settings (R18) |
| `src/finances/sync/runner.py` | new: `LinkRun`, `run_links` (R17) |
| `src/finances/web/app.py` | new: `CSRF_COOKIE`, `NOTICES`, `ACCOUNT_TYPES`, the form token, and the routes of R5 to R16 |
| `src/finances/web/templates/accounts.html`, `people.html`, `sync.html`, `error.html` | replaced: given, do not change |
| `src/finances/web/templates/messages.html`, `sync_accounts.html`, `sync_run.html` | new: given, do not change |
| `src/finances/web/static/app.css` | replaced: given, do not change |
| `tests/unit/test_run_links.py`, `tests/unit/test_transport_proxies.py`, `tests/integration/test_web_forms.py`, `tests/integration/test_web_sync_setup.py` | new: given, do not change |
| `docs/progress.md` | one new entry |

You may add private helpers to `app.py`. Do not change any other production file or any existing test. `layout.html` and `transactions.html` stay as they are.

## Out of scope

- Editing or deleting an account, a person, an owner, a cardholder name, or a mapping; closing an account. Each needs its own design.
- Statement upload, categories, a dashboard, or charts.
- JavaScript of any kind, and anything loaded from outside the app.
- A login, sessions beyond the form token, HTTPS, or any address other than `127.0.0.1`. Phase 20.
- Changing any `fin` command. `fin sync run` keeps its own loop; it may move to `run_links` in a later phase.
- A schedule for syncing. The launchd job already runs `fin sync run` daily.

## Dependencies

Add to `dependencies` in `pyproject.toml`, after `"jinja2>=3.1"`:

```toml
    "python-multipart>=0.0.9",
```

FastAPI needs it to read form fields. Then install:

`.venv/bin/python -m pip install -e ".[dev]"`

## Design

```python
# src/finances/web/app.py
CSRF_COOKIE = "fin_csrf"
NOTICES = {
    "account-added": "Account added.",
    "owner-set": "Owner saved.",
    "person-added": "Person added.",
    "alias-set": "Cardholder name saved.",
    "linked": "Link saved. Map each SimpleFIN account below.",
    "unlinked": "Link removed from the Keychain.",
    "mapped": "Account mapped.",
}
ACCOUNT_TYPES = tuple(item.value for item in AccountType)   # checking, savings, credit_card, other
```

```python
# src/finances/sync/runner.py
@dataclass(frozen=True)
class LinkRun:
    # What one link's sync did, or why it could not run.
    link: str
    report: SyncReport | None
    error: str | None


def run_links(
    engine: Engine,
    links: list[str],
    *,
    today: date,
    transport: Transport,
    days: int = SYNC_DAYS,
) -> list[LinkRun]: ...
```

Every form route is a `POST` route that reads its fields with FastAPI's `Form()`. Missing fields are read as empty text, never as a `422`. Each one ends in one of three ways:

- **refused before it starts** (R3): `403` for the token or the origin, `503` for a database that is not up to date;
- **refused by a check**: the page is shown again with status `400` and the message in `error`. The data is unchanged, and the fields typed are kept where the page has a form for them;
- **done**: a `303` redirect to the page that shows the result, with `notice=KEY` from `NOTICES` in the query, so reloading the page sends nothing again.

Two answers are not redirects: `GET /sync/accounts` is a page, and `POST /sync/run` shows its result directly, because the result exists only once.

The SimpleFIN routes call `transport.urllib_transport` through the module (`from finances.sync import transport`), never through a name imported from it, so that tests can replace it.

## Requirements

### Part 1: the form token

- **R1.** Every page that `_render` shows (all pages, error pages included) makes sure the browser holds a form token:
  - the token is the request's cookie `CSRF_COOKIE` when that cookie is exactly 43 characters from `A-Z`, `a-z`, `0-9`, `_`, and `-`;
  - otherwise it is a new `secrets.token_urlsafe(32)`, and the answer sets the cookie with `HttpOnly`, `SameSite=Strict`, and `Path=/`, and no `Max-Age` (it ends with the browser session);
  - when the cookie was already good, the answer sets no cookie.

  Every template gets it as `csrf`, and every `POST` form in the given templates sends it in a hidden field named `csrf`.
- **R2.** `_render` also gives every template:
  - `section`: the template's name up to its first `_`, so `sync_accounts` and `sync_run` mark SimpleFIN in the menu;
  - `notice`: `NOTICES[KEY]` when the query has `notice=KEY` and `KEY` is in `NOTICES`, otherwise `None`. The query text itself never reaches the page;
  - `error`: `None`, unless the route's context gives one.
- **R3.** Every `POST` route checks, in this order, before it reads or changes anything:
  1. when the request has an `Origin` header, it must be exactly `http://127.0.0.1:PORT` or `http://localhost:PORT`; otherwise answer `403` with the body `Bad origin` (`text/plain`);
  2. the cookie `CSRF_COOKIE` must be present and equal to the form field `csrf`, compared with `hmac.compare_digest`; otherwise answer `403`, `Bad form token` (`text/plain`);
  3. the database must be up to date, as for the pages; otherwise the `503` page with `NOT_MIGRATED`.

  These answers carry the security headers like every other answer.
- **R4.** Only `POST` changes data. A `GET` on a form's path answers `405`.

### Part 2: accounts and people

`accounts.html` gets: `rows` and `closed` as in Phase 16a; `types`, `ACCOUNT_TYPES`; `every_account`, the names of every account, closed included, in `list_accounts` order; `people`, the names in `list_people` order; and `form`, the add form's values: `name`, `institution`, `type`, `last4`, which are empty with `type` `credit_card` unless a refused add sent others.

`people.html` gets `rows` as in Phase 16a and `people`, the names in `list_people` order.

A page shown again after a refusal shows active accounts only, as `GET /accounts` does.

- **R5.** `POST /accounts/add` with `name`, `institution`, `type`, `last4`:
  - `type` not in `ACCOUNT_TYPES` is refused with `type must be one of: checking, savings, credit_card, other`;
  - `last4` is used without outer spaces, and an empty one means none;
  - `create_account` makes the account; its `ValueError` or `AccountExistsError` is refused with its message, and the form keeps the four values sent.

  Done: `/accounts?notice=account-added`.
- **R6.** `POST /accounts/owner` with `account` and `owner`:
  - the account is found by `get_account_by_name`, or refused with `account not found`;
  - `owner` without outer spaces, in any case, equal to `joint` makes the account Joint;
  - otherwise the person is found by `get_person_by_name`, or refused with `person not found`.

  `set_account_owner` records it. Done: `/accounts?notice=owner-set`.
- **R7.** `POST /people/add` with `name`: `create_person`; its `ValueError` or `PersonExistsError` is refused with its message. Done: `/people?notice=person-added`.
- **R8.** `POST /people/alias` with `person` and `cardholder`: the person is found by `get_person_by_name`, or refused with `person not found`; `set_cardholder_alias` records the name, and its `ValueError` is refused with its message. Done: `/people?notice=alias-set`.

### Part 3: SimpleFIN

`sync.html` gets `rows` as in Phase 16a; `links`, the sorted names of the links that have a mapping; and `form`, with `link`, the name typed into the link form (empty unless a refused link sent one).

- **R9.** `POST /sync/link` with `link`, `token`, and `replace`:
  1. `validate_link_name(link)`;
  2. when `load_access_url(link)` finds an access URL and `replace` is not `on`, refuse with `link NAME is already set up; tick Replace to set it up again`, without contacting SimpleFIN;
  3. `claim_access_url(token, transport.urllib_transport)`, then `save_access_url(link, ...)`.

  A `ValueError` or `SyncError` from any step is refused with its message on the SimpleFIN page, with `form` holding the link name. The token is never put into any page's context. Done: `/sync/accounts?link=NAME&notice=linked`.
- **R10.** `POST /sync/unlink` with `link`: `delete_access_url(link)`; `False` is refused with `link NAME is not set up`; a `ValueError` or `SyncError` is refused with its message, on the SimpleFIN page. The link's mappings and pulls stay. Done: `/sync?notice=unlinked`.
- **R11.** `GET /sync/accounts?link=NAME` shows `sync_accounts.html` with:
  - `link`: the name as given;
  - `accounts`: the names of every account, closed included, in `list_accounts` order;
  - `types`: `ACCOUNT_TYPES`;
  - `rows`: one per account in SimpleFIN's answer, in its order: `feed_account` (its id), `institution`, `name`, `currency`, and `mapped_to` (the name of the account mapped to it under this link, or empty);
  - `messages`: SimpleFIN's messages.

  To fetch, it validates the name, loads the access URL, and calls `fetch_accounts(access_url, TODAY, TODAY, transport.urllib_transport)`, where `TODAY` is today's date in UTC. A bad name, or a link that is not set up (`link NAME is not set up`), answers `400`; a `SyncError` answers `502`. Both have the message in `error` and no rows.
- **R12.** `POST /sync/map` with `link`, `feed_account`, and `account`:
  - validates the link name;
  - finds the account by `get_account_by_name`, or refuses with `account not found`;
  - uses `feed_account` without outer spaces, which must be 1 to 200 characters (`feed account id must be 1 to 200 characters`);
  - calls `map_feed_account(session, account_id, feed_id, link)`, whose `ValueError` is refused with its message.

  A refusal shows `error.html` with `message` and `back` set to `/sync`, status `400`. Done: `/sync/accounts?link=NAME&notice=mapped`.
- **R13.** `POST /sync/create` with `link`, `feed_account`, `account`, `institution`, `type`, and `last4` creates the account as R5 does and maps it as R12 does, in one session. Any refusal (R5's and R12's checks, `AccountExistsError` included) rolls the session back, so neither the account nor the mapping is saved, and shows `error.html` as R12 does. Done: as R12.
- **R14.** `POST /sync/run` takes the sorted names of the links that have a mapping and calls `run_links(engine, links, today=TODAY, transport=transport.urllib_transport)`. It answers `200` with `sync_run.html` and:
  - `rows`: for each link that ran, in order, one row per `AccountSync` of its report: `link`; `account` (the account's name, or empty when it is `None`); `feed_account`; `new`, `changed`, `removed`, `same` (the pull's `inserted`, `updated`, `removed`, `unchanged` as text, each empty when there is no pull); `drift` (`format_cents`, empty when there is no pull or no drift); and `problem` (or empty);
  - `errors`: the `error` of each link that did not run, in order;
  - `messages`: `LINK: MESSAGE` for each of SimpleFIN's messages of each link that ran;
  - `ran`: whether there was any link.

  These are the same rows `fin sync run` prints.
- **R15.** No page, error, or log ever holds a setup token or an access URL. Pages show link names and SimpleFIN account ids only.
- **R16.** The `engine` a route makes is disposed when the request ends, as Phase 16a's pages do.

### Part 4: sync

- **R17.** `run_links` syncs each link in `links`, in order, and returns one `LinkRun` per link:
  - a `SyncError` from `load_access_url` gives the error `link NAME: MESSAGE`;
  - no access URL gives `link NAME is not set up`;
  - otherwise it calls `run_sync(session, access_url, today=today, transport=transport, days=days, link=NAME)` inside its own `session_scope(engine)`, so each link's results are committed before the next link starts. A `SyncError` gives `link NAME: MESSAGE`, and the link's session is rolled back.
  - A link that ran has its `report` and `error` `None`; one that did not has `report` `None`.

  One link failing never stops the next.
- **R18.** `urllib_transport` ignores proxy settings in the environment (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and their lower-case forms): its opener is built with `urllib.request.ProxyHandler({})` in front of the redirect handler. Requests go straight to the host in the URL.

### Part 5: the code

- **R19.** `web/app.py` changes data only through `db` repository functions and `sync.links`, and reaches SimpleFIN only through `sync.simplefin` and `sync.runner` with `transport.urllib_transport`. It holds no query and does not import `keyring` or any HTTP library.

## Given templates and stylesheet

Create or replace these files exactly as shown. The tests read their markup. Every table keeps the cells of Phase 16a; the forms come after the tables.

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
{% endblock %}
```

`src/finances/web/templates/people.html`

```html
{% extends "layout.html" %}
{% block title %}People · Finances{% endblock %}
{% block content %}
<h1>People</h1>
{% include "messages.html" %}
{% if rows %}
<table>
<thead><tr><th>Name</th><th>Owns</th><th>Cardholder names</th></tr></thead>
<tbody>
{% for row in rows %}<tr><td>{{ row.name }}</td><td>{{ row.owns }}</td><td>{{ row.cardholders }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No people.</p>
{% endif %}
<h2>Add a person</h2>
<form method="post" action="/people/add" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Name <input name="name" required maxlength="100"></label>
  <button type="submit">Add person</button>
</form>
{% if people %}
<h2>Add a cardholder name</h2>
<p class="hint">The name a statement prints for this person on a shared card.</p>
<form method="post" action="/people/alias" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Person
    <select name="person">
      {% for name in people %}<option value="{{ name }}">{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Cardholder name <input name="cardholder" required maxlength="100"></label>
  <button type="submit">Save name</button>
</form>
{% endif %}
{% endblock %}
```

`src/finances/web/templates/sync.html`

```html
{% extends "layout.html" %}
{% block title %}SimpleFIN · Finances{% endblock %}
{% block content %}
<h1>SimpleFIN</h1>
{% include "messages.html" %}
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

`src/finances/web/templates/error.html`

```html
{% extends "layout.html" %}
{% block content %}
<p class="error">{{ message }}</p>
{% if back %}<p><a href="{{ back }}">Back</a></p>{% endif %}
{% endblock %}
```

`src/finances/web/templates/messages.html`

```html
{% if notice %}<p class="notice">{{ notice }}</p>{% endif %}
{% if error %}<p class="error">{{ error }}</p>{% endif %}
```

`src/finances/web/templates/sync_accounts.html`

```html
{% extends "layout.html" %}
{% block title %}SimpleFIN accounts · Finances{% endblock %}
{% block content %}
<h1>SimpleFIN accounts: {{ link }}</h1>
{% include "messages.html" %}
<p><a href="/sync">Back to SimpleFIN</a></p>
{% if rows %}
<table>
<thead><tr><th>SimpleFIN account</th><th>Institution</th><th>Name</th><th>Currency</th><th>Mapped to</th></tr></thead>
<tbody>
{% for row in rows %}<tr><td>{{ row.feed_account }}</td><td>{{ row.institution }}</td><td>{{ row.name }}</td><td>{{ row.currency }}</td><td>{{ row.mapped_to }}</td></tr>
{% endfor %}</tbody>
</table>
{% for row in rows %}
<section class="map">
<h2>{{ row.institution }}: {{ row.name }}</h2>
{% if accounts %}
<form method="post" action="/sync/map" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <input type="hidden" name="link" value="{{ link }}">
  <input type="hidden" name="feed_account" value="{{ row.feed_account }}">
  <label>Map to
    <select name="account">
      {% for name in accounts %}<option value="{{ name }}"{% if name == row.mapped_to %} selected{% endif %}>{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <button type="submit">Map</button>
</form>
{% endif %}
{% if not row.mapped_to %}
<form method="post" action="/sync/create" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <input type="hidden" name="link" value="{{ link }}">
  <input type="hidden" name="feed_account" value="{{ row.feed_account }}">
  <label>New account name <input name="account" required maxlength="100" value="{{ row.name }}"></label>
  <label>Institution <input name="institution" required maxlength="100" value="{{ row.institution }}"></label>
  <label>Type
    <select name="type">
      {% for kind in types %}<option value="{{ kind }}">{{ kind }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Last 4 digits <input name="last4" maxlength="4" inputmode="numeric"></label>
  <button type="submit">Create and map</button>
</form>
{% endif %}
</section>
{% endfor %}
{% elif not error %}
<p class="empty">No accounts.</p>
{% endif %}
{% for message in messages %}<p class="notice">SimpleFIN: {{ message }}</p>
{% endfor %}
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
{% endblock %}
```

`src/finances/web/static/app.css`

```css
:root { color-scheme: light dark; --line: #8884; --muted: #888; --accent: #2563eb; --bad: #b91c1c; }
body { font: 15px/1.5 system-ui, -apple-system, sans-serif; margin: 0; }
nav { display: flex; gap: 1rem; align-items: baseline; padding: .75rem 1rem; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
nav .brand { font-weight: 600; margin-right: 1rem; }
nav a { color: inherit; text-decoration: none; }
nav a[aria-current="page"] { color: var(--accent); font-weight: 600; }
main { padding: 1rem; max-width: 72rem; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: .35rem .6rem; border-bottom: 1px solid var(--line); }
td.amount, th.amount { text-align: right; font-variant-numeric: tabular-nums; }
.empty { color: var(--muted); }
.error { color: var(--bad); }
.filters { display: flex; gap: .75rem; flex-wrap: wrap; align-items: end; margin-bottom: 1rem; }
.filters label { display: flex; flex-direction: column; font-size: .85rem; }
h2 { font-size: 1.05rem; margin-top: 2rem; }
.notice { color: var(--accent); }
.hint { color: var(--muted); font-size: .9rem; }
.fields { display: flex; gap: .75rem; flex-wrap: wrap; align-items: end; }
.fields label { display: flex; flex-direction: column; font-size: .85rem; }
.fields label.check { flex-direction: row; gap: .35rem; align-items: center; }
form.inline { display: inline; }
ul.links li { margin: .3rem 0; }
section.map { border-top: 1px solid var(--line); margin-top: 1rem; }
```

## Given tests

Create these four files exactly as shown and do not change them. If one of their tests fails, the production code is wrong. Together they reach every line and branch of the code this phase adds, so there are no tests for you to write. The tests of Phase 16a must keep passing unchanged.

`tests/unit/test_run_links.py`

```python
import base64
import json
from datetime import UTC, date, datetime

import keyring
import keyring.backend
import keyring.errors
import pytest
from sqlalchemy import Engine, func, select

from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, map_feed_account
from finances.sync.runner import LinkRun, run_links

TODAY = date(2026, 5, 20)
SERVICE = "finances-simplefin"
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"


def key(access: str) -> str:
    user, password = access.split("//")[1].split("@")[0].split(":")
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def answer(*moves: tuple[str, str]) -> dict:
    posted = int(datetime(2026, 5, 18, 12, tzinfo=UTC).timestamp())
    return {
        "errlist": [],
        "connections": [{"conn_id": "C-1", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": "ACT-1",
                "name": "Probe",
                "conn_id": "C-1",
                "currency": "USD",
                "balance": "-1.00",
                "balance-date": posted,
                "transactions": [
                    {"id": feed_id, "posted": posted, "amount": amount, "description": "PROBE"}
                    for feed_id, amount in moves
                ],
            }
        ],
    }


class Bridge:
    def __init__(self, answers: dict[str, tuple[int, dict]]) -> None:
        self.answers = answers
        self.urls: list[str] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.urls.append(url)
        status, body = self.answers[headers["Authorization"]]
        return status, json.dumps(body).encode()


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringError("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.KeyringError("locked")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.KeyringError("locked")


@pytest.fixture
def mapped(db_engine: Engine) -> Engine:
    """Account 1 under link alex, account 2 under link sam, both as SimpleFIN ACT-1."""
    with session_scope(db_engine) as session:
        for name, link in (("Test Card", "alex"), ("Test Checking", "sam")):
            made = create_account(session, name, "Test Bank", "other")
            map_feed_account(session, made.id, "ACT-1", link)
    return db_engine


def stored(engine: Engine) -> dict[int, int]:
    with session_scope(engine) as session:
        rows = session.execute(
            select(TransactionRow.account_id, func.count()).group_by(TransactionRow.account_id)
        )
        return dict(rows.all())


def test_each_link_is_synced_and_committed(mapped: Engine, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    keychain.passwords[(SERVICE, "sam")] = SAM
    bridge = Bridge(
        {key(ALEX): (200, answer(("A-1", "-1.00"))), key(SAM): (200, answer(("S-1", "-2.00")))}
    )
    runs = run_links(mapped, ["alex", "sam"], today=TODAY, transport=bridge)
    assert [(run.link, run.error) for run in runs] == [("alex", None), ("sam", None)]
    assert [[item.account_id for item in run.report.accounts] for run in runs] == [[1], [2]]
    assert stored(mapped) == {1: 1, 2: 1}


def test_a_failing_link_does_not_stop_the_next(mapped: Engine, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    keychain.passwords[(SERVICE, "sam")] = SAM
    bridge = Bridge({key(ALEX): (403, {}), key(SAM): (200, answer(("S-1", "-2.00")))})
    runs = run_links(mapped, ["alex", "bob", "sam"], today=TODAY, transport=bridge)
    assert runs[:2] == [
        LinkRun("alex", None, "link alex: aggregator access was revoked or is wrong"),
        LinkRun("bob", None, "link bob is not set up"),
    ]
    assert runs[2].error is None
    assert stored(mapped) == {2: 1}


def test_a_keychain_that_fails(mapped: Engine) -> None:
    keyring.set_keyring(BrokenKeyring())
    bridge = Bridge({})
    runs = run_links(mapped, ["alex"], today=TODAY, transport=bridge)
    assert runs == [LinkRun("alex", None, "link alex: could not use the system keychain")]
    assert bridge.urls == []


def test_the_days_asked_for(mapped: Engine, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    bridge = Bridge({key(ALEX): (200, answer())})
    run_links(mapped, ["alex"], today=TODAY, transport=bridge)
    run_links(mapped, ["alex"], today=TODAY, transport=bridge, days=7)
    starts = [int(url.split("start-date=")[1].split("&")[0]) for url in bridge.urls]
    assert [datetime.fromtimestamp(start, UTC).date() for start in starts] == [
        date(2026, 4, 20),
        date(2026, 5, 13),
    ]


def test_no_links(mapped: Engine) -> None:
    assert run_links(mapped, [], today=TODAY, transport=Bridge({})) == []
```

`tests/unit/test_transport_proxies.py`

```python
import importlib
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from finances.sync import transport

PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


class Answer(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"direct"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[int]:
    """A web server on this machine that answers every GET with 200 and `direct`."""
    httpd = HTTPServer(("127.0.0.1", 0), Answer)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def proxied(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Proxy settings that point at a port where nothing listens, read as the module loads."""
    for name in PROXY_KEYS:
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    importlib.reload(transport)
    yield
    monkeypatch.undo()
    importlib.reload(transport)


def test_proxy_settings_are_ignored(server: int, proxied: None) -> None:
    url = f"http://127.0.0.1:{server}/accounts"
    assert transport.urllib_transport("GET", url, {}) == (200, b"direct")
```

`tests/integration/test_web_forms.py`

```python
import re
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AccountRow
from finances.db.repositories import create_account, create_person, set_account_owner
from finances.web.app import create_app

PORT = 8765
NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"
POSTS = [
    "/accounts/add",
    "/accounts/owner",
    "/people/add",
    "/people/alias",
    "/sync/link",
    "/sync/unlink",
    "/sync/map",
    "/sync/create",
    "/sync/run",
]


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


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Alex owns the card, checking has no owner, Sam owns nothing, and an old card is closed."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test <Card>", "Test Bank", "credit_card", last4="1111")
        create_account(session, "Test Checking", "Test Bank", "checking")
        old = create_account(session, "Test Old Card", "Test Bank", "credit_card")
        session.get(AccountRow, old.id).is_active = False
        alex = create_person(session, "Alex")
        create_person(session, "Sam")
        set_account_owner(session, card.id, alex.id)
    engine.dispose()
    client.get("/accounts")
    return client


def token(client: TestClient) -> str:
    return client.cookies["fin_csrf"]


def post(client: TestClient, path: str, **fields: str):
    return client.post(path, data={"csrf": token(client), **fields}, follow_redirects=False)


def accounts(client: TestClient) -> list[list[str]]:
    return Page(client.get("/accounts?closed=true").text).rows[1:]


def people(client: TestClient) -> list[list[str]]:
    return Page(client.get("/people").text).rows[1:]


def refused(response, message: str) -> bool:
    page = Page(response.text)
    return response.status_code == 400 and ("error", message) in page.paragraphs


# The form token


def test_a_page_gives_the_browser_a_form_token(client: TestClient) -> None:
    upgrade_to_head()
    first = client.get("/accounts")
    cookie = first.headers["set-cookie"]
    assert cookie.startswith("fin_csrf=")
    assert "HttpOnly" in cookie and "Path=/" in cookie
    assert "samesite=strict" in cookie.lower()
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token(client))
    assert "set-cookie" not in client.get("/people").headers


@pytest.mark.parametrize("path", ["/accounts", "/people", "/sync"])
def test_every_form_that_changes_data_carries_the_token(home: TestClient, path: str) -> None:
    posts = [form for form in Page(home.get(path).text).forms if form["method"] == "post"]
    assert posts
    for form in posts:
        assert form["inputs"]["csrf"] == ("hidden", token(home))


@pytest.mark.parametrize("cookie", ["", "short", "x" * 42 + "!"])
def test_a_missing_or_malformed_cookie_is_replaced(client: TestClient, cookie: str) -> None:
    upgrade_to_head()
    client.cookies.set("fin_csrf", cookie)
    response = client.get("/accounts")
    fresh = response.headers["set-cookie"].split(";")[0].removeprefix("fin_csrf=")
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", fresh)
    assert Page(response.text).find("/accounts/add")["inputs"]["csrf"] == ("hidden", fresh)


@pytest.mark.parametrize("path", POSTS)
def test_a_form_path_does_nothing_on_get(home: TestClient, path: str) -> None:
    assert home.get(path).status_code == 405


@pytest.mark.parametrize("path", POSTS)
def test_a_form_without_the_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.parametrize("path", POSTS)
def test_a_form_with_another_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={"csrf": "A" * 43}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


@pytest.mark.parametrize("path", POSTS)
def test_a_form_without_the_cookie_is_refused(home: TestClient, path: str) -> None:
    sent = token(home)
    home.cookies.clear()
    response = home.post(path, data={"csrf": sent}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


@pytest.mark.parametrize(
    "origin",
    ["http://evil.example", "null", f"http://127.0.0.1:{PORT + 1}", f"https://127.0.0.1:{PORT}"],
)
def test_a_form_sent_from_another_site_is_refused(home: TestClient, origin: str) -> None:
    response = home.post(
        "/accounts/add",
        data={"csrf": token(home), "name": "Probe", "institution": "Probe Bank", "type": "other"},
        headers={"origin": origin},
        follow_redirects=False,
    )
    assert (response.status_code, response.text) == (403, "Bad origin")
    assert len(accounts(home)) == 3


@pytest.mark.parametrize("origin", [f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"])
def test_a_form_sent_from_this_site_is_accepted(home: TestClient, origin: str) -> None:
    response = home.post(
        "/accounts/add",
        data={"csrf": token(home), "name": "Probe", "institution": "Probe Bank", "type": "other"},
        headers={"origin": origin},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.parametrize("path", POSTS)
def test_forms_need_a_migrated_database(client: TestClient, path: str) -> None:
    client.get("/accounts")
    response = post(client, path)
    assert response.status_code == 503
    assert ("error", NOT_MIGRATED) in Page(response.text).paragraphs


def test_an_unknown_notice_shows_nothing(home: TestClient) -> None:
    page = Page(home.get("/accounts?notice=<b>hello</b>").text)
    assert [kind for kind, _ in page.paragraphs if kind == "notice"] == []


# Accounts


def test_add_an_account(home: TestClient) -> None:
    response = post(
        home,
        "/accounts/add",
        name="  Probe Visa ",
        institution=" Probe Bank ",
        type="credit_card",
        last4="1234",
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/accounts?notice=account-added",
    )
    page = Page(home.get(response.headers["location"]).text)
    assert ("notice", "Account added.") in page.paragraphs
    assert ["Probe Visa", "Probe Bank", "credit_card", "••1234", "yes", ""] in page.rows


def test_add_an_account_without_last_four_digits(home: TestClient) -> None:
    post(home, "/accounts/add", name="Probe Savings", institution="Probe Bank", type="savings")
    assert ["Probe Savings", "Probe Bank", "savings", "", "yes", ""] in accounts(home)


def test_the_add_form_offers_every_type(home: TestClient) -> None:
    form = Page(home.get("/accounts").text).find("/accounts/add")
    assert form["selects"]["type"] == [
        ("checking", False),
        ("savings", False),
        ("credit_card", True),
        ("other", False),
    ]
    assert set(form["inputs"]) == {"csrf", "name", "institution", "last4"}


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (
            {"name": " ", "institution": "Probe Bank", "type": "other"},
            "account name must not be empty",
        ),
        ({"name": "Probe", "institution": "", "type": "other"}, "institution must not be empty"),
        (
            {"name": "Probe", "institution": "Probe Bank", "type": "loan"},
            "type must be one of: checking, savings, credit_card, other",
        ),
        (
            {"name": "Probe", "institution": "Probe Bank", "type": "other", "last4": "12a4"},
            "last4 must be exactly 4 digits",
        ),
        (
            {"name": "test <CARD>", "institution": "Probe Bank", "type": "other"},
            "an account with this name already exists",
        ),
    ],
)
def test_a_refused_account_keeps_the_form(home: TestClient, fields: dict, message: str) -> None:
    response = post(home, "/accounts/add", **fields)
    assert refused(response, message)
    form = Page(response.text).find("/accounts/add")
    assert form["inputs"]["name"] == ("text", fields["name"])
    assert form["inputs"]["institution"] == ("text", fields["institution"])
    assert form["inputs"]["last4"] == ("text", fields.get("last4", ""))
    assert len(accounts(home)) == 3


def test_a_refused_account_keeps_the_chosen_type(home: TestClient) -> None:
    response = post(home, "/accounts/add", name="", institution="Probe Bank", type="savings")
    selected = [
        value
        for value, chosen in Page(response.text).find("/accounts/add")["selects"]["type"]
        if chosen
    ]
    assert selected == ["savings"]


def test_the_owner_form_lists_every_account_and_person(home: TestClient) -> None:
    form = Page(home.get("/accounts").text).find("/accounts/owner")
    assert [value for value, _ in form["selects"]["account"]] == [
        "Test <Card>",
        "Test Checking",
        "Test Old Card",
    ]
    assert [value for value, _ in form["selects"]["owner"]] == ["Alex", "Sam", "joint"]


def test_no_owner_form_without_accounts(client: TestClient) -> None:
    upgrade_to_head()
    actions = [form["action"] for form in Page(client.get("/accounts").text).forms]
    assert actions == ["/accounts/add"]


@pytest.mark.parametrize(
    ("account", "owner", "shown"),
    [
        ("test checking", " sam ", "Sam"),
        ("Test <Card>", "joint", "Joint"),
        ("Test Old Card", "JOINT", "Joint"),
    ],
)
def test_set_an_owner(home: TestClient, account: str, owner: str, shown: str) -> None:
    response = post(home, "/accounts/owner", account=account, owner=owner)
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/accounts?notice=owner-set",
    )
    rows = {row[0].lower(): row[5] for row in accounts(home)}
    assert rows[account.lower()] == shown
    assert ("notice", "Owner saved.") in Page(
        home.get(response.headers["location"]).text
    ).paragraphs


@pytest.mark.parametrize(
    ("account", "owner", "message"),
    [
        ("Nope", "Alex", "account not found"),
        ("Test Checking", "Nobody", "person not found"),
        ("Test Checking", "", "person not found"),
    ],
)
def test_a_refused_owner(home: TestClient, account: str, owner: str, message: str) -> None:
    assert refused(post(home, "/accounts/owner", account=account, owner=owner), message)
    assert accounts(home)[1][5] == ""


# People


def test_add_a_person(home: TestClient) -> None:
    response = post(home, "/people/add", name="  Kim ")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/people?notice=person-added",
    )
    page = Page(home.get(response.headers["location"]).text)
    assert ("notice", "Person added.") in page.paragraphs
    assert ["Kim", "", ""] in page.rows


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("alex", "a person with this name already exists"),
        ("  ", "a person's name must be 1 to 100 characters"),
        ("Joint", "joint and unassigned are reserved names"),
    ],
)
def test_a_refused_person(home: TestClient, name: str, message: str) -> None:
    assert refused(post(home, "/people/add", name=name), message)
    assert [row[0] for row in people(home)] == ["Alex", "Sam"]


def test_add_a_cardholder_name(home: TestClient) -> None:
    response = post(home, "/people/alias", person="sam", cardholder="  sam   q doe ")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/people?notice=alias-set",
    )
    page = Page(home.get(response.headers["location"]).text)
    assert ("notice", "Cardholder name saved.") in page.paragraphs
    assert ["Sam", "", "SAM Q DOE"] in page.rows


def test_a_cardholder_name_moves_to_another_person(home: TestClient) -> None:
    post(home, "/people/alias", person="Sam", cardholder="A DOE")
    post(home, "/people/alias", person="Alex", cardholder="a doe")
    assert people(home) == [["Alex", "Test <Card>", "A DOE"], ["Sam", "", ""]]


@pytest.mark.parametrize(
    ("person", "cardholder", "message"),
    [
        ("Nobody", "A DOE", "person not found"),
        ("Sam", "   ", "a cardholder name must be 1 to 100 characters"),
    ],
)
def test_a_refused_cardholder_name(
    home: TestClient, person: str, cardholder: str, message: str
) -> None:
    assert refused(post(home, "/people/alias", person=person, cardholder=cardholder), message)
    assert people(home) == [["Alex", "Test <Card>", ""], ["Sam", "", ""]]


def test_the_cardholder_form_lists_people(home: TestClient) -> None:
    form = Page(home.get("/people").text).find("/people/alias")
    assert form["selects"]["person"] == [("Alex", False), ("Sam", False)]


def test_no_cardholder_form_without_people(client: TestClient) -> None:
    upgrade_to_head()
    actions = [form["action"] for form in Page(client.get("/people").text).forms]
    assert actions == ["/people/add"]
```

`tests/integration/test_web_sync_setup.py`

```python
import base64
import json
from datetime import UTC, datetime
from html.parser import HTMLParser

import keyring
import keyring.backend
import keyring.errors
import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import (
    create_account,
    list_accounts,
    list_feed_accounts,
)
from finances.sync import transport
from finances.web.app import create_app

PORT = 8765
SERVICE = "finances-simplefin"
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"
CLAIM = "https://bridge.simplefin.org/simplefin/claim/DEMO-1"
TOKEN = base64.b64encode(CLAIM.encode()).decode()
BAD_NAME = "a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter"
RUN_HEADINGS = [
    "Link",
    "Account",
    "SimpleFIN account",
    "New",
    "Changed",
    "Removed",
    "Same",
    "Drift",
    "Problem",
]


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


def stamp(days_ago: int) -> int:
    today = datetime.now(UTC).date()
    noon = datetime(today.year, today.month, today.day, 12, tzinfo=UTC)
    return int(noon.timestamp()) - days_ago * 86400


def account(account_id: str, name: str, balance: str, *moves: tuple[str, int, str]) -> dict:
    return {
        "id": account_id,
        "name": name,
        "conn_id": "C-1",
        "currency": "USD",
        "balance": balance,
        "balance-date": stamp(0),
        "transactions": [
            {"id": feed_id, "posted": stamp(days_ago), "amount": amount, "description": "PROBE"}
            for feed_id, days_ago, amount in moves
        ],
    }


class Bridge:
    """A fake SimpleFIN Bridge: claims give an access URL; each access URL has its answer."""

    def __init__(self) -> None:
        self.claim = (200, ALEX.encode())
        self.answers: dict[str, tuple[int, dict]] = {}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, url))
        if method == "POST":
            return self.claim
        status, body = self.answers[headers["Authorization"]]
        return status, json.dumps(body).encode()

    def answer(self, access: str, *accounts: dict, status: int = 200, messages=()) -> None:
        user, password = access.split("//")[1].split("@")[0].split(":")
        key = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        body = {
            "errlist": [{"code": "con.auth", "msg": text} for text in messages],
            "connections": [
                {"conn_id": "C-1", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}
            ],
            "accounts": list(accounts),
        }
        self.answers[key] = (status, body)


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringError("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.KeyringError("locked")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.KeyringError("locked")


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> Bridge:
    fake = Bridge()
    monkeypatch.setattr(transport, "urllib_transport", fake)
    return fake


@pytest.fixture
def home(tmp_settings: Settings, bridge: Bridge) -> TestClient:
    """Two accounts, nothing mapped, nothing in the Keychain."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_account(session, "Test Checking", "Test Bank", "checking")
    engine.dispose()
    client = TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")
    client.get("/sync")
    return client


def post(client: TestClient, path: str, **fields: str):
    return client.post(
        path, data={"csrf": client.cookies["fin_csrf"], **fields}, follow_redirects=False
    )


def mappings() -> list[tuple[str, str, str]]:
    engine = get_engine()
    with session_scope(engine) as session:
        names = {item.id: item.name for item in list_accounts(session, include_inactive=True)}
        found = [
            (item.link, item.provider_account_id, names[item.account_id])
            for item in list_feed_accounts(session)
        ]
    engine.dispose()
    return found


def refused(response, status: int, message: str) -> bool:
    return response.status_code == status and ("error", message) in Page(response.text).paragraphs


# Linking a SimpleFIN subscription


def test_link_claims_the_token_and_keeps_the_access_in_the_keychain(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-1.00"))
    response = post(home, "/sync/link", link="alex", token=TOKEN)
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/sync/accounts?link=alex&notice=linked",
    )
    assert bridge.calls == [("POST", CLAIM)]
    assert keychain.passwords == {(SERVICE, "alex"): ALEX}
    page = home.get(response.headers["location"])
    assert ("notice", "Link saved. Map each SimpleFIN account below.") in Page(page.text).paragraphs
    assert "alex-pass" not in page.text and TOKEN not in page.text


def test_the_link_form_hides_the_token(home: TestClient) -> None:
    form = Page(home.get("/sync").text).find("/sync/link")
    assert form["inputs"]["token"] == ("password", "")
    assert form["inputs"]["replace"] == ("checkbox", "on")
    assert 'autocomplete="off"' in home.get("/sync").text


def test_a_link_that_exists_is_replaced_only_when_asked(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    keychain.passwords[(SERVICE, "alex")] = SAM
    response = post(home, "/sync/link", link="alex", token=TOKEN)
    assert refused(response, 400, "link alex is already set up; tick Replace to set it up again")
    assert bridge.calls == []
    assert keychain.passwords == {(SERVICE, "alex"): SAM}
    response = post(home, "/sync/link", link="alex", token=TOKEN, replace="on")
    assert response.status_code == 303
    assert keychain.passwords == {(SERVICE, "alex"): ALEX}


@pytest.mark.parametrize(
    ("link", "token", "claim", "message"),
    [
        ("Alex", TOKEN, (200, ALEX.encode()), BAD_NAME),
        ("", TOKEN, (200, ALEX.encode()), BAD_NAME),
        ("alex", "not a token", (200, ALEX.encode()), "setup token is not valid"),
        ("alex", TOKEN, (403, b""), "setup token was already used or does not exist"),
    ],
)
def test_a_refused_link_keeps_the_name_and_never_the_token(
    home: TestClient,
    bridge: Bridge,
    keychain,
    link: str,
    token: str,
    claim: tuple[int, bytes],
    message: str,
) -> None:
    bridge.claim = claim
    response = post(home, "/sync/link", link=link, token=token)
    assert refused(response, 400, message)
    form = Page(response.text).find("/sync/link")
    assert form["inputs"]["link"] == ("text", link)
    assert form["inputs"]["token"] == ("password", "")
    assert TOKEN not in response.text
    assert keychain.passwords == {}


def test_link_when_the_keychain_fails(home: TestClient, bridge: Bridge) -> None:
    keyring.set_keyring(BrokenKeyring())
    response = post(home, "/sync/link", link="alex", token=TOKEN)
    assert refused(response, 400, "could not use the system keychain")
    assert bridge.calls == []


# Unlinking


def test_unlink_forgets_the_access_and_keeps_the_mappings(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    response = post(home, "/sync/unlink", link="alex")
    assert (response.status_code, response.headers["location"]) == (303, "/sync?notice=unlinked")
    assert keychain.passwords == {}
    assert mappings() == [("alex", "ACT-1", "Test Card")]
    page = Page(home.get(response.headers["location"]).text)
    assert ("notice", "Link removed from the Keychain.") in page.paragraphs
    assert page.rows[1][:4] == ["alex", "Test Card", "ACT-1", "no"]
    assert bridge.calls == []


@pytest.mark.parametrize(
    ("link", "message"), [("sam", "link sam is not set up"), ("Sam", BAD_NAME)]
)
def test_a_refused_unlink(home: TestClient, keychain, link: str, message: str) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    assert refused(post(home, "/sync/unlink", link=link), 400, message)
    assert keychain.passwords == {(SERVICE, "alex"): ALEX}


def test_unlink_when_the_keychain_fails(home: TestClient) -> None:
    keyring.set_keyring(BrokenKeyring())
    assert refused(
        post(home, "/sync/unlink", link="alex"), 400, "could not use the system keychain"
    )


def test_the_sync_page_lists_each_mapped_link_with_its_buttons(home: TestClient, keychain) -> None:
    post(home, "/sync/map", link="sam", feed_account="ACT-2", account="Test Checking")
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    page = Page(home.get("/sync").text)
    unlinks = [form for form in page.forms if form["action"] == "/sync/unlink"]
    assert [form["inputs"]["link"] for form in unlinks] == [("hidden", "alex"), ("hidden", "sam")]
    assert [form["action"] for form in page.forms if form["action"] == "/sync/run"] == ["/sync/run"]
    assert '<a href="/sync/accounts?link=alex">' in home.get("/sync").text


def test_no_run_or_unlink_buttons_with_nothing_mapped(home: TestClient) -> None:
    actions = [form["action"] for form in Page(home.get("/sync").text).forms]
    assert actions == ["/sync/link", "/sync/accounts"]


# A link's SimpleFIN accounts


def test_a_links_accounts_with_what_each_is_mapped_to(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    post(home, "/sync/map", link="sam", feed_account="ACT-2", account="Test Checking")
    bridge.answer(
        ALEX,
        account("ACT-1", "Probe <Card>", "-1.00"),
        account("ACT-2", "Probe Savings", "5.00"),
        messages=("Probe note",),
    )
    response = home.get("/sync/accounts?link=alex")
    page = Page(response.text)
    assert response.status_code == 200
    assert page.rows == [
        ["SimpleFIN account", "Institution", "Name", "Currency", "Mapped to"],
        ["ACT-1", "Probe Bank", "Probe <Card>", "USD", "Test Card"],
        ["ACT-2", "Probe Bank", "Probe Savings", "USD", ""],
    ]
    assert ("notice", "SimpleFIN: Probe note") in page.paragraphs
    assert "Probe &lt;Card&gt;" in response.text
    assert "alex-pass" not in response.text
    method, url = bridge.calls[0]
    assert method == "GET" and url.startswith(
        ALEX.replace("alex-user:alex-pass@", "") + "/accounts"
    )


def test_each_account_can_be_mapped_from_a_list(home: TestClient, bridge: Bridge, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Checking")
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-1.00"), account("ACT-2", "Probe X", "0"))
    page = Page(home.get("/sync/accounts?link=alex").text)
    maps = [form for form in page.forms if form["action"] == "/sync/map"]
    assert [form["inputs"]["feed_account"] for form in maps] == [
        ("hidden", "ACT-1"),
        ("hidden", "ACT-2"),
    ]
    assert all(form["inputs"]["link"] == ("hidden", "alex") for form in maps)
    assert maps[0]["selects"]["account"] == [("Test Card", False), ("Test Checking", True)]
    assert maps[1]["selects"]["account"] == [("Test Card", False), ("Test Checking", False)]


def test_only_an_unmapped_account_offers_create_and_map(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-1.00"), account("ACT-2", "Probe X", "0"))
    page = Page(home.get("/sync/accounts?link=alex").text)
    creates = [form for form in page.forms if form["action"] == "/sync/create"]
    assert len(creates) == 1
    inputs = creates[0]["inputs"]
    assert inputs["feed_account"] == ("hidden", "ACT-2")
    assert inputs["account"] == ("text", "Probe X")
    assert inputs["institution"] == ("text", "Probe Bank")
    assert [value for value, _ in creates[0]["selects"]["type"]] == [
        "checking",
        "savings",
        "credit_card",
        "other",
    ]


@pytest.mark.parametrize(
    ("query", "status", "message"),
    [
        ("", 400, BAD_NAME),
        ("?link=Alex", 400, BAD_NAME),
        ("?link=sam", 400, "link sam is not set up"),
        ("?link=alex", 502, "aggregator access was revoked or is wrong"),
    ],
)
def test_a_links_accounts_refused(
    home: TestClient, bridge: Bridge, keychain, query: str, status: int, message: str
) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    bridge.answer(ALEX, status=403)
    response = home.get(f"/sync/accounts{query}")
    assert refused(response, status, message)
    assert Page(response.text).rows == []


def test_a_links_accounts_need_a_migrated_database(tmp_settings: Settings, bridge: Bridge) -> None:
    client = TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")
    response = client.get("/sync/accounts?link=alex")
    assert refused(response, 503, "The database is not up to date. Run: fin db upgrade")
    assert bridge.calls == []


def test_a_links_accounts_when_the_keychain_fails(home: TestClient, bridge: Bridge) -> None:
    keyring.set_keyring(BrokenKeyring())
    assert refused(home.get("/sync/accounts?link=alex"), 502, "could not use the system keychain")
    assert bridge.calls == []


# Mapping


def test_map_an_account(home: TestClient, bridge: Bridge) -> None:
    response = post(home, "/sync/map", link="alex", feed_account=" ACT-1 ", account="test card")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/sync/accounts?link=alex&notice=mapped",
    )
    assert mappings() == [("alex", "ACT-1", "Test Card")]
    response = post(home, "/sync/map", link="alex", feed_account="ACT-7", account="Test Card")
    assert mappings() == [("alex", "ACT-7", "Test Card")]
    assert bridge.calls == []


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"link": "alex", "feed_account": "ACT-1", "account": "Nope"}, "account not found"),
        (
            {"link": "alex", "feed_account": "  ", "account": "Test Card"},
            "feed account id must be 1 to 200 characters",
        ),
        (
            {"link": "alex", "feed_account": "X" * 201, "account": "Test Card"},
            "feed account id must be 1 to 200 characters",
        ),
        (
            {"link": "alex", "feed_account": "ACT-9", "account": "Test Checking"},
            "feed account is already mapped to another account",
        ),
        ({"link": "Alex", "feed_account": "ACT-1", "account": "Test Card"}, BAD_NAME),
    ],
)
def test_a_refused_mapping(home: TestClient, fields: dict, message: str) -> None:
    post(home, "/sync/map", link="alex", feed_account="ACT-9", account="Test Card")
    response = post(home, "/sync/map", **fields)
    assert refused(response, 400, message)
    assert '<a href="/sync">Back</a>' in response.text
    assert mappings() == [("alex", "ACT-9", "Test Card")]


def test_create_an_account_and_map_it(home: TestClient, bridge: Bridge) -> None:
    response = post(
        home,
        "/sync/create",
        link="sam",
        feed_account="ACT-5",
        account=" Probe Savings ",
        institution="Probe Bank",
        type="savings",
        last4="5555",
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/sync/accounts?link=sam&notice=mapped",
    )
    assert mappings() == [("sam", "ACT-5", "Probe Savings")]
    rows = Page(home.get("/accounts").text).rows
    assert ["Probe Savings", "Probe Bank", "savings", "••5555", "yes", ""] in rows
    assert bridge.calls == []


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"account": "test card"}, "an account with this name already exists"),
        ({"type": "loan"}, "type must be one of: checking, savings, credit_card, other"),
        ({"last4": "55"}, "last4 must be exactly 4 digits"),
        ({"feed_account": ""}, "feed account id must be 1 to 200 characters"),
        ({"feed_account": "ACT-9"}, "feed account is already mapped to another account"),
        ({"link": "Sam"}, BAD_NAME),
        ({"institution": " "}, "institution must not be empty"),
    ],
)
def test_a_refused_create_changes_nothing(home: TestClient, fields: dict, message: str) -> None:
    post(home, "/sync/map", link="sam", feed_account="ACT-9", account="Test Card")
    sent = {
        "link": "sam",
        "feed_account": "ACT-5",
        "account": "Probe Savings",
        "institution": "Probe Bank",
        "type": "savings",
        **fields,
    }
    response = post(home, "/sync/create", **sent)
    assert refused(response, 400, message)
    assert mappings() == [("sam", "ACT-9", "Test Card")]
    assert len(Page(home.get("/accounts?closed=true").text).rows) == 3


# Sync now


def test_sync_now_pulls_every_link(home: TestClient, bridge: Bridge, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    keychain.passwords[(SERVICE, "sam")] = SAM
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    post(home, "/sync/map", link="sam", feed_account="ACT-1", account="Test Checking")
    bridge.answer(
        ALEX,
        account("ACT-1", "Probe Card", "-12.50", ("A-1", 3, "-12.50")),
        account("ACT-9", "Probe Unmapped", "1.00"),
    )
    bridge.answer(
        SAM,
        account("ACT-1", "Probe Checking", "-4.00", ("S-1", 2, "-4.00")),
        messages=("Sam bank note",),
    )
    response = post(home, "/sync/run")
    page = Page(response.text)
    assert response.status_code == 200
    assert page.rows == [
        RUN_HEADINGS,
        ["alex", "Test Card", "ACT-1", "1", "0", "0", "0", "", ""],
        ["alex", "", "ACT-9", "", "", "", "", "", "not mapped"],
        ["sam", "Test Checking", "ACT-1", "1", "0", "0", "0", "", ""],
    ]
    assert ("notice", "SimpleFIN sam: Sam bank note") in page.paragraphs
    assert [kind for kind, _ in page.paragraphs if kind == "error"] == []
    assert [
        len(Page(home.get(f"/transactions?account={name}").text).rows)
        for name in (
            "Test Card",
            "Test Checking",
        )
    ] == [2, 2]


def test_sync_now_keeps_what_was_pulled(home: TestClient, bridge: Bridge, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-12.50", ("A-1", 3, "-12.50")))
    post(home, "/sync/run")
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-15.00", ("A-1", 3, "-12.50")))
    rows = Page(post(home, "/sync/run").text).rows
    assert rows[1:] == [["alex", "Test Card", "ACT-1", "0", "0", "0", "1", "-$2.50", ""]]
    status = Page(home.get("/sync").text).rows
    assert status[1][-1] == "-$2.50"


def test_one_link_failing_does_not_stop_the_others(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    keychain.passwords[(SERVICE, "sam")] = SAM
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    post(home, "/sync/map", link="bob", feed_account="ACT-1", account="Test Checking")
    post(
        home,
        "/sync/create",
        link="sam",
        feed_account="ACT-1",
        account="Test Other",
        institution="Probe Bank",
        type="other",
    )
    bridge.answer(ALEX, status=403)
    bridge.answer(SAM, account("ACT-1", "Probe Other", "-4.00", ("S-1", 2, "-4.00")))
    page = Page(post(home, "/sync/run").text)
    assert [text for kind, text in page.paragraphs if kind == "error"] == [
        "link alex: aggregator access was revoked or is wrong",
        "link bob is not set up",
    ]
    assert page.rows == [RUN_HEADINGS, ["sam", "Test Other", "ACT-1", "1", "0", "0", "0", "", ""]]


def test_sync_now_with_nothing_mapped(home: TestClient, bridge: Bridge) -> None:
    response = post(home, "/sync/run")
    assert response.status_code == 200
    assert ("empty", "No mapped accounts.") in Page(response.text).paragraphs
    assert bridge.calls == []
```

## Rules for this phase

- **No secret in a page.** The setup token is read once and passed to `claim_access_url`; the access URL goes only to `save_access_url` and `run_links`. Neither is logged, put into a context, or included in an error.
- **POST only, with the token.** Every route that changes data is `POST` and runs R3's checks first.
- **One address.** The server still listens on `127.0.0.1` only.
- **No JavaScript and nothing from outside.**
- **Thin.** `web/` calls the functions the commands call. No query, no business logic.
- **Tests start no server and contact nothing.** SimpleFIN is replaced in the tests; the Keychain is the in-memory one from `tests/conftest.py`.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.
- Do not run `fin web serve` or `fin sync` against the real database, the real Keychain, or SimpleFIN; the owner does that after verification.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, no warnings summary, at least N + 133 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_run_links.py tests/unit/test_transport_proxies.py tests/integration/test_web_forms.py tests/integration/test_web_sync_setup.py --no-cov` | exactly `133 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the six searches below | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.sync --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "select\(|finances\.db\.orm|session\.(add|execute|delete)|keyring" -- src/finances/web`

`git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`

`git grep -n --untracked -E "0\.0\.0\.0|host=\"" -- src/finances`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/web`

`git grep -n --untracked -E "\"(token|access_url|access)\": |value=\"\{\{ *(token|access)" -- src/finances/web`

The full `pytest` run no longer needs a shell without proxy variables: with R18, it passes with `HTTPS_PROXY` set too.

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 16b: the web interface, setup forms (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. Under "Deviations", list your design choices and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command, and for each of R1 to R19 the name of a test that covers it.
