# Verify Phase 3c: storing and importing statements

Spec: `docs/phases/phase-03c-storing-and-importing-statements.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote five things: domain types, ORM tables with converters, migration `0002`, eight repository functions, and the import service. It also wrote four test files. One test file and `tests/conftest.py` were given. This is the largest phase so far, so check each part on its own and say in the verdict which parts needed a repair.

Judge the code by behavior and by the rules, never by how it is written. These are all correct and must not be reported:

- private helpers of any shape, in any of the listed modules;
- `import_statement` written as one function or as several private stages;
- any chunk size of 500 or less in `existing_fingerprints`;
- unique constraints declared on the column or in `__table_args__`, as long as the database names match;
- migration constraints written with or without explicit names where the naming convention already gives the required name;
- a failed result built with or without keyword arguments.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least `543 passed`, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/integration/test_migration_0002.py tests/integration/test_migrations.py --no-cov` | exactly `44 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with every file under `src/finances/ingest/`, `src/finances/db/`, and `src/finances/domain/` at 100% |
| `.venv/bin/python -c "from finances.db.migrate import head_revision; print(head_revision())"` | `0002` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov=finances.db --cov=finances.domain --cov-branch --cov-report=term-missing --cov-fail-under=100`

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/db/orm.py
 M src/finances/db/repositories.py
 M src/finances/domain/models.py
 M tests/conftest.py
?? src/finances/db/migrations/versions/0002_statements.py
?? src/finances/ingest/service.py
?? tests/integration/test_import_service.py
?? tests/integration/test_migration_0002.py
?? tests/integration/test_statement_repositories.py
?? tests/unit/test_statement_models.py
?? tests/unit/test_statement_orm.py
```

- `tests/integration/test_migration_0002.py` and `tests/conftest.py` are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- src/finances/db/orm.py src/finances/db/repositories.py src/finances/domain/models.py` only adds lines, apart from import lines: nothing in `AccountRow`, `to_account`, `Account`, `AccountType`, `validate_last4`, or the four account repository functions is changed.
- `git diff HEAD -- src/finances/cli src/finances/config.py src/finances/diagnostics.py src/finances/db/engine.py src/finances/db/migrate.py src/finances/db/migrations/env.py src/finances/db/migrations/versions/0001_accounts.py pyproject.toml` is empty.
- `git diff HEAD --stat -- tests` lists `tests/conftest.py` and no other existing test file.
- `git diff HEAD -- src/finances/ingest` is empty: the only change under `ingest` is the new `service.py`.
- `git status --short --ignored` shows no `.db`, `.sqlite`, or `.pdf` file and no `data/` folder in the repository.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 to R3 | domain types | probe script | every line starting `domain:` ends in `ok` |
| R4, R5, R8 to R10 | tables and migration | gate 4 (the 44 given and existing migration tests) | all pass |
| R4 | no SQLAlchemy `Enum` | read `orm.py` | `source` and `section` are `String` columns |
| R6, R7 | converters | probe script | `statements: created with an id and an aware time`, `transactions: a Transaction with enum source and flags`, and `balances: created` end in `ok` |
| R11 to R13 | statement repositories | probe script | every line starting `statements:` ends in `ok` |
| R14 | fingerprints | probe script | every line starting `fingerprints:` ends in `ok`, including `no query carries more than 500 of them` |
| R15 to R17 | transaction repositories | probe script | every line starting `transactions:` ends in `ok` |
| R18, R19 | balances | probe script | every line starting `balances:` ends in `ok` |
| Part 4 rule | no commit in repositories | probe script; first search below | `repositories: nothing was committed by the functions themselves` ends in `ok`; the search prints nothing |
| R20 | already imported | probe script | the three `already imported:` lines and `nothing added` end in `ok` |
| R21 to R24 | failures | probe script | every line starting `failed:` ends in `ok` |
| R25 to R27 | import | probe script | every line starting `import:`, `overlap:`, `named account:`, and `empty statement:` ends in `ok` |
| R26, R28 | nothing partial | probe script | the lines starting `dry run:` and `failed: nothing written by any failure` end in `ok` |
| Part 5 rule | no commit in the service | probe script | the two `import does not commit:` lines end in `ok` |
| R29 to R32 | folder | probe script | every line starting `folder:` ends in `ok` |
| privacy | messages | read every string in `service.py` | the only messages are the ones in R20 to R27; none contains a description, an amount, or a balance |
| scope | nothing extra | probe script | the lines `service: public names`, `service: ImportStatus values`, `service: result fields`, `repositories: new public names`, `orm: new public names`, and `models: new public names` end in `ok` |

