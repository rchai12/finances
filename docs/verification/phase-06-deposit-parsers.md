# Verify Phase 6: the Truist and Marcus deposit account parsers

Spec: `docs/phases/phase-06-deposit-parsers.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote two modules, `src/finances/ingest/parsers/truist.py` and `src/finances/ingest/parsers/marcus.py`, added five given lines to `parsers/__init__.py`, and wrote two test files. Three test files were given, and the fixtures and the real-sample check were already in the repository.

Judge the parsers by what they return and by the rules, never by how they are written. These are all correct and must not be reported:

- any division into private helpers, and any regular expressions that give the specified results;
- two parsers that share no code;
- reading a statement line by line or as one text, in one pass or several;
- finding the Truist balances with one pattern or with `find_labeled_amount`, as long as the results are those of R4.

**Privacy.** You must not open, print, or quote anything under `data/samples/`. Section 9 says exactly what you may run and what you may report.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment, and do not change the environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it; it is `882` when Phases 3e and 5 were the last phases built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 94 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_truist_parser.py tests/unit/test_marcus_parser.py tests/integration/test_truist_marcus_import.py --no-cov` | exactly `94 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with `truist.py` and `marcus.py` each at 100% |
| `.venv/bin/python -c "from finances.ingest.parsers import registered_parsers; print([p.name for p in registered_parsers()])"` | `['capital_one_card', 'boa_card', 'citi_card', 'truist_deposit', 'marcus_savings']` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/ingest/parsers/__init__.py
?? src/finances/ingest/parsers/marcus.py
?? src/finances/ingest/parsers/truist.py
?? tests/integration/test_truist_marcus_import.py
?? tests/unit/test_marcus_parser.py
?? tests/unit/test_marcus_parser_more.py
?? tests/unit/test_truist_parser.py
?? tests/unit/test_truist_parser_more.py
```

- `git diff HEAD -- src/finances/ingest/parsers/__init__.py` adds exactly the five lines under "Design" in the spec (a blank line, two imports with `# noqa: E402`, a blank line, two `register` calls) at the end of the file, and changes nothing else.
- The three given test files are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- src/finances/ingest/parsers/helpers.py src/finances/ingest/parsers/capital_one.py src/finances/ingest/parsers/boa.py src/finances/ingest/parsers/citi.py tests/fixtures tests/real_samples tests/conftest.py src/finances/ingest/service.py src/finances/ingest/reconcile.py src/finances/ingest/dedup.py src/finances/ingest/pdf_text.py src/finances/ingest/statement.py src/finances/db src/finances/domain src/finances/cli pyproject.toml` is empty, and no existing test file is changed.
- `git status --short --ignored` shows no new `.pdf` file and no new file under `data/`.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | Truist detection | probe script | every line starting `truist detect:` |
| R2, R3 | account line and names | probe script | every line starting `truist header:`, `truist year end: savings`, and `truist an account line with text after the number` |
| R4, R5 | balances and period | probe script | `truist balances:`, `truist header: the period starts`, `truist no activity: quarterly period`, and the two lines starting `truist impossible` |
| R6 | declared totals | probe script | `truist totals` and `truist year end: only the printed total is declared` |
| R7, R8, R11 | sections and rows | probe script | every line starting `truist lines:` |
| R9 | debit card details | probe script | the `truist lines:` lines that mention a card, a purchase date, or a month-day token |
| R10 | checks | probe script | `truist lines: five checks from two printed lines, with their numbers` and `pdf truist: five lines across the page break` |
| R12 | Truist missing pieces | probe script | the three lines starting `truist missing` |
| R13 | Marcus detection | probe script | every line starting `marcus detect:` |
| R14 to R16 | Marcus header | probe script | every line starting `marcus header:` and `marcus year end: four-digit account` |
| R17 | balance lines | probe script | `marcus balances` and `marcus lines: balance labels without spaces` |
| R18 to R21 | rows, signs, sections | probe script | every line starting `marcus lines:`, plus `marcus totals: none declared` and `marcus year end: lines` |
| R19 | the balance check | probe script | `marcus a printed amount that disagrees with the balance` |
| R22 | Marcus missing pieces | probe script | the four lines starting `marcus missing`, plus `marcus impossible period date` and `marcus an impossible row date` |
| R23 | order | probe script | the numbered `line N` checks of both banks |
| R24 | undatable row | probe script | `truist row outside the period` |
| R25 | only `StatementError` | probe script | `truist no pages` and `marcus no pages` |
| R26 | registration | probe script; gate 6 | the lines starting `registry:`, `truist registry:`, `marcus registry:` |
| page breaks | sections carry over | probe script | the lines starting `truist pages:`, `marcus pages:`, and the two `lines across the page break` lines |
| end to end | through PDF and registry | probe script | every line starting `pdf truist:` and `pdf marcus:` |
| arithmetic | reconciliation | probe script | `truist reconcile`, `truist no activity: reconciles`, and `marcus reconcile` |
| messages | constant text | read every `raise` in `truist.py` and `marcus.py` | only the nine messages in R12, R19, and R22; the only varying part is the row number |
| scope | nothing extra | probe script | the two lines containing `nothing extra is public` |

`git grep -n --untracked -F -e "strptime" -e "float" -e "print(" -e "logging" -e "\d" -- src/finances/ingest/parsers/truist.py src/finances/ingest/parsers/marcus.py`

## 4. Independent probes

The given tests compare the parsers with six fixed fixtures. This script contains generators that print a synthetic statement from structured data, so it can check statements the fixtures do not contain and know every expected line by construction: a Truist checking statement with checks three to a line, debit card rows with and without a card and a purchase date, zero rows, and a page break; a savings statement over a year end; a statement with no activity; and Marcus statements with repeated rows, a page break, a zero row, and a year end. It then edits statements to test the rules one at a time, and finally sends one statement of each bank through a real PDF and the registry. None of its names, digits, or amounts are in the fixtures or the spec.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It writes no file and reads nothing under `data/`. Every line must end in `ok`; the last line must be `FAILURES 0`. A line that says a section `ran to the end (stopped by ...)` and ends in `FAIL` means the code raised where it should not have; report it with the exception named on that line.

```python
from datetime import date

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser, marcus, registered_parsers, truist
from finances.ingest.parsers.marcus import MarcusSavingsParser
from finances.ingest.parsers.truist import TruistDepositParser
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
    return f"{abs(cents) // 100:,}.{abs(cents) % 100:02d}"


