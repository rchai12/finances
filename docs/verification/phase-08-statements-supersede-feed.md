# Verify Phase 8: statements supersede feed rows

Spec: `docs/phases/phase-08-statements-supersede-feed.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote a pure matcher (`src/finances/domain/matching.py`), five repository functions, and changes to two services: `import_statement` now upgrades and drops feed rows, and `apply_feed` now links a late feed row to its statement row or leaves it out. Two test files were given; the coder wrote one.

Judge the code by what it stores and returns and by the rules, never by how it is written. These are all correct and must not be reported:

- any algorithm in `match_one_to_one` that gives the pairs R1 to R3 describe;
- any private helpers, and any division of the two services;
- looking up statement rows for a feed transaction with one query per transaction;
- any SQLAlchemy 2.0 query in the repository functions that gives the specified result.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it; it is `1228` when Phase 17a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 49 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_matching.py tests/integration/test_statement_supersedes.py --no-cov` | exactly `49 passed` |
| `.venv/bin/python -m pytest tests/integration/test_import_service.py tests/integration/test_feed_service.py --no-cov` | 0 failed: the earlier behavior of both services still holds |
| the coverage command below | `Required test coverage of 100% reached`, with `domain/matching.py`, `db/repositories.py`, `ingest/service.py`, and `sync/service.py` at 100% |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov=finances.db --cov=finances.domain --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/db/repositories.py
 M src/finances/ingest/service.py
 M src/finances/sync/service.py
?? src/finances/domain/matching.py
?? tests/integration/test_statement_supersedes.py
?? tests/integration/test_supersede_repositories.py
?? tests/unit/test_matching.py
```

- The two given test files are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- src/finances/db/repositories.py` only adds lines, apart from import lines that gained a name. No existing function is changed.
- `git diff HEAD --stat -- src/finances/cli src/finances/db/orm.py src/finances/db/migrations src/finances/domain/models.py src/finances/sync/feed.py src/finances/ingest/dedup.py src/finances/ingest/parsers tests/conftest.py pyproject.toml` is empty, and no existing test file is changed. There is no new migration.
- In `StatementImportResult`, the only change is the two fields `upgraded: int = 0` and `dropped: int = 0` after `duplicates`.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 to R4 | the matcher | probe script; given matcher tests in gate 4 | every line starting `matcher:` |
| R5 to R9 | repository functions | the coder's tests (section 5); probe script | every line starting `repositories:` |
| R10, R11 | candidates and matching | probe script | `feed first: one line inserted, five upgraded, one feed row dropped` |
| R12 | upgrade in place | probe script | the lines starting `feed first: upgraded rows`, `feed first: they carry`, and `feed first: card digits` |
| R13, R14 | inserts and drops | probe script | `feed first: the row the statement does not print is gone`, `feed first: rows outside the period and holds are untouched`, and `edges: unmatched feed rows on the first and last day are dropped, the days around are kept` |
| R15 | pending rows | probe script | `feed first: rows outside the period and holds are untouched` |
| R16, R17 | counts and dry run | probe script | `dry run: the counts, and nothing written` |
| R18 | the statement row for a late feed row | probe script | `edges: a late feed row takes the closest statement row, up to five days away` |
| R19 | link or leave out | probe script | every line starting `statement first:`, plus `edges: the first and last day of a period are covered, the days around it are not` and the two lines starting `holds:` |
| R20 | settled once | given test `test_a_posted_feed_row_is_settled_only_when_it_first_arrives` in gate 4 | passes |
| R21 | totals | probe script | `statement first: posted total counts linked rows only` |
| R22 | the same feed twice | probe script | `feed first: the same feed again inserts nothing` and `statement first: the same feed again inserts nothing` |
| R23 | either order | probe script | `order: both orders end with the same ledger` |
| accounts | no crossing | probe script | the two lines starting `accounts:` |
| duplicates | a stored line claims no feed row | given test `test_lines_already_stored_are_duplicates_and_claim_no_feed_row` in gate 4 | passes |
| layering | services use repositories only | read the imports of both services | no ORM class, no `select`; `ingest` does not import `sync`, and `sync` does not import `ingest` |
| deletion | only feed rows | read both services | the only deletion is `delete_feed_transaction`; no statement row is updated by `apply_feed` |