`git grep -n --untracked -E "commit\(|rollback\(|close\(" -- src/finances/db/repositories.py src/finances/ingest/service.py`

`git grep -n --untracked -E "float|print\(|logging|server_default|create_all|finances\.cli" -- src/finances/domain src/finances/db/orm.py src/finances/db/repositories.py src/finances/db/migrations/versions/0002_statements.py src/finances/ingest/service.py`

Both searches must print nothing. (`session_scope` in `import_folder` commits; the service itself must not call `commit`.)

## 4. Independent probes

None of these values are in the given file or the spec. The script uses its own parser, its own statements, and its own PDF builder, so it does not depend on `tests/conftest.py`. It migrates a temporary database, exercises each repository function directly, then runs the import through every outcome: three unreadable or unrecognized inputs, eight kinds of failure, a dry run, an import with repeated lines, the same file again, an overlapping statement, accounts chosen by name, and a folder with files it must take and files it must ignore.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It works inside its own temporary folder. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import dataclasses
import hashlib
import tempfile
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from finances.db import orm, repositories
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import BalanceSnapshotRow, StatementRow, TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_statement,
    existing_fingerprints,
    find_statement_by_hash,
    insert_transactions,
    latest_balance,
    list_statements,
    list_transactions,
)
from finances.domain import models
from finances.domain.models import (
    AccountType,
    BalanceSnapshot,
    DataSource,
    NewTransaction,
    Statement,
    Transaction,
)
from finances.ingest import service
from finances.ingest.dedup import fingerprint_lines
from finances.ingest.parsers import register, registered_parsers, unregister
from finances.ingest.service import (
    ImportStatus,
    StatementImportResult,
    import_folder,
    import_statement,
)
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

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
    """Run one group of checks; an unexpected exception is one failure, not a crash."""
    try:
        function()
    except Exception as exc:  # noqa: BLE001
        check(f"{name}: ran to the end (stopped by {type(exc).__name__}: {exc})", False)


def build_pdf(pages):
    objects = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        operators = ["BT", "/F1 10 Tf"]
        for index, text in enumerate(lines):
            operators.append(f"1 0 0 1 72 {720 - 14 * index} Tm ({text}) Tj")
        operators.append("ET")
        stream = "\n".join(operators).encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
        objects.append(page % len(objects))
        kids.append(len(objects))
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % kid for kid in kids), len(kids))
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def line(month, day, amount, kind, text, **more):
    return StatementLine(date(2026, month, day), None, text, amount, kind, **more)


GROCER = line(3, 2, -1299, Section.PURCHASES, "PROBE   GROCER\t#7", card_last4="5512", external_ref="R1")
MARCH = [
    GROCER,
    GROCER,
    StatementLine(date(2026, 3, 9), date(2026, 3, 7), "PROBE FUEL", -4500, Section.PURCHASES, cardholder="A PERSON"),
    line(3, 15, 20000, Section.PAYMENTS_CREDITS, "PROBE PAYMENT"),
    line(3, 31, -129, Section.INTEREST, "PROBE INTEREST"),
]


def parsed(last4, kind, start, end, opening, closing, lines, totals=None):
    return ParsedStatement("probe_bank", "Probe Bank", kind, last4, start, end, opening, closing, lines, totals or {})


