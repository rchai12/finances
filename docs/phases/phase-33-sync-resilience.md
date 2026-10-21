# Phase 33: sync resilience

## Goal

The daily SimpleFIN sync failed four days running after 14 October 2026: once "aggregator answered with an error", three times "could not reach the aggregator", most likely because the Mac woke at 07:00 before its network was back. One attempt a day loses the day to one blip, and the log did not say when each run happened. After this phase:

- `fin sync run` (what the daily job runs) **tries again** when SimpleFIN cannot be reached at all: after 30, then 60, then 120 seconds, saying so each time. An answer with an error status, and revoked access, are not tried again (they would not change within minutes). The web's **Sync now** does not wait.
- Every sync, from the terminal or the web, **remembers each link's last failure** (when, and the message), and a good sync of that link clears it. `fin sync status`, `fin health`, and the dashboard show it.
- The scheduled jobs write a **start line with the local date and time** before each run.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/sync/runner.py` (`run_links`, `LinkRun`), `src/finances/sync/simplefin.py` (`SyncError`; a critical module), `src/finances/sync/transport.py`
- `src/finances/cli/sync.py` (`run_command`, `status_command`), `src/finances/views/sync.py`
- `src/finances/domain/health.py`, `src/finances/analysis/health.py`
- `scripts/install-sync-schedule.sh`, `scripts/install-backup-schedule.sh`

## Starting state

N is `2911` when Phase 32 is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/sync/simplefin.py` | new: `AggregatorUnreachable` (R1) |
| `src/finances/sync/transport.py` | raises `AggregatorUnreachable` (R1) |
| `src/finances/db/migrations/versions/0011_sync_failures.py` | new: given |
| `src/finances/db/orm.py`, `src/finances/domain/models.py` | new: `SyncFailureRow`, `SyncFailure` (R2) |
| `src/finances/db/repositories.py` | new: `record_sync_failure`, `clear_sync_failure`, `list_sync_failures` (R2) |
| `src/finances/sync/runner.py` | `RETRY_WAITS`; `run_links` retries and remembers failures (R3) |
| `src/finances/cli/sync.py` | `fin sync run` retries (R4); `fin sync status` shows failures (R5) |
| `src/finances/views/sync.py` | new: `failure_lines` (R5) |
| `src/finances/domain/health.py`, `src/finances/analysis/health.py` | failures become `sync` problems (R6) |
| `scripts/install-sync-schedule.sh`, `scripts/install-backup-schedule.sh` | replaced: given (R7) |
| `tests/integration/test_sync_resilience.py`, `tests/integration/test_migration_0011.py`, `tests/unit/test_health_sync_failures.py`, `tests/e2e/test_cli_sync_resilience.py` | new: given |
| `tests/integration/test_sync_resilience_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Syncing more than once a day, notifications, retrying answers with an error status.
- A failure line on the web's SimpleFIN page (the dashboard shows it through health); changing what a good sync does.

## Dependencies

None new. Migration `0011` (given).

## Design

```python
# src/finances/sync/simplefin.py
class AggregatorUnreachable(SyncError):
    """SimpleFIN could not be reached at all: no answer came back."""

# src/finances/domain/models.py
@dataclass(frozen=True)
class SyncFailure:
    link: str
    failed_at: datetime  # UTC
    message: str

# src/finances/db/repositories.py
def record_sync_failure(session: Session, link: str, failed_at: datetime, message: str) -> None: ...
def clear_sync_failure(session: Session, link: str) -> None: ...
def list_sync_failures(session: Session) -> list[SyncFailure]: ...  # by link

# src/finances/sync/runner.py
RETRY_WAITS = (30, 60, 120)

def run_links(
    engine: Engine,
    links: list[str],
    *,
    today: date,
    transport: Transport,
    days: int = SYNC_DAYS,
    retry_waits: Sequence[int] = (),
    sleep: Callable[[float], None] | None = None,       # None: time.sleep, looked up when waiting
    on_retry: Callable[[str, int], None] | None = None, # (link, seconds) before each wait
    now: Callable[[], datetime] | None = None,          # None: the current UTC time
) -> list[LinkRun]: ...