Run each of these searches. Each must print nothing.

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/domain/matching.py src/finances/sync`

`git grep -n --untracked -E "^ *(import|from) +(finances|sqlalchemy)" -- src/finances/domain/matching.py`

`git grep -n --untracked -E "finances\.(ingest|cli)" -- src/finances/sync src/finances/db src/finances/domain`

`git grep -n --untracked -E "finances\.sync" -- src/finances/ingest src/finances/db src/finances/domain`

## 4. Independent probes

The script registers its own made-up statement format, so it needs no real bank layout, and builds its own PDF. It tells the same story twice on fresh databases, once with the feed first and once with the statement first, and compares the two ledgers. It then checks a dry run, holds that post after their statement, a second account, and the first and last day of a period. None of its names, ids, or amounts are in the given tests or the spec.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Each database it uses is a file in a temporary directory that it removes, and it unregisters its parser. Every line must end in `ok`; the last line must be `FAILURES 0`. A line that says a section `ran to the end (stopped by ...)` and ends in `FAIL` means the code raised where it should not have; report it with the exception named on that line.

```python
import dataclasses
import tempfile
from datetime import date
from pathlib import Path

from sqlalchemy import select

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


def july(number):
    return date(2027, 7, number)


class ProbeBank:
    """A made-up statement format: one line per fact, so the probe needs no real bank layout."""

    name = "probe_bank"

    def detect(self, first_page):
        return first_page.lstrip().startswith("PROBEBANK")

    def parse(self, pages):
        from finances.domain.models import AccountType
        from finances.ingest.statement import ParsedStatement, Section, StatementLine

        fields, rows = {}, []
        for line in (line.strip() for page in pages for line in page.splitlines()):
            keyword, _, rest = line.partition(" ")
            if keyword == "ROW":
                day, cents, card, text = rest.split("|", 3)
                kind = Section.PAYMENTS_CREDITS if int(cents) > 0 else Section.PURCHASES
                rows.append(StatementLine(july(int(day)), None, text, int(cents), kind, card_last4=card or None))
            elif keyword:
                fields[keyword] = rest
        start, end = (int(part) for part in fields["PERIOD"].split())
        return ParsedStatement("probe_bank", "Probe Bank", AccountType.CREDIT_CARD, fields["ACCOUNT"], july(start), july(end), int(fields["OPENING"]), int(fields["OPENING"]) + sum(row.amount_cents for row in rows), rows)


def build_pdf(lines):
    operators = ["BT", "/F1 8 Tf"]
    for index, text in enumerate(lines):
        text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        operators.append(f"1 0 0 1 40 {760 - 11 * index} Tm ({text}) Tj")
    operators.append("ET")
    stream = "\n".join(operators).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [5 0 R] /Count 1 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 4 0 R >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


def statement_pdf(start, end, rows, last4="8080"):
    lines = ["PROBEBANK", f"ACCOUNT {last4}", f"PERIOD {start} {end}", "OPENING -50000"]
    return build_pdf(lines + [f"ROW {day}|{cents}|{card}|{text}" for day, cents, text, card in rows])


def run(body):
    """Call body(session) on a new migrated database with two accounts and the probe parser registered."""
    from finances.db.engine import get_engine, session_scope
    from finances.db.migrate import upgrade_to_head
    from finances.db.repositories import create_account
    from finances.ingest.parsers import register, unregister

    parser = ProbeBank()
    register(parser)
    try:
        with tempfile.TemporaryDirectory() as folder:
            url = f"sqlite:///{(Path(folder) / 'probe.db').as_posix()}"
            upgrade_to_head(url)
            engine = get_engine(url)
            try:
                with session_scope(engine) as session:
                    create_account(session, "Probe Card", "Probe Bank", "credit_card", last4="8080")
                    create_account(session, "Probe Other", "Probe Bank", "credit_card", last4="9191")
                    body(session)
            finally:
                engine.dispose()
    finally:
        unregister(parser.name)


