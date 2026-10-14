# Verify Phase 9: test hardening, and the bugs it found

Spec: `docs/phases/phase-09-test-hardening.md`

Do not modify any file in the repository, and do not run `fin` against the real database in `data/` or SimpleFIN. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder added the property profile and `hypothesis`, replaced the closest-first matcher with a best pairing that knows statement-period zones, made `apply_feed` pair a whole pull at once, made `create_account` refuse long names and bad currencies, cut long statement text to its columns, made a deeply nested SimpleFIN answer unreadable instead of a crash, and wrote two test files. Seven test files were given.

Judge the code by what it returns, never by how it is written. These are correct and must not be reported: any algorithm for R5 that returns the specified pairs (a dynamic program, a search); building the zone lists inline or in helpers; computing the statement periods once per import or pull; where in `create_account` the currency check sits, as long as R9's order holds for the checks the tests reach.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it; it is `1753` when Phase 16b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 98 passed, 0 failed, 0 skipped, 0 xfailed, **no warnings summary**, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_matching.py tests/unit/test_properties_money.py tests/unit/test_properties_ingest.py tests/unit/test_parser_fuzz.py tests/unit/test_simplefin_fuzz.py tests/integration/test_ledger_properties.py tests/integration/test_text_limits.py --no-cov` | exactly `127 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| `.venv/bin/python -c "import hypothesis; print('ok')"` | `ok` |
| `git status --short --ignored .hypothesis` | nothing, or `!! .hypothesis/` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain --cov=finances.ingest --cov=finances.sync --cov=finances.db --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M .gitignore
 M docs/progress.md
 M pyproject.toml
 M src/finances/db/repositories.py
 M src/finances/domain/matching.py
 M src/finances/domain/models.py
 M src/finances/ingest/service.py
 M src/finances/sync/service.py
 M src/finances/sync/simplefin.py
 M tests/conftest.py
 M tests/unit/test_matching.py
?? tests/integration/test_ledger_properties.py
?? tests/integration/test_log_hygiene.py
?? tests/integration/test_migration_chain.py
?? tests/integration/test_text_limits.py
?? tests/unit/test_parser_fuzz.py
?? tests/unit/test_properties_ingest.py
?? tests/unit/test_properties_money.py
?? tests/unit/test_simplefin_fuzz.py
```

- The seven given files are identical to the blocks in the spec, `tests/unit/test_matching.py` included.
- `git diff HEAD -- tests/conftest.py` adds only the import and the profile block of R2. `git diff HEAD -- .gitignore` adds only `.hypothesis/`. `git diff HEAD -- pyproject.toml` adds only `"hypothesis>=6.100",` to `dev`.
- No migration file and no other test changed.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1, R2 | tooling | probe script; the third search | every line starting `tooling:`; no output |
| R3 to R6 | pairing | probe script; gate 4 | every line starting `matching:` |
| R7, R8 | pairing in import and pull | probe script; gate 4 | every line starting `ledger:` |
| R9 to R12 | text that fits | probe script; gate 4 | every line starting `limits:` |
| R13 | SimpleFIN | probe script; gate 4 | every line starting `simplefin:` |
| R14 | migration chain | section 5; probe script | the coder's tests check what R14 lists; `migrations: each of the ...` |
| R15 | log hygiene | section 5 | the coder's test runs what R15 lists and asserts on stderr |

Run each of these searches. Each must print nothing.

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "float" -- src/finances/domain src/finances/ingest src/finances/sync src/finances/db`

`git grep -n --untracked -E "derandomize=False|database=|use_true_random=True|@seed|HYPOTHESIS" -- tests ':!tests/conftest.py'`

`git grep -n --untracked -E "(^|[^_a-zA-Z.])print\(|logging" -- src/finances/domain src/finances/ingest/service.py src/finances/sync/service.py src/finances/sync/simplefin.py src/finances/db/repositories.py`

## 4. Independent probe

This script uses a temporary data folder that it removes. It registers its own statement parser for the run (removed at the end), replaces `extract_pages` in the import service so its statements can be plain text, and drives the real import and feed services: a first pull after a statement import listed newest first, a purchase every day for a month pulled two days late, a statement that can pair two feed rows, and a tie across a period's first day. It also checks the matcher and zones with new examples, the length and currency rules (including `fin accounts add`), long statement text, two nested SimpleFIN answers, and walks every migration down and up. It contacts nothing.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import os
import re
import tempfile
from datetime import date, timedelta
from pathlib import Path

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def section(name, run):
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        check(f"{name}: ran to the end (stopped by {type(exc).__name__}: {exc})", False)


