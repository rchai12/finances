# Phase 47j: bounded SQLite lock waiting

## Goal

Set a configurable connection-level SQLite busy timeout, preserving transactions,
foreign keys and query-only enforcement. Existing audit-remediation-design47j
settles the policy; no new owner decision is needed. Architect decision2026-11-17:
FIN_DB_BUSY_TIMEOUT_MS is authoritative even if an explicit URL contains timeout.
Use native driver timeout, never replay application work or introduce retries.

## Read first

AGENTS.md, architecture, testing, phase-conventions, progress; design section47j,
47i review; config.py, db/engine.py, db/migrate.py, tests/conftest.py,
tests/unit/test_config.py and tests/integration/test_engine.py.

## Starting state

47i PASS at4828, no findings/deviations, review
67c8e7e5b01ebde11020c49f76c47a120ade0e31; implementation c0cb517 committed.
**N=4828; Sections: core.** Latest migration0026_proposal_findings.py unchanged.
get_engine(url=None, *, read_only=False) currently calls create_engine(url) with
SQLite driver's default timeout, enables foreign_keys in connect event and
query_only when requested. session_scope commits on success, rolls back on
Exception and always closes. Settings is cached; environment prefix FIN_.
Both tests/conftest.py and tests/unit/test_config.py have explicit env-key lists.
Both need the new key for deterministic isolation. Existing sections already put
new test names in core. No table, schema or migration change.

Commit finalized planning docs before coding. Fresh isolated clone of planning
HEAD, linked existing venv and local symlink exclusion, explicit clone/src
PYTHONPATH and checked finances.__file__. Record full baseline SHA and unchanged
spec/guide bytes. Preserve unrelated .vscode/settings.json; no packages installed.

## Scope

| Path | Change |
|---|---|
| src/finances/config.py | Add validated setting |
| src/finances/db/engine.py | Driver timeout on SQLite engine connections |
| tests/conftest.py | Add FIN_DB_BUSY_TIMEOUT_MS to _ENV_KEYS only |
| tests/unit/test_config.py | Add same key to its _ENV_KEYS only |
| tests/unit/test_db_timeout_settings.py | New: eight given cases |
| tests/integration/test_db_busy_timeout.py | New: seven given cases |
| tests/integration/test_db_lock_wait_behavior.py | New: coder tests |
| .env.example | Setting/default/range and operations doc reference |
| docs/database-locks.md | New operations guidance |
| docs/progress.md | Append phase entry |

## Out of scope

WAL, migration/schema changes, dialect/business SQL, retries, transaction replay,
connection lifetime/pool rewrites, restore concurrency fixes, new CLI options,
backends other than SQLite, exception translation, unrelated test/source cleanup.

## Dependencies

None new. SQLite/SQLAlchemy driver spike on this environment confirmed timeout
0.137 seconds reports137 through PRAGMA busy_timeout, including an explicit URL
with timeout=0 when connect_args supplies0.137. SQL is confined to existing
SQLite engine boundary or synthetic engine tests; no business query changes.

## Design

Settings field exactly `db_busy_timeout_ms: int`, default30000, inclusive0..120000,
using Pydantic Field(ge=0, le=120000). Environment key FIN_DB_BUSY_TIMEOUT_MS.
Use established Pydantic integer/environment parsing, not custom bool/string
policies. Invalid bounds raise normal ValidationError with field location;
no bespoke message. Existing settings behavior/cache stays unchanged.

get_engine signature and return remain unchanged. Obtain timeout through
get_settings() for every valid engine construction, including explicit URL and
read_only calls. Do not cache outside existing settings cache. Pass
`connect_args={"timeout": settings.db_busy_timeout_ms / 1000}` to create_engine.
This one conversion is elapsed time, not money. Apply to sqlite://, :memory:,
file URLs, configured URL, readonly and reopened/new pooled connections. Setting
wins over URL timeout query parameters. Configure before connections are opened;
no per-operation retries or busy-timeout statement needed at call sites.

Retain backend refusal before new timeout-specific work for unsupported backend,
parent creation, connect listener foreign_keys=ON and optional query_only=ON,
cursor closure and returned engine lifecycle. session_scope remains unchanged.
Do not enable check_same_thread bypass, change transaction isolation/autocommit,
WAL, pools or engine disposal. sqlite backend validation is preserved exactly.

Timeout0 means no lock wait;30000 means up to thirty seconds of SQLite busy
handling;120000 is maximum. This is not an operation deadline: connection setup,
queries and application work take additional time; some lock upgrades/deadlocks
may be refused immediately. SQLAlchemy OperationalError and rollback remain
existing behavior on lock exhaustion. No retry/replay after returning an error.
A failed transaction must commit no partial state, and subsequent transactions
must still work after holder release.

