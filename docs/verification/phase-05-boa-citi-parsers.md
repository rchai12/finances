# Verify Phase 5: the Bank of America and Citi credit card parsers

Spec: `docs/phases/phase-05-boa-citi-parsers.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote two modules, `src/finances/ingest/parsers/boa.py` and `src/finances/ingest/parsers/citi.py`, added one function to `helpers.py` and five given lines to `parsers/__init__.py`, and wrote two test files. Four test files were given, and the fixtures and the real-sample check were already in the repository.

Judge the parsers by what they return and by the rules, never by how they are written. These are all correct and must not be reported:

- any division into private helpers, and any regular expressions that give the specified results;
- two parsers that share no code, or that repeat each other;
- reading a statement line by line or as one text, in one pass or two;
- building the period dates with `date(...)` in any way that avoids `strptime`.

**Privacy.** You must not open, print, or quote anything under `data/samples/`. Section 9 says exactly what you may run and what you may report.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it; it is `703` when Phase 4 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 106 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_find_labeled_amount.py tests/unit/test_boa_parser.py tests/unit/test_citi_parser.py tests/integration/test_boa_citi_import.py --no-cov` | exactly `106 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with `boa.py`, `citi.py`, and `helpers.py` each at 100% |
| `.venv/bin/python -c "from finances.ingest.parsers import registered_parsers; print([p.name for p in registered_parsers()])"` | `['capital_one_card', 'boa_card', 'citi_card']` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/ingest/parsers/__init__.py
 M src/finances/ingest/parsers/helpers.py
?? src/finances/ingest/parsers/boa.py
?? src/finances/ingest/parsers/citi.py
?? tests/integration/test_boa_citi_import.py
?? tests/unit/test_boa_parser.py
?? tests/unit/test_boa_parser_more.py
?? tests/unit/test_citi_parser.py
?? tests/unit/test_citi_parser_more.py
?? tests/unit/test_find_labeled_amount.py
```

