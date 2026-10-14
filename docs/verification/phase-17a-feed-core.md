# Verify Phase 17a: the feed core

Spec: `docs/phases/phase-17a-feed-core.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote one migration, one domain class, two ORM classes with a converter, nine repository functions, and a new package `src/finances/sync/` with the feed types and `apply_feed`. Two test files were given; the coder wrote two more.

Judge the code by what it stores and returns and by the rules, never by how it is written. These are all correct and must not be reported:

- any private helpers and constants in `sync/service.py` and `db/repositories.py`;
- looking up the stored rows once for the whole feed or once per transaction;
- any SQLAlchemy 2.0 query that gives the specified result;
- checking a feed in one pass or several, as long as `account not found` comes first and nothing is written before the last check.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it; it is `1038` when Phase 6 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 61 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/integration/test_migration_0003.py tests/integration/test_feed_service.py --no-cov` | exactly `61 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with every module of `finances.sync`, `finances.db`, and `finances.domain` at 100% |
| `.venv/bin/python -c "from finances.db.migrate import head_revision; print(head_revision())"` | `0003` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov=finances.db --cov=finances.domain --cov-branch --cov-report=term-missing --cov-fail-under=100`

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/db/orm.py
 M src/finances/db/repositories.py
 M src/finances/domain/models.py
?? src/finances/db/migrations/versions/0003_feed.py
?? src/finances/sync/
?? tests/integration/test_feed_repositories.py
?? tests/integration/test_feed_service.py
?? tests/integration/test_migration_0003.py
?? tests/unit/test_feed_models.py
```

- `src/finances/sync/` holds exactly `__init__.py` (a docstring and nothing else), `feed.py`, and `service.py`.
- The two given test files are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- src/finances/domain/models.py src/finances/db/orm.py src/finances/db/repositories.py` only adds lines, apart from import lines that gained a name. `Transaction`, `NewTransaction`, `TransactionRow`, `insert_transactions`, and `add_balance_snapshot` are unchanged.
- `git diff HEAD --stat -- src/finances/db/migrations/versions/0001_accounts.py src/finances/db/migrations/versions/0002_statements.py src/finances/db/migrations/env.py src/finances/ingest src/finances/cli src/finances/config.py tests/conftest.py pyproject.toml` is empty, and no existing test file is changed.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | the migration | gate 4 (the given migration tests); probe script | every line starting `migration:` |
| R1 | the file | read `0003_feed.py` | `revision = "0003"`, `down_revision = "0002"`; no import from `finances`; no `server_default`; every constraint named; `downgrade` drops the two tables only |
| R2 to R5 | classes | probe script | every line starting `shape:` |
| R6 | fingerprint | probe script | `shape: the fingerprint` |
| R7, R8, R9, R12, R13, R15 | repository edges | probe script | every line starting `repositories:` |
| R9 | chunks | read `find_feed_transactions` | the ids are asked for in chunks, as `existing_fingerprints` does |
| R10, R11, R14 | repository writes | probe script | every line starting `story` |
| R16 | refusals | probe script | every line starting `refused:` |
| R17 | descriptions | probe script | `story 1: stored as provisional rows with collapsed text` and the two lines starting `limits:` |
| R18 | insert, update, replace, remove | probe script | every line starting `story 1` and `story 2`, plus every line starting `posting:` and `accounts:` |
| R18 step 3 | statement rows | probe script | every line starting `audited:` |
| R19 | posted total | probe script | `story 1: posted total leaves pending rows out; no drift on a first balance` and `posting: rows that did not come from the feed are not in the posted total` |
| R20 | balance snapshot | probe script | `story 2: the newest balance is the feed's` and `story 5` |
| R21 | drift | probe script | `story 2: drift is zero when the balance follows the posted rows`, and the lines starting `story 3`, `story 4`, `story 5` |
| R22 | the pull record | probe script | the count lines of `story 1` and `story 2` |
| R23 | no commit | read `sync/service.py` | no `commit(` and no `rollback(` |
| messages | constant text | read every `raise` in `sync/` and in the new repository functions | only the seven messages in R16 and the one in R11; none is an f-string |
| layering | service uses repositories only | read the imports of `sync/service.py` | nothing from `finances.db.orm`, no `select`, no ORM class |