CARD = AccountType.CREDIT_CARD
MAR1, MAR31, APR1, APR30 = date(2026, 3, 1), date(2026, 3, 31), date(2026, 4, 1), date(2026, 4, 30)
STATEMENTS = {
    "march": parsed("9001", CARD, MAR1, MAR31, -50000, -37227, MARCH),
    "april": parsed("9001", CARD, APR1, APR30, -10000, -13298, [GROCER, GROCER, line(4, 2, -700, Section.FEES, "PROBE FEE")]),
    "offbythree": parsed("9001", CARD, MAR1, MAR31, -50000, -37224, MARCH),
    "sections": parsed("9001", CARD, MAR1, MAR31, -50000, -37227, MARCH, {Section.FEES: -100, Section.PURCHASES: -7098, Section.INTEREST: 5}),
    "both": parsed("9001", CARD, MAR1, MAR31, -50000, -37230, MARCH, {Section.INTEREST: 0}),
    "baddigits": parsed("12a4", CARD, MAR1, MAR31, 0, 0, []),
    "checking": parsed("0042", AccountType.CHECKING, MAR1, MAR31, 100000, 100000, []),
    "unknown4": parsed("7777", AccountType.SAVINGS, MAR1, MAR31, 5, 5, []),
    "shared": parsed("3003", CARD, MAR1, MAR31, 0, -250, [line(3, 3, -250, Section.PURCHASES, "PROBE SNACK")]),
}


class ProbeParser:
    name = "probe_bank"

    def detect(self, first_page):
        return first_page.strip().startswith("PROBE ")

    def parse(self, pages):
        key = pages[0].split()[1]
        if key == "broken":
            raise StatementError("probe statement is malformed")
        return STATEMENTS[key]


def pdf(key, salt=""):
    return build_pdf([[f"PROBE {key}", f"copy {salt}"]])


def counts(engine):
    with session_scope(engine) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(table))
            for table in (StatementRow, TransactionRow, BalanceSnapshotRow)
        )


def new_transaction(account_id, fingerprint, day=5, amount=-450, statement_id=None):
    return NewTransaction(
        account_id=account_id, statement_id=statement_id, posted_date=date(2026, 2, day), transaction_date=None,
        amount_cents=amount, description="PROBE ROW", section=None, card_last4=None, cardholder=None,
        external_id=None, source=DataSource.AGGREGATOR, is_pending=True, fingerprint=fingerprint,
    )


# ------------------------------------------------------------------- domain
def domain_checks():
    check("domain: DataSource values", [(m.name, m.value) for m in DataSource] == [("STATEMENT", "statement"), ("AGGREGATOR", "aggregator")])
    fields = {cls.__name__: [f.name for f in dataclasses.fields(cls)] for cls in (Statement, NewTransaction, Transaction, BalanceSnapshot)}
    check("domain: Statement fields", fields["Statement"] == ["id", "account_id", "source_filename", "file_sha256", "parser_name", "period_start", "period_end", "opening_balance_cents", "closing_balance_cents", "lines_parsed", "rows_inserted", "rows_duplicate", "imported_at"])
    core = ["account_id", "statement_id", "posted_date", "transaction_date", "amount_cents", "description", "section", "card_last4", "cardholder", "external_id", "source", "is_pending", "fingerprint"]
    check("domain: NewTransaction fields", fields["NewTransaction"] == core)
    check("domain: Transaction fields", fields["Transaction"] == ["id", *core, "created_at"])
    check("domain: BalanceSnapshot fields", fields["BalanceSnapshot"] == ["id", "account_id", "as_of_date", "balance_cents", "source", "created_at"])
    check("domain: all four are frozen", all(cls.__dataclass_params__.frozen for cls in (Statement, NewTransaction, Transaction, BalanceSnapshot)))
    imports = [text for text in Path(models.__file__).read_text(encoding="utf-8").splitlines() if text.startswith(("import ", "from "))]
    check(f"domain: imports nothing from the project {imports}", not any("finances" in text for text in imports))