def ledger(session, account_id=1):
    from finances.db.orm import FeedItemRow, TransactionRow

    stmt = (
        select(TransactionRow, FeedItemRow.feed_id)
        .outerjoin(FeedItemRow, FeedItemRow.transaction_id == TransactionRow.id)
        .where(TransactionRow.account_id == account_id)
        .order_by(TransactionRow.id)
    )
    return [(row.id, feed_id, row.posted_date.day, row.amount_cents, row.description, row.source, row.is_pending) for row, feed_id in session.execute(stmt).all()]


ROWS = [
    (6, -1875, "PROBE BAKERY #7", "8080"),
    (6, -1875, "PROBE BAKERY #7", "8080"),
    (9, -5230, "PROBE FUEL 0042", ""),
    (14, 40000, "PROBE PAYMENT RECEIVED", ""),
    (22, -18840, "PROBE HOTEL", "8080"),
    (25, -999, "PROBE STREAMING", ""),
]


def delivered():
    from finances.sync.feed import AccountFeed, FeedTransaction

    return AccountFeed([
        FeedTransaction("t-1", july(5), -1875, "Probe Bakery"),
        FeedTransaction("t-2", july(7), -1875, "Probe Bakery", card_last4="7007"),
        FeedTransaction("t-3", july(9), -5230, "Probe Fuel", transaction_date=july(8), card_last4="6116"),
        FeedTransaction("t-4", july(17), 40000, "Payment"),
        FeedTransaction("t-5", july(27), -18840, "Probe Hotel"),
        FeedTransaction("t-6", july(12), -4444, "Probe Not Printed"),
        FeedTransaction("t-7", july(28), -2222, "Probe After The Period"),
        FeedTransaction("t-8", july(4), -999, "Probe Too Far Before"),
        FeedTransaction("t-9", july(20), -3333, "Probe Hold", is_pending=True),
    ])


WANT = sorted([
    (6, -1875, "PROBE BAKERY #7", "statement", False), (6, -1875, "PROBE BAKERY #7", "statement", False),
    (9, -5230, "PROBE FUEL 0042", "statement", False), (14, 40000, "PROBE PAYMENT RECEIVED", "statement", False),
    (22, -18840, "PROBE HOTEL", "statement", False), (25, -999, "PROBE STREAMING", "statement", False),
    (28, -2222, "Probe After The Period", "aggregator", False), (4, -999, "Probe Too Far Before", "aggregator", False),
    (20, -3333, "Probe Hold", "aggregator", True),
])


def matcher_checks():
    from finances.domain import matching
    from finances.domain.matching import MATCH_MAX_DAYS, MatchItem, match_one_to_one

    def item(key, cents, day):
        return MatchItem(key, cents, july(day))

    check("matcher: the reach is five days", MATCH_MAX_DAYS == 5)
    check("matcher: MatchItem fields in order, frozen", [field.name for field in dataclasses.fields(MatchItem)] == ["key", "amount_cents", "day"] and MatchItem.__dataclass_params__.frozen)
    check("matcher: five days apart pairs, six does not", match_one_to_one([item(1, 700, 10)], [item(2, 700, 15)]) == [(1, 2)] and match_one_to_one([item(1, 700, 10)], [item(2, 700, 16)]) == [])
    check("matcher: amounts must be equal", match_one_to_one([item(1, 700, 10)], [item(2, -700, 10), item(3, 701, 10)]) == [])
    left = [item(11, 700, 10), item(12, 700, 12), item(13, 900, 12)]
    right = [item(21, 900, 9), item(22, 700, 13), item(23, 700, 12), item(24, 700, 6)]
    check("matcher: closest first, each used once, in the order of the left list", match_one_to_one(left, right) == [(11, 22), (12, 23), (13, 21)])
    check("matcher: a tie goes to the earlier left item, then the earlier right item", match_one_to_one([item(1, 5, 9), item(2, 5, 11)], [item(8, 5, 10)]) == [(1, 8)] and match_one_to_one([item(1, 5, 10)], [item(8, 5, 11), item(9, 5, 9)]) == [(1, 8)])
    check("matcher: the closest day wins over the first listed", match_one_to_one([item(1, 5, 10)], [item(8, 5, 14), item(9, 5, 11)]) == [(1, 9)])
    check("matcher: a given reach", match_one_to_one([item(1, 5, 1)], [item(2, 5, 3)], max_days=1) == [] and match_one_to_one([item(1, 5, 1)], [item(2, 5, 3)], 2) == [(1, 2)])
    public = sorted(name for name, value in vars(matching).items() if getattr(value, "__module__", "") == matching.__name__ and not name.startswith("_"))
    check(f"matcher: public names {public}", public == ["MatchItem", "match_one_to_one"])
    source = Path(matching.__file__).read_text(encoding="utf-8")
    check("matcher: the module imports nothing from the project", "finances" not in source and "sqlalchemy" not in source)


