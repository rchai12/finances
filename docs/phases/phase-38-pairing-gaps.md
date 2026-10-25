# Phase 38: pairing after unsplit and unshare, and the links that can be unlinked

## Goal

Two small gaps found by the post-37 audit (`docs/audit.md`) and confirmed against the code:

- Transfer pairing skips a split or shared transaction. Removing the split on the web, or removing a share on the web or in the terminal, makes the transaction a candidate again, but nothing pairs it until the next import, sync, or `fin categorize`; until then a transfer between the household's own accounts counts as spending. (`fin transactions unsplit` already pairs, through `categorize_all`. Rules, aliases, and clearing categories cannot create a pair, since pairing does not read categories, so they stay as they are.)
- The SimpleFIN page decides which links get an Unlink button partly from `_keychain_links`, which reads the `passwords` dict that only the tests' in-memory Keychain has. On the real macOS Keychain it finds nothing. The links come instead from the database, as `Sync now` already takes them (`list_feed_links`).

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/categorize/transfers.py` (`pair_transfers`), `src/finances/db/repositories/transfers.py` (`list_transfer_movements`: what is a candidate)
- `src/finances/web/routes/transactions.py` (`remove_split`), `src/finances/web/routes/shared.py` (`clear_share`), `src/finances/cli/shared.py` (`remove_command`)
- `src/finances/web/routes/sync.py` (`_keychain_links`, `_sync_page`, `run`), `src/finances/db/repositories/feed_links.py` (`list_feed_links`)

## Starting state

N is `3998` when Phase 37 is the last phase built. `pair_transfers(session)` stores every clear candidate and leaves the commit to the caller. `list_feed_links` returns the links that have a mapped or a seen feed account. No migration.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/routes/transactions.py` | `remove_split` pairs (R1) |
| `src/finances/web/routes/shared.py` | `clear_share` pairs (R2) |
| `src/finances/cli/shared.py` | `remove_command` pairs (R2) |
| `src/finances/web/routes/sync.py` | `_keychain_links` removed; the links from the database (R3) |
| `tests/integration/test_web_recheck.py` | the given diff (R4) |
| `tests/integration/test_pairing_gaps.py` | new: given |
| `tests/integration/test_pairing_gaps_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Pairing after rules, aliases, clearing categories, or any other action.
- Listing links from the Keychain by any other means; a change to `fin sync` commands.
- The other findings of `docs/audit.md`.

## Dependencies

None new.

## Requirements

- **R1.** `remove_split` calls `pair_transfers(session)` right after its `categorize(session)`, in the same session. The redirect and notice do not change.
- **R2.** `clear_share` and `remove_command` call `pair_transfers(session)` right after `unshare_transaction`, in the same session. Their redirect, notice, and output do not change; a refusal still pairs nothing and changes nothing.
- **R3.** `_sync_page`'s `links` are the links of its mapping rows together with `list_feed_links(session)` (read in its existing session), sorted. `_keychain_links` is deleted, and `sync.py` no longer imports `keyring`.
- **R4.** Apply the given diff to `tests/integration/test_web_recheck.py`: the link in its unlink test gets a seen feed account, the state a person reaches after linking. No other earlier test changes.

## Given diff to an earlier test

```text
diff --git a/tests/integration/test_web_recheck.py b/tests/integration/test_web_recheck.py
index a3a2ef1..13667a8 100644
--- a/tests/integration/test_web_recheck.py
+++ b/tests/integration/test_web_recheck.py
@@ -1,4 +1,4 @@
-from datetime import UTC, datetime
+from datetime import UTC, date, datetime
 from pathlib import Path
 
 import pytest
@@ -6,7 +6,9 @@ from fastapi.testclient import TestClient
 
 from finances.config import Settings
 from finances.db.backup import list_backups, make_backup
+from finances.db.engine import get_engine, session_scope
 from finances.db.migrate import upgrade_to_head
+from finances.db.repositories import record_seen_feed_account
 from finances.sync.links import load_access_url, save_access_url
 from finances.web.app import create_app
 from finances.web.login import set_password
