# Verify Phase 3b: statement checks and reading

Spec: `docs/phases/phase-03b-statement-checks-and-reading.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

This is the first phase written by a more capable coder under a looser spec. The coder chose its own order of work and internal structure, and wrote the tests for two of the four parts. So this guide checks three things: that the code behaves as required (the probe script), that the coder's own tests would catch a regression (section 5), and that nothing beyond the spec was built (section 7).

Judge the code by behavior and by the rules, never by how it is written. These variations are all correct and must not be reported:

- the registry stored as a dict, a list, or any other private structure;
- private helper functions, at module level or nested;
- `reconcile` written as one pass or several;
- any way of counting repeats in `fingerprint_lines` that gives the specified values;
- catching the encrypted case before or inside the general `try`.

`ingest/reconcile.py` and `ingest/dedup.py` are critical modules (`docs/testing.md`).

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -c "import pypdf; print(pypdf.__version__.split('.')[0])"` | a number, `5` or higher |
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least `495 passed`, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_reconcile.py tests/unit/test_dedup.py --no-cov` | exactly `45 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with every file under `src/finances/ingest/` at 100% |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M pyproject.toml
 M src/finances/ingest/parsers/__init__.py
 M tests/conftest.py
?? src/finances/ingest/dedup.py
?? src/finances/ingest/pdf_text.py
?? src/finances/ingest/reconcile.py
?? tests/unit/test_dedup.py
?? tests/unit/test_parser_registry.py
?? tests/unit/test_pdf_text.py
?? tests/unit/test_reconcile.py
```

- `git diff HEAD -- pyproject.toml` adds exactly one line, `"pypdf>=5",`, in `dependencies`. `cryptography` and `pycryptodome` are not added.
- `tests/unit/test_reconcile.py`, `tests/unit/test_dedup.py`, and `tests/conftest.py` are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- src/finances/ingest/statement.py src/finances/ingest/parsers/helpers.py src/finances/domain src/finances/db src/finances/cli src/finances/diagnostics.py tests/integration tests/e2e` is empty, and no earlier unit test file is changed.
- No file was created under `data/`, and `git status --short --ignored` shows no new `.pdf` file anywhere in the repository.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 to R6 | reconciliation | probe script | every line starting `reconcile:` ends in `ok` |
| R6 | integers only | first search below | no output |
| R7 to R10 | fingerprints | probe script | every line starting `fingerprints:` ends in `ok` |
| R11, R12 | pages and layout | probe script | `pdf: three pages of text`, `the empty page is kept`, `one line of text per printed row`, `column gaps are kept wide`, `spaces inside a cell are kept`, `last page`, and `no pages` end in `ok` |
| R13 | encryption | probe script | `owner-only encryption is read` and `password protected` end in `ok` |
| R14 | unreadable files | probe script | the six `pdf: unreadable` lines and `the library's own error is not attached` end in `ok` |
| R15 | library warnings | probe script | `library warnings silenced` ends in `ok` |
| R16 to R18 | register, unregister, list | probe script | the `registry:` lines about order, copy, duplicate name, unregister, and registering again end in `ok` |
| R19 to R21 | detection | probe script | the `registry:` lines about single match, first page, no match, later page, no pages, two matches, and empty registry end in `ok` |
| R22 | protocol | read `parsers/__init__.py` | `StatementParser` subclasses `typing.Protocol` and declares `name: str`, `detect(self, first_page: str) -> bool`, and `parse(self, pages: list[str]) -> ParsedStatement`, and nothing else |
| messages | constant text | read every `raise` in the four modules | six messages in total, each the exact text in the spec; only the R21 message is built, and only from parser names |
| layering | imports | second search below | no output |
| scope | nothing extra | probe script | the four `nothing extra is public` lines and `ReconcileResult fields` end in `ok` |

`git grep -n --untracked -E "float|round\(| / " -- src/finances/ingest/reconcile.py src/finances/ingest/dedup.py`

`git grep -n --untracked -E "print\(|logging\.(debug|info|warning|error)|finances\.(db|cli)" -- src/finances/ingest`

## 4. Independent probes

None of these values are in the given tests or in the spec's examples. The script builds its own PDFs, including encrypted ones, and its own parsers, and computes each expected fingerprint from the format in R7 without calling the code under test.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It writes no file. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import dataclasses
import hashlib
import io
import logging
import re
from datetime import date

from pypdf import PdfReader, PdfWriter

from finances.domain.models import AccountType
from finances.ingest import dedup, pdf_text, reconcile as reconcile_module
from finances.ingest import parsers
from finances.ingest.dedup import fingerprint_lines
from finances.ingest.parsers import detect_parser, register, registered_parsers, unregister
from finances.ingest.pdf_text import extract_pages
from finances.ingest.reconcile import ReconcileResult, reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def outcome(function, *args):
    """Return the value, or the exception type name and message."""
    try:
        return function(*args)
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, str(exc))