# -------------------------------------------------------------- repositories
def repository_checks(engine):
    with session_scope(engine) as session:
        made = create_statement(
            session, account_id=1, source_filename="feb.pdf", file_sha256="b" * 64, parser_name="probe_bank",
            period_start=date(2026, 2, 1), period_end=date(2026, 2, 28), opening_balance_cents=-2**40,
            closing_balance_cents=7, lines_parsed=3, rows_inserted=2, rows_duplicate=1,
        )
        check("statements: created with an id and an aware time", type(made) is Statement and made.id == 1 and made.imported_at.utcoffset() == timedelta(0))
        check("statements: values kept", (made.opening_balance_cents, made.closing_balance_cents, made.lines_parsed, made.rows_inserted, made.rows_duplicate) == (-2**40, 7, 3, 2, 1))
        check("statements: found by hash before commit", find_statement_by_hash(session, "b" * 64) == made)
        check("statements: unknown hash", find_statement_by_hash(session, "c" * 64) is None)
        create_statement(
            session, account_id=2, source_filename="jan.pdf", file_sha256="a" * 64, parser_name="probe_bank",
            period_start=date(2026, 1, 1), period_end=date(2026, 1, 31), opening_balance_cents=0,
            closing_balance_cents=0, lines_parsed=0, rows_inserted=0, rows_duplicate=0,
        )
        create_statement(
            session, account_id=1, source_filename="dec.pdf", file_sha256="d" * 64, parser_name="probe_bank",
            period_start=date(2025, 12, 1), period_end=date(2026, 2, 28), opening_balance_cents=0,
            closing_balance_cents=0, lines_parsed=0, rows_inserted=0, rows_duplicate=0,
        )
        check("statements: newest period first, then newest id", [s.source_filename for s in list_statements(session)] == ["dec.pdf", "feb.pdf", "jan.pdf"])
        check("statements: one account", [s.source_filename for s in list_statements(session, account_id=2)] == ["jan.pdf"])
        check("statements: account with none", list_statements(session, 3) == [])

        rows = [new_transaction(1, f"{n:064d}", day=1 + n % 28, amount=-n) for n in range(1203)]
        check("transactions: insert returns the count", insert_transactions(session, rows) == 1203)
        check("transactions: insert of nothing", insert_transactions(session, []) == 0)
        insert_transactions(session, [new_transaction(2, "f" * 64, statement_id=2)])
        asked = [f"{n:064d}" for n in range(0, 1203, 3)] + ["e" * 64, "f" * 64]
        sizes = []

        def record(conn, cursor, statement, parameters, context, executemany):
            sizes.append(len(parameters))

        everything = [f"{n:064d}" for n in range(1203)]
        event.listen(engine, "before_cursor_execute", record)
        all_found = existing_fingerprints(session, 1, everything)
        event.remove(engine, "before_cursor_execute", record)
        check("fingerprints: all 1203 found", all_found == set(everything))
        check(f"fingerprints: no query carries more than 500 of them {sizes}", len(sizes) >= 3 and max(sizes) <= 501)
        found = existing_fingerprints(session, 1, asked)
        check("fingerprints: more than a thousand asked at once", type(found) is set and found == {f"{n:064d}" for n in range(0, 1203, 3)})
        check("fingerprints: another account's are not returned", existing_fingerprints(session, 2, iter(asked)) == {"f" * 64})
        check("fingerprints: nothing asked", existing_fingerprints(session, 1, []) == set())

        newest = list_transactions(session, account_id=1, limit=3)
        expected_ids = sorted((n + 1 for n in range(1203) if n % 28 == 27), reverse=True)[:3]
        check("transactions: newest date first, then newest id", [(t.posted_date.day, t.id) for t in newest] == [(28, i) for i in expected_ids])
        first = newest[0]
        check("transactions: a Transaction with enum source and flags", type(first) is Transaction and first.source is DataSource.AGGREGATOR and first.is_pending is True and first.created_at.utcoffset() == timedelta(0))
        check("transactions: default limit is 100", len(list_transactions(session)) == 100)
        ranged = list_transactions(session, account_id=1, start=date(2026, 2, 10), end=date(2026, 2, 11), limit=5000)
        check("transactions: date range includes both ends", {t.posted_date.day for t in ranged} == {10, 11} and len(ranged) == 86)
        check("transactions: only a start", {t.posted_date.day for t in list_transactions(session, start=date(2026, 2, 28), limit=5000)} == {28})
        check("transactions: only an end", {t.posted_date.day for t in list_transactions(session, end=date(2026, 2, 1), limit=5000)} == {1})
        other = list_transactions(session, account_id=2)
        check("transactions: one account", len(other) == 1 and other[0].statement_id == 2 and other[0].fingerprint == "f" * 64)
        check("transactions: limit must be positive", outcome(list_transactions, session, limit=0) == ("ValueError", "limit must be at least 1"))

        check("balances: none yet", latest_balance(session, 1) is None)
        first_balance = add_balance_snapshot(session, 1, date(2026, 2, 28), -12345, DataSource.STATEMENT)
        check("balances: created", type(first_balance) is BalanceSnapshot and first_balance.source is DataSource.STATEMENT and first_balance.created_at.utcoffset() == timedelta(0))
        again = add_balance_snapshot(session, 1, date(2026, 2, 28), 999, DataSource.STATEMENT)
        check("balances: the first one recorded is kept", again == first_balance and again.balance_cents == -12345)
        add_balance_snapshot(session, 1, date(2026, 2, 28), 5, DataSource.AGGREGATOR)
        add_balance_snapshot(session, 1, date(2026, 1, 31), 1, DataSource.STATEMENT)
        add_balance_snapshot(session, 2, date(2026, 6, 30), 2, DataSource.STATEMENT)
        check("balances: three rows for account 1", session.scalar(select(func.count()).select_from(BalanceSnapshotRow).where(BalanceSnapshotRow.account_id == 1)) == 3)
        latest = latest_balance(session, 1)
        check("balances: latest date wins, newest id on a tie", (latest.as_of_date, latest.balance_cents, latest.source) == (date(2026, 2, 28), 5, DataSource.AGGREGATOR))
        check("balances: per account", latest_balance(session, 2).balance_cents == 2 and latest_balance(session, 3) is None)
        session.rollback()
    check("repositories: nothing was committed by the functions themselves", counts(engine) == (0, 0, 0))


