# Verify Phase 4: the Capital One credit card parser

Spec: `docs/phases/phase-04-capital-one-parser.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote one module, `src/finances/ingest/parsers/capital_one.py`, added three given lines to `parsers/__init__.py`, and wrote one test file. Two test files were given, and the fixtures and the real-sample check were already in the repository.

Judge the parser by what it returns and by the rules, never by how it is written. These are all correct and must not be reported:

- any division into private helpers, and any regular expressions that give the specified results;
- reading the statement line by line or as one text;
- building the period dates with `date(...)` and the `MONTHS` tuple in any way that avoids `strptime`;
- passing the period to `parse_month_day` in whatever way dates every row correctly.

**Privacy.** This phase is the first that can touch real statements. You must not open, print, or quote anything under `data/samples/` either. Section 9 says exactly what you may run and what you may report.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least `632 passed`, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_capital_one_parser.py tests/integration/test_capital_one_import.py --no-cov` | exactly `42 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with `src/finances/ingest/parsers/capital_one.py` at 100% |
| `.venv/bin/python -c "from finances.ingest.parsers import registered_parsers; print([p.name for p in registered_parsers()])"` | `['capital_one_card']` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/ingest/parsers/__init__.py
?? src/finances/ingest/parsers/capital_one.py
?? tests/integration/test_capital_one_import.py
?? tests/unit/test_capital_one_parser.py
?? tests/unit/test_capital_one_parser_more.py
```

- `git diff HEAD -- src/finances/ingest/parsers/__init__.py` adds exactly the three lines under "Design" in the spec (an import with `# noqa: E402`, a blank line, and the `register` call) at the end of the file, and changes nothing else.
- The two given test files are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- tests/fixtures tests/real_samples tests/conftest.py src/finances/ingest/parsers/helpers.py src/finances/ingest/service.py src/finances/ingest/reconcile.py src/finances/ingest/dedup.py src/finances/ingest/pdf_text.py src/finances/ingest/statement.py src/finances/db src/finances/domain src/finances/cli pyproject.toml` is empty, and no existing test file is changed.
- `git status --short --ignored` shows no new `.pdf` file and no new file under `data/`.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | detection | probe script | every line starting `detect:` ends in `ok` |
| R2 | registration | probe script; gate 6 | the two `registry:` lines end in `ok` |
| R3 to R5 | header | probe script | every line starting `header:` ends in `ok` |
| R4 | no `strptime` | search below | no output |
| R6 | balances | probe script | `balances: opening and closing are negated` and `credit balance: positive opening and closing` end in `ok` |
| R7 | declared totals | probe script | `totals: all four declared` ends in `ok` |
| R8 to R12 | rows | probe script | every line starting `lines:` ends in `ok`, and so do `rows before any card section are ignored`, `rows after a card's Total Transactions line are ignored`, `a refund listed among the transactions is positive and stays a purchase`, and `inner spaces of a description are collapsed` |
| Part 3 rule | labels | probe script | `a label followed by a number that is not money is skipped` ends in `ok` |
| R9 | page breaks | probe script | the two `pages:` lines and `pdf: the card section carries over the page break` end in `ok` |
| R13 to R15 | interest and fees | probe script | `lines: two interest lines, in the statement's order`, `no interest or fee lines when they are zero`, and `pdf: four lines, the last one interest` end in `ok` |
| R16 | missing pieces | probe script | the four `missing` lines and `an impossible date in the period line` end in `ok` |
| R17 | undatable row | probe script | `a row dated outside the period is an error` ends in `ok` |
| R18 | only `StatementError` | probe script | `no pages` ends in `ok` |
| end to end | through PDF and registry | probe script | every line starting `pdf:` ends in `ok` |
| arithmetic | reconciliation | probe script | every line starting `reconcile:` ends in `ok` |
| messages | constant text | read every `raise` in `capital_one.py` | only the four messages in R16; none is an f-string or built from statement text |
| scope | nothing extra | probe script | `capital_one: nothing extra is public` ends in `ok` |

`git grep -n --untracked -F -e "strptime" -e "float" -e "print(" -e "logging" -e "\d" -- src/finances/ingest/parsers/capital_one.py`