Run each of these searches. Each must print nothing.

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/sync`

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances/sync`

`git grep -n --untracked -E "finances\.(ingest|cli)" -- src/finances/sync src/finances/db src/finances/domain`

## 4. Independent probes

The given tests fix `apply_feed` with small feeds. This script tells one longer story on a fresh database (four pulls on a card account, with holds that post under new ids, a removed hold, a pull without a balance, and a balance that drifts), then checks the rules one at a time on further fresh databases: rows confirmed by a statement, two accounts with the same feed id, a pending row that posts, every refusal, and the edges of the repository functions. None of its ids, names, or amounts are in the given tests or the spec.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Each database it uses is a file in a temporary directory that it removes. Every line must end in `ok`; the last line must be `FAILURES 0`. A line that says a section `ran to the end (stopped by ...)` and ends in `FAIL` means the code raised where it should not have; report it with the exception named on that line.

```python
import dataclasses
import hashlib
import tempfile
from datetime import date
from pathlib import Path

from sqlalchemy import inspect, select

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def outcome(function, *args, **kwargs):
    """Return the value, or the exception type name and message."""
    try:
        return function(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, str(exc))


def section(name, function):
    try:
        function()
    except Exception as exc:  # noqa: BLE001
        check(f"{name}: ran to the end (stopped by {type(exc).__name__}: {exc})", False)


def june(number):
    return date(2027, 6, number)


def run(body):
    """Call body(session) on a new migrated database with three accounts, then throw it away."""
    from finances.db.engine import get_engine, session_scope
    from finances.db.migrate import upgrade_to_head
    from finances.db.repositories import create_account

    with tempfile.TemporaryDirectory() as folder:
        url = f"sqlite:///{(Path(folder) / 'probe.db').as_posix()}"
        upgrade_to_head(url)
        engine = get_engine(url)
        try:
            with session_scope(engine) as session:
                create_account(session, "Probe Card", "Probe Bank", "credit_card", last4="8080")
                create_account(session, "Probe Checking", "Probe Bank", "checking", last4="9191")
                create_account(session, "Probe Savings", "Probe Bank", "savings")
                body(session)
        finally:
            engine.dispose()


def ledger(session, account_id):
    from finances.db.orm import FeedItemRow, TransactionRow

    stmt = (
        select(TransactionRow, FeedItemRow.feed_id)
        .outerjoin(FeedItemRow, FeedItemRow.transaction_id == TransactionRow.id)
        .where(TransactionRow.account_id == account_id)
        .order_by(TransactionRow.id)
    )
    return [(row.id, feed_id, row.posted_date, row.amount_cents, row.description, row.is_pending, row.source) for row, feed_id in session.execute(stmt).all()]


def shape_checks():
    from finances.db.orm import Base, FeedItemRow, FeedPullRow
    from finances.domain.models import FeedPull
    from finances.sync import feed as feed_module
    from finances.sync import service as service_module
    from finances.sync.feed import AccountFeed, FeedError, FeedTransaction, feed_fingerprint

    names = [field.name for field in dataclasses.fields(FeedPull)]
    check("shape: FeedPull fields in order", names == ["id", "account_id", "inserted", "updated", "removed", "unchanged", "feed_total_cents", "balance_cents", "balance_date", "drift_cents", "pulled_at"])
    check("shape: FeedPull is frozen", FeedPull.__dataclass_params__.frozen)
    names = [field.name for field in dataclasses.fields(FeedTransaction)]
    check("shape: FeedTransaction fields in order", names == ["feed_id", "posted_date", "amount_cents", "description", "is_pending", "transaction_date", "card_last4", "replaces_feed_id"])
    item = FeedTransaction("z", june(1), -1, "PROBE")
    check("shape: FeedTransaction defaults", (item.is_pending, item.transaction_date, item.card_last4, item.replaces_feed_id) == (False, None, None, None))
    check("shape: FeedTransaction and AccountFeed are frozen", FeedTransaction.__dataclass_params__.frozen and AccountFeed.__dataclass_params__.frozen)
    empty, other = AccountFeed(), AccountFeed()
    check("shape: AccountFeed defaults, and its lists are not shared", (empty.transactions, empty.removed_feed_ids, empty.balance_cents, empty.balance_date) == ([], [], None, None) and empty.transactions is not other.transactions)
    check("shape: FeedError is an Exception and not a ValueError", issubclass(FeedError, Exception) and not issubclass(FeedError, ValueError))
    check("shape: the fingerprint", feed_fingerprint(42, "probe-id") == hashlib.sha256(b"feed\n42\nprobe-id").hexdigest())
    check("shape: tables of the two ORM classes", (FeedItemRow.__tablename__, FeedPullRow.__tablename__) == ("feed_items", "feed_pulls") and {"feed_items", "feed_pulls"} <= set(Base.metadata.tables))
    for module, expected in ((feed_module, ["AccountFeed", "FeedError", "FeedTransaction", "feed_fingerprint"]), (service_module, ["apply_feed"])):
        public = sorted(name for name, value in vars(module).items() if getattr(value, "__module__", "") == module.__name__ and not name.startswith("_"))
        check(f"shape: {module.__name__} public names {public}", public == expected)


def migration_checks():
    from finances.db.engine import get_engine
    from finances.db.migrate import head_revision, upgrade_to_head
    from finances.db.orm import Base

    with tempfile.TemporaryDirectory() as folder:
        url = f"sqlite:///{(Path(folder) / 'probe.db').as_posix()}"
        check("migration: the newest revision is 0003 or later", head_revision() >= "0003" and upgrade_to_head(url) == head_revision())
        engine = get_engine(url)
        try:
            found = inspect(engine)
            for table in ("feed_items", "feed_pulls"):
                declared = Base.metadata.tables[table]
                columns = found.get_columns(table)
                check(f"migration: {table} has the columns of its ORM class", [(c["name"], c["nullable"]) for c in columns] == [(c.name, c.nullable) for c in declared.columns])
            uniques = sorted(tuple(u["column_names"]) for u in found.get_unique_constraints("feed_items"))
            check("migration: feed_items is unique on (account_id, feed_id) and on transaction_id", uniques == [("account_id", "feed_id"), ("transaction_id",)])
        finally:
            engine.dispose()


def story_checks():
    from finances.db.repositories import latest_balance, list_transactions
    from finances.sync.feed import AccountFeed, FeedTransaction, feed_fingerprint
    from finances.sync.service import apply_feed

    def body(session):
        first = apply_feed(session, 1, AccountFeed(
            [FeedTransaction("t-100", june(1), -1875, "PROBE   BAKERY  #7", card_last4="8080", transaction_date=date(2027, 5, 31)),
             FeedTransaction("t-101", june(2), -5230, "PROBE FUEL"),
             FeedTransaction("hold-1", june(2), -10000, "PROBE HOTEL HOLD", is_pending=True),
             FeedTransaction("hold-2", june(2), -2500, "PROBE CINEMA", is_pending=True)],
            [], -57105, june(2)))
        check("story 1: four inserted", (first.inserted, first.updated, first.removed, first.unchanged) == (4, 0, 0, 0))
        check("story 1: posted total leaves pending rows out; no drift on a first balance", (first.feed_total_cents, first.drift_cents) == (-7105, None))
        rows = ledger(session, 1)
        check("story 1: stored as provisional rows with collapsed text", [(r[1], r[4], r[5], r[6]) for r in rows] == [("t-100", "PROBE BAKERY #7", False, "aggregator"), ("t-101", "PROBE FUEL", False, "aggregator"), ("hold-1", "PROBE HOTEL HOLD", True, "aggregator"), ("hold-2", "PROBE CINEMA", True, "aggregator")])
        stored = list_transactions(session, 1)
        check("story 1: fingerprints, and nothing a statement would add", sorted(t.fingerprint for t in stored) == sorted(feed_fingerprint(1, name) for name in ("t-100", "t-101", "hold-1", "hold-2")) and all((t.statement_id, t.section, t.cardholder, t.external_id) == (None, None, None, None) for t in stored))

        second = apply_feed(session, 1, AccountFeed(
            [FeedTransaction("t-100", june(1), -1875, "PROBE BAKERY #7", card_last4="8080", transaction_date=date(2027, 5, 31)),
             FeedTransaction("t-101", june(3), -5320, "PROBE FUEL 0042"),
             FeedTransaction("t-102", june(4), -18840, "PROBE HOTEL", replaces_feed_id="hold-1"),
             FeedTransaction("t-103", june(4), 40000, "PROBE PAYMENT")],
            ["hold-1", "hold-2", "never-delivered"], -36035, june(4)))
        check("story 2: one inserted, two updated, one removed, one unchanged", (second.inserted, second.updated, second.removed, second.unchanged) == (1, 2, 1, 1))
        rows = ledger(session, 1)
        check("story 2: the hold became the posted row under the same stored id", [(r[0], r[1], r[3], r[5]) for r in rows] == [(1, "t-100", -1875, False), (2, "t-101", -5320, False), (3, "t-102", -18840, False), (5, "t-103", 40000, False)])
        check("story 2: the replaced row carries the fingerprint of its new id", [x.fingerprint for x in list_transactions(session, 1) if x.id == 3] == [feed_fingerprint(1, "t-102")])
        check("story 2: drift is zero when the balance follows the posted rows", (second.feed_total_cents, second.drift_cents) == (13965, 0))
        balance = latest_balance(session, 1)
        check("story 2: the newest balance is the feed's", (balance.as_of_date, balance.balance_cents, balance.source.value) == (june(4), -36035, "aggregator"))

        third = apply_feed(session, 1, AccountFeed([FeedTransaction("t-104", june(5), -999, "PROBE STREAMING")], []))
        check("story 3: a pull without a balance has no drift", (third.balance_cents, third.balance_date, third.drift_cents, third.feed_total_cents) == (None, None, None, 12966))
        fourth = apply_feed(session, 1, AccountFeed([], [], -37395, june(6)))
        check("story 4: a missing transaction shows as drift against the last balance", (fourth.inserted, fourth.unchanged, fourth.drift_cents) == (0, 0, -361))
        fifth = apply_feed(session, 1, AccountFeed([], [], -37295, june(6)))
        check("story 5: drift is measured from the pull before, and the day's balance is replaced", fifth.drift_cents == 100 and latest_balance(session, 1).balance_cents == -37295)

    run(body)


def rule_checks():
    from finances.db.orm import TransactionRow
    from finances.sync.feed import AccountFeed, FeedTransaction
    from finances.sync.service import apply_feed

    def audited(session):
        apply_feed(session, 2, AccountFeed([FeedTransaction("k-1", june(1), 250000, "PROBE PAYROLL"), FeedTransaction("k-2", june(2), -120000, "PROBE RENT")], [], 130000, june(2)))
        for row in session.scalars(select(TransactionRow)).all():
            row.source = "statement"
        session.flush()
        before = ledger(session, 2)
        pull = apply_feed(session, 2, AccountFeed(
            [FeedTransaction("k-1", june(9), 1, "PROBE CHANGED"), FeedTransaction("k-3", june(3), -500, "PROBE NEW", replaces_feed_id="k-2")], ["k-2"], 129500, june(3)))
        check("audited: statement rows are neither changed, replaced, nor removed", ledger(session, 2)[:2] == before)
        check("audited: counts", (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (1, 0, 0, 1))
        check("audited: they still count toward the posted total", (pull.feed_total_cents, pull.drift_cents) == (129500, 0))

    def separate(session):
        apply_feed(session, 1, AccountFeed([FeedTransaction("shared", june(1), -100, "PROBE ONE")], [], -100, june(1)))
        pull = apply_feed(session, 2, AccountFeed([FeedTransaction("shared", june(1), 900, "PROBE TWO")], [], 900, june(1)))
        check("accounts: the same feed id in two accounts is two rows", (pull.inserted, pull.drift_cents) == (1, None) and len(ledger(session, 1)) == 1 and len(ledger(session, 2)) == 1)
        apply_feed(session, 2, AccountFeed([], ["shared"]))
        check("accounts: a removal touches only its own account", len(ledger(session, 1)) == 1 and ledger(session, 2) == [])
        check("accounts: an account without a pull has none", outcome(apply_feed, session, 3, AccountFeed()).drift_cents is None)

    def posting(session):
        from finances.db.repositories import insert_transactions
        from finances.domain.models import DataSource, NewTransaction

        insert_transactions(session, [NewTransaction(3, None, june(1), None, 777700, "PROBE OPENING DEPOSIT", "deposits", None, None, None, DataSource.STATEMENT, False, "e" * 64)])
        first = apply_feed(session, 3, AccountFeed([FeedTransaction("w-1", june(2), -4000, "PROBE WITHDRAWAL", is_pending=True)], [], 777700, june(2)))
        check("posting: rows that did not come from the feed are not in the posted total", (first.inserted, first.feed_total_cents) == (1, 0))
        second = apply_feed(session, 3, AccountFeed([FeedTransaction("w-1", june(2), -4000, "PROBE WITHDRAWAL")], [], 773700, june(2)))
        check("posting: a pending row that posts unchanged under its own id is an update", (second.updated, second.unchanged, second.feed_total_cents, second.drift_cents) == (1, 0, -4000, 0))
        check("posting: the statement row is untouched", ledger(session, 3)[0][1:5] == (None, june(1), 777700, "PROBE OPENING DEPOSIT"))

    run(audited)
    run(separate)
    run(posting)


def refusal_checks():
    from finances.db.orm import BalanceSnapshotRow, FeedPullRow
    from finances.sync.feed import AccountFeed, FeedTransaction
    from finances.sync.service import apply_feed

    good = FeedTransaction("ok-1", june(1), -100, "PROBE GOOD")
    cases = [
        ("an empty id", AccountFeed([good, FeedTransaction("", june(1), -1, "PROBE")]), "feed has an unusable transaction id"),
        ("an id with a trailing space", AccountFeed([good, FeedTransaction("x ", june(1), -1, "PROBE")]), "feed has an unusable transaction id"),
        ("an id of 101 characters", AccountFeed([good, FeedTransaction("q" * 101, june(1), -1, "PROBE")]), "feed has an unusable transaction id"),
        ("an unusable replaced id", AccountFeed([good, FeedTransaction("x", june(1), -1, "PROBE", replaces_feed_id=" ")]), "feed has an unusable transaction id"),
        ("an unusable removed id", AccountFeed([good], [""]), "feed has an unusable transaction id"),
        ("a blank description", AccountFeed([good, FeedTransaction("x", june(1), -1, "   ")]), "feed has an empty description"),
        ("five card digits", AccountFeed([good, FeedTransaction("x", june(1), -1, "PROBE", card_last4="80808")]), "feed has unusable card digits"),
        ("the same id twice", AccountFeed([good, FeedTransaction("ok-1", june(2), -2, "PROBE")]), "feed has a duplicate transaction id"),
        ("an id delivered and removed", AccountFeed([good], ["ok-1"]), "feed removes a transaction it also delivers"),
        ("a balance without a date", AccountFeed([good], [], -5, None), "feed balance and its date must come together"),
        ("a date without a balance", AccountFeed([good], [], None, june(1)), "feed balance and its date must come together"),
    ]

    def body(session):
        for label, bad, message in cases:
            got = outcome(apply_feed, session, 1, bad)
            check(f"refused: {label}", got == ("FeedError", message))
        check("refused: an unknown account", outcome(apply_feed, session, 404, AccountFeed([good])) == ("FeedError", "account not found"))
        check("refused: nothing was written by any of them", ledger(session, 1) == [] and session.scalars(select(FeedPullRow)).all() == [] and session.scalars(select(BalanceSnapshotRow)).all() == [])
        long_text = "PROBE " + "W" * 600
        pull = outcome(apply_feed, session, 1, AccountFeed([FeedTransaction("q" * 100, june(1), -1, long_text)]))
        check("limits: an id of 100 characters and a description cut to 500", getattr(pull, "inserted", None) == 1 and [len(r[4]) for r in ledger(session, 1)] == [500])
        again = outcome(apply_feed, session, 1, AccountFeed([FeedTransaction("q" * 100, june(1), -1, long_text)]))
        check("limits: the cut description is unchanged on the next pull", getattr(again, "unchanged", None) == 1)

    run(body)


def repository_checks():
    from finances.db import repositories
    from finances.domain.models import DataSource

    def body(session):
        check("repositories: get_account", repositories.get_account(session, 2).name == "Probe Checking" and repositories.get_account(session, 404) is None)
        first = repositories.set_balance_snapshot(session, 3, june(1), 100, DataSource.AGGREGATOR)
        second = repositories.set_balance_snapshot(session, 3, june(1), 250, DataSource.AGGREGATOR)
        other = repositories.set_balance_snapshot(session, 3, june(1), 300, DataSource.STATEMENT)
        check("repositories: set_balance_snapshot replaces per account, date, and source", (first.id, second.id, second.balance_cents) == (1, 1, 250) and other.id == 2)
        check("repositories: no feed pull yet", repositories.latest_feed_pull(session, 3) is None and repositories.latest_feed_pull(session, 3, with_balance=True) is None)
        check("repositories: posted total of an account without feed rows", repositories.feed_posted_total(session, 3) == 0)
        check("repositories: no feed transactions found for unknown ids", repositories.find_feed_transactions(session, 3, ["a", "b"]) == {} and repositories.find_feed_transactions(session, 3, []) == {})
        check("repositories: deleting a row that is not from the feed", repositories.delete_feed_transaction(session, 12345) is False)

    run(body)


section("shape", shape_checks)
section("migration", migration_checks)
section("story", story_checks)
section("rules", rule_checks)
section("refusals", refusal_checks)
section("repositories", repository_checks)
print("FAILURES", failures)
```