- `git diff HEAD -- src/finances/ingest/parsers/__init__.py` adds exactly the five lines under "Design" in the spec (a blank line, two imports with `# noqa: E402`, a blank line, two `register` calls) at the end of the file, and changes nothing else.
- `git diff HEAD -- src/finances/ingest/parsers/helpers.py` only adds: the function `find_labeled_amount`, and private names it uses. No existing line is changed or removed.
- The four given test files are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- src/finances/ingest/parsers/capital_one.py tests/fixtures tests/real_samples tests/conftest.py src/finances/ingest/service.py src/finances/ingest/reconcile.py src/finances/ingest/dedup.py src/finances/ingest/pdf_text.py src/finances/ingest/statement.py src/finances/db src/finances/domain src/finances/cli pyproject.toml` is empty, and no existing test file is changed.
- `git status --short --ignored` shows no new `.pdf` file and no new file under `data/`.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1, R2 | the label rule | probe script; given helper tests in gate 4 | every line starting `helper:` |
| R3 | BoA detection | probe script | every line starting `boa detect:` |
| R4 to R6 | BoA header | probe script | every line starting `boa header:` and `boa year end: the start year` |
| R5 | no `strptime` | search below | no output |
| R7 | BoA balances | probe script | `boa balances: negated` and `boa credit balance: positive` |
| R8 | BoA declared totals | probe script | `boa totals` |
| R9 to R12 | BoA rows | probe script | every line starting `boa lines:`, plus `boa year end: row dates` and `boa rows before any section are ignored` |
| R13 | BoA missing pieces | probe script | the four lines starting `boa missing`, plus `boa impossible period date` and `boa unknown month` |
| R14 | Citi detection | probe script | every line starting `citi detect:` |
| R15 to R17 | Citi header | probe script | every line starting `citi header:` |
| R18 | Citi balances | probe script | `citi balances: negated` |
| R19 | Citi declared totals | probe script | `citi totals` |
| R20 to R24 | Citi cardholders and rows | probe script | every line starting `citi lines:` |
| R25 | Citi missing pieces | probe script | the four lines starting `citi missing`, plus `citi impossible period date` |
| R26 | order | probe script | the numbered `line N` checks of both banks |
| R27 | undatable row | probe script | `boa row outside the period` and `citi row outside the period` |
| R28 | only `StatementError` | probe script | `boa no pages` and `citi no pages` |
| R29 | registration | probe script; gate 6 | the lines starting `registry:`, `boa registry:`, `citi registry:` |
| page breaks | sections carry over | probe script | the lines starting `boa pages:`, `citi pages:`, and the two `four lines across the page break` lines |
| end to end | through PDF and registry | probe script | every line starting `pdf boa:` and `pdf citi:` |
| arithmetic | reconciliation | probe script | `boa reconcile` and `citi reconcile` |
| messages | constant text | read every `raise` in `boa.py` and `citi.py` | only the eight messages in R13 and R25; none is an f-string or built from statement text |
| scope | nothing extra | probe script | the two lines containing `nothing extra is public` |

`git grep -n --untracked -F -e "strptime" -e "float" -e "print(" -e "logging" -e "\d" -- src/finances/ingest/parsers/boa.py src/finances/ingest/parsers/citi.py`

Then read `find_labeled_amount` in `helpers.py`: it has the signature in the spec, uses `parse_amount` for the money, and contains no `float`, `print(`, or `logging`.

## 4. Independent probes

The given tests compare the parsers with five fixed fixtures. This script contains generators that print a synthetic statement from structured data, so it can check statements the fixtures do not contain and know every expected line by construction: a Bank of America statement with two cards, a page break, zero rows, and two kinds of interest; one that crosses a year end with a credit balance; and a Citi statement with three cardholders, one of them without activity, a row without a sale date, and a rewards page. It then edits statements to test the rules one at a time, and finally sends one statement of each bank through a real PDF and the registry. None of its names, digits, or amounts are in the fixtures or the spec.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It writes no file and reads nothing under `data/`. Every line must end in `ok`; the last line must be `FAILURES 0`. A line that says a section `ran to the end (stopped by ...)` and ends in `FAIL` means the code raised where it should not have; report it with the exception named on that line.

```python
from datetime import date

from finances.domain.models import AccountType
from finances.ingest.parsers import boa, citi, detect_parser, registered_parsers
from finances.ingest.parsers.boa import BoaCardParser
from finances.ingest.parsers.citi import CitiCardParser
from finances.ingest.parsers.helpers import find_labeled_amount
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


# ----- generators of synthetic statement text, in the layouts the parsers must read -----
def money(cents):
    return f"${abs(cents) // 100:,}.{abs(cents) % 100:02d}"


def plain(cents):
    """An amount as BoA prints it in a row: no dollar sign, a minus for credits."""
    return ("-" if cents < 0 else "") + f"{abs(cents) // 100:,}.{abs(cents) % 100:02d}"


def signed(cents, plus=False):
    sign = "-" if cents < 0 else ("+" if plus else "")
    return sign + money(cents)


def boa_totals(spec):
    """Printed (file-sign) totals: purchases positive, credits negative."""
    return {
        "credits": sum(r[5] for r in spec["credits"]),
        "purchases": sum(r[5] for r in spec["purchases"]),
        "fees": sum(r[3] for r in spec["fees"]),
        "interest": sum(r[3] for r in spec["interest"]),
    }


def render_boa(spec):
    """spec: number (16 digits spaced), period text, previous (printed cents), credits/purchases rows
    (trans, post, text, ref, card, printed cents), fees/interest rows (trans, post, text, printed cents),
    break_after (purchase rows on page 1)."""
    t = boa_totals(spec)
    new = spec["previous"] + t["credits"] + t["purchases"] + t["fees"] + t["interest"]
    head = [
        "Bank of America" + " " * 40 + "www.bankofamerica.com",
        "Customized Cash Rewards Visa Signature",
        f"Account# {spec['number']}",
        spec["period"],
    ]
    columns = [
        "Transaction   Posting" + " " * 38 + "Reference   Account",
        "Date          Date      Description" + " " * 24 + "Number      Number      Amount",
    ]
    page = [
        *head,
        "",
        "Account Summary",
        f"Previous Balance" + " " * 26 + signed(spec["previous"]),
        f"Payments and Other Credits" + " " * 16 + signed(t["credits"]),
        f"Purchases and Adjustments" + " " * 17 + signed(t["purchases"]),
        f"Fees Charged" + " " * 30 + signed(t["fees"]),
        f"Interest Charged" + " " * 26 + signed(t["interest"]),
        f"New Balance Total" + " " * 25 + signed(new),
        f"Total Credit Line" + " " * 25 + "$20,000.00",
        f"Statement Closing Date" + " " * 20 + "04/28/2026",
        "",
        "Transactions",
        *columns,
        "Payments and Other Credits",
    ]
    pages = []

    def six(r):
        trans, post, text, ref, card, cents = r
        return f"{trans}   {post}   {text}" + " " * max(2, 44 - len(text)) + f"{ref}   {card}   {plain(cents)}"

    def four(r):
        trans, post, text, cents = r
        return f"{trans}   {post}   {text}" + " " * max(2, 58 - len(text)) + plain(cents)

    page += [six(r) for r in spec["credits"]]
    page += [f"TOTAL PAYMENTS AND OTHER CREDITS FOR THIS PERIOD" + " " * 10 + signed(t["credits"]), "Purchases and Adjustments"]
    for position, r in enumerate(spec["purchases"]):
        if position == spec.get("break_after", -1):
            page += ["continued on next page...", "Page 1 of 2"]
            pages.append(page)
            page = [*head, "", "Transactions (continued)", *columns]
        page.append(six(r))
    page += [f"TOTAL PURCHASES AND ADJUSTMENTS FOR THIS PERIOD" + " " * 11 + signed(t["purchases"]), "Fees Charged"]
    page += [four(r) for r in spec["fees"]]
    page += [f"TOTAL FEES CHARGED FOR THIS PERIOD" + " " * 24 + signed(t["fees"]), "Interest Charged"]
    page += [four(r) for r in spec["interest"]]
    page += [
        f"TOTAL INTEREST CHARGED FOR THIS PERIOD" + " " * 20 + signed(t["interest"]),
        "",
        "2026 Totals Year-to-Date",
        "Total fees charged in 2026      $29.00",
        "Total interest charged in 2026      $12.34",
        "",
        "Rewards",
        "04/28   04/28   CASH BACK EARNED THIS PERIOD" + " " * 20 + "12.00",
    ]
    pages.append(page)
    return pages, new


def citi_totals(spec):
    purchases = sum(r[3] for _, _, rows in spec["cards"] for r in rows)
    payments = sum(r[3] for r in spec["credits"] if r[4] == "payment")
    credits = sum(r[3] for r in spec["credits"] if r[4] == "credit")
    return {
        "payments": payments, "credits": credits, "purchases": purchases,
        "fees": sum(r[3] for r in spec["fees"]), "interest": sum(r[3] for r in spec["interest"]),
    }


def render_citi(spec):
    """spec: last4, period text, previous (printed cents), credits rows (sale, post, text, printed cents,
    'payment'|'credit'), cards (holder, last4, rows (sale-or-None, post, text, printed cents)),
    fees/interest rows (sale, post, text, printed cents), break_after_card (index) optional."""
    t = citi_totals(spec)
    new = spec["previous"] + t["payments"] + t["credits"] + t["purchases"] + t["fees"] + t["interest"]
    head = [
        "Citi" + " " * 50 + "www.citicards.com",
        "Costco Anywhere Visa Card by Citi",
        f"Account number ending in: {spec['last4']}",
        f"Billing Period: {spec['period']}",
    ]
    columns = ["Sale    Post", "Date    Date    Description" + " " * 34 + "Amount"]
    page = [
        *head,
        "",
        "Account Summary",
        "Previous balance" + " " * 22 + signed(spec["previous"]),
        "Payments" + " " * 30 + "-" + money(t["payments"]),
        "Credits" + " " * 31 + "-" + money(t["credits"]),
        "Purchases" + " " * 29 + "+" + money(t["purchases"]),
        "Cash advances" + " " * 25 + "+$0.00",
        "Fees" + " " * 34 + "+" + money(t["fees"]),
        "Interest" + " " * 30 + "+" + money(t["interest"]),
        "New balance" + " " * 27 + signed(new),
        "Credit Limit" + " " * 26 + "$10,000.00",
        "",
        "CARDHOLDER SUMMARY",
        *(f"{holder}      Card ending in {last4}      New Charges      {money(sum(r[3] for r in rows))}" for holder, last4, rows in spec["cards"]),
        "",
        "ACCOUNT ACTIVITY",
        *columns,
        "Payments, Credits and Adjustments",
    ]
    pages = []

    def row(r):
        sale, post, text, cents = r[:4]
        first = sale if sale else " " * 5
        return f"{first}   {post}   {text}" + " " * max(2, 44 - len(text)) + signed(cents)

    page += [row(r) for r in spec["credits"]]
    for index, (holder, _last4, rows) in enumerate(spec["cards"]):
        if index == spec.get("break_before_card", -1):
            page += ["Page 1 of 3"]
            pages.append(page)
            page = [*head, "", "ACCOUNT ACTIVITY (continued)", *columns]
        page.append(holder)
        if rows:
            page.append("Standard Purchases")
            page += [row(r) for r in rows]
        else:
            page.append("No Activity")
    page += ["Fees Charged", *(row(r) for r in spec["fees"]), "TOTAL FEES FOR THIS PERIOD" + " " * 22 + money(t["fees"])]
    page += ["Interest Charged", *(row(r) for r in spec["interest"]), "TOTAL INTEREST FOR THIS PERIOD" + " " * 18 + money(t["interest"])]
    page += ["", "2026 totals year-to-date", "Total fees charged in 2026      $0.00", "Total interest charged in 2026      $0.00"]
    pages.append(page)
    pages.append([
        *head,
        "",
        "Costco Cash Rewards Summary",
        "Rewards balance from last statement      $12.34",
        "09/10   Rewards earned this period      $7.59",
        "Purchases      1% on all other purchases",
    ])
    return pages, new


def md(text, years):
    month, day = (int(part) for part in text.split("/"))
    return date(years[month], month, day)


def boa_expected(spec, years):
    lines = []
    for kind, rows in ((Section.PAYMENTS_CREDITS, spec["credits"]), (Section.PURCHASES, spec["purchases"])):
        for trans, post, text, ref, card, cents in rows:
            lines.append(StatementLine(md(post, years), md(trans, years), " ".join(text.split()), -cents, kind, card_last4=card, external_ref=ref))
    for kind, rows in ((Section.FEES, spec["fees"]), (Section.INTEREST, spec["interest"])):
        for trans, post, text, cents in rows:
            if cents:
                lines.append(StatementLine(md(post, years), md(trans, years), text, -cents, kind))
    return lines


def citi_expected(spec, years):
    lines = []
    for sale, post, text, cents, _ in spec["credits"]:
        lines.append(StatementLine(md(post, years), md(sale, years), text, -cents, Section.PAYMENTS_CREDITS))
    for holder, last4, rows in spec["cards"]:
        for sale, post, text, cents in rows:
            lines.append(StatementLine(md(post, years), md(sale, years) if sale else None, text, -cents, Section.PURCHASES, card_last4=last4, cardholder=holder))
    for kind, rows in ((Section.FEES, spec["fees"]), (Section.INTEREST, spec["interest"])):
        for sale, post, text, cents in rows:
            if cents:
                lines.append(StatementLine(md(post, years), md(sale, years), text, -cents, kind))
    return lines


BOA_WINTER = dict(
    number="4400 0000 0000 8080", period="November 28 - December 27, 2026", previous=120050,
    credits=[("12/05", "12/05", "PAYMENT FROM CHK 0042 CONF#P11111111", "6001", "8080", -100000),
             ("12/09", "12/10", "PROBE OUTLET RETURN TULSA OK", "6002", "9191", -4575)],
    purchases=[("11/27", "11/28", "PROBE BAKERY #7 TULSA OK", "6003", "8080", 1875),
               ("12/01", "12/02", "PROBE FUEL 0042 1234 TULSA OK", "6004", "9191", 5230),
               ("12/26", "12/27", "PROBE BAKERY #7 TULSA OK", "6005", "8080", 1875)],
    fees=[("12/15", "12/15", "LATE FEE FOR PAYMENT DUE 12/10", 2900), ("12/15", "12/15", "ANNUAL FEE WAIVED", 0)],
    interest=[("12/27", "12/27", "INTEREST CHARGED ON PURCHASES", 1800), ("12/27", "12/27", "INTEREST CHARGED ON CASH ADVANCES", 41)],
    break_after=1,
)
BOA_NEW_YEAR = dict(
    number="4400 0000 0000 0007", period="December 28 - January 27, 2028", previous=-1000,
    credits=[], purchases=[("12/31", "01/02", "PROBE KIOSK", "7001", "0007", 250)], fees=[], interest=[],
)
CITI_WINTER = dict(
    last4="8080", period="11/28/26-12/27/26", previous=120050,
    credits=[("12/05", "12/05", "ONLINE PAYMENT, THANK YOU", -100000, "payment"),
             ("12/09", "12/10", "PROBE OUTLET RETURN TULSA OK", -4575, "credit")],
    cards=[("PAT Q SMITH", "8080", [("11/27", "11/28", "PROBE BAKERY #7 TULSA OK", 1875), (None, "12/02", "PROBE FUEL 0042", 5230)]),
           ("LEE SMITH-JONES", "9191", []),
           ("AL O'DAY", "7272", [("12/26", "12/27", "PROBE BAKERY #7 TULSA OK", 1875)])],
    fees=[("12/15", "12/15", "LATE FEE", 2900), ("12/15", "12/15", "ANNUAL FEE WAIVED", 0)],
    interest=[("12/27", "12/27", "INTEREST CHARGED TO STANDARD PURCH", 1841)],
    break_before_card=2,
)


def text_pages(pages):
    return ["\n".join(page) for page in pages]


def edited(pages, old, new):
    return [page.replace(old, new) for page in pages]


def boa_checks():
    parser = BoaCardParser()
    rendered, new = render_boa(BOA_WINTER)
    pages = text_pages(rendered)
    check("boa detect: generated first page", parser.detect(pages[0]) is True)
    statement = parser.parse(pages)
    check("boa header: names", (statement.parser_name, statement.institution, statement.account_type) == ("boa_card", "Bank of America", AccountType.CREDIT_CARD))
    check("boa header: last four digits of the account number", statement.account_last4 == "8080")
    check("boa header: period", (statement.period_start, statement.period_end) == (date(2026, 11, 28), date(2026, 12, 27)))
    check("boa balances: negated", (statement.opening_balance_cents, statement.closing_balance_cents) == (-120050, -new))
    want = boa_expected(BOA_WINTER, {11: 2026, 12: 2026})
    check(f"boa lines: count {len(statement.lines)} of {len(want)}", len(statement.lines) == len(want))
    for index, (got, expected) in enumerate(zip(statement.lines, want, strict=False)):
        check(f"boa lines: line {index} ({expected.section.value})", got == expected)
    check("boa lines: zero rows are left out", not any(item.amount_cents == 0 for item in statement.lines))
    check("boa lines: reference and card come from their own columns", (statement.lines[3].external_ref, statement.lines[3].card_last4) == ("6004", "9191"))
    check("boa lines: fee and interest rows have no card or reference", all(item.card_last4 is None and item.external_ref is None for item in statement.lines[5:]))
    check("boa lines: no cardholder", all(item.cardholder is None for item in statement.lines))
    check("boa lines: the row after the totals is not read", not any("CASH BACK" in item.description for item in statement.lines))
    check("boa totals", statement.declared_section_totals == {Section.PAYMENTS_CREDITS: 104575, Section.PURCHASES: -8980, Section.FEES: -2900, Section.INTEREST: -1841})
    check("boa reconcile", reconcile(statement).ok)
    check("boa pages: one page or two gives the same statement", parser.parse(["\n".join(pages)]) == statement)
    spaced = parser.parse(edited(pages, "PROBE FUEL 0042 1234 TULSA OK", "PROBE   FUEL  0042 1234   TULSA OK"))
    check("boa lines: inner spaces of a description are collapsed", spaced == statement)
    found = outcome(detect_parser, pages)
    check("boa registry: detect_parser picks it", getattr(found, "name", None) == "boa_card")

    rendered, new = render_boa(BOA_NEW_YEAR)
    pages = text_pages(rendered)
    statement = parser.parse(pages)
    check("boa year end: the start year is one less than the printed year", (statement.period_start, statement.period_end) == (date(2027, 12, 28), date(2028, 1, 27)))
    check("boa year end: row dates", statement.lines == [StatementLine(date(2028, 1, 2), date(2027, 12, 31), "PROBE KIOSK", -250, Section.PURCHASES, card_last4="0007", external_ref="7001")])
    check("boa credit balance: positive", (statement.opening_balance_cents, statement.closing_balance_cents) == (1000, 750))
    for label, old, message in [
        ("account number", "Account# 4400 0000 0000 0007", "boa: account number not found"),
        ("period", "December 28 - January 27, 2028", "boa: statement period not found"),
        ("previous balance", "Previous Balance", "boa: previous balance not found"),
        ("new balance", "New Balance Total", "boa: new balance not found"),
    ]:
        check(f"boa missing {label}", outcome(parser.parse, edited(pages, old, "XXXX")) == ("StatementError", message))
    check("boa impossible period date", outcome(parser.parse, edited(pages, "January 27, 2028", "January 32, 2028")) == ("StatementError", "boa: statement period not found"))
    check("boa unknown month", outcome(parser.parse, edited(pages, "December 28 - January", "Smarch 28 - January")) == ("StatementError", "boa: statement period not found"))
    check("boa row outside the period", outcome(parser.parse, edited(pages, "12/31   01/02   PROBE KIOSK", "07/04   07/05   PROBE KIOSK")) == ("StatementError", "date is outside the statement period"))
    check("boa no pages", outcome(parser.parse, [])[0] == "StatementError")
    stray = ["\n".join(["12/30   12/30   PROBE STRAY ROW      7009   0007   9.99", *pages[0].split("\n")])]
    check("boa rows before any section are ignored", parser.parse(stray).lines == statement.lines)
    for label, page, want in [("address only", "bankofamerica.com", False), ("account only", "Account# 1", False), ("both", "bankofamerica.com Account# 1", True), ("citi page", "citicards.com\nBilling Period: 01/01/26-01/31/26", False)]:
        check(f"boa detect: {label}", parser.detect(page) is want)


def citi_checks():
    parser = CitiCardParser()
    rendered, new = render_citi(CITI_WINTER)
    pages = text_pages(rendered)
    check("citi detect: generated first page", parser.detect(pages[0]) is True)
    statement = parser.parse(pages)
    check("citi header: names", (statement.parser_name, statement.institution, statement.account_type) == ("citi_card", "Citi", AccountType.CREDIT_CARD))
    check("citi header: account digits", statement.account_last4 == "8080")
    check("citi header: two-digit years", (statement.period_start, statement.period_end) == (date(2026, 11, 28), date(2026, 12, 27)))
    check("citi balances: negated", (statement.opening_balance_cents, statement.closing_balance_cents) == (-120050, -new))
    want = citi_expected(CITI_WINTER, {11: 2026, 12: 2026})
    check(f"citi lines: count {len(statement.lines)} of {len(want)}", len(statement.lines) == len(want))
    for index, (got, expected) in enumerate(zip(statement.lines, want, strict=False)):
        check(f"citi lines: line {index} ({expected.section.value}, {expected.cardholder})", got == expected)
    check("citi lines: payments have no cardholder or card", all(item.cardholder is None and item.card_last4 is None for item in statement.lines[:2]))
    check("citi lines: a row without a sale date", statement.lines[3].transaction_date is None and statement.lines[3].posted_date == date(2026, 12, 2))
    check("citi lines: third cardholder after a page break and one with no activity", (statement.lines[4].cardholder, statement.lines[4].card_last4) == ("AL O'DAY", "7272"))
    check("citi lines: fee and interest rows have no cardholder", all(item.cardholder is None and item.card_last4 is None for item in statement.lines[5:]))
    check("citi lines: zero rows are left out", not any(item.amount_cents == 0 for item in statement.lines))
    check("citi lines: the rewards page is not read", not any("Rewards" in item.description for item in statement.lines))
    check("citi totals", statement.declared_section_totals == {Section.PAYMENTS_CREDITS: 104575, Section.PURCHASES: -8980, Section.FEES: -2900, Section.INTEREST: -1841})
    check("citi reconcile", reconcile(statement).ok)
    check("citi pages: one page or three gives the same statement", parser.parse(["\n".join(pages)]) == statement)
    spaced = parser.parse(edited(pages, "PROBE BAKERY #7 TULSA OK", "PROBE   BAKERY  #7   TULSA OK"))
    check("citi lines: inner spaces of a description are collapsed", spaced == statement)
    check("citi lines: rows before any section are ignored", parser.parse(["\n".join(["11/29   11/29   PROBE STRAY ROW      $9.99", *pages])]).lines == statement.lines)
    found = outcome(detect_parser, pages)
    check("citi registry: detect_parser picks it", getattr(found, "name", None) == "citi_card")
    for label, old, message in [
        ("account number", "Account number ending in: 8080", "citi: account number not found"),
        ("period", "Billing Period: 11/28/26-12/27/26", "citi: billing period not found"),
        ("previous balance", "Previous balance", "citi: previous balance not found"),
        ("new balance", "New balance", "citi: new balance not found"),
    ]:
        check(f"citi missing {label}", outcome(parser.parse, edited(pages, old, "XXXX")) == ("StatementError", message))
    check("citi impossible period date", outcome(parser.parse, edited(pages, "11/28/26-12/27/26", "11/31/26-12/27/26")) == ("StatementError", "citi: billing period not found"))
    check("citi row outside the period", outcome(parser.parse, edited(pages, "11/27   11/28   PROBE BAKERY", "06/01   06/02   PROBE BAKERY")) == ("StatementError", "date is outside the statement period"))
    check("citi no pages", outcome(parser.parse, [])[0] == "StatementError")
    for label, page, want in [("address only", "citicards.com", False), ("period only", "Billing Period: 01/01/26-01/31/26", False), ("both", "citicards.com\nBilling Period: 01/01/26-01/31/26", True), ("boa page", "bankofamerica.com Account# 1", False)]:
        check(f"citi detect: {label}", parser.detect(page) is want)


def helper_checks():
    lines = ["Balance      12,345 points", "A      Balance      - $1,000.01      B      $2.00", "Balance      $9.00"]
    check("helper: first line with money after the label", find_labeled_amount(lines, "Balance") == -100001)
    check("helper: label must start the line or follow two spaces", find_labeled_amount(["Old Balance   $5.00"], "Balance") is None)
    check("helper: no match", find_labeled_amount(lines, "Total") is None and find_labeled_amount([], "Balance") is None)
    check("helper: unreadable money is passed over", find_labeled_amount(["Due   - + $1.00", "Due   +$3.50"], "Due") == 350)
    check("helper: label characters are literal", find_labeled_amount(["A.B   $1.00"], "A.B") == 100 and find_labeled_amount(["AxB   $1.00"], "A.B") is None)


def build_pdf(pages):
    objects = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        operators = ["BT", "/F1 8 Tf"]
        for index, row in enumerate(lines):
            for column, cell in enumerate(row.split("\t")):
                text = cell.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                operators.append(f"1 0 0 1 {40 + 110 * column} {760 - 11 * index} Tm ({text}) Tj")
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


def pdf_checks():
    boa_lines = [
        "Bank of America   www.bankofamerica.com", "Account# 4400 0000 0000 6006", "July 10 - August 9, 2026",
        "Previous Balance   $80.00", "Payments and Other Credits   -$80.00", "Purchases and Adjustments   $100.00",
        "Fees Charged   $0.00", "Interest Charged   $1.25", "New Balance Total   $101.25",
        "Payments and Other Credits", "07/30  07/31\tPAYMENT FROM CHK 0042   8001  6006  -80.00",
        "TOTAL PAYMENTS AND OTHER CREDITS FOR THIS PERIOD   -$80.00",
        "Purchases and Adjustments", "07/09  07/10\tPROBE GARDEN CENTER   8002  6006  60.00",
    ]
    boa_second = ["Transactions (continued)", "08/08  08/09\tPROBE CINEMA 12   8003  6006  40.00",
                  "TOTAL PURCHASES AND ADJUSTMENTS FOR THIS PERIOD   $100.00", "Interest Charged",
                  "08/09  08/09\tINTEREST CHARGED ON PURCHASES   1.25", "TOTAL INTEREST CHARGED FOR THIS PERIOD   $1.25"]
    pages = extract_pages(build_pdf([boa_lines, boa_second]))
    statement = detect_parser(pages).parse(pages)
    check("pdf boa: through extract_pages and the registry", statement.parser_name == "boa_card" and statement.account_last4 == "6006")
    check("pdf boa: four lines across the page break", [(item.amount_cents, item.section) for item in statement.lines] == [(8000, Section.PAYMENTS_CREDITS), (-6000, Section.PURCHASES), (-4000, Section.PURCHASES), (-125, Section.INTEREST)])
    check("pdf boa: reconciles", reconcile(statement).ok and statement.closing_balance_cents == -10125)
    citi_lines = [
        "Citi   www.citicards.com", "Account number ending in: 5005", "Billing Period: 07/10/26-08/09/26",
        "Previous balance   $80.00", "Payments   -$80.00", "Credits   -$0.00", "Purchases   +$100.00", "Fees   +$0.00",
        "Interest   +$1.25", "New balance   $101.25", "CARDHOLDER SUMMARY",
        "KIM DOE   Card ending in 5005   New Charges   $60.00", "RAY DOE   Card ending in 5115   New Charges   $40.00",
        "Payments, Credits and Adjustments", "07/30  07/31\tONLINE PAYMENT, THANK YOU   -$80.00",
        "KIM DOE", "Standard Purchases", "07/09  07/10\tPROBE GARDEN CENTER   $60.00",
    ]
    citi_second = ["RAY DOE", "Standard Purchases", "\t08/09\tPROBE CINEMA 12   $40.00", "Fees Charged",
                   "TOTAL FEES FOR THIS PERIOD   $0.00", "Interest Charged",
                   "08/09  08/09\tINTEREST CHARGED TO STANDARD PURCH   $1.25", "TOTAL INTEREST FOR THIS PERIOD   $1.25"]
    pages = extract_pages(build_pdf([citi_lines, citi_second]))
    statement = detect_parser(pages).parse(pages)
    check("pdf citi: through extract_pages and the registry", statement.parser_name == "citi_card" and statement.account_last4 == "5005")
    check("pdf citi: four lines across the page break", [(item.amount_cents, item.cardholder, item.card_last4) for item in statement.lines] == [(8000, None, None), (-6000, "KIM DOE", "5005"), (-4000, "RAY DOE", "5115"), (-125, None, None)])
    check("pdf citi: the row without a sale date", statement.lines[2].transaction_date is None and statement.lines[2].posted_date == date(2026, 8, 9))
    check("pdf citi: reconciles", reconcile(statement).ok and statement.closing_balance_cents == -10125)


section("boa", boa_checks)
section("citi", citi_checks)
section("helper", helper_checks)
section("pdf", pdf_checks)
names = [parser.name for parser in registered_parsers()]
check(f"registry: three parsers, each once {names}", sorted(names) == ["boa_card", "capital_one_card", "citi_card"])
for module, expected in ((boa, ["BoaCardParser"]), (citi, ["CitiCardParser"])):
    public = sorted(name for name, value in vars(module).items() if getattr(value, "__module__", "") == module.__name__ and not name.startswith("_"))
    check(f"{module.__name__}: nothing extra is public {public}", public == expected)
print("FAILURES", failures)
```

## 5. The coder's tests

Read `tests/unit/test_boa_parser_more.py` and `tests/unit/test_citi_parser_more.py`.

- **Coverage of requirements.** For each of R1 to R29, name a test, given or the coder's, that would fail if the requirement were broken. A requirement with no such test is a finding. The coder's final message lists its own mapping; check it, do not trust it.
- **Assertions are exact.** Messages are compared with `==` against the full text, and lines are compared as whole `StatementLine` values or field by field with literal expected values. No `assert True`, no `pytest.raises(Exception)`, no `skip` or `xfail`, and no expected value produced by calling a parser.
- **Synthetic data.** Every name, merchant, number, and amount is invented. No test reads `data/`, and none opens a PDF from disk.
- **Isolation.** No test registers or unregisters a parser without the `parser_registry` fixture.
- **Spot checks.** For each change below, say which test, given or the coder's, would fail, by reading the test. If none would, that is a finding.
  1. A Bank of America statement with no `New Balance Total` is reported as `boa: previous balance not found`.
  2. A Bank of America period `June 31, 2026` raises `ValueError` instead of `StatementError`.
  3. A missing `Fees Charged` summary line gives a `FEES` declared total of `0` instead of no entry.
  4. A Citi statement with `Payments` but no `Credits` still declares a `PAYMENTS_CREDITS` total.
  5. A Citi row dated outside the period is skipped instead of raising.
  6. A Citi row printed before `Payments, Credits and Adjustments` is read.
  7. A Citi cardholder name printed with two spaces between its words above the rows is not recognized.
  8. `parse([])` raises `IndexError` in either parser.

## 6. Project rules that apply to this phase

- **Money and signs.** Purchases, fees, and interest come out negative; payments and refunds positive; a balance owed negative. The probe script checks each.
- **Privacy.** Neither module logs or prints, and their messages carry no statement text.
- **Layering.** `git grep -n --untracked -E "finances\.(db|cli)" -- src/finances/ingest/parsers` prints nothing.
- **Test data.** The fixtures are unchanged (section 2), and the coder's tests add no file under `tests/fixtures/`.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- Any change to `capital_one.py`, including moving it onto `find_labeled_amount`.
- A base class for parsers, a shared "card parser" module, or any new function in `helpers.py` other than `find_labeled_amount`.
- Any change to the import service, reconciliation, fingerprints, or PDF extraction made to accommodate a parser.
- Merchant clean-up: stripping city or state from a description, or changing its case.
- Any code that reads `data/` other than the given `check_real_samples.py`.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 5: the Bank of America and Citi credit card parsers (YYYY-MM-DD)` with a real date. "Built" gives N, the passed count, and the outcome of the real-statement check as counts only. No part of the entry quotes a statement: no merchant, name, amount, balance, or file name from `data/samples/`. Earlier entries are unchanged.

## 9. Real statements

Run this once, from the repository root:

`.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`

- If it reports `no PDF files in data/samples`, write "no samples on this machine" in your report. Do not treat it as a failure.
- Otherwise report only the counts on its last line and, for each failing sample, the summary line it printed: the sample number, the parser name, the line count, the difference in cents, and the sections that differ.
- A sample that shows as `xfail` with `unrecognized statement format` belongs to a bank whose parser does not exist yet. That is expected.
- A failing sample whose parser is `boa_card` or `citi_card` is a finding against this phase. A failing sample whose parser is `capital_one_card` is reported on its own line as a Phase 4 finding and does not change this phase's verdict.
- Do not open a PDF, do not print extracted text, do not run a parser on a sample yourself, and do not include a file name from `data/samples/` in your report.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then four lines:

`Total passed: <the count from section 1>`

`Real statements: <no samples on this machine, or the counts from section 9>`

`Parts that needed a repair: <none, or Part 1 to Part 4 / tests>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code. For a failing real sample, pass on its summary line and nothing else; if the cause is not visible from the synthetic layouts, say so in your report so that the architect can add a synthetic example.