## 4. Independent probes

The given tests compare the parser with five fixed fixtures. This script contains a small generator that prints a synthetic statement from structured data, so it can check statements the fixtures do not contain and know every expected line by construction: an account with two cards across a year end and a page break, two kinds of interest and a fee, a continuation line, a leap day, and a credit balance. It then edits a statement line by line to test the rules one at a time, and finally sends a statement through a real PDF and the registry. None of its names, digits, or amounts are in the fixtures or the spec.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It writes no file and reads nothing under `data/`. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import io
from datetime import date

from finances.domain.models import AccountType
from finances.ingest.parsers import capital_one, detect_parser, registered_parsers
from finances.ingest.parsers.capital_one import CapitalOneCardParser
from finances.ingest.pdf_text import extract_pages
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import Section, StatementLine

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


# ----- a generator of synthetic statement text, in the layout the parser must read -----
def money(cents):
    return f"${abs(cents) // 100:,}.{abs(cents) % 100:02d}"


def summary_amount(sign, cents):
    body = money(cents)
    if cents < 0:
        body = "- " + body
    return f"{sign} {body}".strip() if sign else body


def render(spec):
    """spec: dict with product, network, last4, period (text), days, summary (dict of cents as
    printed), cards (list of (holder, last4, credits, purchases)), interest (dict), fees,
    total_transactions, page_break_after (number of purchase rows on page 1 for first card)."""
    head = [
        "Capital One" + " " * 50 + "capitalone.com",
        f"{spec['product']}      {spec['network']} ending in {spec['last4']}",
        f"{spec['period']}      {spec['days']} days in Billing Cycle",
    ]
    s = spec["summary"]
    page = [
        *head,
        "",
        "Payment Information" + " " * 30 + "Account Summary",
        f"Payment Due Date      {spec['due']}" + " " * 14 + f"Previous Balance      {summary_amount('', s['previous'])}",
        f"New Balance      {summary_amount('', s['new'])}" + " " * 20 + f"Payments      {summary_amount('', -abs(s['payments'])) if s['payments'] else '- $0.00'}",
        f"Minimum Payment Due      $25.00" + " " * 12 + f"Other Credits      {'- ' + money(s['credits'])}",
        " " * 49 + f"Transactions      + {money(s['transactions'])}",
        " " * 49 + f"Cash Advances      + $0.00",
        " " * 49 + f"Fees Charged      + {money(s['fees'])}",
        " " * 49 + f"Interest Charged      + {money(s['interest'])}",
        " " * 49 + f"New Balance      = {summary_amount('', s['new'])}",
        "",
        "Rewards Summary      Previous Balance      1,234      Earned This Period      56",
        "",
    ]
    pages = []

    def row(r):
        trans, post, text, cents = r[:4]
        amount = ("- " if cents > 0 else "") + money(cents)
        out = [f"{trans}      {post}      {text}" + " " * max(2, 46 - len(text)) + amount]
        out += [" " * 22 + extra for extra in (r[4] if len(r) > 4 else [])]
        return out

    columns = "Trans Date      Post Date      Description" + " " * 34 + "Amount"
    for index, (holder, last4, credits, purchases) in enumerate(spec["cards"]):
        if credits:
            page += [f"{holder} #{last4}: Payments, Credits and Adjustments", columns]
            for r in credits:
                page += row(r)
            page.append("")
        page += [f"{holder} #{last4}: Transactions", columns]
        for position, r in enumerate(purchases):
            if index == 0 and position == spec.get("page_break_after", -1):
                page += ["", "Additional Information on the next page", "Page 1 of 2"]
                pages.append(page)
                page = [*head, "", "Transactions (Continued)", columns]
            page += row(r)
        page += [f"{holder} #{last4}: Total Transactions" + " " * 20 + money(sum(-r[3] for r in purchases)), ""]
    page += [
        f"Total Transactions for This Period" + " " * 20 + money(spec["total_transactions"]),
        "",
        "Fees",
        f"Total Fees for This Period" + " " * 28 + money(s["fees"]),
        "",
        "Interest Charged",
        *(f"Interest Charge on {name}" + " " * 24 + money(cents) for name, cents in spec["interest"].items()),
        f"Total Interest for This Period" + " " * 24 + money(s["interest"]),
        "",
        f"Total Fees charged in {spec['year']}      $35.00",
        f"Total Interest charged in {spec['year']}      $1.20",
        "",
        "Page %d of %d" % (len(pages) + 1, len(pages) + 1),
    ]
    pages.append(page)
    return pages


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def day(text, year):
    month, number = text.split()
    return date(year, MONTHS.index(month) + 1, int(number))