# ------------------------------------------------------------------ service
HINT = 'no account ends in 7777; add one with: fin accounts add --name "NAME" --institution "Probe Bank" --type savings --last4 7777'


def service_checks(engine):
    def run(key, salt="", **options):
        with session_scope(engine) as session:
            return import_statement(session, filename=options.pop("filename", f"{key}.pdf"), content=pdf(key, salt), **options)

    result = run("march", filename="/probe/inbox/march statement.pdf", dry_run=True)
    check("dry run: result", result == StatementImportResult("march statement.pdf", ImportStatus.DRY_RUN, "dry run: nothing written", "probe_bank", "Probe Card", MAR1, MAR31, 5, 5, 0))
    check("dry run: nothing written", counts(engine) == (0, 0, 0))

    with session_scope(engine) as session:
        failed = [
            ("unreadable bytes", import_statement(session, filename="x.pdf", content=b"PROBE march"), "could not read PDF"),
            ("unrecognized", import_statement(session, filename="x.pdf", content=build_pdf([["SOMETHING ELSE"]])), "unrecognized statement format"),
            ("parser error", import_statement(session, filename="x.pdf", content=pdf("broken")), "probe statement is malformed"),
        ]
    for label, found, message in failed:
        check(f"failed: {label}", found == StatementImportResult("x.pdf", ImportStatus.FAILED, message))

    for label, key, options, message in [
        ("no account with those digits", "unknown4", {}, HINT),
        ("two accounts share the digits", "shared", {}, "more than one account ends in these digits; name the account"),
        ("named account does not exist", "march", {"account_name": "Nobody"}, "account not found"),
        ("named account has other digits", "march", {"account_name": "Probe Checking"}, "account does not match the statement"),
        ("statement digits are not digits", "baddigits", {}, "statement has no usable account digits"),
        ("off by three cents", "offbythree", {}, "statement does not reconcile: off by 3 cents"),
        ("section totals only", "sections", {}, "statement does not reconcile: off by 0 cents; section totals differ: fees, interest"),
        ("balance and sections", "both", {}, "statement does not reconcile: off by -3 cents; section totals differ: interest"),
    ]:
        found = run(key, **options)
        check(f"failed: {label}", (found.status, found.message, found.inserted, found.duplicates) == (ImportStatus.FAILED, message, 0, 0))
        check(f"failed: {label}: what was read is reported", found.parser_name == "probe_bank" and found.period_start == MAR1)
    check("failed: nothing written by any failure", counts(engine) == (0, 0, 0))
    unmatched = run("unknown4")
    check("failed: no account name when none matched", unmatched.account_name is None and unmatched.lines_parsed == 0)
    check("failed: account name once matched", run("offbythree").account_name == "Probe Card" and run("offbythree").lines_parsed == 5)

    content = pdf("march")
    with session_scope(engine) as session:
        result = import_statement(session, filename="inbox/march.pdf", content=content)
    check("import: result", result == StatementImportResult("march.pdf", ImportStatus.IMPORTED, "imported", "probe_bank", "Probe Card", MAR1, MAR31, 5, 5, 0))
    check("import: one statement, five transactions, one balance", counts(engine) == (1, 5, 1))
    with session_scope(engine) as session:
        stored = find_statement_by_hash(session, hashlib.sha256(content).hexdigest())
        check("import: statement record", stored is not None and (stored.account_id, stored.source_filename, stored.parser_name, stored.period_start, stored.period_end) == (1, "march.pdf", "probe_bank", MAR1, MAR31))
        check("import: statement balances and counts", stored is not None and (stored.opening_balance_cents, stored.closing_balance_cents, stored.lines_parsed, stored.rows_inserted, stored.rows_duplicate) == (-50000, -37227, 5, 5, 0))
        rows = sorted(list_transactions(session, account_id=1), key=lambda t: t.id)
        check("import: rows in statement order", [t.amount_cents for t in rows] == [-1299, -1299, -4500, 20000, -129])
        check("import: fingerprints are the ones fingerprint_lines gives", [t.fingerprint for t in rows] == fingerprint_lines(1, MARCH))
        check("import: description has collapsed whitespace", rows[0].description == "PROBE GROCER #7")
        check("import: card, reference, section", (rows[0].card_last4, rows[0].external_id, rows[0].section, rows[3].section) == ("5512", "R1", "purchases", "payments_credits"))
        check("import: dates and cardholder", (rows[2].posted_date, rows[2].transaction_date, rows[2].cardholder, rows[0].transaction_date) == (date(2026, 3, 9), date(2026, 3, 7), "A PERSON", None))
        check("import: source, pending flag, statement link", all((t.source, t.is_pending, t.statement_id) == (DataSource.STATEMENT, False, stored.id) for t in rows))
        balance = latest_balance(session, 1)
        check("import: balance snapshot", (balance.as_of_date, balance.balance_cents, balance.source) == (MAR31, -37227, DataSource.STATEMENT))

    for label, options in [("again", {}), ("again as a dry run", {"dry_run": True}), ("again under another name", {"filename": "copy.pdf", "account_name": "Probe Card"})]:
        again = run("march", **options)
        expected = StatementImportResult(options.get("filename", "march.pdf"), ImportStatus.ALREADY_IMPORTED, "already imported")
        check(f"already imported: {label}", again == expected)
    check("already imported: nothing added", counts(engine) == (1, 5, 1))

    overlap = run("april", dry_run=True)
    check("overlap: dry run counts the duplicates", (overlap.status, overlap.inserted, overlap.duplicates) == (ImportStatus.DRY_RUN, 1, 2))
    overlap = run("april")
    check("overlap: only the new line is inserted", (overlap.status, overlap.lines_parsed, overlap.inserted, overlap.duplicates) == (ImportStatus.IMPORTED, 3, 1, 2))
    check("overlap: two statements, six transactions, two balances", counts(engine) == (2, 6, 2))
    with session_scope(engine) as session:
        april = list_statements(session, account_id=1)[0]
        check("overlap: statement counts", (april.period_end, april.lines_parsed, april.rows_inserted, april.rows_duplicate) == (APR30, 3, 1, 2))

    named = run("shared", account_name="  probe twin B ")
    check("named account: chosen among accounts that share digits", (named.status, named.account_name, named.inserted) == (ImportStatus.IMPORTED, "Probe Twin B", 1))
    plain = run("unknown4", account_name="Probe Plain")
    check("named account: one without digits accepts any statement", (plain.status, plain.account_name) == (ImportStatus.IMPORTED, "Probe Plain"))
    empty = run("checking")
    check("empty statement: imported with a balance and no rows", (empty.status, empty.account_name, empty.inserted) == (ImportStatus.IMPORTED, "Probe Checking", 0))

    before = counts(engine)
    session = Session(engine)
    kept = import_statement(session, filename="march2.pdf", content=pdf("march", "second copy"))
    session.rollback()
    session.close()
    check("import does not commit: result says duplicates", (kept.status, kept.inserted, kept.duplicates) == (ImportStatus.IMPORTED, 0, 5))
    check("import does not commit: rolled back", counts(engine) == before)