.env.example includes FIN_DB_BUSY_TIMEOUT_MS=30000 with0..120000ms explanation.
docs/database-locks.md explains configuration/restart or new process (settings
cache), scope/URL precedence, zero/default/max, native waiting versus whole
operation deadline, early refusal, rollback and no automatic retry. It must not
claim this makes restore safe during other processes or enables concurrent writes.
No instructions to expose DB/network, enable WAL or access real data for tests.

## Requirements

- R1: validated field/default/bounds/environment/cache isolation.
- R2: native driver timeout for all get_engine paths/new connections, setting precedence.
- R3: waiting writer succeeds after holder releases, once only, with exact stored result.
- R4: exhausted/zero timeout fails boundedly and rolls back all work; no replay.
- R5: foreign-key/query-only/backend/lifetime/session behavior preserved.
- R6: accurate environment/operations docs and bounded scope.

## Given diff to earlier tests

No behavior pin changes. Two exact isolation edits only: append
"FIN_DB_BUSY_TIMEOUT_MS" to _ENV_KEYS tuples in tests/conftest.py and
 tests/unit/test_config.py. No other statements/fixtures/assertions in either
file may change. No other existing tests change. These are implementation steps,
not given tests requiring a broader rewrite.

## Given tests

Fifteen cases in two files; copy unchanged.

`tests/unit/test_db_timeout_settings.py`

```python
import pytest
from pydantic import ValidationError

from finances.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FIN_DB_BUSY_TIMEOUT_MS", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default():
    assert Settings(_env_file=None).db_busy_timeout_ms == 30000


@pytest.mark.parametrize("value", [0, 17, 120000])
def test_valid_bounds(value):
    assert Settings(_env_file=None, db_busy_timeout_ms=value).db_busy_timeout_ms == value


@pytest.mark.parametrize("value", [-1, 120001])
def test_invalid_bounds(value):
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, db_busy_timeout_ms=value)
    assert caught.value.errors()[0]["loc"] == ("db_busy_timeout_ms",)


def test_environment(monkeypatch):
    monkeypatch.setenv("FIN_DB_BUSY_TIMEOUT_MS", "271")
    get_settings.cache_clear()
    assert get_settings().db_busy_timeout_ms == 271


def test_shared_fixture_clears_timeout_environment():
    from tests import conftest

    assert "FIN_DB_BUSY_TIMEOUT_MS" in conftest._ENV_KEYS
```

`tests/integration/test_db_busy_timeout.py`

```python
import pytest

from finances.config import get_settings
from finances.db.engine import get_engine


@pytest.mark.parametrize("kind", ["memory", "file", "configured"])
@pytest.mark.parametrize("read_only", [False, True], ids=["write", "read"])
def test_every_connection_timeout(tmp_settings, monkeypatch, tmp_path, kind, read_only):
    monkeypatch.setenv("FIN_DB_BUSY_TIMEOUT_MS", "137")
    get_settings.cache_clear()
    url = {
        "memory": "sqlite:///:memory:",
        "file": "sqlite:///" + (tmp_path / "new.db").as_posix(),
        "configured": None,
    }[kind]
    engine = get_engine(url, read_only=read_only)
    try:
        with engine.connect() as first, engine.connect() as second:
            for connection in (first, second):
                assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 137
                assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
                assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == int(
                    read_only
                )
        engine.dispose()
        with engine.connect() as fresh:
            assert fresh.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 137
    finally:
        engine.dispose()


def test_setting_overrides_url_timeout(tmp_settings, monkeypatch):
    monkeypatch.setenv("FIN_DB_BUSY_TIMEOUT_MS", "211")
    get_settings.cache_clear()
    engine = get_engine("sqlite:///:memory:?timeout=0")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 211
    finally:
        engine.dispose()
```

Fresh fail47j at approved predecessor: exactly15 fail for missing setting,
ignored bounds/env isolation, or old driver5000/URL0ms rather than configured
values. Collection and lint/format pass. These PRAGMA inspections need no schema;
actual app-content concurrency tests below use migrated synthetic databases.
No product stubs, reference implementation, full-suite run or default30s waits
were used by architect.

## Tests to write

In tests/integration/test_db_lock_wait_behavior.py (core):

- File-backed DB migrated through upgrade_to_head; seed synthetic account(s).
  Hold a writer lock in connection A. Independent engine/connection B in a worker
  thread attempts a distinct synthetic write with configured2000ms timeout.
  Use Events/barriers and a SQLAlchemy pre-execute or SQLite trace marker so
  parent knows the worker is issuing its write; assert it remains pending for a
  bounded observation window (e.g. done.wait(0.1) false), then release A before
  configured timeout. Join within generous5s deadline, surface worker exceptions,
  assert one committed B result and no duplicated side effects/replayed work.