def render_truist(spec):
    """spec: product, number, previous_date, new_date (MM/DD/YYYY), previous (cents), checks
    [(MM/DD, number, cents, starred)], withdrawals and deposits [(MM/DD, text, cents)],
    per_line (checks per printed line), break_after (withdrawal rows on page 1), spaced (bool)."""
    checks, out, into = spec.get("checks", []), spec.get("withdrawals", []), spec.get("deposits", [])
    t_checks, t_out, t_in = sum(r[2] for r in checks), sum(r[2] for r in out), sum(r[2] for r in into)
    new = spec["previous"] - t_checks - t_out + t_in
    head = []
    if spec.get("spaced"):
        head.append("T r u   i s   t .c   o   m")
    head += [
        "Truist Bank, Member FDIC" + " " * 30 + "Your account statement",
        f"For {spec['new_date']}",
        f"{spec['product']} {spec['number']}",
    ]
    page = [
        *head,
        "",
        "Account summary",
        f"Your previous balance as of {spec['previous_date']}" + " " * 20 + ("-" if spec["previous"] < 0 else "") + money(spec["previous"]),
        "Checks" + " " * 50 + "- " + plain(t_checks),
        "Other withdrawals, debits and service charges" + " " * 11 + "- " + plain(t_out),
        "Deposits, credits and interest" + " " * 26 + "+ " + plain(t_in),
        f"Your new balance as of {spec['new_date']}" + " " * 25 + "= " + ("-" if new < 0 else "") + money(new),
        "",
    ]
    pages = []

    def row(r):
        day, text, cents = r
        return f"{day}   {text}" + " " * max(2, 70 - len(text)) + plain(cents)

    if checks:
        per_line = spec.get("per_line", 1)
        page += ["Checks", "   ".join(["DATE     CHECK #     AMOUNT($)"] * per_line)]
        for index in range(0, len(checks), per_line):
            cells = [f"{day}    {'*' if starred else ' '}{number}     {plain(cents)}" for day, number, cents, starred in checks[index:index + per_line]]
            page.append("      ".join(cells))
        page += ["* indicates a skip in sequential check numbers above this item", "Total checks" + " " * 44 + "= " + money(t_checks), ""]
    if out:
        page += ["Other withdrawals, debits and service charges", "DATE    DESCRIPTION" + " " * 56 + "AMOUNT($)"]
        for position, r in enumerate(out):
            if position == spec.get("break_after", -1):
                page += ["continued", "PAGE 1 OF 2"]
                pages.append(page)
                page = [*head, "", "Other withdrawals, debits and service charges (continued)", "DATE    DESCRIPTION" + " " * 56 + "AMOUNT($)"]
            page.append(row(r))
        page += ["Total other withdrawals, debits and service charges" + " " * 5 + "= " + money(t_out), ""]
    if into:
        page += ["Deposits, credits and interest", "DATE    DESCRIPTION" + " " * 56 + "AMOUNT($)"]
        page += [row(r) for r in into]
        page += ["Total deposits, credits and interest" + " " * 20 + "= " + money(t_in), ""]
    page += ["Important: questions about your statement", "10/01   Call the number on your card by this date" + " " * 10 + "1.00"]
    pages.append(page)
    return pages, new