def line(day, amount, section, description="PROBE MERCHANT", **more):
    return StatementLine(date(2026, 3, day), None, description, amount, section, **more)


def statement(opening, closing, lines, totals=None):
    return ParsedStatement(
        "probe", "Probe Bank", AccountType.CHECKING, "0042", date(2026, 3, 1), date(2026, 3, 31),
        opening, closing, lines, totals or {},
    )


# ---------------------------------------------------------------- reconcile
LINES = [
    line(2, 310055, Section.DEPOSITS),
    line(3, -129, Section.WITHDRAWALS),
    line(9, -8871, Section.WITHDRAWALS),
    line(9, -4000, Section.CHECKS),
    line(30, 7, Section.INTEREST),
]
good = reconcile(statement(50000, 347062, LINES))
check("reconcile: balanced", good == ReconcileResult(True, 347062, 347062, 0, {}))
high = reconcile(statement(50000, 347063, LINES))
check("reconcile: one cent high", (high.ok, high.difference_cents, high.expected_closing_cents) == (False, 1, 347062))
low = reconcile(statement(50000, 347061, LINES))
check("reconcile: one cent low", (low.ok, low.difference_cents) == (False, -1))
totals = {Section.WITHDRAWALS: -9000, Section.DEPOSITS: 310055, Section.CHECKS: -4001, Section.FEES: 0, Section.PURCHASES: 5}
wrong = reconcile(statement(50000, 347062, LINES, totals))
check("reconcile: wrong sections fail a balanced statement", wrong.ok is False and wrong.difference_cents == 0)
check("reconcile: mismatches are (declared, computed)", wrong.section_mismatches == {Section.CHECKS: (-4001, -4000), Section.PURCHASES: (5, 0)})
check("reconcile: mismatches keep declared order", list(wrong.section_mismatches) == [Section.CHECKS, Section.PURCHASES])
check("reconcile: undeclared sections are not reported", Section.INTEREST not in wrong.section_mismatches)
both = reconcile(statement(50000, 0, LINES, {Section.INTEREST: 8}))
check("reconcile: both failures at once", (both.ok, both.difference_cents, both.section_mismatches) == (False, -347062, {Section.INTEREST: (8, 7)}))
huge = 2**60 + 1
exact = reconcile(statement(-huge, 3, [line(1, huge, Section.DEPOSITS), line(1, 3, Section.DEPOSITS)], {Section.DEPOSITS: huge + 3}))
check("reconcile: exact on very large amounts", exact.ok is True and type(exact.expected_closing_cents) is int)
subject = statement(50000, 347062, list(LINES), dict(totals))
reconcile(subject)
check("reconcile: statement untouched", subject.lines == LINES and subject.declared_section_totals == totals)
check("reconcile: result is frozen", outcome(setattr, good, "ok", False)[0] == "FrozenInstanceError")
check("reconcile: empty statement", reconcile(statement(-1, -1, [])) == ReconcileResult(True, -1, -1, 0, {}))


# ------------------------------------------------------------- fingerprints
def expected_fingerprint(*parts):
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


rent = line(1, -150000, Section.WITHDRAWALS, "Probe  Rent\tLLC")
fee = line(1, -150000, Section.FEES, "probe rent llc", cardholder="A PERSON")
card = line(4, -2599, Section.PURCHASES, "PROBE GROCER", card_last4="9001", external_ref="AB12")
result = fingerprint_lines(31, [rent, card, fee, rent])
check("fingerprints: exact payload format", result[0] == expected_fingerprint("31", "2026-03-01", "-150000", "PROBE RENT LLC", "", "", "0"))
check("fingerprints: card and reference fields", result[1] == expected_fingerprint("31", "2026-03-04", "-2599", "PROBE GROCER", "9001", "AB12", "0"))
check("fingerprints: repeats counted per identical key", result[2] == expected_fingerprint("31", "2026-03-01", "-150000", "PROBE RENT LLC", "", "", "1"))
check("fingerprints: third repeat", result[3] == expected_fingerprint("31", "2026-03-01", "-150000", "PROBE RENT LLC", "", "", "2"))
check("fingerprints: all different", len(set(result)) == 4)
check("fingerprints: a new call starts from zero", fingerprint_lines(31, [rent]) == [result[0]])
check("fingerprints: account matters", fingerprint_lines(13, [rent]) != [result[0]])
check("fingerprints: hex strings", all(type(value) is str and len(value) == 64 and value == value.lower() for value in result))
check("fingerprints: many lines", len(set(fingerprint_lines(31, [rent] * 500))) == 500)
check("fingerprints: empty", fingerprint_lines(31, []) == [])


