# Phase 45c: a link for every History record

## Goal

A repair and the last part of Phase 45. `views.audit.change_link` looks a change's kind up in a fixed table that has no entry for `proposal`, `alias`, `settlement`, or `finding`, so the History page fails with a server error (a `KeyError`) whenever one of those records is among the 200 it shows. Accepting any agent proposal is enough. With the owner's choices (2026-11-08):

- a proposal links to `/review`, an alias to `/categories` (its Merchant aliases section), a settlement to `/shared`, and a finding to the Insights page of its month (`/insights?month=YYYY-MM`), or to `/insights` when the record says `in every month`;
- a test fails the check when any kind in `finances.domain.audit.KINDS` has no link, so a new kind cannot break the page again;
- should a kind still have no link, its Record cell shows as plain text instead of the page failing.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/views/audit.py`, `src/finances/web/routes/history.py`, `src/finances/web/templates/history.html`, `src/finances/domain/audit.py`, `src/finances/domain/findings.py` (`finding_text`: the text a finding record holds)

## Starting state

N is `4291` when Phase 45b is the last phase built. **Sections: web.** No migration.

## Scope

| Path | What changes |
|---|---|
| `src/finances/views/audit.py` | `change_link` (R1, R2) |
| `src/finances/web/templates/history.html` | the given diff (R3) |
| `tests/integration/test_web_history_links.py` | new: given |
| `docs/progress.md` | one new entry |

## Out of scope

- A link to one proposal, alias, or settlement (their pages list them; there is no page per record); a History link for a finding's own row on Insights; any change to `fin audit`.

## Dependencies

None new.

## Design

```python
# src/finances/views/audit.py
def change_link(change: Change) -> str | None: ...
```

| Kind | Link |
|---|---|
| `transaction` | `/transactions/<record_id>`, as today |
| `account`, `person`, `category`, `rule`, `transfer`, `statement`, `backup` | as today |
| `proposal` | `/review` |
| `alias` | `/categories` |
| `settlement` | `/shared` |
| `finding` | the record's text (`after`, or `before` when `after` is None, as a reopen stores it) ends with ` in YYYY-MM` (four digits, a dash, two digits): `/insights?month=YYYY-MM`; otherwise `/insights` |
| any other | None |

The template links the Record cell only when the link is not None, and otherwise shows the record's text alone in the cell.

## Requirements

- **R1.** `change_link` as designed, for every kind in `KINDS`.
- **R2.** A kind not in the table gives None, never an error.
- **R3.** Apply the given template diff.

## Given template diff

```text
diff --git a/src/finances/web/templates/history.html b/src/finances/web/templates/history.html
index 623f3cf..fce7cce 100644
--- a/src/finances/web/templates/history.html
+++ b/src/finances/web/templates/history.html
@@ -20,7 +20,7 @@
 <table>
 <thead><tr><th>When (UTC)</th><th>Who</th><th>Action</th><th>Record</th><th>Before</th><th>After</th></tr></thead>
 <tbody>
-{% for row, link in rows %}<tr><td>{{ row.when }}</td><td>{{ row.who }}</td><td>{{ row.action }}</td><td><a href="{{ link }}">{{ row.record }}</a></td><td>{{ row.before }}</td><td>{{ row.after }}</td></tr>
+{% for row, link in rows %}<tr><td>{{ row.when }}</td><td>{{ row.who }}</td><td>{{ row.action }}</td><td>{% if link %}<a href="{{ link }}">{{ row.record }}</a>{% else %}{{ row.record }}{% endif %}</td><td>{{ row.before }}</td><td>{{ row.after }}</td></tr>
 {% endfor %}</tbody>
 </table>
 {% if rows|length >= limit %}<p class="hint">Showing the {{ limit }} newest. Choose an action or a day to see others.</p>{% endif %}
```

## Given tests

11 tests in one file. Do not change them. `test_web_history.py` passes unchanged with the template diff.

`tests/integration/test_web_history_links.py`

```python
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AuditRow
from finances.db.repositories import record_change
from finances.domain.audit import KINDS, Change
from finances.views.audit import change_link
from finances.web.app import create_app
from tests.support import WEB_PORT, page

AT = datetime(2026, 5, 25, 14, 3, tzinfo=UTC)


def change(kind: str, before: str | None = None, after: str | None = None) -> Change:
    return Change(1, AT, "person", "x", kind, 4, before, after)


@pytest.mark.parametrize(
    ("kind", "before", "after", "link"),
    [
        ("proposal", None, "transaction 7: Dining", "/review"),
        ("alias", None, "ACME CAFE -> ACME COFFEE", "/categories"),
        ("settlement", None, "Sam paid Alex", "/shared"),
        ("finding", None, "spike for Dining in 2026-05", "/insights?month=2026-05"),
        ("finding", "interest in 2026-06", None, "/insights?month=2026-06"),
        ("finding", None, "interest in every month", "/insights"),
        ("finding", "interest in every month", None, "/insights"),
    ],
)
def test_the_kinds_that_had_no_link(
    kind: str, before: str | None, after: str | None, link: str
) -> None:
    assert change_link(change(kind, before, after)) == link


def test_every_kind_has_a_link() -> None:
    assert [kind for kind in KINDS if change_link(change(kind, None, "x in 2026-05")) is None] == []


def test_a_kind_with_no_link_gives_none() -> None:
    assert change_link(change("nope")) is None


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def test_the_page_shows_a_proposal_and_a_finding(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        record_change(session, action="proposal_accepted", kind="proposal", record_id=3, after="x")
        record_change(
            session,
            action="finding_handled",
            kind="finding",
            record_id=1,
            after="spike for Dining in 2026-05",
        )
    engine.dispose()
    response = client.get("/history")
    assert response.status_code == 200
    found = page(client, "/history")
    assert "/review" in found.links
    assert "/insights?month=2026-05" in found.links


def test_a_kind_with_no_link_shows_as_plain_text(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        session.add(AuditRow(at=AT, who="person", action="x", kind="nope", record_id=9))
    engine.dispose()
    response = client.get("/history")
    assert response.status_code == 200
    assert "<td>nope 9</td>" in response.text
```

## Tests to write

None: the given file covers the phase.

## Rules for this phase

- No earlier test changes.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first web`;
- the given test file above, 11 tests; at least N + 11 passed in all;
- `git diff --stat HEAD -- tests` prints nothing;
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/views/audit.py,*/finances/web/routes/history.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 45c: a link for every History record (YYYY-MM-DD)`.