def render_marcus(spec):
    """spec: number, start, end (MM/DD/YYYY), opening (cents), rows [(MM/DD/YYYY, text, signed cents,
    continuation or None)], break_after (rows on page 1), spaced_labels (bool), wrong (row index whose
    printed amount is one cent off)."""
    head = [
        "Marcus by Goldman Sachs" + " " * 20 + "ONLINE SAVINGS ACCOUNT STATEMENT",
        "Goldman Sachs Bank USA, Member FDIC",
        f"Statement Period      {spec['start']} to {spec['end']}",
        f"Account Number      {spec['number']}",
    ]
    columns = "Date          Description" + " " * 40 + "Credits      Debits      Balance"
    first, last = ("Beginning Balance", "Ending Balance") if spec.get("spaced_labels") else ("Beginning Balance", "EndingBalance")
    page = [*head, "", "ACCOUNT ACTIVITY", columns, f"{spec['start']}   {first}" + " " * 50 + money(spec["opening"])]
    pages = []
    balance = spec["opening"]
    for index, (day, text, cents, more) in enumerate(spec["rows"]):
        if index == spec.get("break_after", -1):
            page += ["Page 1 of 2"]
            pages.append(page)
            page = [*head, "", "ACCOUNT ACTIVITY (continued)", columns]
        balance += cents
        printed = abs(cents) + (1 if index == spec.get("wrong", -1) else 0)
        gap = " " * (max(2, 56 - len(text)) + (0 if cents > 0 else 12))
        page.append(f"{day}   {text}{gap}{money(printed)}" + " " * (14 if cents > 0 else 2) + ("-" if balance < 0 else "") + money(balance))
        if more:
            page.append(" " * 16 + more)
    page += [f"{spec['end']}   {last}" + " " * 53 + ("-" if balance < 0 else "") + money(balance), "", "INTEREST SUMMARY", "Annual Percentage Yield Earned      4.25%", "Interest Paid Year to Date      $123.45      $1,000.00"]
    pages.append(page)
    return pages, balance


def md(text, years, sep="/"):
    month, day = (int(part) for part in text.split(sep))
    return date(years[month], month, day)


def truist_expected(spec, years):
    lines = []
    for day, number, cents, _ in spec.get("checks", []):
        lines.append(StatementLine(md(day, years), None, f"CHECK {number}", -cents, Section.CHECKS, external_ref=number))
    for sign, kind, rows in ((-1, Section.WITHDRAWALS, spec.get("withdrawals", [])), (1, Section.DEPOSITS, spec.get("deposits", []))):
        for day, text, cents in rows:
            words = text.split()
            card = bought = None
            if text.startswith("DEBIT CARD "):
                card = words[-1] if len(words[-1]) == 4 and words[-1].isdigit() else None
                days = [w for w in words if len(w) == 5 and w[2] == "-" and (w[:2] + w[3:]).isdigit()]
                bought = md(days[-1], years, "-") if days else None
            lines.append(StatementLine(md(day, years), bought, text, sign * cents, kind, card_last4=card))
    return lines


def marcus_expected(spec):
    lines = []
    for day, text, cents, _ in spec["rows"]:
        month, dom, year = (int(part) for part in day.split("/"))
        if "".join(text.split()) == "InterestPaid":
            kind = Section.INTEREST
        else:
            kind = Section.DEPOSITS if cents > 0 else Section.WITHDRAWALS
        lines.append(StatementLine(date(year, month, dom), None, text, cents, kind))
    return lines


