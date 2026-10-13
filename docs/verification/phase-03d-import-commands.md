# Verify Phase 3d: the import commands

Spec: `docs/phases/phase-03d-import-commands.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote three new modules under `src/finances/cli/` (`common.py`, `importing.py`, `listing.py`), registered three command groups in `main.py`, and replaced two inline checks in `accounts.py`. Both test files were given, and they fix the exact text of every command.

Judge the commands by what they print and how they exit, never by how they are written. These are all correct and must not be reported:

- private helpers and module-level constants of any shape in the three new modules;
- one helper shared by both list commands, or separate code in each;
- a status text table, or `if` statements, for the four status texts;
- building a table with a loop over headings or with one `add_column` call per heading.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, 0 failed, 0 skipped, 0 xfailed, no warnings summary, `Required test coverage of 85.0% reached`, and a passed count at least 41 above the count the coder recorded as N in `docs/progress.md` |
| `.venv/bin/python -m pytest tests/e2e/test_cli_import.py tests/e2e/test_cli_listing.py --no-cov` | exactly `41 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with every file under `src/finances/cli/` at 100% |
| `.venv/bin/fin --help` | lists `doctor`, `db`, `accounts`, `import`, `statements`, and `transactions` |

`.venv/bin/python -m pytest tests/e2e tests/unit/test_diagnostics.py -o addopts="" --import-mode=importlib --cov=finances.cli --cov=finances.diagnostics --cov-branch --cov-report=term-missing --cov-fail-under=100`

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths, plus `tests/e2e/test_cli_import_more.py` if the coder needed it. Report every other one.

```
 M docs/progress.md
 M src/finances/cli/accounts.py
 M src/finances/cli/main.py
?? src/finances/cli/common.py
?? src/finances/cli/importing.py
?? src/finances/cli/listing.py
?? tests/e2e/test_cli_import.py
?? tests/e2e/test_cli_listing.py
```