def expected_lines(spec, years):
    """The lines the parser must return for a spec. years maps a month name to its year."""
    lines = []
    for holder, last4, credits, purchases in spec["cards"]:
        for kind, rows in ((Section.PAYMENTS_CREDITS, credits), (Section.PURCHASES, purchases)):
            for row in rows:
                trans, post, text, cents = row[:4]
                lines.append(
                    StatementLine(
                        day(post, years[post.split()[0]]), day(trans, years[trans.split()[0]]),
                        " ".join(text.split()), cents, kind, card_last4=last4, cardholder=holder,
                    )
                )
    for name, cents in spec["interest"].items():
        if cents:
            lines.append(StatementLine(spec["end"], None, f"INTEREST CHARGE ON {name.upper()}", -cents, Section.INTEREST))
    if spec["summary"]["fees"]:
        lines.append(StatementLine(spec["end"], None, "TOTAL FEES FOR THIS PERIOD", -spec["summary"]["fees"], Section.FEES))
    return lines


WINTER = dict(
    product="Savor Credit Card", network="World Elite Mastercard", last4="8080", period="Dec 5, 2026 - Jan 4, 2027",
    days=31, due="Feb 1, 2027", year=2027, end=date(2027, 1, 4),
    summary=dict(previous=120050, payments=100000, credits=4575, transactions=30920, fees=2900, interest=1841, new=51136),
    cards=[
        ("PAT Q SMITH", "8080",
         [("Dec 20", "Dec 21", "CAPITAL ONE ONLINE PYMT", 100000)],
         [("Dec 4", "Dec 5", "PROBE BAKERY #7AUSTINTX", -1875), ("Dec 31", "Jan 2", "PROBE FUEL 0042", -5230),
          ("Jan 3", "Jan 4", "PROBE AIR0099887766DENVERCO", -19999, ["TK#: 0099887766 PSGR: SMITH/PAT", "ORIG: AUS DEST: DEN"]),
          ("Jan 3", "Jan 4", "PROBE BAKERY #7AUSTINTX", -1875)]),
        ("LEE SMITH-JONES", "9191",
         [("Dec 28", "Dec 29", "PROBE OUTLET RETURN", 4575)],
         [("Dec 15", "Dec 16", "PROBE PHARMACY", -1941)]),
    ],
    interest={"Purchases": 1800, "Cash Advances": 41, "Other Balances": 0}, total_transactions=30920, page_break_after=2,
)
WINTER_YEARS = {"Dec": 2026, "Jan": 2027}
LEAP = dict(
    product="Quicksilver Credit Card", network="Visa Signature", last4="0007", period="Feb 1, 2028 - Feb 29, 2028",
    days=29, due="Mar 25, 2028", year=2028, end=date(2028, 2, 29),
    summary=dict(previous=-1000, payments=0, credits=0, transactions=250, fees=0, interest=0, new=-750),
    cards=[("A B", "0007", [], [("Feb 29", "Feb 29", "PROBE KIOSK", -250)])],
    interest={"Purchases": 0, "Cash Advances": 0, "Other Balances": 0}, total_transactions=250,
)


def build_pdf(pages):
    objects = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        operators = ["BT", "/F1 8 Tf"]
        for index, row in enumerate(lines):
            for column, cell in enumerate(row.split("\t")):
                text = cell.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                operators.append(f"1 0 0 1 {40 + 230 * column} {760 - 11 * index} Tm ({text}) Tj")
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


def text_pages(spec):
    return ["\n".join(page) for page in render(spec)]