T_WINTER = dict(
    product="TRUIST DIMENSION CHECKING", number="1000000008080", spaced=True,
    previous_date="11/27/2026", new_date="12/28/2026", previous=91000,
    checks=[("11/30", "3301", 5000, False), ("12/04", "3302", 1234, False), ("12/09", "3310", 60000, True),
            ("12/15", "3311", 99, False), ("12/16", "3313", 0, False), ("12/27", "3312", 100000, False)],
    per_line=3,
    withdrawals=[("11/30", "DEBIT CARD PURCHASE PROBE BAKERY 11-26 TULSA OK 6006", 1875),
                 ("12/02", "DEBIT CARD PURCHASE PROBE FUEL 0042 TULSA OK", 5230),
                 ("12/11", "ONLINE TRANSFER TO PROBE SAVINGS 4110000009191", 250000),
                 ("12/18", "DEBIT CARD RECURRING PYMT PROBEFLIX 12-17 800-555-0199 CA 7007", 1599),
                 ("12/20", "PAPER STATEMENT FEE WAIVED", 0),
                 ("12/21", "PROBE AUTOPAY 12-12 REF 4455", 356),
                 ("12/26", "DEBIT CARD PURCHASE PROBE 10-10 CAFE 12-24 TULSA OK 6006", 940)],
    deposits=[("11/28", "ACH CORP CREDIT PAYROLL PROBE WORKS LLC", 410000),
              ("12/22", "DEBIT CARD PURCHASE RETURN PROBE OUTLET 12-20 TULSA OK 6006", 4575)],
    break_after=2,
)
T_NEW_YEAR = dict(
    product="TRUIST ONE SAVINGS", number="41100000000007",
    previous_date="12/31/2027", new_date="01/31/2028", previous=700,
    deposits=[("01/31", "INTEREST PAYMENT", 3)],
)
T_QUIET = dict(product="TRUIST ONE SAVINGS", number="4110000005005", previous_date="02/28/2027", new_date="05/31/2027", previous=31415)
M_WINTER = dict(
    number="300100008080", start="11/28/2026", end="12/27/2026", opening=120050,
    rows=[("11/28/2026", "ACHDepositInternettransferfromPROBE BANK", 100000, "************8080"),
          ("12/05/2026", "ACHWithdrawalInternettransfertoPROBE BANK", -4575, None),
          ("12/05/2026", "ACHWithdrawalInternettransfertoPROBE BANK", -4575, "************8080"),
          ("12/20/2026", "WireDepositPROBE WORKS", 1234567, None),
          ("12/27/2026", "Interest Paid", 1841, None)],
    break_after=3, spaced_labels=True,
)
M_YEAR_END = dict(
    number="9007", start="12/15/2027", end="01/14/2028", opening=5,
    rows=[("12/31/2027", "InterestPaid", 1, None), ("01/01/2028", "FeeWaived", 0, None), ("01/02/2028", "ACHWithdrawalClosing", -6, None)],
)


def text_pages(pages):
    return ["\n".join(page) for page in pages]


def edited(pages, old, new):
    assert any(old in page for page in pages), old
    return [page.replace(old, new) for page in pages]


