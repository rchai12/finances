# Verify Phase 11a: categories, merchants, and rules

Spec: `docs/phases/phase-11a-categories-and-rules.md`

Do not modify any file in the repository, and do not run `fin` against the real database in `data/`. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder added migration `0008` (categories seeded with a default tree, rules, assignments), a merchant-cleaning function, a rule picker, repository functions, a `categorize` service, views, and the commands `fin categories`, `fin rules`, `fin categorize`, `fin uncategorized`, and `fin transactions set-category`; imports and syncs now categorize quietly. Four test files and the migration were given; two test files are the coder's.

Judge the code by what it does. These are correct and must not be reported: regular expressions written differently, as long as R1's steps give the same results; one session or several in a command; how `categorize` stores its counts.

## 1. Gates

Run each command on its own line from the repository root. Do not activate the virtual environment.

**N** is the passed count before the phase; the coder's entry in `docs/progress.md` states it. It is `2060` when Phase 23 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 98 passed in the `tests` step, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_merchants.py tests/unit/test_category_rules.py tests/integration/test_migration_0008.py tests/e2e/test_cli_categories.py --no-cov` | exactly `98 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| `git diff HEAD --stat -- tests src/finances/db/migrations/versions/000[1-7]*` | nothing |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.categorize --cov=finances.domain --cov=finances.db --cov=finances.views --cov=finances.cli --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` shows only the paths of the spec's Scope table. Report every other one.
- The migration and the four given test files are identical to the blocks in the spec.
- No existing test and no earlier migration changed (gate 4).

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | merchant cleaning | probe; gate 2 | `merchants: ...` |
| R2 to R4 | rules | probe; gate 2 | every line starting `rules:` |
| R5 to R13 | the database | gate 2; section 5 | the coder's repository tests cover each item of the spec's list |
| R12 | a categorized feed row dropped | probe | every line starting `feed:` and `statement:` |
| R14, R15 | categorizing | probe; gate 2 | every line starting `commands:` |
| R16 to R23 | the commands | gate 2 (`tests/e2e/test_cli_categories.py`); probe | passes |

Run each of these searches. Each must print nothing.

`git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain`

`git grep -n --untracked -E "select\(|session\.(add|execute|delete)|pick_rule|clean_merchant\(" -- src/finances/cli`

## 4. Independent probe

The script uses a temporary data folder that it removes. It cleans new synthetic descriptions, picks rules, drives the new commands through Typer's runner, and then applies a feed and imports a statement through the real services with a parser it registers for the run (removed afterwards): one categorized feed row is upgraded by the statement and one is dropped. It contacts nothing.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import os
import tempfile
from datetime import date

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


def merchants():
    from finances.domain.merchants import clean_merchant

    cases = {
        "DEBIT CARD PURCHASE TST* PROBE NOODLES 11-02 OAKVILLE": "PROBE NOODLES",
        "PROBE HARDWARE #4471 SPRINGFIELD IL": "PROBE HARDWARE",
        "paypal *probe   tunes": "PROBE TUNES",
        "PROBE BAKERY 312-555-0199": "PROBE BAKERY",
        "PROBE TRANSIT 9876543210": "PROBE TRANSIT",
        "ATM WITHDRAWAL REF#X1": "ATM WITHDRAWAL",
    }
    found = {text: clean_merchant(text) for text in cases}
    check("merchants: new descriptions are cleaned as specified", found == cases)


def rules():
    from finances.domain.models import CategoryRule
    from finances.domain.rules import pick_rule

    rules = [
        CategoryRule(4, "NOODLES", "contains", 0, 13),
        CategoryRule(2, "PROBE", "starts_with", 0, 14),
        CategoryRule(9, "PROBE NOODLES", "equals", 0, 15),
    ]
    check(
        "rules: equal priorities go to the lowest id", pick_rule("probe noodles", rules) == rules[1]
    )
    rules.append(CategoryRule(11, "PROBE NOODLES", "equals", 1, 16))
    check("rules: a higher priority wins", pick_rule("PROBE NOODLES", rules) == rules[3])


def commands():
    from typer.testing import CliRunner

    from finances.cli.main import app
    from finances.db.engine import get_engine, session_scope
    from finances.db.orm import TransactionRow
    from finances.db.repositories import create_account

    runner = CliRunner(env={"COLUMNS": "200"})

    def run(*args):
        return runner.invoke(app, [str(a) for a in args])

    run("db", "upgrade")
    engine = get_engine()
    with session_scope(engine) as session:
        account = create_account(session, "Probe Checking", "Probe Bank", "checking", last4="5050")
        for day, cents, text in (
            (10, -1250, "TST* PROBE NOODLES"),
            (11, -890, "PROBE NOODLES #2"),
            (12, 250000, "PROBE PAYROLL"),
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2027, 3, day),
                    amount_cents=cents,
                    description=text,
                    source="statement",
                    fingerprint=f"n{day}".ljust(64, "0"),
                )
            )
    engine.dispose()
    listed = run("categories", "list")
    check(
        "commands: the default tree has 34 categories in 12 groups",
        listed.exit_code == 0 and listed.stdout.count("\n") > 34,
    )
    added = run("rules", "add", "--pattern", "probe noodles", "--category", "Dining")
    check(
        "commands: a rule categorizes past transactions at once",
        added.stdout
        == 'Added rule 1: contains "PROBE NOODLES" -> Dining.\nCategorized 3 transactions: 2 changed, 1 without a category.\n',
    )
    hand = run("transactions", "set-category", "--id", "1", "--category", "Groceries")
    again = run("categorize")
    check(
        "commands: a category set by hand survives categorizing",
        hand.stdout == "Transaction 1: Groceries, set by hand.\n"
        and again.stdout == "Categorized 3 transactions: 0 changed, 1 without a category.\n",
    )
    left = run("uncategorized")
    check(
        "commands: only the payroll is left uncategorized",
        "PROBE PAYROLL" in left.stdout and "NOODLES" not in left.stdout,
    )