def winter_checks():
    pages = text_pages(WINTER)
    check("generator: the winter statement has two pages", len(pages) == 2)
    parser = CapitalOneCardParser()
    check("detect: generated first page", parser.detect(pages[0]) is True)
    statement = parser.parse(pages)
    check("header: names", (statement.parser_name, statement.institution, statement.account_type) == ("capital_one_card", "Capital One", AccountType.CREDIT_CARD))
    check("header: account digits are the account's, not a later card's", statement.account_last4 == "8080")
    check("header: period across a year end", (statement.period_start, statement.period_end) == (date(2026, 12, 5), date(2027, 1, 4)))
    check("balances: opening and closing are negated", (statement.opening_balance_cents, statement.closing_balance_cents) == (-120050, -51136))
    want = expected_lines(WINTER, WINTER_YEARS)
    check(f"lines: count {len(statement.lines)} of {len(want)}", len(statement.lines) == len(want))
    for index, (got, expected) in enumerate(zip(statement.lines, want, strict=False)):
        check(f"lines: line {index} ({expected.section.value}, {expected.card_last4})", got == expected)
    check("lines: a purchase dated the day before the period starts", statement.lines[1].transaction_date == date(2026, 12, 4))
    check("lines: December and January rows get different years", statement.lines[2].transaction_date.year == 2026 and statement.lines[2].posted_date.year == 2027)
    check("lines: continuation text is not kept", not any("PSGR" in item.description or "ORIG" in item.description for item in statement.lines))
    check("lines: two interest lines, in the statement's order", [item.description for item in statement.lines if item.section is Section.INTEREST] == ["INTEREST CHARGE ON PURCHASES", "INTEREST CHARGE ON CASH ADVANCES"])
    check("totals: all four declared", statement.declared_section_totals == {Section.PAYMENTS_CREDITS: 104575, Section.FEES: -2900, Section.INTEREST: -1841, Section.PURCHASES: -30920})
    result = reconcile(statement)
    check("reconcile: adds up", result.ok and result.difference_cents == 0)

    one_page = ["\n".join(pages)]
    check("pages: the same text on one page parses the same", parser.parse(one_page) == statement)
    padded = [("\n\n".join("   " + line + "   " for line in page.split("\n"))) for page in pages]
    check("pages: blank lines and outer spaces do not matter", parser.parse(padded) == statement)
    check("registry: registered once", [p.name for p in registered_parsers()].count("capital_one_card") == 1)
    found = outcome(detect_parser, pages)
    check("registry: detect_parser picks it", getattr(found, "name", None) == "capital_one_card")


def leap_checks():
    statement = CapitalOneCardParser().parse(text_pages(LEAP))
    check("credit balance: positive opening and closing", (statement.opening_balance_cents, statement.closing_balance_cents) == (1000, 750))
    check("leap day row", statement.lines == [StatementLine(date(2028, 2, 29), date(2028, 2, 29), "PROBE KIOSK", -250, Section.PURCHASES, card_last4="0007", cardholder="A B")])
    check("no interest or fee lines when they are zero", len(statement.lines) == 1)
    check("reconcile: adds up", reconcile(statement).ok)