# src/finances/views/sync.py
def failure_lines(failures: list[SyncFailure]) -> list[str]: ...

# src/finances/domain/health.py: one keyword parameter added, with a default
def health_problems(accounts, newest_backup, as_of, *, failures: Iterable[SyncFailure] = ()) -> list[Problem]: ...
```

Texts, in full:

| Where | Text |
|---|---|
| `fin sync run`, before each wait (stderr) | `link LINK: could not reach the aggregator; trying again in N seconds.` |
| `fin sync status`, after the table, one per failure | `Last failure of link LINK: YYYY-MM-DD HH:MM UTC: MESSAGE.` |
| `fin health`, a `sync` problem with an empty account | `The last sync of link LINK failed on YYYY-MM-DD: MESSAGE.` (the UTC date), with Phase 25's sync action |

## Requirements

- **R1.** `AggregatorUnreachable` is a `SyncError`. `urllib_transport` raises it, with the same message `could not reach the aggregator`, where it raised `SyncError` for an `OSError`. `simplefin.py` stays fully covered.
- **R2.** The given migration, and `SyncFailureRow` matching it. `record_sync_failure` stores the link's failure, replacing an earlier one of the same link, with the message cut to 200 characters (`fit`). `clear_sync_failure` deletes the link's failure, if any. `list_sync_failures` returns them ordered by link, `failed_at` UTC-aware (as `FeedPull.pulled_at` is). None commit.
- **R3.** `run_links`, for each link: while `run_sync` raises `AggregatorUnreachable` and waits are left in `retry_waits`, it calls `on_retry(link, seconds)` (when given), then waits `seconds` with `sleep` (when `None`, `time.sleep` looked up at that moment, so a test can replace `time.sleep`), then tries again. Any other `SyncError` ends the link at once. Afterwards, in a session of its own: a link that ended in `AGGREGATOR_FAILED` or `KEYCHAIN_FAILED` gets `record_sync_failure(link, now(), cause)`; a link that ran gets `clear_sync_failure(link)`; a link `NOT_SET_UP` gets neither. Everything else about `run_links` is unchanged.
- **R4.** `fin sync run` passes `retry_waits=RETRY_WAITS` and an `on_retry` that prints the retry line to stderr. Its other output is unchanged. The web's `POST /sync/run` and `GET /sync/accounts` pass no waits.
- **R5.** `failure_lines` formats each failure as in the table (the time in UTC, to the minute). `fin sync status` prints them after its table; with no mapped accounts it prints only `No mapped accounts.`, as now.
- **R6.** `health_problems` adds one `sync` problem per failure (account empty, detail as in the table, Phase 25's sync action), ordered with the others by Phase 25's rule. `gather_health` passes `list_sync_failures`. The dashboard shows them through health, unchanged.
- **R7.** The given scripts run each scheduled job through `/bin/bash -c`, printing `== YYYY-MM-DD HH:MM:SS ZONE` before `exec`ing the command. The owner reinstalls both jobs after this phase is committed (below).

## Given migration and scripts

`src/finances/db/migrations/versions/0011_sync_failures.py`

```python
"""Create sync_failures: the last failed sync of each SimpleFIN link, cleared by a good one."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_failures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("link", sa.String(30), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sync_failures"),
        sa.UniqueConstraint("link", name="uq_sync_failures_link"),
    )


def downgrade() -> None:
    op.drop_table("sync_failures")
```

`scripts/install-sync-schedule.sh`

```sh
#!/bin/bash
# Run `fin sync run` every day at a set time, as the logged-in user, with launchd.
#
#   scripts/install-sync-schedule.sh              daily at 07:00
#   scripts/install-sync-schedule.sh 6 30         daily at 06:30
#   scripts/install-sync-schedule.sh 7 0 --now    install, then run once straight away
#
# The job runs inside the user's login session, so it can read the SimpleFIN access in the
# Keychain. Paths are worked out from where this repository is, so the same command works on
# any Mac. Output goes to data/logs/sync.log (data/ is never committed). Each run starts
# with a line giving the local date and time. Installing again replaces the earlier job.
# Remove it with scripts/uninstall-sync-schedule.sh.
set -euo pipefail

LABEL="local.finances.sync"
HOUR="${1:-7}"
MINUTE="${2:-0}"
RUN_NOW="${3:-}"

if ! [[ "$HOUR" =~ ^[0-9]{1,2}$ ]] || ((10#$HOUR > 23)); then
    echo "Error: the hour must be 0 to 23" >&2
    exit 1
fi
if ! [[ "$MINUTE" =~ ^[0-9]{1,2}$ ]] || ((10#$MINUTE > 59)); then
    echo "Error: the minute must be 0 to 59" >&2
    exit 1
fi
if [[ -n "$RUN_NOW" && "$RUN_NOW" != "--now" ]]; then
    echo "Error: the only third argument is --now" >&2
    exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIN="$REPO/.venv/bin/fin"
LOGS="$REPO/data/logs"
AGENTS="$HOME/Library/LaunchAgents"
PLIST="$AGENTS/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [[ ! -x "$FIN" ]]; then
    echo "Error: $FIN not found; install the project first" >&2
    exit 1
fi
mkdir -p "$LOGS" "$AGENTS"

cat >"$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>printf '== %s\\n' "\$(date '+%Y-%m-%d %H:%M:%S %Z')"; exec "$FIN" sync run</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>$((10#$HOUR))</integer>
    <key>Minute</key>
    <integer>$((10#$MINUTE))</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOGS/sync.log</string>
  <key>StandardErrorPath</key>
  <string>$LOGS/sync.log</string>
</dict>
</plist>
PLIST
plutil -lint "$PLIST" >/dev/null

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
printf 'Scheduled fin sync run daily at %02d:%02d (log: %s)\n' "$((10#$HOUR))" "$((10#$MINUTE))" "$LOGS/sync.log"

if [[ "$RUN_NOW" == "--now" ]]; then
    launchctl kickstart "$DOMAIN/$LABEL"
    echo "Started one run now; see the log when it finishes."
fi
```

`scripts/install-backup-schedule.sh`

```sh
#!/bin/bash
# Run `fin backup run` every day at a set time, as the logged-in user, with launchd.
#
#   scripts/install-backup-schedule.sh              daily at 02:00
#   scripts/install-backup-schedule.sh 3 30         daily at 03:30
#   scripts/install-backup-schedule.sh 2 0 --now    install, then run once straight away
#
# Backups go to FIN_BACKUP_DIR (data/backups unless set; see docs/backups.md). Paths are worked
# out from where this repository is, so the same command works on any Mac. Output goes to
# data/logs/backup.log (data/ is never committed). Each run starts with a line giving the
# local date and time.
# Installing again replaces the earlier job.
# Remove it with scripts/uninstall-backup-schedule.sh.
set -euo pipefail

LABEL="local.finances.backup"
HOUR="${1:-2}"
MINUTE="${2:-0}"
RUN_NOW="${3:-}"

if ! [[ "$HOUR" =~ ^[0-9]{1,2}$ ]] || ((10#$HOUR > 23)); then
    echo "Error: the hour must be 0 to 23" >&2
    exit 1
fi
if ! [[ "$MINUTE" =~ ^[0-9]{1,2}$ ]] || ((10#$MINUTE > 59)); then
    echo "Error: the minute must be 0 to 59" >&2
    exit 1
fi
if [[ -n "$RUN_NOW" && "$RUN_NOW" != "--now" ]]; then
    echo "Error: the only third argument is --now" >&2
    exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIN="$REPO/.venv/bin/fin"
LOGS="$REPO/data/logs"
AGENTS="$HOME/Library/LaunchAgents"
PLIST="$AGENTS/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [[ ! -x "$FIN" ]]; then
    echo "Error: $FIN not found; install the project first" >&2
    exit 1
fi
mkdir -p "$LOGS" "$AGENTS"

cat >"$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>printf '== %s\\n' "\$(date '+%Y-%m-%d %H:%M:%S %Z')"; exec "$FIN" backup run</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>$((10#$HOUR))</integer>
    <key>Minute</key>
    <integer>$((10#$MINUTE))</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOGS/backup.log</string>
  <key>StandardErrorPath</key>
  <string>$LOGS/backup.log</string>
</dict>
</plist>
PLIST
plutil -lint "$PLIST" >/dev/null

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
printf 'Scheduled fin backup run daily at %02d:%02d (log: %s)\n' "$((10#$HOUR))" "$((10#$MINUTE))" "$LOGS/backup.log"

if [[ "$RUN_NOW" == "--now" ]]; then
    launchctl kickstart "$DOMAIN/$LABEL"
    echo "Started one run now; see the log when it finishes."
fi
```

## Given tests

15 tests in four files. The integration tests pass a recording `sleep` and a fixed `now`; the end-to-end tests replace `time.sleep`, so nothing waits.

`tests/integration/test_sync_resilience.py`

```python
import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine

from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import list_sync_failures, record_sync_failure
from finances.domain.models import SyncFailure
from finances.sync.links import KEYCHAIN_SERVICE
from finances.sync.runner import AGGREGATOR_FAILED, RETRY_WAITS, run_links
from finances.sync.simplefin import AggregatorUnreachable

TODAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 20, 7, 0, 5, tzinfo=UTC)
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"
EMPTY = json.dumps({"errlist": [], "connections": [], "accounts": []}).encode()
UNREACHABLE = "could not reach the aggregator"


class Bridge:
    """A fake SimpleFIN: it fails the first `failures` requests as `failure`, then answers."""

    def __init__(self, failures: int = 0, failure: str = "unreachable") -> None:
        self.failures = failures
        self.failure = failure
        self.calls = 0

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls += 1
        if self.calls <= self.failures:
            if self.failure == "unreachable":
                raise AggregatorUnreachable(UNREACHABLE)
            return {"error": 500, "revoked": 403}[self.failure], b""
        return 200, EMPTY


@pytest.fixture
def engine(db_url: str, keychain) -> Engine:
    upgrade_to_head(db_url)
    keychain.passwords[(KEYCHAIN_SERVICE, "alex")] = ALEX
    keychain.passwords[(KEYCHAIN_SERVICE, "sam")] = SAM
    found = get_engine(db_url)
    yield found
    found.dispose()


def failures(engine: Engine) -> list[SyncFailure]:
    with session_scope(engine) as session:
        return list_sync_failures(session)


def sync(engine: Engine, bridge, links=("alex",), **options):
    waits: list[float] = []
    retries: list[tuple[str, int]] = []
    runs = run_links(
        engine,
        list(links),
        today=TODAY,
        transport=bridge,
        sleep=waits.append,
        on_retry=lambda link, seconds: retries.append((link, seconds)),
        now=lambda: NOW,
        **options,
    )
    return runs, waits, retries


def test_the_waits() -> None:
    assert RETRY_WAITS == (30, 60, 120)


def test_unreachable_twice_then_answered(engine: Engine) -> None:
    bridge = Bridge(failures=2)
    runs, waits, retries = sync(engine, bridge, retry_waits=RETRY_WAITS)
    assert [run.failure for run in runs] == [None]
    assert runs[0].report is not None
    assert (bridge.calls, waits, retries) == (3, [30, 60], [("alex", 30), ("alex", 60)])
    assert failures(engine) == []


def test_unreachable_every_time(engine: Engine) -> None:
    bridge = Bridge(failures=99)
    runs, waits, retries = sync(engine, bridge, retry_waits=RETRY_WAITS)
    assert [(run.failure, run.cause) for run in runs] == [(AGGREGATOR_FAILED, UNREACHABLE)]
    assert (bridge.calls, waits) == (4, [30, 60, 120])
    assert failures(engine) == [SyncFailure("alex", NOW, UNREACHABLE)]


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("error", "aggregator answered with an error"),
        ("revoked", "aggregator access was revoked or is wrong"),
    ],
)
def test_an_answer_with_an_error_is_not_tried_again(
    engine: Engine, failure: str, message: str
) -> None:
    bridge = Bridge(failures=99, failure=failure)
    runs, waits, _ = sync(engine, bridge, retry_waits=RETRY_WAITS)
    assert [run.cause for run in runs] == [message]
    assert (bridge.calls, waits) == (1, [])
    assert failures(engine) == [SyncFailure("alex", NOW, message)]


def test_without_waits_nothing_is_tried_again(engine: Engine) -> None:
    bridge = Bridge(failures=99)
    runs, waits, _ = sync(engine, bridge)
    assert [run.cause for run in runs] == [UNREACHABLE]
    assert (bridge.calls, waits) == (1, [])
    assert failures(engine) == [SyncFailure("alex", NOW, UNREACHABLE)]


def test_a_good_sync_clears_the_links_failure_only(engine: Engine) -> None:
    earlier = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)
    with session_scope(engine) as session:
        record_sync_failure(session, "alex", earlier, UNREACHABLE)
        record_sync_failure(session, "sam", earlier, UNREACHABLE)
    runs, _, _ = sync(engine, Bridge(), links=("alex",))
    assert [run.failure for run in runs] == [None]
    assert failures(engine) == [SyncFailure("sam", earlier, UNREACHABLE)]


def test_a_new_failure_replaces_the_old_one(engine: Engine) -> None:
    with session_scope(engine) as session:
        record_sync_failure(session, "alex", datetime(2026, 10, 19, 7, 0, tzinfo=UTC), "older")
    sync(engine, Bridge(failures=99, failure="error"))
    assert failures(engine) == [SyncFailure("alex", NOW, "aggregator answered with an error")]
```

`tests/integration/test_migration_0011.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import Base, SyncFailureRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("link", "VARCHAR(30)", False),
    ("failed_at", "DATETIME", False),
    ("message", "VARCHAR(200)", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def at_0011(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    command.upgrade(make_config(url), "0011")
    return url


def test_0011_follows_0010() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0011")
    assert script.down_revision == "0010"


def test_the_table(at_0011: str) -> None:
    engine = get_engine(at_0011)
    found = inspect(engine)
    columns = [
        (c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("sync_failures")
    ]
    uniques = [
        (u["name"], u["column_names"]) for u in found.get_unique_constraints("sync_failures")
    ]
    foreign = [
        (f["constrained_columns"], f["referred_table"])
        for f in found.get_foreign_keys("sync_failures")
    ]
    primary = found.get_pk_constraint("sync_failures")
    engine.dispose()
    assert columns == COLUMNS
    assert uniques == [("uq_sync_failures_link", ["link"])]
    assert foreign == []
    assert (primary["name"], primary["constrained_columns"]) == ("pk_sync_failures", ["id"])
    assert [(c.name, str(c.type), c.nullable) for c in SyncFailureRow.__table__.columns] == COLUMNS
    assert SyncFailureRow.__table__ is Base.metadata.tables["sync_failures"]


def test_downgrade_removes_only_the_table(at_0011: str) -> None:
    command.downgrade(make_config(at_0011), "0010")
    engine = get_engine(at_0011)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert "sync_failures" not in names and "budgets" in names
```

`tests/unit/test_health_sync_failures.py`

```python
from datetime import UTC, date, datetime

from finances.domain.health import Problem, health_problems
from finances.domain.models import SyncFailure

AS_OF = date(2026, 10, 20)
SYNC = "Run fin sync run; if it fails, link SimpleFIN again (docs/sync-setup.md)."


def test_a_stored_failure_is_a_sync_problem() -> None:
    found = health_problems(
        [],
        AS_OF,
        AS_OF,
        failures=[
            SyncFailure(
                "sam",
                datetime(2026, 10, 19, 23, 30, tzinfo=UTC),
                "aggregator answered with an error",
            ),
            SyncFailure(
                "alex", datetime(2026, 10, 20, 11, 0, tzinfo=UTC), "could not reach the aggregator"
            ),
        ],
    )
    assert found == [
        Problem(
            "sync",
            "",
            "The last sync of link alex failed on 2026-10-20: could not reach the aggregator.",
            SYNC,
        ),
        Problem(
            "sync",
            "",
            "The last sync of link sam failed on 2026-10-19: aggregator answered with an error.",
            SYNC,
        ),
    ]


def test_no_failures_by_default() -> None:
    assert health_problems([], AS_OF, AS_OF) == []
```

`tests/e2e/test_cli_sync_resilience.py`

```python
import json
import re
from datetime import UTC, datetime

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import create_account, map_feed_account
from finances.sync import transport
from finances.sync.links import KEYCHAIN_SERVICE
from finances.sync.simplefin import AggregatorUnreachable
from tests.support import run, table_rows

ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
EMPTY = json.dumps({"errlist": [], "connections": [], "accounts": []}).encode()
FAILED = re.compile(
    r"Last failure of link alex: \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC:"
    r" could not reach the aggregator\."
)


def unreachable(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    raise AggregatorUnreachable("could not reach the aggregator")


def answers(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    return 200, EMPTY


@pytest.fixture
def linked(tmp_settings: Settings, keychain, monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Test Card mapped under link alex; waits are recorded instead of slept."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        map_feed_account(session, card.id, "ACT-1", "alex")
    engine.dispose()
    keychain.passwords[(KEYCHAIN_SERVICE, "alex")] = ALEX
    waits: list[float] = []
    monkeypatch.setattr("time.sleep", waits.append)
    return waits


def test_the_daily_sync_tries_again_then_remembers_the_failure(
    linked: list[float], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(transport, "urllib_transport", unreachable)
    result = run("sync", "run")
    assert result.exit_code == 1
    assert result.stderr.splitlines() == [
        "link alex: could not reach the aggregator; trying again in 30 seconds.",
        "link alex: could not reach the aggregator; trying again in 60 seconds.",
        "link alex: could not reach the aggregator; trying again in 120 seconds.",
        "Error: link alex: could not reach the aggregator",
    ]
    assert linked == [30, 60, 120]
    status = run("sync", "status").stdout
    assert [line for line in status.splitlines() if FAILED.fullmatch(line)] != []
    today = datetime.now(UTC).date().isoformat()
    health = table_rows(run("health").stdout)
    assert [
        "sync",
        "",
        f"The last sync of link alex failed on {today}: could not reach the aggregator.",
        "Run fin sync run; if it fails, link SimpleFIN again (docs/sync-setup.md).",
    ] in health


def test_a_good_sync_clears_it(linked: list[float], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transport, "urllib_transport", unreachable)
    run("sync", "run")
    monkeypatch.setattr(transport, "urllib_transport", answers)
    assert run("sync", "run").exit_code == 0
    assert "Last failure" not in run("sync", "status").stdout
    assert not any(row[2].startswith("The last sync") for row in table_rows(run("health").stdout))
```

## Tests to write

`tests/integration/test_sync_resilience_more.py`:

- a Keychain failure is remembered; a link that is not set up is not;
- the web's Sync now does not wait (an unreachable fake answers at once, and the failure is stored);
- `record_sync_failure` cuts a 300-character message to 200;
- `fin sync status` with two failures prints them by link.

## After the phase is committed (the owner)

```
scripts/install-sync-schedule.sh 7 0
scripts/install-backup-schedule.sh 2 0
```

Each run in `data/logs/sync.log` and `data/logs/backup.log` then starts with `== date time zone`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_sync_resilience.py tests/integration/test_migration_0011.py tests/unit/test_health_sync_failures.py tests/e2e/test_cli_sync_resilience.py`, 15 tests;
- every earlier sync and health test passes unchanged;
- `bash -n scripts/install-sync-schedule.sh && bash -n scripts/install-backup-schedule.sh` prints nothing; the scripts are not run;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov=finances.domain.health --cov=finances.analysis.health --cov=finances.views.sync --cov=finances.cli.sync --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the search: `git grep -n --untracked -E "urlopen|urllib\.request|socket\." -- src/finances` (only `src/finances/sync/transport.py`).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 33: sync resilience (YYYY-MM-DD)`.
