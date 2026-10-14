# Verify Phase 6a: repairs from the first run on real statements

Spec: `docs/phases/phase-06a-real-statement-repairs.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder changed two modules: `src/finances/ingest/pdf_text.py` (a page that layout mode cannot read is read in plain mode; wide gaps are narrowed) and `src/finances/ingest/parsers/truist.py` (labels matched with spaces ignored; the balance is the first money after its date). Two test files were given. The coder wrote no tests in this phase.

Judge the code by what it returns, never by how it is written. These are all correct and must not be reported:

- matching labels with a regular expression, or by removing whitespace and comparing;
- the Truist parser using `find_labeled_amount` or not;
- narrowing gaps with any expression that turns every run of three or more spaces into two and changes nothing else;
- any private helpers.

**Privacy.** You must not open, print, or quote anything under `data/samples/`. Section 9 says what you may run and report.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 95 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_pdf_text_repairs.py tests/unit/test_truist_parser_spacing.py --no-cov` | exactly `95 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with `pdf_text.py` and `parsers/truist.py` at 100% |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/ingest/parsers/truist.py
 M src/finances/ingest/pdf_text.py
?? tests/unit/test_pdf_text_repairs.py
?? tests/unit/test_truist_parser_spacing.py
```

- The two given test files are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD --stat -- tests/fixtures tests/real_samples tests/conftest.py tests/unit/test_pdf_text.py tests/unit/test_truist_parser.py tests/unit/test_truist_parser_more.py src/finances/ingest/parsers/helpers.py src/finances/ingest/parsers/boa.py src/finances/ingest/parsers/citi.py src/finances/ingest/parsers/capital_one.py src/finances/ingest/parsers/marcus.py src/finances/ingest/service.py pyproject.toml` is empty, and no existing test file is changed.
- In `truist.py`, the account line, the rows, the checks, the debit card details, and the three messages are as they were. Read the diff: changes are confined to how headings, the closing `Total` line, the two balances, and the declared totals are found.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | plain mode for a failing page | probe script | `pdf: a statement with a blank last page is read, the blank page as an empty string`, `pdf: blank pages before and after`, `pdf: only blank pages`, and `pdf: any failure of layout mode falls back to plain mode, with gaps narrowed` |
| R1 | plain mode only when needed | given test `test_plain_mode_is_not_used_when_layout_mode_works` in gate 4 | passes |
| R2 | `None` | probe script | `pdf: plain mode returning nothing is an empty page` |
| R3 | both modes fail | given test `test_a_page_that_neither_mode_can_read_is_an_unreadable_pdf`; read `pdf_text.py` | passes; the only messages are `PDF is password protected` and `could not read PDF`, raised `from None` |
| R4 | gaps | probe script | `pdf: columns are two spaces apart` and `pdf: no run of three spaces is left` |
| R5 | unchanged behavior | probe script; the existing `tests/unit/test_pdf_text.py` in gate 3 | `pdf: unreadable bytes still give the constant message` |
| R6 | headings | probe script | the six lines starting `truist: a space after every`, plus `truist: a heading with more words on its line opens nothing` and `truist: a heading followed by an amount opens nothing` |
| R7 | closing | probe script | `truist: any line starting with Total closes the section` |
| R8 | balances | probe script | `truist: the plain statement`, `truist: the first money after the date is the balance`, `truist: text between the date and the money`, `truist: no space between the date and the money`, `truist: a date that does not exist`, `truist: a balance label inside other words` |
| R9 | totals | probe script | `truist: its totals, and it reconciles` and `truist: a total label inside other words is not declared` |
| R10 | nothing else moved | gate 3; section 2 | every existing test passes unedited |
| end to end | through a real PDF | probe script | `pdf: it parses and reconciles` and the line starting `round trip:` |
| speed | wide text | probe script | `truist: narrowed wide text parses the same, quickly` |

`git grep -n --untracked -F -e "strptime" -e "float" -e "print(" -e "\d" -- src/finances/ingest/parsers/truist.py src/finances/ingest/pdf_text.py`

## 4. Independent probes

The script builds its own PDFs, some with pages that have no content, and its own Truist statement whose labels are spaced in six different ways. None of its names or amounts are in the given tests, the fixtures, or the spec.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It writes no file and reads nothing under `data/`. Every line must end in `ok`; the last line must be `FAILURES 0`. A line that says a section `ran to the end (stopped by ...)` and ends in `FAIL` means the code raised where it should not have; report it with the exception named on that line.

```python
import io
import re
import time
from datetime import date