def edge_checks():
    parser = CapitalOneCardParser()
    base = text_pages(LEAP)[0].split("\n")

    def variant(change):
        return ["\n".join(change(list(base)))]

    stray = variant(lambda lines: lines[:4] + ["Feb 2      Feb 3      PROBE STRAY ROW                  $9.99"] + lines[4:])
    check("rows before any card section are ignored", parser.parse(stray).lines == CapitalOneCardParser().parse(["\n".join(base)]).lines)
    position = next(index for index, line in enumerate(base) if "Total Transactions" in line and "#" in line)
    after_total = variant(lambda lines: lines[: position + 1] + ["Feb 5      Feb 6      PROBE AFTER TOTAL                $1.00"] + lines[position + 1 :])
    check("rows after a card's Total Transactions line are ignored", len(parser.parse(after_total).lines) == 1)
    refund = variant(lambda lines: [line.replace("PROBE KIOSK" + " " * 35 + "$2.50", "PROBE KIOSK" + " " * 35 + "- $2.50") for line in lines])
    got = parser.parse(refund).lines
    check("a refund listed among the transactions is positive and stays a purchase", len(got) == 1 and (got[0].amount_cents, got[0].section) == (250, Section.PURCHASES))
    spaced = variant(lambda lines: [line.replace("PROBE KIOSK", "PROBE   KIOSK") for line in lines])
    check("inner spaces of a description are collapsed", parser.parse(spaced).lines[0].description == "PROBE KIOSK")
    trap = variant(lambda lines: ["Rewards      Previous Balance      9,999      New Balance      8,888"] + lines)
    check("a label followed by a number that is not money is skipped", parser.parse(trap).opening_balance_cents == 1000)
    outside = variant(lambda lines: [line.replace("Feb 29      Feb 29      PROBE KIOSK", "Aug 15      Aug 16      PROBE KIOSK") for line in lines])
    check("a row dated outside the period is an error", outcome(parser.parse, outside) == ("StatementError", "date is outside the statement period"))
    for label, needle, message in [
        ("card ending", "ending in 0007", "capital one: card ending not found"),
        ("billing period", "Feb 1, 2028 - Feb 29, 2028", "capital one: billing period not found"),
        ("previous balance", "Previous Balance", "capital one: previous balance not found"),
        ("new balance", "New Balance", "capital one: new balance not found"),
    ]:
        broken = variant(lambda lines, needle=needle: [line.replace(needle, "XXXX") for line in lines])
        check(f"missing {label}", outcome(parser.parse, broken) == ("StatementError", message))
    check("an impossible date in the period line", outcome(parser.parse, variant(lambda lines: [line.replace("Feb 29, 2028", "Feb 30, 2028") for line in lines])) == ("StatementError", "capital one: billing period not found"))
    check("no pages", outcome(parser.parse, [])[0] == "StatementError")
    for label, page, want in [
        ("brand only", "Capital One", False),
        ("cycle line only", "29 days in Billing Cycle", False),
        ("another bank", "Example Bank\nStatement Period 09/01/2026 to 09/30/2026", False),
        ("web address and cycle line", "manage it at capitalone.com\n29 days in Billing Cycle", True),
        ("lower case does not count", "capital one\n29 days in billing cycle", False),
    ]:
        check(f"detect: {label}", parser.detect(page) is want)


def pdf_checks():
    lines = [
        "Capital One\tcapitalone.com",
        "Savor Credit Card\tWorld Elite Mastercard ending in 6006",
        "Jun 10, 2026 - Jul 9, 2026\t30 days in Billing Cycle",
        "Payment Due Date   Aug 5, 2026\tPrevious Balance   $80.00",
        "New Balance   $101.25\tPayments   - $80.00",
        "\tOther Credits   - $0.00",
        "\tTransactions   + $100.00",
        "\tFees Charged   + $0.00",
        "\tInterest Charged   + $1.25",
        "\tNew Balance   = $101.25",
        "KIM DOE #6006: Payments, Credits and Adjustments",
        "Jun 30  Jul 1\tCAPITAL ONE AUTOPAY PYMT\t- $80.00",
        "KIM DOE #6006: Transactions",
        "Jun 9  Jun 10\tPROBE GARDEN CENTER\t$60.00",
        "Jul 8  Jul 9\tPROBE CINEMA 12\t$40.00",
        "KIM DOE #6006: Total Transactions\t$100.00",
        "Total Transactions for This Period\t$100.00",
        "Interest Charge on Purchases\t$1.25",
    ]
    pages = extract_pages(build_pdf([lines[:14], ["Transactions (Continued)", *lines[14:]]]))
    statement = detect_parser(pages).parse(pages)
    check("pdf: read through extract_pages and the registry", statement.parser_name == "capital_one_card" and statement.account_last4 == "6006")
    check("pdf: balances", (statement.opening_balance_cents, statement.closing_balance_cents) == (-8000, -10125))
    check("pdf: four lines, the last one interest", [(item.amount_cents, item.section) for item in statement.lines] == [(8000, Section.PAYMENTS_CREDITS), (-6000, Section.PURCHASES), (-4000, Section.PURCHASES), (-125, Section.INTEREST)])
    check("pdf: the card section carries over the page break", statement.lines[2].cardholder == "KIM DOE" and statement.lines[2].posted_date == date(2026, 7, 9))
    check("pdf: reconciles", reconcile(statement).ok)