# ------------------------------------------------------------------- folder
def folder_checks(engine, root):
    inbox = root / "inbox"
    (inbox / "nested").mkdir(parents=True)
    (inbox / "b march copy.PDF").write_bytes(pdf("march", "folder b"))
    (inbox / "a checking.pdf").write_bytes(pdf("checking", "folder a"))
    (inbox / "c broken.pdf").write_bytes(b"not a pdf")
    (inbox / "d april copy.pdf").write_bytes(pdf("april", "folder d"))
    (inbox / "notes.txt").write_text("PROBE march")
    (inbox / "pdf").write_bytes(pdf("march", "no suffix"))
    (inbox / "nested" / "e.pdf").write_bytes(pdf("march", "nested"))
    before = counts(engine)
    dry = import_folder(engine, inbox, dry_run=True)
    check("folder: PDFs only, top level only, in name order", [r.filename for r in dry] == ["a checking.pdf", "b march copy.PDF", "c broken.pdf", "d april copy.pdf"])
    check("folder: dry run statuses", [r.status for r in dry] == [ImportStatus.DRY_RUN, ImportStatus.DRY_RUN, ImportStatus.FAILED, ImportStatus.DRY_RUN])
    check("folder: dry run writes nothing", counts(engine) == before)
    real = import_folder(engine, inbox)
    check("folder: a failure does not stop the rest", [r.status for r in real] == [ImportStatus.IMPORTED, ImportStatus.IMPORTED, ImportStatus.FAILED, ImportStatus.IMPORTED])
    check("folder: the failure's message", real[2] == StatementImportResult("c broken.pdf", ImportStatus.FAILED, "could not read PDF"))
    check("folder: counts per file", [(r.inserted, r.duplicates) for r in real] == [(0, 0), (0, 5), (0, 0), (0, 3)])
    check("folder: each file was committed", counts(engine)[0] == before[0] + 3)
    second = import_folder(engine, inbox)
    check("folder: a second run finds everything imported", [r.status for r in second] == [ImportStatus.ALREADY_IMPORTED, ImportStatus.ALREADY_IMPORTED, ImportStatus.FAILED, ImportStatus.ALREADY_IMPORTED])
    (root / "empty").mkdir()
    check("folder: empty folder", import_folder(engine, root / "empty") == [])