from pypdf import PdfReader, PdfWriter

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


def section(name, function):
    try:
        function()
    except Exception as exc:  # noqa: BLE001
        check(f"{name}: ran to the end (stopped by {type(exc).__name__}: {exc})", False)


def build_pdf(pages, blank_after=0, blank_before=0):
    """A PDF with one text page per list of lines; a tab starts a new column. Blank pages have no content."""
    objects = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        operators = ["BT", "/F1 8 Tf"]
        for index, row in enumerate(lines):
            for column, cell in enumerate(row.split("\t")):
                text = cell.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                operators.append(f"1 0 0 1 {40 + 150 * column} {760 - 11 * index} Tm ({text}) Tj")
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
    writer = PdfWriter()
    for _ in range(blank_before):
        writer.add_blank_page(612, 792)
    for page in PdfReader(io.BytesIO(bytes(out))).pages:
        writer.add_page(page)
    for _ in range(blank_after):
        writer.add_blank_page(612, 792)
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def spread(text, step):
    out, seen = [], 0
    for character in text:
        out.append(character)
        if not character.isspace():
            seen += 1
            if seen % step == 0:
                out.append(" ")
    return "".join(out).strip()


CARD = [
    "Capital One\tcapitalone.com", "Probe Rewards Card  Visa ending in 6006", "Jul 10, 2027 - Aug 9, 2027  31 days in Billing Cycle",
    "Previous Balance  $80.00", "Payments  - $80.00", "Other Credits  - $0.00", "Transactions  + $100.00",
    "Fees Charged  + $0.00", "Interest Charged  + $0.00", "New Balance  = $100.00",
    "KIM PROBE #6006: Payments, Credits and Adjustments", "Jul 30\tJul 31\tPROBE MOBILE PYMT\t- $80.00",
    "KIM PROBE #6006: Transactions", "Jul 11\tJul 12\tPROBE GARDEN CENTER\t$60.00", "Aug 8\tAug 9\tPROBE CINEMA 12\t$40.00",
    "KIM PROBE #6006: Total Transactions  $100.00", "Total Transactions for This Period  $100.00",
]


def truist_lines(step):
    def label(text):
        return spread(text, step) if step else text

    return [
        "T r u  i s  t .c  o  m", "Truist Bank, Member FDIC  Your account statement", "For 08/09/2027", "TRUIST PROBE CHECKING 1000000007007",
        label("Your previous balance as of 07/09/2027") + "  $80.00  Probe rewards earned  $3.21",
        "Checks  - 20.00  Probe rate  0.01%",
        label("Other withdrawals, debits and service charges") + "  - 100.00",
        label("Deposits, credits and interest") + "  + 141.25",
        label("Your new balance as of 08/09/2027") + "  = $101.25",
        "  " + label("Checks") + "  ", "DATE  CHECK #  AMOUNT($)  DATE  CHECK #  AMOUNT($)", "07/15  5001  12.00  07/20  *5005  8.00",
        label("Total checks") + "  = $20.00",
        label("Other withdrawals, debits and service charges"), "DATE  DESCRIPTION  AMOUNT($)",
        "07/11  DEBIT CARD PURCHASE PROBE GARDEN 07-09 TULSA OK 6116  60.00", "08/08  PROBE CINEMA 12 AUTOPAY  40.00",
        label("Total other withdrawals, debits and service charges") + "  = $100.00",
        label("Deposits, credits and interest"), "DATE  DESCRIPTION  AMOUNT($)", "08/01  MOBILE DEPOSIT  141.25",
        label("Total deposits, credits and interest") + "  = $141.25",
        "Deposits, credits and interest are available the next business day", "08/05  PROBE STRAY ROW  9.99",
    ]