folder = tempfile.TemporaryDirectory()
saved = os.environ.get("FIN_DATA_DIR")
os.environ["FIN_DATA_DIR"] = folder.name

from finances.config import get_settings  # noqa: E402

get_settings.cache_clear()

import finances.ingest.service as ingest  # noqa: E402
from finances.db.engine import get_engine, session_scope  # noqa: E402
from finances.db.migrate import upgrade_to_head  # noqa: E402
from finances.domain.models import AccountType  # noqa: E402
from finances.ingest.parsers import register, unregister  # noqa: E402
from finances.ingest.statement import ParsedStatement, Section, StatementLine  # noqa: E402
from finances.sync.feed import AccountFeed, FeedTransaction  # noqa: E402
from finances.sync.service import apply_feed  # noqa: E402

APRIL = (date(2027, 4, 1), date(2027, 4, 30))
probe_lines = {}


class ProbeParser:
    """Reads 'PROBE <name>' and returns the statement stored under that name."""

    name = "probe_nine"

    def detect(self, first_page):
        return first_page.startswith("PROBE ")

    def parse(self, pages):
        lines, last4 = probe_lines[pages[0].split()[1]]
        return ParsedStatement(
            parser_name=self.name,
            institution="Probe Bank",
            account_type=AccountType.CREDIT_CARD,
            account_last4=last4,
            period_start=APRIL[0],
            period_end=APRIL[1],
            opening_balance_cents=0,
            closing_balance_cents=sum(item.amount_cents for item in lines),
            lines=lines,
        )


def line(day, cents, text="PROBE SHOP", cardholder=None, reference=None):
    return StatementLine(
        day, None, text, cents, Section.PURCHASES, None, cardholder, reference
    )


def item(key, day, zone=0, cents=-375):
    from finances.domain.matching import MatchItem

    return MatchItem(key, cents, date(2027, 4, day), zone)


def matching():
    from finances.domain.matching import match_one_to_one, period_zone

    check(
        "matching: the most pairs are made",
        match_one_to_one([item(1, 3), item(2, 7)], [item(5, 6), item(6, 11)])
        == [(1, 5), (2, 6)],
    )
    check(
        "matching: a pair within one zone beats a closer pair across zones",
        match_one_to_one([item(1, 20, 3)], [item(5, 19, 2), item(6, 23, 3)])
        == [(1, 6)],
    )
    check(
        "matching: more pairs beat pairs within one zone",
        match_one_to_one(
            [item(1, 22, 3), item(2, 17, 2)], [item(5, 21, 3), item(6, 27, 4)]
        )
        == [(1, 6), (2, 5)],
    )
    check(
        "matching: among equals the fewest days apart win",
        match_one_to_one(
            [item(1, 10), item(2, 16)], [item(5, 12), item(6, 13), item(7, 20)]
        )
        == [(1, 5), (2, 6)],
    )
    check(
        "matching: ties go to the earlier day, then the earlier position",
        match_one_to_one([item(1, 12), item(2, 12)], [item(5, 2), item(6, 16)])
        == [(1, 6)]
        and match_one_to_one([item(2, 12), item(1, 12)], [item(5, 2), item(6, 16)])
        == [(2, 6)]
        and match_one_to_one([item(1, 12)], [item(5, 14), item(6, 10)]) == [(1, 6)],
    )
    check(
        "matching: amounts are paired separately and keys come back in left order",
        match_one_to_one(
            [item(30, 9, cents=-100), item(-4, 9), item(0, 2, cents=-100)],
            [item(7, 9), item(8, 3, cents=-100), item(9, 9, cents=-100)],
        )
        == [(30, 9), (-4, 7), (0, 8)],
    )
    periods = [
        (date(2027, 3, 1), date(2027, 3, 31)),
        (date(2027, 1, 1), date(2027, 1, 31)),
    ]
    zones = [
        period_zone(date(2026, 12, 31), periods),
        period_zone(date(2027, 1, 1), periods),
        period_zone(date(2027, 1, 31), periods),
        period_zone(date(2027, 2, 15), periods),
        period_zone(date(2027, 3, 1), periods),
        period_zone(date(2027, 4, 1), periods),
        period_zone(date(2027, 4, 1), []),
    ]
    check(
        "matching: the zones of days among two periods", zones == [0, 1, 1, 2, 3, 4, 0]
    )