- The two given test files are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- src/finances/cli/accounts.py` removes the two inline revision checks and the import they needed, adds two calls to `require_current_schema` and its import, and changes nothing else: every option, help text, and printed text is as before.
- `git diff HEAD -- src/finances/cli/main.py` adds imports and three `add_typer` calls, and changes nothing else.
- `git diff HEAD -- src/finances/ingest src/finances/db src/finances/domain src/finances/config.py src/finances/diagnostics.py src/finances/cli/db.py pyproject.toml tests/conftest.py tests/unit tests/integration tests/fixtures tests/real_samples` is empty, and so is `git diff HEAD -- tests/e2e/test_cli.py tests/e2e/test_cli_accounts.py`.
- `git status --short --ignored` shows no `.db`, `.sqlite`, or `.pdf` file and no `data/` folder created by this phase.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1, R2 | database check | probe script; search below | the four `before upgrade:` lines, `common: require_current_schema exists`, and the two `uses the shared schema check` lines end in `ok`; the search prints nothing |
| R3 to R8 | `import statement` | probe script | every line starting `import:` ends in `ok` |
| R9 to R12 | `import folder` | probe script | every line starting `folder:` ends in `ok` |
| R13 to R15 | `statements list` | probe script | `empty: statements` and every line starting `statements:` end in `ok` |
| R16, R17 | `transactions list` | probe script | `empty: transactions` and every line starting `transactions:` end in `ok` |
| R18 | registration | probe script; gate 6 | `help: five command groups` ends in `ok` |
| R19 | no tracebacks | given tests (gate 4) | every failure test asserts `isinstance(result.exception, SystemExit)` and passes |
| earlier commands | unchanged | probe script; `.venv/bin/python -m pytest tests/e2e/test_cli.py tests/e2e/test_cli_accounts.py --no-cov` | `accounts: the earlier commands still work` ends in `ok`; the tests pass |

`git grep -n --untracked -E "current_revision|head_revision|select\(|Row\b|reconcile|fingerprint|extract_pages|detect_parser|logging" -- src/finances/cli/accounts.py src/finances/cli/importing.py src/finances/cli/listing.py`

The search must print nothing. A match means a command is doing work that belongs to the service or the repositories.

## 4. Independent probes

The given tests run each command against a fresh database with the fake bank format. This script runs one continuous session with its own parser and its own statements, the way a person would use the program: every command refused before the database is migrated, an import with no matching account, a dry run, a real import, the same file again, several kinds of failure, a folder with files it must take and files it must ignore, an account closed afterwards, and both listings with every option. None of its names or amounts are in the given tests.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It works inside its own temporary folder and sets `FIN_DATA_DIR` for itself. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import os
import tempfile
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from finances.cli import common, importing, listing
from finances.cli.main import app
from finances.config import get_settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, StatementRow, TransactionRow
from finances.domain.models import AccountType
from finances.ingest.parsers import register, registered_parsers, unregister
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
BULLETS = "••"
failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def run(*args):
    return CliRunner(env={"COLUMNS": "220"}).invoke(app, [str(arg) for arg in args])


def rows(output):
    """Every row of a Rich table as a list of cells, heading first."""
    found = []
    for line in output.splitlines():
        if line.startswith(("│", "┃")):
            found.append([cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]])
    return found


def failed_cleanly(result, message):
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


def build_pdf(lines):
    objects = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    operators = ["BT", "/F1 10 Tf"] + [f"1 0 0 1 72 {720 - 14 * i} Tm ({text}) Tj" for i, text in enumerate(lines)] + ["ET"]
    stream = "\n".join(operators).encode("latin-1")
    objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 4 0 R >>")
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = b"<< /Type /Pages /Kids [5 0 R] /Count 1 >>"
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


def line(month, day, amount, kind, text, **more):
    return StatementLine(date(2026, month, day), None, text, amount, kind, **more)


def parsed(last4, kind, start, end, opening, closing, lines):
    return ParsedStatement("probe_bank", "Probe Bank", kind, last4, start, end, opening, closing, lines)


MARCH = [
    line(3, 2, -1299, Section.PURCHASES, "PROBE GROCER #7", card_last4="5512"),
    line(3, 9, -4500, Section.PURCHASES, "PROBE FUEL"),
    line(3, 15, 20000, Section.PAYMENTS_CREDITS, "PROBE PAYMENT"),
]
STATEMENTS = {
    "march": parsed("9001", AccountType.CREDIT_CARD, date(2026, 3, 1), date(2026, 3, 31), -5000000, -4985799, MARCH),
    "april": parsed("9001", AccountType.CREDIT_CARD, date(2026, 4, 1), date(2026, 4, 30), 0, -1999, [MARCH[0], line(4, 2, -700, Section.FEES, "PROBE FEE")]),
    "savings": parsed("0042", AccountType.SAVINGS, date(2026, 1, 1), date(2026, 3, 31), 100000, 100250, [line(3, 31, 250, Section.INTEREST, "PROBE INTEREST PAID")]),
    "unbalanced": parsed("9001", AccountType.CREDIT_CARD, date(2026, 5, 1), date(2026, 5, 31), 0, -7, []),
    "stranger": parsed("7777", AccountType.CHECKING, date(2026, 5, 1), date(2026, 5, 31), 0, 0, []),
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


def write(folder, name, key, salt=""):
    path = folder / name
    path.write_bytes(build_pdf([f"PROBE {key}", f"copy {salt}"]))
    return path


def counts():
    engine = get_engine()
    with session_scope(engine) as session:
        found = (session.query(StatementRow).count(), session.query(TransactionRow).count())
    engine.dispose()
    return found


def session_checks(root):
    inbox = root / "in box"
    inbox.mkdir()
    march = write(inbox, "march 2026.pdf", "march")

    for args in (["import", "statement", march], ["import", "folder", inbox], ["statements", "list"], ["transactions", "list"]):
        result = run(*args)
        check(f"before upgrade: fin {args[0]} {args[1]}", result.exit_code == 1 and result.stderr == NOT_MIGRATED and result.stdout == "")
    run("db", "upgrade")
    check("empty: statements", run("statements", "list").stdout == "No statements.\n")
    check("empty: transactions", run("transactions", "list").stdout == "No transactions.\n")

    hint = 'no account ends in 9001; add one with: fin accounts add --name "NAME" --institution "Probe Bank" --type credit_card --last4 9001'
    check("import: no account yet", failed_cleanly(run("import", "statement", march), hint))
    run("accounts", "add", "--name", "Probe Card", "--institution", "Probe Bank", "--type", "credit_card", "--last4", "9001")
    run("accounts", "add", "--name", "Probe Savings", "--institution", "Probe Bank", "--type", "savings", "--last4", "0042")
    run("accounts", "add", "--name", "Probe Spare", "--institution", "Probe Bank", "--type", "checking")

    block = "Parser: probe_bank\nAccount: Probe Card\nPeriod: 2026-03-01 to 2026-03-31\nLines: 3\nInserted: 3\nDuplicates: 0\n"
    dry = run("import", "statement", march, "--dry-run")
    check("import: dry run text", dry.exit_code == 0 and dry.stdout == "File: march 2026.pdf\n" + block + "Status: dry run, nothing written\n")
    check("import: dry run stores nothing", counts() == (0, 0))
    real = run("import", "statement", march)
    check("import: text", real.exit_code == 0 and real.stdout == "File: march 2026.pdf\n" + block + "Status: imported\n" and real.stderr == "")
    check("import: stored", counts() == (1, 3))
    again = run("import", "statement", march, "--account", "Probe Card")
    check("import: again", again.exit_code == 0 and again.stdout == "File: march 2026.pdf\nStatus: already imported\n")
    check("import: unreconciled", failed_cleanly(run("import", "statement", write(root, "u.pdf", "unbalanced")), "statement does not reconcile: off by -7 cents"))
    check("import: parser error", failed_cleanly(run("import", "statement", write(root, "b.pdf", "broken")), "probe statement is malformed"))
    check("import: wrong named account", failed_cleanly(run("import", "statement", write(root, "m2.pdf", "march", "x"), "--account", "Probe Savings"), "account does not match the statement"))
    spare = run("import", "statement", write(root, "s.pdf", "stranger"), "--account", "probe spare")
    check("import: named account without digits", spare.exit_code == 0 and "Account: Probe Spare\n" in spare.stdout)
    check("import: a folder is not a file", run("import", "statement", inbox).exit_code == 2)
    check("import: failures stored nothing", counts() == (2, 3))

    write(inbox, "april.PDF", "april")
    write(inbox, "savings q1.pdf", "savings")
    (inbox / "zz broken.pdf").write_bytes(b"not a pdf")
    (inbox / "readme.txt").write_text("PROBE march")
    (inbox / "sub").mkdir()
    write(inbox / "sub", "ignored.pdf", "march", "sub")
    listing_dry = run("import", "folder", inbox, "--dry-run")
    table = rows(listing_dry.stdout)
    check("folder: headings", table[:1] == [["File", "Parser", "Account", "Period", "Lines", "Inserted", "Duplicates", "Status"]])
    check("folder: files in name order, PDFs at the top level only", [r[0] for r in table[1:]] == ["april.PDF", "march 2026.pdf", "savings q1.pdf", "zz broken.pdf"])
    check("folder: dry run row", table[1] == ["april.PDF", "probe_bank", "Probe Card", "2026-04-01 to 2026-04-30", "2", "1", "1", "dry run, nothing written"])
    check("folder: dry run exit code and error line", listing_dry.exit_code == 1 and listing_dry.stderr == "Error: zz broken.pdf: could not read PDF\n")
    check("folder: dry run stored nothing", counts() == (2, 3))
    done = run("import", "folder", inbox)
    table = rows(done.stdout)
    check("folder: statuses", [r[-1] for r in table[1:]] == ["imported", "already imported", "imported", "failed"])
    check("folder: an already imported row has empty cells", table[2] == ["march 2026.pdf", "", "", "", "0", "0", "0", "already imported"])
    check("folder: a failed row has empty cells", table[4] == ["zz broken.pdf", "", "", "", "0", "0", "0", "failed"])
    check("folder: savings row", table[3] == ["savings q1.pdf", "probe_bank", "Probe Savings", "2026-01-01 to 2026-03-31", "1", "1", "0", "imported"])
    check("folder: exit code 1 because one failed", done.exit_code == 1 and isinstance(done.exception, SystemExit))
    check("folder: stored", counts() == (4, 5))
    (inbox / "zz broken.pdf").unlink()
    clean = run("import", "folder", inbox)
    check("folder: exit code 0 when nothing fails", clean.exit_code == 0 and clean.stderr == "")
    (root / "none").mkdir()
    check("folder: no PDFs", run("import", "folder", root / "none").stdout == "No PDF files.\n")
    check("folder: a file is not a folder", run("import", "folder", march).exit_code == 2)

    engine = get_engine()
    with session_scope(engine) as session:
        session.query(AccountRow).filter_by(name="Probe Savings").one().is_active = False
    engine.dispose()
    table = rows(run("statements", "list").stdout)
    check("statements: headings", table[:1] == [["Account", "File", "Parser", "Period", "Opening", "Closing", "Lines", "New"]])
    check("statements: newest period first", [r[1] for r in table[1:]] == ["s.pdf", "april.PDF", "savings q1.pdf", "march 2026.pdf"])
    check("statements: money with separators and signs", table[4] == ["Probe Card", "march 2026.pdf", "probe_bank", "2026-03-01 to 2026-03-31", "-$50,000.00", "-$49,857.99", "3", "3"])
    check("statements: lines and new rows differ after an overlap", table[2][-2:] == ["2", "1"])
    check("statements: a closed account is still named", table[3][0] == "Probe Savings" and table[3][4:6] == ["$1,000.00", "$1,002.50"])
    check("statements: one account", [r[1] for r in rows(run("statements", "list", "--account", "PROBE CARD").stdout)[1:]] == ["april.PDF", "march 2026.pdf"])
    check("statements: account with none", run("statements", "list", "--account", "Probe Spare").exit_code == 0)
    check("statements: unknown account", failed_cleanly(run("statements", "list", "--account", "Ghost"), "account not found"))

    table = rows(run("transactions", "list").stdout)
    check("transactions: headings", table[:1] == [["Date", "Account", "Description", "Amount", "Card", "Section"]])
    check("transactions: newest first", [r[0] for r in table[1:]] == ["2026-04-02", "2026-03-31", "2026-03-15", "2026-03-09", "2026-03-02"])
    check("transactions: fee row", table[1] == ["2026-04-02", "Probe Card", "PROBE FEE", "-$7.00", "", "fees"])
    check("transactions: masked card", table[5] == ["2026-03-02", "Probe Card", "PROBE GROCER #7", "-$12.99", BULLETS + "5512", "purchases"])
    check("transactions: positive amount", table[3][3] == "$200.00" and table[2] == ["2026-03-31", "Probe Savings", "PROBE INTEREST PAID", "$2.50", "", "interest"])
    ranged = rows(run("transactions", "list", "--from", "2026-03-09", "--to", "2026-03-31").stdout)
    check("transactions: both ends of the range are included", [r[0] for r in ranged[1:]] == ["2026-03-31", "2026-03-15", "2026-03-09"])
    check("transactions: account and limit", [r[0] for r in rows(run("transactions", "list", "--account", "probe card", "--limit", "2").stdout)[1:]] == ["2026-04-02", "2026-03-15"])
    check("transactions: nothing in range", run("transactions", "list", "--to", "2025-12-31").stdout == "No transactions.\n")
    check("transactions: unknown account", failed_cleanly(run("transactions", "list", "--account", "Ghost"), "account not found"))
    check("transactions: bad limit and bad date", run("transactions", "list", "--limit", "0").exit_code == 2 and run("transactions", "list", "--from", "March").exit_code == 2)
    listed = run("accounts", "list", "--all")
    check("accounts: the earlier commands still work", listed.exit_code == 0 and "Probe Spare" in listed.stdout)
    help_text = run("--help").stdout
    check("help: five command groups", all(name in help_text for name in ("db", "accounts", "import", "statements", "transactions")))


start = Path.cwd()
saved = registered_parsers()
try:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder).resolve()
        os.chdir(root)
        os.environ["FIN_DATA_DIR"] = str(root / "data")
        os.environ.pop("FIN_DATABASE_URL", None)
        get_settings.cache_clear()
        for parser in saved:
            unregister(parser.name)
        register(ProbeParser())
        session_checks(root)
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)
finally:
    for parser in registered_parsers():
        unregister(parser.name)
    for parser in saved:
        register(parser)
    os.chdir(start)
    os.environ.pop("FIN_DATA_DIR", None)
    get_settings.cache_clear()

check("common: require_current_schema exists", callable(getattr(common, "require_current_schema", None)))
for module in (importing, listing):
    source = Path(module.__file__).read_text(encoding="utf-8")
    check(f"{module.__name__}: uses the shared schema check", "require_current_schema" in source and "current_revision" not in source)
print("FAILURES", failures)
```