def order_checks():
    from finances.ingest.service import import_statement
    from finances.sync.service import apply_feed

    content = statement_pdf(6, 25, ROWS)
    found = {}

    def feed_first(session):
        pull = apply_feed(session, 1, delivered())
        check("feed first: nine rows stored as provisional", (pull.inserted, len(ledger(session))) == (9, 9))
        ids = {entry[1]: entry[0] for entry in ledger(session)}
        result = import_statement(session, filename="july.pdf", content=content)
        check("feed first: the statement is imported", getattr(result, "message", None) == "imported")
        check("feed first: one line inserted, five upgraded, one feed row dropped", (result.inserted, result.upgraded, result.dropped, result.duplicates, result.lines_parsed) == (1, 5, 1, 0, 6))
        after = {entry[1]: entry for entry in ledger(session) if entry[1]}
        check("feed first: upgraded rows keep their ids and feed ids", all(after[name][0] == ids[name] for name in ("t-1", "t-2", "t-3", "t-4", "t-5")))
        check("feed first: they carry the statement's day and text", (after["t-5"][2], after["t-5"][4], after["t-5"][5]) == (22, "PROBE HOTEL", "statement") and (after["t-4"][2], after["t-4"][4]) == (14, "PROBE PAYMENT RECEIVED"))
        check("feed first: the row the statement does not print is gone", "t-6" not in after)
        check("feed first: rows outside the period and holds are untouched", [(after[name][5], after[name][6]) for name in ("t-7", "t-8", "t-9")] == [("aggregator", False), ("aggregator", False), ("aggregator", True)])
        from finances.db.orm import TransactionRow
        bakery = session.get(TransactionRow, ids["t-2"])
        fuel = session.get(TransactionRow, ids["t-3"])
        check("feed first: card digits and purchase date the statement lacks are kept from the feed", (bakery.card_last4, fuel.transaction_date, fuel.card_last4) == ("8080", july(8), "6116"))
        check("feed first: upgraded rows point at the statement", bakery.statement_id == 1 and bakery.section == "purchases" and len(bakery.fingerprint) == 64)
        from finances.sync.feed import feed_fingerprint
        check("feed first: upgraded rows carry the statement's fingerprint, not the feed's", bakery.fingerprint != feed_fingerprint(1, "t-2") and fuel.fingerprint != feed_fingerprint(1, "t-3"))
        again = apply_feed(session, 1, delivered())
        check("feed first: the same feed again inserts nothing", (again.inserted, again.updated, again.removed, again.unchanged) == (0, 0, 0, 9))
        found["feed first"] = sorted(entry[2:] for entry in ledger(session))
        check("feed first: the final ledger", found["feed first"] == WANT)

    def statement_first(session):
        result = import_statement(session, filename="july.pdf", content=content)
        check("statement first: six lines inserted", (result.inserted, result.upgraded, result.dropped) == (6, 0, 0))
        before = [entry[0:1] + entry[2:] for entry in ledger(session)]
        pull = apply_feed(session, 1, delivered())
        check("statement first: three rows inserted, six left as they are", (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (3, 0, 0, 6))
        check("statement first: the statement rows are unchanged", [entry[0:1] + entry[2:] for entry in ledger(session)][:6] == before)
        linked = sorted(entry[1] for entry in ledger(session) if entry[1] and entry[5] == "statement")
        check("statement first: five statement rows now carry feed ids", linked == ["t-1", "t-2", "t-3", "t-4", "t-5"])
        check("statement first: posted total counts linked rows only", pull.feed_total_cents == -1875 - 1875 - 5230 + 40000 - 18840 - 2222 - 999)
        again = apply_feed(session, 1, delivered())
        check("statement first: the same feed again inserts nothing", (again.inserted, again.updated, again.removed, again.unchanged) == (0, 0, 0, 9))
        found["statement first"] = sorted(entry[2:] for entry in ledger(session))
        check("statement first: the final ledger", found["statement first"] == WANT)

    run(feed_first)
    run(statement_first)
    check("order: both orders end with the same ledger", found.get("feed first") == found.get("statement first") == WANT)


def rule_checks():
    from finances.ingest.service import ImportStatus, import_statement
    from finances.sync.feed import AccountFeed, FeedTransaction
    from finances.sync.service import apply_feed

    def dry(session):
        apply_feed(session, 1, delivered())
        before = ledger(session)
        result = import_statement(session, filename="july.pdf", content=statement_pdf(6, 25, ROWS), dry_run=True)
        check("dry run: the counts, and nothing written", result.status is ImportStatus.DRY_RUN and (result.inserted, result.upgraded, result.dropped) == (1, 5, 1) and ledger(session) == before)

    def holds(session):
        apply_feed(session, 1, AccountFeed([FeedTransaction("h-1", july(8), -5230, "Hold One", True), FeedTransaction("h-2", july(21), -18000, "Hold Two", True), FeedTransaction("h-3", july(13), -4444, "Hold Three", True)]))
        import_statement(session, filename="july.pdf", content=statement_pdf(6, 25, ROWS))
        pull = apply_feed(session, 1, AccountFeed([FeedTransaction("h-1", july(9), -5230, "Posted One"), FeedTransaction("p-2", july(22), -18840, "Posted Two", replaces_feed_id="h-2"), FeedTransaction("h-3", july(13), -4444, "Posted Three")], ["h-2"]))
        check("holds: three holds that posted inside the period are removed", (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (0, 0, 3, 0))
        rows = ledger(session)
        check("holds: two statement rows took their feed ids, the third had no line", sorted(entry[1] for entry in rows if entry[1]) == ["h-1", "p-2"] and len(rows) == 6 and all(entry[5] == "statement" for entry in rows))

    def other_account(session):
        apply_feed(session, 2, AccountFeed([FeedTransaction("o-1", july(6), -1875, "Other Bakery"), FeedTransaction("o-2", july(12), -4444, "Other")]))
        result = import_statement(session, filename="july.pdf", content=statement_pdf(6, 25, ROWS))
        check("accounts: another account's feed rows are not upgraded or dropped", (result.inserted, result.upgraded, result.dropped) == (6, 0, 0) and [entry[5] for entry in ledger(session, 2)] == ["aggregator", "aggregator"])
        pull = apply_feed(session, 2, AccountFeed([FeedTransaction("o-3", july(9), -5230, "Other Fuel"), FeedTransaction("o-4", july(15), -1, "Other")]))
        check("accounts: another account's statement neither links nor blocks its feed", pull.inserted == 2 and all(entry[1] is None for entry in ledger(session, 1)))

    def edges(session):
        import_statement(session, filename="mid.pdf", content=statement_pdf(10, 20, [(12, -700, "PROBE MID", ""), (16, -700, "PROBE MID", "")]))
        pull = apply_feed(session, 1, AccountFeed([
            FeedTransaction("e-1", july(10), -1, "First Day"), FeedTransaction("e-2", july(20), -2, "Last Day"),
            FeedTransaction("e-3", july(9), -3, "Day Before"), FeedTransaction("e-4", july(21), -4, "Day After"),
            FeedTransaction("e-5", july(17), -700, "Closest To The Second Line"), FeedTransaction("e-6", july(7), -700, "Five Days Before The First Line"),
        ]))
        check("edges: the first and last day of a period are covered, the days around it are not", sorted(entry[1] for entry in ledger(session) if entry[5] == "aggregator") == ["e-3", "e-4"])
        check("edges: a late feed row takes the closest statement row, up to five days away", [(entry[2], entry[1]) for entry in ledger(session) if entry[5] == "statement"] == [(12, "e-6"), (16, "e-5")] and (pull.inserted, pull.unchanged) == (2, 4))

    def edges_feed_first(session):
        apply_feed(session, 1, AccountFeed([
            FeedTransaction("e-1", july(10), -1, "First Day"), FeedTransaction("e-2", july(20), -2, "Last Day"),
            FeedTransaction("e-3", july(9), -3, "Day Before"), FeedTransaction("e-4", july(21), -4, "Day After"),
        ]))
        result = import_statement(session, filename="mid.pdf", content=statement_pdf(10, 20, [(12, -700, "PROBE MID", "")]))
        check("edges: unmatched feed rows on the first and last day are dropped, the days around are kept", result.dropped == 2 and sorted(entry[1] for entry in ledger(session) if entry[1]) == ["e-3", "e-4"])

    run(dry)
    run(holds)
    run(other_account)
    run(edges)
    run(edges_feed_first)


def repository_checks():
    from finances.db import repositories

    def body(session):
        check("repositories: no provisional rows, no unlinked rows, nothing covered", repositories.list_provisional_transactions(session, 1, july(1), july(31)) == [] and repositories.find_unlinked_statement_transactions(session, 1, -1, july(1), july(31)) == [] and repositories.statement_covers(session, 1, july(15)) is False)
        got = outcome(repositories.confirm_transaction, session, 404, statement_id=1, posted_date=july(1), transaction_date=None, description="x", section=None, card_last4=None, cardholder=None, external_id=None, fingerprint="f" * 64)
        check("repositories: confirming an unknown transaction", got == ("ValueError", "transaction not found"))

    run(body)


section("matcher", matcher_checks)
section("order", order_checks)
section("rules", rule_checks)
section("repositories", repository_checks)
print("FAILURES", failures)
```

## 5. The coder's tests

Read `tests/integration/test_supersede_repositories.py`.

- **Coverage of requirements.** For each of R1 to R23, name a test, given or the coder's, that would fail if the requirement were broken. A requirement with no such test is a finding. The coder's final message lists its own mapping; check it, do not trust it.
- **Repository tests go through the functions.** Each of R5 to R9 has a test that calls the function directly and compares what it returns or stores. A function reached only through a service is a finding.
- **Assertions are exact.** No `assert True`, no `pytest.raises(Exception)`, no `skip` or `xfail`, and no expected value produced by calling the code under test.
- **Synthetic data.** Invented merchants, ids, and amounts.
- **Spot checks.** For each change below, say which test, given or the coder's, would fail, by reading the test. If none would, that is a finding.
  1. `list_provisional_transactions` returns pending rows.
  2. `list_provisional_transactions` leaves out a row dated on `end`.
  3. `confirm_transaction` leaves `source` as `aggregator`.
  4. `confirm_transaction` deletes the row's `feed_items` row.
  5. `find_unlinked_statement_transactions` returns a row that already has a feed id.
  6. `find_unlinked_statement_transactions` returns rows of another account.
  7. `statement_covers` is false on the last day of a period.
  8. `statement_covers` is true for another account's statement.
  9. `import_statement` drops an unmatched feed row dated the day after the period ends.
  10. `apply_feed` stores a late feed row that is inside a statement's period and has no line.

## 6. Project rules that apply to this phase

- **Money.** Integer cents, compared exactly; the first search in section 3 finds no `float`.
- **Privacy.** No network import, nothing logged, and no exception carries statement or feed content.
- **Layering.** `domain/matching.py` imports nothing from the project (second search). `sync` and `ingest` do not import each other (third and fourth searches).
- **Schema.** No migration and no ORM change (section 2).

## 7. Out of scope

Each of these must be absent. Report any that is present.

- Any change under `src/finances/cli/`, or any printed output of the new counts.
- A comparison of descriptions, merchants, or card digits in the matcher or the services.
- Matching between two accounts.
- A new table, column, or migration.
- Settling posted aggregator rows again on a later pull.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 8: statements supersede feed rows (YYYY-MM-DD)` with a real date. "Built" gives N and the passed count. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 to Part 5 / tests>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code.