def truist_checks():
    parser = TruistDepositParser()
    rendered, new = render_truist(T_WINTER)
    pages = text_pages(rendered)
    check("truist detect: generated first page", parser.detect(pages[0]) is True)
    statement = parser.parse(pages)
    check("truist header: names", (statement.parser_name, statement.institution) == ("truist_deposit", "Truist"))
    check("truist header: checking, last four digits", (statement.account_type, statement.account_last4) == (AccountType.CHECKING, "8080"))
    check("truist header: the period starts the day after the previous balance", (statement.period_start, statement.period_end) == (date(2026, 11, 28), date(2026, 12, 28)))
    check("truist balances: as printed, positive", (statement.opening_balance_cents, statement.closing_balance_cents) == (91000, new))
    want = truist_expected({**T_WINTER, "checks": [r for r in T_WINTER["checks"] if r[2]], "withdrawals": [r for r in T_WINTER["withdrawals"] if r[2]]}, {11: 2026, 12: 2026})
    check(f"truist lines: count {len(statement.lines)} of {len(want)}", len(statement.lines) == len(want))
    for index, (got, expected) in enumerate(zip(statement.lines, want, strict=False)):
        check(f"truist lines: line {index} ({expected.section.value})", got == expected)
    by_text = {item.description: item for item in statement.lines}
    check("truist lines: five checks from two printed lines, with their numbers", [item.external_ref for item in statement.lines[:5]] == ["3301", "3302", "3310", "3311", "3312"])
    check("truist lines: checks and withdrawals negative, deposits positive", all((item.amount_cents > 0) == (item.section is Section.DEPOSITS) for item in statement.lines))
    check("truist lines: a debit card row without a card or date has neither", (by_text["DEBIT CARD PURCHASE PROBE FUEL 0042 TULSA OK"].card_last4, by_text["DEBIT CARD PURCHASE PROBE FUEL 0042 TULSA OK"].transaction_date) == (None, None))
    check("truist lines: the last month-day token is the purchase date", by_text["DEBIT CARD PURCHASE PROBE 10-10 CAFE 12-24 TULSA OK 6006"].transaction_date == date(2026, 12, 24))
    check("truist lines: a purchase before the period keeps its date", by_text["DEBIT CARD PURCHASE PROBE BAKERY 11-26 TULSA OK 6006"].transaction_date == date(2026, 11, 26))
    check("truist lines: a transfer row has no card", by_text["ONLINE TRANSFER TO PROBE SAVINGS 4110000009191"].card_last4 is None)
    check("truist lines: only debit card rows get a card or a purchase date", (by_text["PROBE AUTOPAY 12-12 REF 4455"].card_last4, by_text["PROBE AUTOPAY 12-12 REF 4455"].transaction_date) == (None, None))
    check("truist lines: zero rows are left out", not any(item.amount_cents == 0 for item in statement.lines))
    check("truist lines: the row after the last total is not read", not any("Call the number" in item.description for item in statement.lines))
    check("truist totals", statement.declared_section_totals == {Section.CHECKS: -166333, Section.WITHDRAWALS: -260000, Section.DEPOSITS: 414575})
    check("truist reconcile", reconcile(statement).ok)
    check("truist pages: one page or two gives the same statement", parser.parse(["\n".join(pages)]) == statement)
    check("truist registry: detect_parser picks it", getattr(outcome(detect_parser, pages), "name", None) == "truist_deposit")
    spaced = parser.parse(edited(pages, "PROBE FUEL 0042 TULSA OK", "PROBE   FUEL  0042   TULSA OK"))
    check("truist lines: inner spaces of a description are collapsed", spaced == statement)
    stray = ["\n".join(["12/01   PROBE STRAY ROW      9.99", *pages[0].split("\n")]), *pages[1:]]
    check("truist lines: rows before any section are ignored", outcome(parser.parse, stray) == statement)
    late = outcome(parser.parse, edited(pages, "12/26   DEBIT CARD PURCHASE PROBE 10-10", "07/04   DEBIT CARD PURCHASE PROBE 10-10"))
    check("truist row outside the period", late == ("StatementError", "date is outside the statement period"))
    odd = outcome(parser.parse, edited(pages, "PROBEFLIX 12-17", "PROBEFLIX 13-45"))
    check("truist lines: an impossible purchase date is left empty", getattr(odd, "lines", None) is not None and [item.transaction_date for item in odd.lines if "PROBEFLIX" in item.description] == [None])

    rendered, new = render_truist(T_NEW_YEAR)
    pages = text_pages(rendered)
    statement = parser.parse(pages)
    check("truist year end: savings, period, last four of a long number", (statement.account_type, statement.account_last4, statement.period_start, statement.period_end) == (AccountType.SAVINGS, "0007", date(2028, 1, 1), date(2028, 1, 31)))
    check("truist year end: the one line", statement.lines == [StatementLine(date(2028, 1, 31), None, "INTEREST PAYMENT", 3, Section.DEPOSITS)])
    check("truist year end: only the printed total is declared", statement.declared_section_totals == {Section.DEPOSITS: 3})
    for label, old, message in [
        ("account line", "TRUIST ONE SAVINGS 41100000000007", "truist: account line not found"),
        ("previous balance", "Your previous balance as of", "truist: previous balance not found"),
        ("new balance", "Your new balance as of", "truist: new balance not found"),
    ]:
        check(f"truist missing {label}", outcome(parser.parse, edited(pages, old, "XXXX")) == ("StatementError", message))
    check("truist an account line with text after the number", outcome(parser.parse, edited(pages, "TRUIST ONE SAVINGS 41100000000007", "TRUIST ONE SAVINGS 41100000000007 PAGE 1")) == ("StatementError", "truist: account line not found"))
    check("truist impossible previous date", outcome(parser.parse, edited(pages, "as of 12/31/2027", "as of 12/32/2027")) == ("StatementError", "truist: previous balance not found"))
    check("truist impossible new date", outcome(parser.parse, edited(pages, "as of 01/31/2028", "as of 02/31/2028")) == ("StatementError", "truist: new balance not found"))
    check("truist no pages", outcome(parser.parse, []) == ("StatementError", "truist: account line not found"))

    rendered, new = render_truist(T_QUIET)
    statement = parser.parse(text_pages(rendered))
    check("truist no activity: no lines, no totals, equal balances", (statement.lines, statement.declared_section_totals, statement.opening_balance_cents, statement.closing_balance_cents) == ([], {}, 31415, 31415))
    check("truist no activity: quarterly period", (statement.period_start, statement.period_end) == (date(2027, 3, 1), date(2027, 5, 31)))
    check("truist no activity: reconciles", reconcile(statement).ok)
    for label, page, want in [("name only", "Truist", False), ("title only", "Your account statement", False), ("both", "Your account statement Truist", True), ("marcus page", "Goldman Sachs Bank USA\nONLINE SAVINGS ACCOUNT STATEMENT", False)]:
        check(f"truist detect: {label}", parser.detect(page) is want)