## 5. The coder's tests

The spec requires no new tests. If `tests/e2e/test_cli_import_more.py` exists:

- each test in it reaches a line that the given tests do not, and asserts exact output and an exit code;
- it uses `tmp_settings`, `fake_bank`, and temporary files only, and reads nothing under `data/`;
- no `skip`, `xfail`, `assert True`, or `pytest.raises(Exception)`.

If it does not exist, there is nothing to review here.

## 6. Project rules that apply to this phase

- **Thin commands.** The search in section 3.
- **Layering.** `git grep -n -E "finances\.cli" -- src/finances/ingest src/finances/db src/finances/domain` prints nothing: nothing below the CLI imports it.
- **Streams.** Read every `typer.echo` in the three new modules: each line starting `Error:` has `err=True`, and no other line has it.
- **Privacy.** No logging in `src/finances/cli/`, and no command writes a file.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- An option beyond the ones in the spec's Design tables: no `--force`, `--allow-mismatch`, `--delete`, `--verbose`, `--format`, or `--yes`.
- A summary line after a table, colors or styles, or a column for the import time.
- Any new function in `service.py` or `repositories.py`.
- Sorting, filtering, or de-duplicating done in the CLI.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 3d: the import commands (YYYY-MM-DD)` with a real date. "Built" gives N and the final passed count, and the final count is at least N + 41. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 to Part 5>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the command, what it printed on each stream, and its exit code), and what is required. Do not prescribe the code. Ask for the acceptance commands to be run again after the fix.