# ---------------------------------------------------------------------- PDF
def build_pdf(pages):
    objects = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        operators = ["BT", "/F1 10 Tf"]
        for index, row in enumerate(lines):
            for column, cell in enumerate(row.split("\t")):
                text = cell.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                operators.append(f"1 0 0 1 {72 + 180 * column} {720 - 14 * index} Tm ({text}) Tj")
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


def encrypted(content, user_password):
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(content)))
    writer.encrypt(user_password=user_password, owner_password="probe-owner", algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


document = build_pdf([["PROBE BANK", "03/04\tPROBE GROCER 9001\t25.99", "03/09   CHECK 1042\t\t40.00"], [], ["LAST PAGE (3)"]])
pages = outcome(extract_pages, document)
shape = type(pages) is list and len(pages) == 3 and all(type(page) is str for page in pages)
check("pdf: three pages of text", shape)
rows = pages[0].split("\n") if shape else ["", "", ""]
check("pdf: the empty page is kept as an empty string", shape and pages[1] == "")
check("pdf: one line of text per printed row", len(rows) == 3 and rows[0] == "PROBE BANK")
check("pdf: column gaps are kept wide (layout mode)", re.fullmatch(r"03/04 {5,}PROBE GROCER 9001 {5,}25\.99", rows[1]) is not None)
check("pdf: spaces inside a cell are kept", re.fullmatch(r"03/09   CHECK 1042 {20,}40\.00", rows[2]) is not None)
check("pdf: last page", shape and pages[2] == "LAST PAGE (3)")
check("pdf: no pages", outcome(extract_pages, build_pdf([])) == [])
opened = outcome(extract_pages, encrypted(document, ""))
check("pdf: owner-only encryption is read", type(opened) is list and opened[-1:] == ["LAST PAGE (3)"])
check("pdf: password protected", outcome(extract_pages, encrypted(document, "probe-user")) == ("StatementError", "PDF is password protected"))
UNREADABLE = ("StatementError", "could not read PDF")
for label, content in [
    ("empty bytes", b""),
    ("plain text", b"03/04 PROBE GROCER 25.99"),
    ("header only", b"%PDF-1.4\n"),
    ("cut in half", document[: len(document) // 2]),
    ("xref removed", document.replace(b"startxref", b"startxxxx")[:300]),
    ("zip signature", b"PK\x03\x04" + bytes(200)),
]:
    check(f"pdf: unreadable ({label})", outcome(extract_pages, content) == UNREADABLE)
try:
    extract_pages(b"03/04 PROBE GROCER 25.99")
except StatementError as error:
    check("pdf: the library's own error is not attached", error.__cause__ is None and error.__suppress_context__ is True)
check("pdf: library warnings silenced", logging.getLogger("pypdf._reader").getEffectiveLevel() >= logging.ERROR)


# ----------------------------------------------------------------- registry
class Probe:
    def __init__(self, name, word):
        self.name, self.word, self.calls = name, word, []

    def detect(self, first_page):
        self.calls.append(first_page)
        return self.word in first_page

    def parse(self, pages):
        return statement(0, 0, [])


before = registered_parsers()
check("registry: empty before any parser is registered", before == [])
north, south, east = Probe("north", "NORTH"), Probe("south", "SOUTH"), Probe("east", "SOUTH")
try:
    register(south)
    register(north)
    listed = registered_parsers()
    check("registry: registration order", listed == [south, north])
    listed.append("junk")
    check("registry: the returned list is a copy", registered_parsers() == [south, north])
    check("registry: duplicate name", outcome(register, Probe("north", "X")) == ("ValueError", "parser name is already registered"))
    check("registry: still two parsers", len(registered_parsers()) == 2)
    check("registry: single match", outcome(detect_parser, ["...NORTH...", "SOUTH on page two"]) is north)
    check("registry: only the first page is offered", south.calls == ["...NORTH..."] and north.calls == ["...NORTH..."])
    UNKNOWN = ("StatementError", "unrecognized statement format")
    check("registry: no match", outcome(detect_parser, ["WEST"]) == UNKNOWN)
    check("registry: match only on a later page", outcome(detect_parser, ["WEST", "NORTH"]) == UNKNOWN)
    check("registry: no pages", outcome(detect_parser, []) == UNKNOWN)
    register(east)
    two = outcome(detect_parser, ["SOUTH"])
    check("registry: two matches named in registration order", two == ("StatementError", "statement matches more than one parser: south, east"))
    unregister("south")
    check("registry: unregister", registered_parsers() == [north, east] and outcome(detect_parser, ["SOUTH"]) is east)
    check("registry: unregister unknown", outcome(unregister, "south") == ("ValueError", "parser name is not registered"))
    register(south)
    check("registry: a removed name can be registered again, at the end", registered_parsers() == [north, east, south])
except Exception as exc:  # noqa: BLE001
    check(f"registry: probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)
finally:
    for parser in registered_parsers():
        unregister(parser.name)
check("registry: empty again", registered_parsers() == [])
check("registry: empty registry never matches", outcome(detect_parser, ["NORTH"]) == ("StatementError", "unrecognized statement format"))

for module, expected in [
    (reconcile_module, ["ReconcileResult", "reconcile"]),
    (dedup, ["fingerprint_lines"]),
    (pdf_text, ["extract_pages"]),
    (parsers, ["StatementParser", "detect_parser", "register", "registered_parsers", "unregister"]),
]:
    public = sorted(
        name
        for name, value in vars(module).items()
        if getattr(value, "__module__", "") == module.__name__ and not name.startswith("_")
    )
    check(f"{module.__name__}: nothing extra is public {public}", public == expected)
check("ReconcileResult fields", [f.name for f in dataclasses.fields(ReconcileResult)] == ["ok", "expected_closing_cents", "actual_closing_cents", "difference_cents", "section_mismatches"])
print("FAILURES", failures)
```

## 5. The coder's tests

Read `tests/unit/test_pdf_text.py` and `tests/unit/test_parser_registry.py`.

- **Coverage of requirements.** For each of R11 to R22, name the test that would fail if the requirement were broken. A requirement with no such test is a finding, even when the code is correct. The coder's final message lists its own mapping; check it, do not trust it.
- **Assertions are exact.** Messages are compared with `==` against the full text. No `assert True`, no `pytest.raises(Exception)`, no `skip` or `xfail`, and no expected value produced by calling the function under test.
- **Isolation.** Every test that registers a parser uses the `parser_registry` fixture. Run `.venv/bin/python -m pytest tests/unit/test_parser_registry.py tests/unit/test_pdf_text.py --no-cov -p no:randomly` and then the same two files in the opposite order; both must pass, and `.venv/bin/python -c "from finances.ingest.parsers import registered_parsers; print(registered_parsers())"` must print `[]`.
- **Synthetic data.** Invented text only. No test reads a file under `data/` or anywhere outside pytest's temporary directories, and none needs the network.
- **Layer.** Both files are unit tests under `tests/unit/`.
- **Spot checks.** For each change below, say which of the coder's tests would fail, by reading the test. If none would, that is a finding.
  1. `extract_pages` calls `page.extract_text()` without `extraction_mode="layout"`.
  2. `extract_pages` raises `PDF is password protected` for every encrypted PDF, without trying the empty password.
  3. `detect_parser` returns the first parser that matches and never raises the "more than one parser" error.
  4. `registered_parsers` returns the registry's own list instead of a copy.
  5. `extract_pages` raises `StatementError("could not read PDF")` without `from None`.

## 6. Project rules that apply to this phase

- **No tolerance in reconciliation.** `git grep -n --untracked -E "abs\(|<= *1|tolerance" -- src/finances/ingest/reconcile.py` prints nothing.
- **Nothing remembered between fingerprint calls.** `dedup.py` has no module-level mutable state: no list, dict, set, or counter assigned outside a function.
- **In memory only.** `git grep -n --untracked -E "open\(|Path\(|tempfile" -- src/finances/ingest/pdf_text.py` prints nothing: the PDF is read from the bytes it was given.
- **Privacy.** No module logs or prints, and no message other than R21's is an f-string or is built with `%` or `.format`.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- A parser class in production code, or a call to `register` outside tests: `git grep -n --untracked -w "register" -- src` shows the `def register` line and, at most, docstrings or comments. No line calls it.
- Parameters beyond the ones under Design: no tolerance, password, strict, or mode argument on any of the public functions.
- New modules under `src/` other than `reconcile.py`, `dedup.py`, and `pdf_text.py`.
- Database, repository, service, or command-line code for statements.
- Changes to Phase 3a's modules or tests.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 3b: statement checks and reading (YYYY-MM-DD)` with a real date. "Built" gives the passed count. "Deviations" lists the coder's design choices; each must be inside the spec's Scope and must not change a public name, a signature, a message, or a given file. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 / Part 2 / Part 3 / Part 4 / tests>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the call and its result, or the file and line), and what is required. Do not prescribe the code. For a missing test, name the requirement and say that a test must fail when it is broken. Ask for the acceptance commands to be run again after the fix.