def ledger_case(name, lines, pulls, import_after, last4):
    """Pull the feed day by day; import the April statement right after the pull of import_after."""
    probe_lines[name] = (lines, last4)
    with session_scope(get_engine()) as session:
        from finances.db.repositories import create_account

        account_id = create_account(
            session, f"Probe {name}", "Probe Bank", "credit_card", last4=last4
        ).id
    for today, feed in pulls:
        with session_scope(get_engine()) as session:
            apply_feed(session, account_id, feed)
        if today == import_after:
            with session_scope(get_engine()) as session:
                result = ingest.import_statement(
                    session, filename=f"{name}.pdf", content=f"PROBE {name}".encode()
                )
                assert result.status.value == "imported", result.message
    from sqlalchemy import select

    from finances.db.orm import TransactionRow

    with session_scope(get_engine()) as session:
        return session.execute(
            select(
                TransactionRow.posted_date,
                TransactionRow.amount_cents,
                TransactionRow.source,
            )
            .where(TransactionRow.account_id == account_id)
            .order_by(TransactionRow.posted_date, TransactionRow.id)
        ).all()


def feed_of(spent, today, newest_first=True):
    window = [
        entry for entry in spent if today - timedelta(days=30) <= entry[1] <= today
    ]
    window.sort(key=lambda entry: entry[1], reverse=newest_first)
    return AccountFeed(
        [FeedTransaction(key, day, cents, "PROBE SHOP") for key, day, cents in window]
    )


def ledger():
    upgrade_to_head()
    ingest.extract_pages = lambda content: [content.decode()]
    register(ProbeParser())
    try:
        first_pull = date(2027, 5, 3)
        spent = [
            ("F28", date(2027, 4, 28), -375),
            ("F30", date(2027, 4, 30), -375),
            ("F02", date(2027, 5, 2), -375),
        ]
        rows = ledger_case(
            "backfill",
            [line(date(2027, 4, 28), -375), line(date(2027, 4, 30), -375)],
            [
                (date(2027, 5, 2), AccountFeed()),
                (first_pull, feed_of(spent, first_pull)),
            ],
            date(2027, 5, 2),
            "9001",
        )
        check(
            "ledger: a first pull after an import keeps a later equal purchase",
            [(day.day, source) for day, _, source in rows]
            == [(28, "statement"), (30, "statement"), (2, "aggregator")],
        )
        coffees = [
            (f"C{n}", date(2027, 4, 1) + timedelta(days=n), -375) for n in range(30)
        ]
        lagged = [(key, day + timedelta(days=2), cents) for key, day, cents in coffees]
        days = [date(2027, 4, 2) + timedelta(days=n) for n in range(35)]
        rows = ledger_case(
            "daily",
            [line(day, cents) for _, day, cents in coffees],
            [
                (today, feed_of(lagged, today, newest_first=today.day % 2 == 0))
                for today in days
            ],
            date(2027, 5, 3),
            "9002",
        )
        check(
            "ledger: a daily purchase pulled two days late is stored once per day",
            len(rows) == 30 and {source for _, _, source in rows} == {"statement"},
        )
        pair = [("P1", date(2027, 4, 24), -375), ("P2", date(2027, 5, 1), -375)]
        rows = ledger_case(
            "pairs",
            [line(date(2027, 4, 21), -375), line(date(2027, 4, 28), -375)],
            [(date(2027, 5, 2), feed_of(pair, date(2027, 5, 2)))],
            date(2027, 5, 2),
            "9003",
        )
        check(
            "ledger: a statement pairs as many feed rows as it can",
            [(day.day, source) for day, _, source in rows]
            == [(21, "statement"), (28, "statement")],
        )
        edge = [("E1", date(2027, 3, 29), -375), ("E2", date(2027, 4, 4), -375)]
        rows = ledger_case(
            "edge",
            [line(date(2027, 4, 1), -375)],
            [
                (date(2027, 4, 5), feed_of(edge, date(2027, 4, 5))),
                (date(2027, 5, 3), feed_of(edge, date(2027, 5, 3))),
            ],
            date(2027, 5, 3),
            "9004",
        )
        check(
            "ledger: a tie across the period's first day goes to the purchase inside the period",
            [(day.month, day.day, source) for day, _, source in rows]
            == [(3, 29, "aggregator"), (4, 1, "statement")],
        )
    finally:
        unregister("probe_nine")


