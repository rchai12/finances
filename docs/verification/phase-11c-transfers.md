# Verify Phase 11c: transfers

Spec: `docs/phases/phase-11c-transfers.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure, the probe, and the verdict.

The coder added transfer pairs and rejections (migration 0009, given), the pure functions that find candidates and clear pairs, the repositories, a service, views, `fin transfers`, and pairing after every categorize run. One migration and three test files were given.

These are correct and must not be reported: one query or several in a view; `get_transaction` per line in the views; Typer's own exit code 2 for an id that is not a whole number.

## 1. Gates

N is `2249` when Phase 11b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 41 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_transfers.py tests/integration/test_migration_0009.py tests/e2e/test_cli_transfers.py --no-cov` | exactly `41 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.transfers --cov=finances.categorize.transfers --cov=finances.views.transfers --cov=finances.cli.transfers --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|transfer_candidates|clear_pairs" -- src/finances/cli src/finances/web` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/cli/categories.py
 M src/finances/cli/main.py
 M src/finances/db/orm.py
 M src/finances/db/repositories.py
 M src/finances/domain/models.py
 M src/finances/web/app.py
?? src/finances/categorize/transfers.py
?? src/finances/cli/transfers.py
?? src/finances/db/migrations/versions/0009_transfers.py
?? src/finances/domain/transfers.py
?? src/finances/views/transfers.py
?? tests/e2e/test_cli_transfers.py
?? tests/integration/test_migration_0009.py
?? tests/integration/test_transfer_store.py
?? tests/unit/test_transfers.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R3, R14 to R20 | gate 2 | passes |
| R4 to R8, R11 to R13, R21 | the coder's `tests/integration/test_transfer_store.py` | each item of the spec's "Tests to write" has a test |
| R4 (pending), R9, R11 | probe | every line |
| R21 | `git diff HEAD -- src/finances/web/app.py` | only `pair_transfers` added after `categorize` in `POST /sync/run`, and its import |

## 4. Probe

It migrates a temporary database it removes, adds synthetic feed transactions in two accounts, records a rejection, pairs, then deletes a paired and a rejected feed transaction through `delete_feed_transaction` with foreign keys on.

```python
# Phase 11c probe: pairs and rejections on a feed transaction that goes away, and pending rows.
import shutil
import tempfile
from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select

import finances.db

failures = 0


def check(label: str, passed: bool) -> None:
    global failures
    failures += 0 if passed else 1
    print(f"{label} {'ok' if passed else 'FAILED'}")


folder = Path(tempfile.mkdtemp())
try:
    from finances.categorize.transfers import pair_transfers
    from finances.db.engine import get_engine, session_scope
    from finances.db.orm import FeedItemRow, TransactionRow, TransferPairRow, TransferRejectionRow
    from finances.db.repositories import create_account, delete_feed_transaction, reject_transfer

    url = f"sqlite:///{(folder / 'probe.db').as_posix()}"
    config = Config()
    config.set_main_option("script_location", str(Path(finances.db.__file__).parent / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = get_engine(url)

    def add(session, account, number, cents, pending=False):
        row = TransactionRow(
            account_id=account.id,
            posted_date=date(2026, 5, 3),
            amount_cents=cents,
            description="PROBE TRANSFER",
            source="feed",
            is_pending=pending,
            fingerprint=f"p{number}".ljust(64, "0"),
        )
        session.add(row)
        session.flush()
        session.add(FeedItemRow(account_id=account.id, feed_id=f"F{number}", transaction_id=row.id))
        session.flush()
        return row.id

    def count(session, row_class) -> int:
        return session.scalar(select(func.count()).select_from(row_class))

    with session_scope(engine) as session:
        one = create_account(session, "Probe One", "Probe Bank", "checking")
        two = create_account(session, "Probe Two", "Probe Bank", "savings")
        out_id, in_id = add(session, one, 1, -700), add(session, two, 2, 700)
        other_out, other_in = add(session, one, 3, -900), add(session, two, 4, 900)
        add(session, one, 5, -1100, pending=True)
        add(session, two, 6, 1100)
        reject_transfer(session, other_out, other_in)
        result = pair_transfers(session)
    check(
        "pair: one clear pair, pending and rejected rows left alone",
        (result.paired, result.waiting) == (1, 0),
    )
    try:
        with session_scope(engine) as session:
            delete_feed_transaction(session, in_id)
            delete_feed_transaction(session, other_out)
            left = (count(session, TransferPairRow), count(session, TransferRejectionRow))
        check("delete: a paired and a rejected feed transaction go with their rows", left == (0, 0))
    except Exception as error:  # noqa: BLE001
        check(f"delete: raised {type(error).__name__}", False)
    with session_scope(engine) as session:
        check("delete: the other side stays", session.get(TransactionRow, out_id) is not None)
    engine.dispose()
except Exception as error:  # noqa: BLE001
    check(f"probe: raised {type(error).__name__}: {error}", False)
finally:
    shutil.rmtree(folder, ignore_errors=True)
print(f"FAILURES {failures}")
```

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. `clear_pairs` checks only the out side.
2. `unpair_transfer` does not record a rejection.
3. `create_transfer_pair` checks "already in a transfer" before the accounts.
4. `reject_transfer` leaves a pair of the same two transactions in place.
5. `list_uncategorized` still lists paired transactions.

## 6. Out of scope

Each must be absent: any transfer template, route, or link on the web; a change to spending totals; a category set or cleared by pairing.