@@ -97,6 +99,12 @@ def test_linking_needs_the_password(home: TestClient) -> None:
 
 def test_unlinking_has_a_page_and_needs_the_password(home: TestClient) -> None:
     save_access_url("alex", "https://user:secret@bridge.example/simplefin")
+    engine = get_engine()
+    with session_scope(engine) as session:
+        record_seen_feed_account(
+            session, "alex", "ACT-0001", "EXAMPLE CHECKING", "EXAMPLE BANK", date(2026, 10, 24)
+        )
+    engine.dispose()
     found = page(home, "/sync")
     assert [form["method"] for form in found.all("/sync/unlink")] == ["get"]
     confirm = page(home, "/sync/unlink?link=alex")
```

## Given tests

4 tests in one file. Do not change them.

`tests/integration/test_pairing_gaps.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    find_transfer_pair,
    record_seen_feed_account,
    set_account_owner,
    set_split,
    share_transaction,
)
from finances.sync.links import save_access_url
from finances.web.app import create_app
from tests.support import WEB_PORT, page, post, run


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    """Sam owns a checking and a savings account; $500.00 leaves checking (1) and reaches
    savings (2) on the same day, a clear transfer that nothing has paired yet."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        sam = create_person(session, "Sam")
        create_person(session, "Alex")
        for number, (name, kind, cents) in enumerate(
            (("Test Checking", "checking", -50000), ("Test Savings", "savings", 50000)), start=1
        ):
            account = create_account(session, name, "Test Bank", kind)
            set_account_owner(session, account.id, sam.id)
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, 10),
                    amount_cents=cents,
                    description="ONLINE TRANSFER",
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
    engine.dispose()
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    found.get("/sync")
    return found


def paired() -> bool:
    engine = get_engine()
    with session_scope(engine) as session:
        found = find_transfer_pair(session, 1)
    engine.dispose()
    return found is not None


def prepare(change) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        change(session)
    engine.dispose()


def test_clearing_a_split_on_the_web_pairs_the_transfer(client: TestClient) -> None:
    prepare(lambda session: set_split(session, 1, [(-30000, "Groceries"), (-20000, "Dining")]))
    response = post(client, "/transactions/1/split/clear")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/1?notice=split-removed",
    )
    assert paired()


def test_unsharing_on_the_web_pairs_the_transfer(client: TestClient) -> None:
    prepare(lambda session: share_transaction(session, 1, "Alex"))
    response = post(client, "/transactions/1/share/clear")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/1?notice=share-removed",
    )
    assert paired()


def test_unsharing_in_the_terminal_pairs_the_transfer(client: TestClient) -> None:
    prepare(lambda session: share_transaction(session, 1, "Alex"))
    result = run("shared", "remove", "--id", 1)
    assert (result.exit_code, result.output) == (0, "Transaction 1: no longer shared.\n")
    assert paired()


def test_unlink_is_offered_for_the_links_the_database_knows(client: TestClient) -> None:
    save_access_url("alex", "https://user:secret@bridge.example/simplefin")
    prepare(
        lambda session: record_seen_feed_account(
            session, "bea", "ACT-0001", "EXAMPLE CHECKING", "EXAMPLE BANK", date(2026, 5, 10)
        )
    )
    found = page(client, "/sync")
    assert [form["inputs"]["link"] for form in found.all("/sync/unlink")] == [("hidden", "bea")]
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_pairing_gaps_more.py`:

- clearing a split whose transaction has no transfer partner pairs nothing (`find_transfer_pair` is None) and still redirects with `split-removed`;
- `fin shared remove --id 99` (no such transaction) fails as before and stores no pair, with the fixture's clear transfer still unpaired;
- a link with a **mapped** account and another with only a seen account both get an Unlink form, in sorted order (`alex`, `bea`);
- with no links at all the SimpleFIN page has no Unlink form.

## Rules for this phase

- `pair_transfers` runs in the session that made the change, so the change and its pair commit together.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 4 tests; at least N + 4 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/integration/test_web_recheck.py`;
- `git grep -n -e "passwords" -e "keyring" -- src/finances/web/routes` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web.routes.sync --cov=finances.web.routes.transactions --cov=finances.web.routes.shared --cov=finances.cli.shared --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 38: pairing after unsplit and unshare, and the links that can be unlinked (YYYY-MM-DD)`.