def limits():
    from typer.testing import CliRunner

    from finances.cli.main import app
    from finances.db.repositories import create_account

    with session_scope(get_engine()) as session:
        kept = create_account(session, "K" * 100, "B" * 100, "savings", currency="GBP")
        check(
            "limits: 100 characters and GBP are kept",
            (len(kept.name), kept.currency) == (100, "GBP"),
        )
    for name, institution, currency, message in (
        ("L" * 101, "Probe", "USD", "account name must be at most 100 characters"),
        ("Probe L", "B" * 101, "USD", "institution must be at most 100 characters"),
        ("Probe M", "Probe", "gbp", "currency must be three capital letters"),
        ("Probe N", "Probe", "GB", "currency must be three capital letters"),
        ("Probe O", "Probe", "GBPS", "currency must be three capital letters"),
    ):
        try:
            with session_scope(get_engine()) as session:
                create_account(session, name, institution, "other", currency=currency)
            refused = None
        except ValueError as error:
            refused = str(error)
        check(
            f"limits: refused with '{message}' ({len(name)}, {len(institution)}, {currency})",
            refused == message,
        )
    result = CliRunner().invoke(
        app,
        [
            "accounts",
            "add",
            "--name",
            "Probe P",
            "--institution",
            "Probe",
            "--type",
            "other",
            "--currency",
            "eur",
        ],
    )
    check(
        "limits: fin accounts add refuses a lower-case currency",
        result.exit_code == 1
        and "currency must be three capital letters" in result.output,
    )
    ingest.extract_pages = lambda content: [content.decode()]
    register(ProbeParser())
    try:
        words = " ".join(f"ITEM{n:04d}" for n in range(90))
        long_text = f"PROBE    {words}"
        probe_lines["long"] = (
            [line(date(2027, 4, 9), -999, long_text, "Q" * 150, "R" * 120)],
            "9005",
        )
        with session_scope(get_engine()) as session:
            create_account(
                session, "Probe long", "Probe Bank", "credit_card", last4="9005"
            )
        with session_scope(get_engine()) as session:
            ingest.import_statement(session, filename="long.pdf", content=b"PROBE long")
        from sqlalchemy import select

        from finances.db.orm import TransactionRow

        with session_scope(get_engine()) as session:
            row = session.scalars(
                select(TransactionRow).where(TransactionRow.amount_cents == -999)
            ).one()
            expected = " ".join(long_text.split())[:500].rstrip()
            check(
                "limits: a long statement description, cardholder, and reference are cut to fit",
                (row.description, row.cardholder, row.external_id)
                == (expected, "Q" * 100, "R" * 100)
                and len(row.description) <= 500,
            )
    finally:
        unregister("probe_nine")


def simplefin():
    from finances.sync.simplefin import SyncError, fetch_accounts

    access = "https://p-user:p-pass@bridge.simplefin.org/simplefin"
    for label, body in (
        ("a deeply nested list", b"[" * 200_000),
        ("deep accounts", b'{"accounts":' + b"[" * 200_000 + b"]" * 200_000 + b"}"),
    ):
        try:
            fetch_accounts(
                access, date(2027, 4, 1), date(2027, 4, 2), lambda *_: (200, body)
            )
            outcome = "read"
        except SyncError as error:
            outcome = str(error)
        check(
            f"simplefin: {label} is unreadable",
            outcome == "aggregator answer could not be read",
        )