def marcus_checks():
    parser = MarcusSavingsParser()
    rendered, new = render_marcus(M_WINTER)
    pages = text_pages(rendered)
    check("marcus detect: generated first page", parser.detect(pages[0]) is True)
    statement = parser.parse(pages)
    check("marcus header: names and type", (statement.parser_name, statement.institution, statement.account_type) == ("marcus_savings", "Marcus by Goldman Sachs", AccountType.SAVINGS))
    check("marcus header: account digits and period", (statement.account_last4, statement.period_start, statement.period_end) == ("8080", date(2026, 11, 28), date(2026, 12, 27)))
    check("marcus balances", (statement.opening_balance_cents, statement.closing_balance_cents) == (120050, new))
    want = marcus_expected(M_WINTER)
    check(f"marcus lines: count {len(statement.lines)} of {len(want)}", len(statement.lines) == len(want))
    for index, (got, expected) in enumerate(zip(statement.lines, want, strict=False)):
        check(f"marcus lines: line {index} ({expected.section.value})", got == expected)
    check("marcus lines: two equal rows on one day are both kept", [item.amount_cents for item in statement.lines[1:3]] == [-4575, -4575])
    check("marcus lines: continuation lines are not read", not any("*" in item.description for item in statement.lines))
    check("marcus lines: interest has its own section", statement.lines[-1].section is Section.INTEREST and statement.lines[-1].amount_cents == 1841)
    check("marcus lines: no purchase date, card, or reference", all((item.transaction_date, item.card_last4, item.cardholder, item.external_ref) == (None, None, None, None) for item in statement.lines))
    check("marcus totals: none declared", statement.declared_section_totals == {})
    check("marcus reconcile", reconcile(statement).ok)
    check("marcus pages: one page or two gives the same statement", parser.parse(["\n".join(pages)]) == statement)
    check("marcus registry: detect_parser picks it", getattr(outcome(detect_parser, pages), "name", None) == "marcus_savings")
    check("marcus lines: inner spaces of a description are collapsed", outcome(parser.parse, edited(pages, "WireDepositPROBE WORKS", "WireDepositPROBE    WORKS")) == statement)
    check("marcus lines: balance labels without spaces", outcome(parser.parse, edited(edited(pages, "Beginning Balance", "BeginningBalance"), "Ending Balance", "EndingBalance")) == statement)
    wrong = outcome(parser.parse, edited(pages, "$12,345.67", "$12,345.76"))
    check("marcus a printed amount that disagrees with the balance", wrong == ("StatementError", "marcus: row 4 does not match its balance"))
    check("marcus an impossible row date", outcome(parser.parse, edited(pages, "12/20/2026", "12/40/2026")) == ("StatementError", "marcus: row 4 has an impossible date"))
    for label, old, message in [
        ("account number", "Account Number", "marcus: account number not found"),
        ("period", "Statement Period", "marcus: statement period not found"),
        ("beginning balance", "Beginning Balance", "marcus: beginning balance not found"),
        ("ending balance", "Ending Balance", "marcus: ending balance not found"),
    ]:
        check(f"marcus missing {label}", outcome(parser.parse, edited(pages, old, "XXXX")) == ("StatementError", message))
    check("marcus impossible period date", outcome(parser.parse, edited(pages, "11/28/2026 to", "11/31/2026 to")) == ("StatementError", "marcus: statement period not found"))
    check("marcus no pages", outcome(parser.parse, []) == ("StatementError", "marcus: account number not found"))

    rendered, new = render_marcus(M_YEAR_END)
    statement = parser.parse(text_pages(rendered))
    check("marcus year end: four-digit account, period", (statement.account_last4, statement.period_start, statement.period_end) == ("9007", date(2027, 12, 15), date(2028, 1, 14)))
    check("marcus year end: lines and a zero closing balance", statement.lines == [item for item in marcus_expected(M_YEAR_END) if item.amount_cents] and len(statement.lines) == 2 and statement.closing_balance_cents == 0 and reconcile(statement).ok)
    for label, page, want in [("bank only", "Goldman Sachs Bank USA", False), ("title only", "ONLINE SAVINGS ACCOUNT STATEMENT", False), ("both", "ONLINE SAVINGS ACCOUNT STATEMENT Goldman Sachs Bank USA", True), ("truist page", "Truist\nYour account statement", False)]:
        check(f"marcus detect: {label}", parser.detect(page) is want)


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
    first = [
        "Truist Bank   Your account statement", "For 08/09/2026", "TRUIST ONE CHECKING 1000000006006",
        "Your previous balance as of 07/09/2026   $80.00", "Checks   - 20.00",
        "Other withdrawals, debits and service charges   - 100.00", "Deposits, credits and interest   + 141.25",
        "Your new balance as of 08/09/2026   = $101.25", "Checks", "07/15  5001  12.00\t07/20  *5005  8.00",
        "Total checks   = $20.00", "Other withdrawals, debits and service charges",
        "07/11\tDEBIT CARD PURCHASE PROBE GARDEN 07-09 6116   60.00",
    ]
    second = ["Other withdrawals, debits and service charges (continued)", "08/08\tPROBE CINEMA 12 AUTOPAY   40.00",
              "Total other withdrawals, debits and service charges   = $100.00", "Deposits, credits and interest",
              "08/01\tMOBILE DEPOSIT   141.25", "Total deposits, credits and interest   = $141.25"]
    pages = extract_pages(build_pdf([first, second]))
    statement = detect_parser(pages).parse(pages)
    check("pdf truist: through extract_pages and the registry", (statement.parser_name, statement.account_last4) == ("truist_deposit", "6006"))
    check("pdf truist: five lines across the page break", [(item.amount_cents, item.section) for item in statement.lines] == [(-1200, Section.CHECKS), (-800, Section.CHECKS), (-6000, Section.WITHDRAWALS), (-4000, Section.WITHDRAWALS), (14125, Section.DEPOSITS)])
    check("pdf truist: purchase date and card", (statement.lines[2].transaction_date, statement.lines[2].card_last4) == (date(2026, 7, 9), "6116"))
    check("pdf truist: reconciles", reconcile(statement).ok and statement.closing_balance_cents == 10125)
    lines = [
        "Marcus by Goldman Sachs   ONLINE SAVINGS ACCOUNT STATEMENT", "Goldman Sachs Bank USA", "Statement Period   07/10/2026 to 08/09/2026",
        "Account Number   300100005005", "07/10/2026\tBeginning Balance   $80.00", "07/30/2026\tACHDepositPROBE   $60.00   $140.00",
    ]
    more = ["08/02/2026\tACHWithdrawalPROBE   $40.00   $100.00", "08/09/2026\tInterestPaid   $1.25   $101.25", "08/09/2026\tEndingBalance   $101.25"]
    pages = extract_pages(build_pdf([lines, more]))
    statement = detect_parser(pages).parse(pages)
    check("pdf marcus: through extract_pages and the registry", (statement.parser_name, statement.account_last4) == ("marcus_savings", "5005"))
    check("pdf marcus: three lines across the page break", [(item.amount_cents, item.section) for item in statement.lines] == [(6000, Section.DEPOSITS), (-4000, Section.WITHDRAWALS), (125, Section.INTEREST)])
    check("pdf marcus: reconciles", reconcile(statement).ok and statement.closing_balance_cents == 10125)