## 5. The coder's tests

Read `tests/unit/test_feed_models.py` and `tests/integration/test_feed_repositories.py`.

- **Coverage of requirements.** For each of R1 to R23, name a test, given or the coder's, that would fail if the requirement were broken. A requirement with no such test is a finding. The coder's final message lists its own mapping; check it, do not trust it.
- **Repository tests go through the functions.** Each of R7 to R15 has a test that calls the function and compares what it returns, and where it writes, a second check that reads the database back (through another repository function, or a direct query). A repository function that is only reached through `apply_feed` is a finding.
- **Assertions are exact.** Values are compared with `==` against literals. No `assert True`, no `pytest.raises(Exception)`, no `skip` or `xfail`, and no expected value produced by calling the code under test.
- **Synthetic data.** Invented merchants, ids, and amounts.
- **Spot checks.** For each change below, say which test, given or the coder's, would fail, by reading the test. If none would, that is a finding.
  1. `set_balance_snapshot` adds a second row for the same account, date, and source.
  2. `find_feed_transactions` returns rows of another account that use the same feed id.
  3. `update_feed_transaction` also changes `source` or `section`.
  4. `update_feed_transaction` on a statement row without a feed id silently does nothing.
  5. `delete_feed_transaction` deletes a statement row that has no feed id.
  6. `feed_posted_total` returns `None` for an account with no rows.
  7. `feed_posted_total` leaves out a row once its `source` is `statement`.
  8. `latest_feed_pull(..., with_balance=True)` returns the newest pull even when it has no balance.
  9. `to_feed_pull` returns a `pulled_at` without a time zone.

## 6. Project rules that apply to this phase

- **Money.** Integer cents throughout; the first search in section 3 finds no `float`.
- **Privacy.** No network library is imported (second search). Nothing is logged, and no exception carries feed content.
- **Layering.** `sync` does not import `ingest` or `cli`; `db` and `domain` do not import `sync` (third search).
- **Migrations.** `0001` and `0002` are unchanged (section 2), and the schema change ships as `0003`.
- **Test data.** No file was added under `tests/fixtures/`.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- An HTTP client, a provider's name or URL, a token, `keyring`, or a new dependency in `pyproject.toml`.
- A `fin sync` command or any change under `src/finances/cli/`.
- A new column on `transactions`, or any change to `Transaction`, `NewTransaction`, or `TransactionRow`.
- Code that matches feed rows to statement lines, or that sets a row's `source` to `statement`.
- A mapping between a provider's accounts and ours.
- Logging of pulls, scheduling, or retries.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 17a: the feed core (YYYY-MM-DD)` with a real date. "Built" gives N and the passed count. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 to Part 4 / tests>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code.