def migrations():
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect

    from finances.db.migrate import MIGRATIONS

    url = f"sqlite:///{(Path(folder.name) / 'chain.db').as_posix()}"
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    chain = [
        entry.revision
        for entry in reversed(
            list(ScriptDirectory.from_config(config).walk_revisions())
        )
    ]
    steady = True
    for revision in chain:
        command.upgrade(config, revision)
        engine = get_engine(url)
        before = sorted(inspect(engine).get_table_names())
        engine.dispose()
        command.downgrade(config, "-1")
        command.upgrade(config, revision)
        engine = get_engine(url)
        steady = steady and sorted(inspect(engine).get_table_names()) == before
        engine.dispose()
    check(
        f"migrations: each of the {len(chain)} revisions goes down and up again",
        steady and len(chain) >= 6,
    )


def tooling():
    import hypothesis  # noqa: F401

    ignored = Path(".gitignore").read_text(encoding="utf-8")
    conftest = Path("tests/conftest.py").read_text(encoding="utf-8")
    check(
        "tooling: hypothesis is installed and .hypothesis/ is ignored",
        ".hypothesis/" in ignored.splitlines(),
    )
    check(
        "tooling: the profile keeps no example database and runs the same examples",
        re.search(r"database=None", conftest) is not None
        and "derandomize=True" in conftest,
    )


try:
    for name, run in (
        ("matching", matching),
        ("ledger", ledger),
        ("limits", limits),
        ("simplefin", simplefin),
        ("migrations", migrations),
        ("tooling", tooling),
    ):
        section(name, run)
finally:
    if saved is None:
        os.environ.pop("FIN_DATA_DIR", None)
    else:
        os.environ["FIN_DATA_DIR"] = saved
    folder.cleanup()
print("FAILURES", failures)
```

## 5. The coder's tests

`tests/integration/test_migration_chain.py` (R14):

- It reads the revisions through `ScriptDirectory`; no list of revision names is typed out. Adding a migration file would add it to the walk.
- For each revision it upgrades, records tables with columns, unique constraints, and foreign keys, goes down one revision and up again, and compares. A record of table names only is a finding.
- It goes down to `base`, checks that only an empty `alembic_version` remains, goes up to head, and calls `compare_metadata` against `Base.metadata`, expecting no differences.
- It writes an account with plain SQL at the first revision and reads it back after upgrading revision by revision.

`tests/integration/test_log_hygiene.py` (R15):

- It sets `FIN_LOG_LEVEL=INFO`, runs the commands R15 lists through `CliRunner`, and replaces `transport.urllib_transport` with a fake. It touches no network and no real keychain.
- It asserts the merchant appears in the stdout of `fin transactions list`, and that no stderr holds the merchant, the amount (as printed and as cents), the account digits, or the password.

For both: no `assert True`, no blanket `pytest.raises(Exception)`, no `skip` or `xfail`, synthetic data only.

Spot checks. For each change below, say which test would fail, by reading the tests. If none would, that is a finding.

1. `ingest/service.py` logs `logger.info("line %s", line.description)` for each fresh line. (The coder's log hygiene test must fail.)
2. Migration `0005`'s `downgrade` stops dropping the `link` column. (The coder's chain test must fail.)
3. `match_one_to_one` scores a same-zone pair above a second pair. (`test_more_pairs_beat_pairs_within_one_zone`.)
4. `apply_feed` pairs every posted transaction of the pull, settled or not. (`test_a_tie_at_import_does_not_push_a_later_transaction_out` or another ledger test.)
5. The upgrade path of an import stores the description without cutting it. (`test_long_statement_text_is_cut_to_fit[True]`.)

## 6. Project rules that apply to this phase

- **Money.** No `float` in the changed modules (second search).
- **Layering.** `domain/matching.py` imports nothing from the project: `git grep -n "finances" -- src/finances/domain/matching.py` prints nothing.
- **Determinism.** No test sets its own seed, database, or `derandomize=False` (third search).
- **Privacy rule 4.** Nothing new logs (fourth search, and the coder's log hygiene test).

## 7. Out of scope

Each of these must be absent. Report any that is present.

- A `tests/golden/` folder or an `--update-golden` option.
- A new migration, or a change to the drop rules of Phase 8 or to `MATCH_MAX_DAYS`.
- Any change to a parser module.
- A currency field in the web form, or a currency upper-cased on the user's behalf.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 9: test hardening, and the bugs it found (YYYY-MM-DD)` with a real date. "Built" gives N, the passed count, and the five fixes. "Follow-ups" holds the three known limits. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 to Part 6>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, the test, or the file and line), and what is required. Do not prescribe the code.