section("truist", truist_checks)
section("marcus", marcus_checks)
section("pdf", pdf_checks)
names = [parser.name for parser in registered_parsers()]
check(f"registry: five parsers, each once {names}", sorted(names) == ["boa_card", "capital_one_card", "citi_card", "marcus_savings", "truist_deposit"])
for module, expected in ((truist, ["TruistDepositParser"]), (marcus, ["MarcusSavingsParser"])):
    public = sorted(name for name, value in vars(module).items() if getattr(value, "__module__", "") == module.__name__ and not name.startswith("_"))
    check(f"{module.__name__}: nothing extra is public {public}", public == expected)
print("FAILURES", failures)
```

## 5. The coder's tests

Read `tests/unit/test_truist_parser_more.py` and `tests/unit/test_marcus_parser_more.py`.

- **Coverage of requirements.** For each of R1 to R26, name a test, given or the coder's, that would fail if the requirement were broken. A requirement with no such test is a finding. The coder's final message lists its own mapping; check it, do not trust it.
- **Assertions are exact.** Messages are compared with `==` against the full text, and lines are compared as whole `StatementLine` values or field by field with literal expected values. No `assert True`, no `pytest.raises(Exception)`, no `skip` or `xfail`, and no expected value produced by calling a parser.
- **Synthetic data.** Every name, merchant, number, and amount is invented. No test reads `data/`, and none opens a PDF from disk.
- **Isolation.** No test registers or unregisters a parser without the `parser_registry` fixture.
- **Spot checks.** For each change below, say which test, given or the coder's, would fail, by reading the test. If none would, that is a finding.
  1. A Truist statement with no new balance line is reported as `truist: previous balance not found`.
  2. A Truist previous-balance date of `08/32/2026` raises `ValueError` instead of `StatementError`.
  3. A missing `Total checks` line gives a `CHECKS` declared total of `0` instead of no entry.
  4. A Truist check dated outside the period is skipped instead of raising.
  5. A Truist row printed before the first section heading is read.
  6. A Marcus row after a zero row is reported with a number one too low.
  7. A Marcus line with a date, some text, and one money is taken as the opening balance whatever its label.
  8. A Marcus balance of `-$5.00` is read as `500`.
  9. `parse([])` raises `IndexError` or `AttributeError` in either parser.

## 6. Project rules that apply to this phase

- **Money and signs.** Withdrawals and checks come out negative, deposits and interest positive, balances as printed. The probe script checks each.
- **Privacy.** Neither module logs or prints, and their messages carry no statement text.
- **Layering.** `git grep -n --untracked -E "finances\.(db|cli)" -- src/finances/ingest/parsers` prints nothing.
- **Test data.** The fixtures are unchanged (section 2), and the coder's tests add no file under `tests/fixtures/`.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- Any change to `helpers.py` or to the three card parsers.
- A base class for parsers or a shared "deposit parser" module.
- Any change to the import service, reconciliation, fingerprints, or PDF extraction made to accommodate a parser.
- Transfer matching, or any attempt to pair a withdrawal with a deposit.
- Merchant clean-up: removing the date or card digits from a Truist description, or adding spaces to a Marcus description.
- Any code that reads `data/` other than the given `check_real_samples.py`, and any `fin import` run on `data/`.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 6: the Truist and Marcus deposit account parsers (YYYY-MM-DD)` with a real date. "Built" gives N, the passed count, and the outcome of the real-statement check as counts only. "Follow-ups" says that the Truist checks, headings, and balance lines are unconfirmed until real statements pass. No part of the entry quotes a statement: no merchant, name, amount, balance, or file name from `data/samples/`. Earlier entries are unchanged.

## 9. Real statements

Run this once, from the repository root:

`.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`

- If it reports `no PDF files in data/samples`, write "no samples on this machine" in your report. Do not treat it as a failure.
- Otherwise report only the counts on its last line and, for each sample that fails or shows as `xfail`, the summary line it printed: the sample number, the parser name, the line count, the difference in cents, and the sections that differ.
- A failing sample whose parser is `truist_deposit` or `marcus_savings` is a finding against this phase. Say in your report whether the cause could be one of the three unconfirmed parts of the Truist layout the spec lists; you can only judge that from the counts.
- A failing sample whose parser is a card parser is reported on its own line as a finding for Phase 4 or 5 and does not change this phase's verdict. The same holds for a sample that shows as `xfail`.
- Do not open a PDF, do not print extracted text, do not run a parser on a sample yourself, and do not include a file name from `data/samples/` in your report.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then four lines:

`Total passed: <the count from section 1>`

`Real statements: <no samples on this machine, or the counts from section 9>`

`Parts that needed a repair: <none, or Part 1 to Part 3 / tests>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code. For a failing real sample, pass on its summary line and nothing else; if the cause is not visible from the synthetic layouts, say so in your report so that the architect can add a synthetic example.