section("domain", domain_checks)
saved = registered_parsers()
try:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder).resolve()
        url = f"sqlite:///{(root / 'probe.db').as_posix()}"
        upgrade_to_head(url)
        engine = get_engine(url)
        with session_scope(engine) as session:
            create_account(session, "Probe Card", "Probe Bank", "credit_card", last4="9001")
            create_account(session, "Probe Checking", "Probe Bank", "checking", last4="0042")
            create_account(session, "Probe Plain", "Probe Bank", "savings")
            create_account(session, "Probe Twin A", "Probe Bank", "credit_card", last4="3003")
            create_account(session, "Probe Twin B", "Probe Bank", "credit_card", last4="3003")
        section("repositories", lambda: repository_checks(engine))
        register(ProbeParser())
        section("service", lambda: service_checks(engine))
        section("folder", lambda: folder_checks(engine, root))
        engine.dispose()
        left = sorted(path.name for path in root.iterdir())
        check(f"nothing unexpected was written {left}", left == ["empty", "inbox", "probe.db"])
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)
finally:
    for parser in registered_parsers():
        unregister(parser.name)
    for parser in saved:
        register(parser)


def public(module):
    return sorted(name for name, value in vars(module).items() if getattr(value, "__module__", "") == module.__name__ and not name.startswith("_"))