def pdf_checks():
    from finances.ingest.parsers import detect_parser
    from finances.ingest.pdf_text import extract_pages
    from finances.ingest.reconcile import reconcile

    blank = PdfWriter()
    blank.add_blank_page(612, 792)
    held = io.BytesIO()
    blank.write(held)
    page = PdfReader(io.BytesIO(held.getvalue())).pages[0]
    unreadable = outcome(lambda: page.extract_text(extraction_mode="layout"))
    check("pdf: the probe's blank page is one layout mode cannot read", isinstance(unreadable, tuple) and unreadable[0] == "KeyError")
    pages = outcome(extract_pages, build_pdf([CARD], blank_after=1))
    check("pdf: a statement with a blank last page is read, the blank page as an empty string", isinstance(pages, list) and len(pages) == 2 and pages[1] == "" and "PROBE GARDEN CENTER" in pages[0])
    statement = detect_parser(pages).parse(pages)
    check("pdf: it parses and reconciles", statement.parser_name == "capital_one_card" and len(statement.lines) == 3 and reconcile(statement).ok)
    pages = outcome(extract_pages, build_pdf([["PROBE ONE"], ["PROBE TWO"]], blank_before=1, blank_after=2))
    check("pdf: blank pages before and after", pages == ["", "PROBE ONE", "PROBE TWO", "", ""])
    check("pdf: only blank pages", outcome(extract_pages, build_pdf([], blank_after=3)) == ["", "", ""])
    pages = outcome(extract_pages, build_pdf([["P1\tP2\tP3", "\t\tQ3", "R1 R1\tR2"]]))
    check("pdf: columns are two spaces apart", isinstance(pages, list) and pages[0].split("\n") == ["P1  P2  P3", "  Q3", "R1 R1  R2"])
    check("pdf: no run of three spaces is left", isinstance(pages, list) and "   " not in pages[0])
    import pypdf

    real = pypdf.PageObject.extract_text
    answers = {"plain": "PROBE   PLAIN    TEXT"}

    def fake(self, *args, **kwargs):
        if kwargs.get("extraction_mode") == "layout":
            raise RuntimeError("probe")
        return answers["plain"]

    pypdf.PageObject.extract_text = fake
    try:
        first = outcome(extract_pages, build_pdf([["x"]]))
        answers["plain"] = None
        second = outcome(extract_pages, build_pdf([["x"]]))
    finally:
        pypdf.PageObject.extract_text = real
    check("pdf: any failure of layout mode falls back to plain mode, with gaps narrowed", first == ["PROBE  PLAIN  TEXT"])
    check("pdf: plain mode returning nothing is an empty page", second == [""])
    check("pdf: unreadable bytes still give the constant message", outcome(extract_pages, b"not a pdf at all") == ("StatementError", "could not read PDF"))


def truist_checks():
    from finances.domain.models import AccountType
    from finances.ingest.parsers.truist import TruistDepositParser
    from finances.ingest.reconcile import reconcile
    from finances.ingest.statement import Section

    parser = TruistDepositParser()
    plain = parser.parse(["\n".join(truist_lines(0))])
    check("truist: the plain statement", (plain.account_type, plain.account_last4, plain.period_start, plain.period_end, plain.opening_balance_cents, plain.closing_balance_cents) == (AccountType.CHECKING, "7007", date(2027, 7, 10), date(2027, 8, 9), 8000, 10125))
    check("truist: its lines", [(item.amount_cents, item.section) for item in plain.lines] == [(-1200, Section.CHECKS), (-800, Section.CHECKS), (-6000, Section.WITHDRAWALS), (-4000, Section.WITHDRAWALS), (14125, Section.DEPOSITS)])
    check("truist: its totals, and it reconciles", plain.declared_section_totals == {Section.CHECKS: -2000, Section.WITHDRAWALS: -10000, Section.DEPOSITS: 14125} and reconcile(plain).ok)
    for step in (1, 2, 3, 4, 6, 9):
        check(f"truist: a space after every {step} characters of each label changes nothing", outcome(parser.parse, ["\n".join(truist_lines(step))]) == plain)
    lines = truist_lines(0)

    def changed(old, new):
        assert old in lines
        return outcome(parser.parse, ["\n".join(new if line == old else line for line in lines)])

    check("truist: the first money after the date is the balance", plain.opening_balance_cents == 8000)
    check("truist: text between the date and the money", changed(lines[4], "Your previous balance as of 07/09/2027 was  $80.00") == ("StatementError", "truist: previous balance not found"))
    check("truist: a date that does not exist", changed(lines[8], "Your new balance as of 08/3 2/2027  = $101.25") == ("StatementError", "truist: new balance not found"))
    check("truist: no space between the date and the money", changed(lines[4], "Your previous balance as of 07/09/2027$80.00") == ("StatementError", "truist: previous balance not found"))
    check("truist: a balance label inside other words", changed(lines[4], "NoteYour previous balance as of 07/09/2027  $80.00") == ("StatementError", "truist: previous balance not found"))
    more = changed("Other withdrawals, debits and service charges", "Other withdrawals, debits and service charges continued here")
    check("truist: a heading with more words on its line opens nothing", getattr(more, "lines", None) is not None and [item.section for item in more.lines] == [Section.CHECKS, Section.CHECKS, Section.DEPOSITS])
    summary = changed("Deposits, credits and interest", "Deposits, credits and interest  + 141.25")
    check("truist: a heading followed by an amount opens nothing", getattr(summary, "lines", None) is not None and Section.DEPOSITS not in [item.section for item in summary.lines])
    closed = changed("Total checks  = $20.00", "T o t a l s")
    check("truist: any line starting with Total closes the section", getattr(closed, "lines", None) is not None and len(closed.lines) == 5 and Section.CHECKS not in closed.declared_section_totals)
    inside = changed("Total deposits, credits and interest  = $141.25", "SubTotal deposits, credits and interest  = $141.25")
    check("truist: a total label inside other words is not declared", getattr(inside, "declared_section_totals", {}).keys() == {Section.CHECKS, Section.WITHDRAWALS})
    wide = [line.replace("  ", " " * 4000) for line in truist_lines(2)]
    started = time.monotonic()
    narrowed = [re.sub(" {3,}", "  ", line) for line in wide]
    result = outcome(parser.parse, ["\n".join(narrowed)])
    check("truist: narrowed wide text parses the same, quickly", result == plain and time.monotonic() - started < 2)