def feed_then_statement():
    import finances.ingest.service as ingest
    from finances.categorize.service import categorize
    from finances.db.engine import get_engine, session_scope
    from finances.db.repositories import create_account, create_rule, list_category_assignments
    from finances.domain.models import AccountType
    from finances.ingest.parsers import register, unregister
    from finances.ingest.statement import ParsedStatement, Section, StatementLine
    from finances.sync.feed import AccountFeed, FeedTransaction
    from finances.sync.service import apply_feed

    class Parser:
        name = "probe_eleven"

        def detect(self, first_page):
            return first_page == "PROBE ELEVEN"

        def parse(self, pages):
            line = StatementLine(date(2027, 4, 3), None, "PROBE NOODLES", -1250, Section.PURCHASES)
            return ParsedStatement(
                self.name,
                "Probe Bank",
                AccountType.CREDIT_CARD,
                "6060",
                date(2027, 4, 1),
                date(2027, 4, 30),
                0,
                -1250,
                [line],
            )

    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Probe Card", "Probe Bank", "credit_card", last4="6060")
        feed = AccountFeed(
            [
                FeedTransaction("F1", date(2027, 4, 4), -1250, "PROBE NOODLES"),
                FeedTransaction("F2", date(2027, 4, 9), -777, "PROBE NOODLES"),
            ]
        )
        apply_feed(session, card.id, feed)
        create_rule(session, "NOODLES", "Dining")
        categorize(session)
        before = list_category_assignments(session)
    ingest.extract_pages = lambda content: [content.decode()]
    register(Parser())
    try:
        with session_scope(engine) as session:
            result = ingest.import_statement(session, filename="april.pdf", content=b"PROBE ELEVEN")
            after = list_category_assignments(session)
    finally:
        unregister("probe_eleven")
        engine.dispose()
    check(
        "feed: both feed rows were categorized",
        len([a for a in before.values() if a.category_id]) >= 2,
    )
    check(
        "statement: one feed row is upgraded and the other dropped, without an error",
        result.status.value == "imported" and (result.upgraded, result.dropped) == (1, 1),
    )
    upgraded = [a for a in after.values()]
    check(
        "statement: the upgraded row keeps its category, the dropped row's category is gone",
        len(upgraded) == len(before) - 1,
    )


try:
    for name, step in (
        ("merchants", merchants),
        ("rules", rules),
        ("commands", commands),
        ("feed", feed_then_statement),
    ):
        section(name, step)
finally:
    if saved is None:
        os.environ.pop("FIN_DATA_DIR", None)
    else:
        os.environ["FIN_DATA_DIR"] = saved
    folder.cleanup()
print("FAILURES", failures)
```

## 5. The coder's tests

- `tests/integration/test_category_repositories.py` and `tests/integration/test_categorize_service.py` exist and cover every item of the spec's "Tests to write". A missing item is a finding.
- No `assert True`, no blanket `pytest.raises(Exception)`, no `skip` or `xfail`; messages are asserted in full; synthetic data only.
- Spot checks. For each change below, say which test would fail, by reading the tests. If none would, that is a finding.
  1. `categorize` overwrites a manual assignment.
  2. `delete_rule` removes every assignment, not only that rule's.
  3. `create_rule` stores the pattern as typed instead of normalized.
  4. `delete_feed_transaction` leaves the assignment. (The probe's `statement:` lines must also fail.)
  5. `fin sync run` prints the categorizing line.

## 6. Out of scope

Each of these must be absent. Report any that is present.

- Web pages for categories or rules; transfer pairing; refunds.
- Renaming or deleting categories; a stored merchants table.
- A change to `fin transactions list` output or to `scripts/critical_modules.txt`.

## 7. Progress log

`docs/progress.md` ends with an entry headed `## Phase 11a: categories, merchants, and rules (YYYY-MM-DD)` with a real date, N, and the passed count.

## Verdict

`PASS`, or `FAIL` followed by one line per finding:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from the tests step>`

`Parts that needed a repair: <none, or Part 1 to Part 5>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement, what was observed, and what is required. Do not prescribe the code.