check(f"service: public names {public(service)}", public(service) == ["ImportStatus", "StatementImportResult", "import_folder", "import_statement"])
check("service: ImportStatus values", [(m.name, m.value) for m in ImportStatus] == [("IMPORTED", "imported"), ("DRY_RUN", "dry_run"), ("ALREADY_IMPORTED", "already_imported"), ("FAILED", "failed")])
check("service: result fields", [f.name for f in dataclasses.fields(StatementImportResult)] == ["filename", "status", "message", "parser_name", "account_name", "period_start", "period_end", "lines_parsed", "inserted", "duplicates"])
new_in_repositories = sorted(set(public(repositories)) - {"AccountExistsError", "create_account", "find_accounts_by_last4", "get_account_by_name", "list_accounts"})
check(f"repositories: new public names {new_in_repositories}", new_in_repositories == ["add_balance_snapshot", "create_statement", "existing_fingerprints", "find_statement_by_hash", "insert_transactions", "latest_balance", "list_statements", "list_transactions"])
new_in_orm = sorted(set(public(orm)) - {"AccountRow", "Base", "to_account"})
check(f"orm: new public names {new_in_orm}", new_in_orm == ["BalanceSnapshotRow", "StatementRow", "TransactionRow", "to_balance_snapshot", "to_statement", "to_transaction"])
new_in_models = sorted(set(public(models)) - {"Account", "AccountType", "validate_last4"})
check(f"models: new public names {new_in_models}", new_in_models == ["BalanceSnapshot", "DataSource", "NewTransaction", "Statement", "Transaction"])
print("FAILURES", failures)
```

## 5. The coder's tests

Read the four test files the coder wrote.

- **Coverage of requirements.** For each of R1 to R7 and R11 to R32, name a test that would fail if the requirement were broken. A requirement with no such test is a finding, even when the code is correct. The coder's final message lists its own mapping; check it, do not trust it.
- **Assertions are exact.** Messages are compared with `==` against the full text. Whole results are compared, not only the status. No `assert True`, no `pytest.raises(Exception)`, no `skip` or `xfail`, and no expected value produced by calling the function under test (computing an expected fingerprint with `fingerprint_lines` is fine: that function belongs to an earlier phase).
- **Real inputs.** Service tests pass real PDF bytes from `fake_statement_pdf` or `make_pdf`. `extract_pages`, `detect_parser`, `reconcile`, and the repositories are not patched or mocked.
- **Database.** Integration tests use `db_engine`. `git grep -n "create_all" -- tests` prints nothing.
- **Isolation.** Every test that needs a parser uses `fake_bank` or `parser_registry`. After the full run, `.venv/bin/python -c "from finances.ingest.parsers import registered_parsers; print(registered_parsers())"` prints `[]`.
- **Layers and data.** Unit tests are under `tests/unit/` and open no database. Integration tests are under `tests/integration/`. All data is invented, and nothing reads `data/`.
- **Spot checks.** For each change below, say which of the coder's tests would fail, by reading the test. If none would, that is a finding.
  1. `existing_fingerprints` drops the `account_id` condition.
  2. `add_balance_snapshot` updates the existing row's balance instead of leaving it.
  3. `insert_transactions` calls `session.commit()`.
  4. `list_transactions` uses `<` for `end`.
  5. `import_statement` writes during a dry run.
  6. `import_statement` skips the reconcile stage.
  7. `import_statement` stores `filename` as given, with its folders.
  8. `import_folder` looks into subfolders.

## 6. Project rules that apply to this phase

- **Money.** Every amount and balance column is `BigInteger`, and every amount field is `int`.
- **Layering.** `git grep -n -E "^(from|import) finances" -- src/finances/domain` prints nothing. `git grep -n "finances.ingest" -- src/finances/db` prints nothing.
- **Portable SQL.** `git grep -n --untracked -E "text\(|exec_driver_sql|PRAGMA|sqlite" -- src/finances/db/repositories.py src/finances/ingest/service.py` prints nothing.
- **Migrations.** Exactly one new file under `versions/`. It does not import `finances`.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- Any change under `src/finances/cli/`, or a new command.
- A parameter that lets an unreconciled statement through (`allow_mismatch`, `force`, or similar), or a `reconciled` column.
- Any function that updates or deletes statements, transactions, or snapshots.
- Any production code that writes `DataSource.AGGREGATOR` or `is_pending=True`.
- A parser class under `src/`, or a call to `register` outside tests.
- New dependencies in `pyproject.toml`.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 3c: storing and importing statements (YYYY-MM-DD)` with a real date. "Built" gives the passed count. "Deviations" lists the coder's design choices; each must be inside the spec's Scope and must not change a public name, a signature, a message, a table definition, or a given file. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 / Part 2 / Part 3 / Part 4 / Part 5 / tests>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the call and its result, or the file and line), and what is required. Do not prescribe the code. For a missing test, name the requirement and say that a test must fail when it is broken. Ask for the acceptance commands to be run again after the fix.