def round_trip_checks():
    from finances.ingest.parsers import detect_parser
    from finances.ingest.pdf_text import extract_pages
    from finances.ingest.reconcile import reconcile

    lines = truist_lines(3)
    pages = extract_pages(build_pdf([lines[:14], lines[14:]], blank_after=1))
    statement = detect_parser(pages).parse(pages)
    check("round trip: a spaced Truist statement with a blank last page, through a real PDF", statement.parser_name == "truist_deposit" and len(pages) == 3 and len(statement.lines) == 5 and reconcile(statement).ok and statement.closing_balance_cents == 10125)


section("pdf", pdf_checks)
section("truist", truist_checks)
section("round trip", round_trip_checks)
print("FAILURES", failures)
```

## 5. The coder's tests

There are none to review. Confirm that the coder added no test file beyond the two given ones and edited no existing test (section 2).

## 6. Project rules that apply to this phase

- **Money.** `parse_amount` reads every amount; the search in section 3 finds no `float`.
- **Privacy.** Neither module logs or prints. No exception carries text from a page or from `pypdf`.
- **Layering.** `git grep -n --untracked -E "finances\.(db|cli)" -- src/finances/ingest/parsers src/finances/ingest/pdf_text.py` prints nothing.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- Any change to the other four parsers or to `helpers.py`.
- Row patterns rewritten for speed.
- A different PDF library, a new dependency, or handling of rotated text.
- A change to the `Checks` rows rule.
- Any change under `tests/real_samples/` or `tests/fixtures/`.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 6a: repairs from the first run on real statements (YYYY-MM-DD)` with a real date. "Built" gives N, the passed count, and the outcome of the real-statement check as counts and seconds only. "Follow-ups" says the Truist `Checks` rows are still unconfirmed. No part of the entry quotes a statement. Earlier entries are unchanged.

## 9. Real statements

Run this once, from the repository root, and note how long it takes:

`.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`

- If it reports `no PDF files in data/samples`, write "no samples on this machine" in your report. Do not treat it as a failure.
- Otherwise every sample should pass, with none failed and none `xfail`, in seconds. Report the counts on the last line and the time.
- For a sample that fails or shows as `xfail`, report its summary line. That is a finding against this phase when its parser is `truist_deposit` or when the reason is `could not read PDF`; for another parser, report it on its own line and leave the verdict to the rest of this guide.
- A run that takes more than a minute is a finding against R4.
- You may also run `.venv/bin/python tests/real_samples/describe_layout.py` and quote its lines for a failing sample. It prints counts, yes-or-no answers, seconds, and fixed names only.
- Do not open a PDF, do not print extracted text, do not run a parser on a sample yourself, and do not include a file name from `data/samples/` in your report.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then four lines:

`Total passed: <the count from section 1>`

`Real statements: <no samples on this machine, or the counts and seconds from section 9>`

`Parts that needed a repair: <none, or Part 1 / Part 2>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code. For a failing real sample, pass on its summary line and the layout report's lines for it, and nothing else.