section("winter", winter_checks)
section("leap", leap_checks)
section("edges", edge_checks)
section("pdf", pdf_checks)
public = sorted(name for name, value in vars(capital_one).items() if getattr(value, "__module__", "") == capital_one.__name__ and not name.startswith("_"))
check(f"capital_one: nothing extra is public {public}", public == ["CapitalOneCardParser"])
print("FAILURES", failures)
```

## 5. The coder's tests

Read `tests/unit/test_capital_one_parser_more.py`.

- **Coverage of requirements.** For each of R1 to R18, name a test, given or the coder's, that would fail if the requirement were broken. A requirement with no such test is a finding. The coder's final message lists its own mapping; check it, do not trust it.
- **Assertions are exact.** Messages are compared with `==` against the full text, and lines are compared as whole `StatementLine` values or field by field with literal expected values. No `assert True`, no `pytest.raises(Exception)`, no `skip` or `xfail`, and no expected value produced by calling the parser.
- **Synthetic data.** Every name, merchant, number, and amount is invented. No test reads `data/`, and none opens a PDF from disk.
- **Isolation.** No test registers or unregisters a parser without the `parser_registry` fixture.
- **Spot checks.** For each change below, say which test, given or the coder's, would fail, by reading the test. If none would, that is a finding.
  1. The summary label rule accepts a label anywhere in a line, without requiring the start of the line or two spaces before it.
  2. `Other Credits` missing from a statement still produces a `PAYMENTS_CREDITS` declared total.
  3. A zero `Interest Charge on Cash Advances` line produces an interest line.
  4. The fee line is placed before the interest lines.
  5. A missing `New Balance` is reported as `capital one: previous balance not found`.
  6. A row dated outside the period is skipped instead of raising.
  7. `parse([])` raises `IndexError`.

## 6. Project rules that apply to this phase

- **Money and signs.** Purchases, fees, and interest come out negative; payments and refunds positive; a balance owed negative. The probe script checks each.
- **Privacy.** `capital_one.py` does not log or print, and its messages carry no statement text.
- **Layering.** `git grep -n --untracked -E "finances\.(db|cli)" -- src/finances/ingest/parsers` prints nothing.
- **Test data.** The fixtures are unchanged (section 2), and the coder's tests add no file under `tests/fixtures/`.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- Another parser, a base class for parsers, or a new function in `helpers.py`.
- Any change to the import service, reconciliation, fingerprints, or PDF extraction made to accommodate the parser.
- Merchant clean-up: stripping city or state from a description, or changing its case.
- Any code that reads `data/` other than the given `check_real_samples.py`.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 4: the Capital One credit card parser (YYYY-MM-DD)` with a real date. "Built" gives the passed count and the outcome of the real-statement check as counts only. No part of the entry quotes a statement: no merchant, name, amount, balance, or file name from `data/samples/`. Earlier entries are unchanged.

## 9. Real statements

Run this once, from the repository root:

`.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`

- If it reports `no PDF files in data/samples`, write "no samples on this machine" in your report. Do not treat it as a failure.
- Otherwise report only the counts on its last line and, for each failing sample, the summary line it printed: the sample number, the parser name, the line count, the difference in cents, and the sections that differ.
- A sample that shows as `xfail` with `unrecognized statement format` belongs to a bank whose parser does not exist yet. That is expected.
- A Capital One sample that fails is a finding against this phase, reported with its summary line only.
- Do not open a PDF, do not print extracted text, do not run the parser on a sample yourself, and do not include a file name from `data/samples/` in your report.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then four lines:

`Total passed: <the count from section 1>`

`Real statements: <no samples on this machine, or the counts from section 9>`

`Parts that needed a repair: <none, or Part 1 to Part 6 / tests>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code. For a failing real sample, pass on its summary line and nothing else; if the cause is not visible from the synthetic layout, say so in your report so that the architect can add a synthetic example.