- Held writer never releases until worker exits: timeout50ms (not default30s).
  B transaction must raise SQLAlchemy OperationalError wrapping sqlite3.OperationalError
  with SQLITE_BUSY primary result code, under generous5s hard completion bound.
  Before its blocked write include a safe read and staged ORM rows; after error
  session_scope must roll back, no proposed changes appear. After releasing A,
  a new transaction writes successfully. Do not require exact elapsed milliseconds.
- Timeout0 with held lock refuses without waiting for release, same bounded
  cleanup/error path. A commits its intended data; B leaves no partial rows.
- On fresh/reopened connections, timeout0/default30000/max120000 are reflected
  in PRAGMA without sleeping. Cover sqlite:// as well as :memory:, explicit
  file URL and get_engine() default; cache-clear then changed value uses new engine.
- Foreign key violation still raises IntegrityError, read_only engine refuses
  DML and commits no change, non-SQLite refusal message unchanged, relative-path
  parent creation unchanged. Existing engine tests remain intact.
- Environment isolation: poison FIN_DB_BUSY_TIMEOUT_MS before directly requesting
  tmp_settings (request.getfixturevalue, not fixture argument created earlier);
  assert fixture clears it and default30000 is restored. Avoid real .env files;
  explicit temporary .env override may also be tested with known synthetic value.
- Engine API spying may verify create_engine receives seconds, including subsecond
 137ms, but PRAGMA and real contention assertions remain authoritative. Assert no
  per-operation retry wrappers, pragma added to business services or settings
  lifetime changes. Unit tests for other config fields stay unchanged.

Events, futures and connections cleaned in finally even after assertion failure.
Each worker opens/uses/closes its own connection; never pass a live Session across
threads. Synchronize with events and generous deadlines; no sleeps to 'hope' a
lock was acquired, no global seeds, real data, default30s waits or elapsed-time
performance promises. Compare stored synthetic DB contents after transactions.
No synthetic financial content outside tests/fixtures is written to repo; pytest
tmp_path databases are temporary. Mutations/lock SQL stay in disposable tests.

R1 settings/isolation cases; R2 given per-connection/URL and boundary cases;
R3/R4 event-coordinated file contention and state assertions; R5 retained engine
and new preservation cases; R6 operations review/scope audit. Cover all changed
module lines/branches with meaningful assertions, not assertions on coverage.

## Rules for this phase

All privacy/money/layering rules apply; int cents, no network/Keychain/real
DB/statements/aggregator. No migration/dependency/retry/WAL or new coverage pragma.
No business service changes. Coder/verifier do not commit/push. No full reference
feature implementation in architect scratch.

## Acceptance

Sequentially in isolated checkout with clone PYTHONPATH:

1. `.venv/bin/python scripts/check.py --first core --workers 4`: final
   All checks passed.; all sections zero failed/skipped, no xfails/warnings
   summary, overall/critical gates; at least **4843** passes (4828+15) plus coder cases.
2. Immediately `.venv/bin/python -m coverage report --include="*/finances/config.py,*/finances/db/engine.py" --fail-under=100`:
   both modules and TOTAL100%, zero missing lines/branches/partials.
3. `.venv/bin/python -m pytest tests/unit/test_db_timeout_settings.py tests/integration/test_db_busy_timeout.py --no-cov`:
   exactly15 passed.
4. `.venv/bin/python -m pytest tests/integration/test_db_lock_wait_behavior.py --no-cov`:
   all coder cases pass; at least one contention success, held-lock refusal,
   zero-wait refusal and preserved DB state case. Report actual case ids/counts.
5. Scope/given equality, two precise env-list changes only in earlier tests,
   session_scope unchanged, no dependency/schema/section/source changes elsewhere.
   Docs satisfy all operational limits. Inspect for retry/replay, WAL/pool or
   check_same_thread/isolation changes: none. Existing engine/error tests pass.

No separate probe: driver-observed PRAGMA tests plus independent verifier's real
lock/state tests provide direct evidence, without duplicating contention logic.

## Report

Standard progress headed `## Phase 47j: bounded SQLite lock waiting (YYYY-MM-DD)`.
N4828, given15, full planning SHA, clone/import provenance, exact contention tests,
section table, last ten lines and all other gates. New public setting field named;
functions retain signatures. Record native wait scope, no retries/WAL, limits and
any deviations/follow-ups. Phase47 audit remediation ends here; deferred findings
remain conditional, not automatically scheduled implementations.
