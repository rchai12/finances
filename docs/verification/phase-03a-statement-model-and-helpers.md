# Verify Phase 3a: the statement model and parsing helpers

Spec: `docs/phases/phase-03a-statement-model-and-helpers.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote the members of `Section`, the fields of `StatementLine` and `ParsedStatement`, and the bodies of `parse_amount`, `infer_year`, and `parse_month_day`, and possibly private helpers (names starting with `_`). Everything else was given: `StatementError`, the class shells, the constants, `collapse_ws`, the `def` lines, and both test files. Judge the code by behavior and by the rules.

`parsers/helpers.py` is a critical module (`docs/testing.md`): a wrong year or a wrong sign here corrupts every transaction a parser produces. 100% coverage and a clean probe run are both required.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `41 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `450 passed`, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| the coverage command below this table | `Required test coverage of 100% reached` |

`.venv/bin/python -m pytest tests/unit/test_statement.py tests/unit/test_parser_helpers.py -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, `?? src/finances/ingest/`, `?? tests/unit/test_parser_helpers.py`, `?? tests/unit/test_statement.py`. Report every other path.
- `src/finances/ingest/` holds exactly `__init__.py` (empty), `statement.py`, and `parsers/` with `__init__.py` (empty) and `helpers.py` (ignore `__pycache__`).
- `git diff HEAD -- src tests/integration tests/e2e tests/conftest.py pyproject.toml` is empty.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test files untouched | compare the two test files with the blocks in steps 5 and 6 of the spec | identical apart from trailing whitespace; each file ends with a newline |
| given | given parts kept | compare `statement.py` and `helpers.py` with the blocks in steps 3 and 4 | docstrings, `StatementError`, class lines, decorators, `EARLY_DAYS`, `LATE_DAYS`, `MONTHS`, `collapse_ws`, and the three `def` lines are unchanged. Import lines may differ |
| R1 to R3 | the classes | probe script | every line starting `line:`, `section:`, or `statement:` ends in `ok` |
| R4 to R7 | amounts | probe script | every line starting `amount` ends in `ok` |
| R8 to R11 | years | probe script | every line starting `year` ends in `ok` |
| R8 | the window uses the constants | read `infer_year` | it uses `EARLY_DAYS` and `LATE_DAYS`, not the numbers 60 and 7 written again |
| R12, R13 | month and day | probe script | every line starting `date` ends in `ok` |
| rules | constant messages | read every `raise` in both files | each message is a constant string: no f-string, `%`, or `.format`, and nothing built from the input |
| rules | forbidden names | run the search below this table | no output |
| scope | nothing extra | probe script | the two `nothing extra is public` lines end in `ok` |

`git grep -n --untracked -F -e "\d" -e "strptime" -e "float" -e "print(" -e "logging" -- src/finances/ingest`

## 4. Independent probes

None of these values are in the given tests. The script uses different statement periods (a spring month, one that crosses a year end, two Februaries, and one thirteen months long) and checks both edges of the date window on each. For amounts it uses signs in combinations the tests do not list, three values that lose a cent in `float`, and a Unicode minus sign. For dates it uses mixed case, tabs, and digits from other alphabets.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import dataclasses
import typing
from datetime import date

from finances.domain.models import AccountType
from finances.ingest import statement as statement_module
from finances.ingest.parsers import helpers
from finances.ingest.parsers.helpers import infer_year, parse_amount, parse_month_day
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


BAD_MONEY = ("ValueError", "invalid money text")
OUTSIDE = ("StatementError", "date is outside the statement period")
AMBIGUOUS = ("StatementError", "date matches more than one year")
UNRECOGNIZED = ("StatementError", "unrecognized date text")

line = StatementLine(date(2026, 3, 12), None, "FOOBAR GROCERY", -2599, Section.PURCHASES, external_ref="A1")
credit = dataclasses.replace(line, amount_cents=1500, section=Section("payments_credits"), cardholder="JOHN DOE")
check("line: positional construction and defaults", (line.card_last4, line.cardholder, line.external_ref) == (None, None, "A1"))
check("line: replace makes a new line", credit.section is Section.PAYMENTS_CREDITS and line.amount_cents == -2599)
check("line: usable in a set", len({line, dataclasses.replace(line)}) == 1)
check("section: formats as its value", f"{Section.WITHDRAWALS}" == "withdrawals" and Section.FEES == "fees")
check("section: unknown value", outcome(Section, "refunds")[0] == "ValueError")
stmt = ParsedStatement("probe", "Probe Bank", AccountType.CHECKING, "0042", date(2026, 3, 10), date(2026, 4, 9), 100000, 98901, [line, credit])
check("statement: totals default to empty", stmt.declared_section_totals == {})
hints = typing.get_type_hints(ParsedStatement) | typing.get_type_hints(StatementLine)
check("statement: declared types", (hints["lines"], hints["section"], hints["declared_section_totals"]) == (list[StatementLine], Section, dict[Section, int]))
defaults = [f.name for cls in (StatementLine, ParsedStatement) for f in dataclasses.fields(cls) if f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING]
check("statement: only the optional fields have defaults", defaults == ["card_last4", "cardholder", "external_ref", "declared_section_totals"])
check("section: seven values in order", [member.value for member in Section] == ["payments_credits", "purchases", "fees", "interest", "deposits", "withdrawals", "checks"])
stmt.declared_section_totals[Section.PURCHASES] = -2599
other = dataclasses.replace(stmt, lines=[], declared_section_totals={})
check("statement: each statement has its own totals", other.declared_section_totals == {} and len(stmt.lines) == 2)
check("statement: sum of lines", stmt.opening_balance_cents + sum(item.amount_cents for item in stmt.lines) == stmt.closing_balance_cents)

AMOUNTS = {
    "+ $0.07": 7,
    "= -43.19": -4319,
    "-  12.3": -1230,
    "=+$1": 100,
    "+12.34 ": 1234,
    " =  $1,000,000.00": 100000000,
    "- .05": -5,
    "+ 0.29": 29,
    "= 4.35": 435,
    "(1,000)": -100000,
    "+ (1.00)": BAD_MONEY,
    "+1-": BAD_MONEY,
    "=-=5": BAD_MONEY,
    "- - 5": BAD_MONEY,
    "+$-5": BAD_MONEY,
    "1 +": BAD_MONEY,
    " = ": BAD_MONEY,
    "−5.00": BAD_MONEY,
    "= $1 = ": BAD_MONEY,
    "== 5": BAD_MONEY,
    "=  = $5": BAD_MONEY,
    "+ 1 000": BAD_MONEY,
}
for text, want in AMOUNTS.items():
    got = outcome(parse_amount, text)
    check(f"amount {text!r} -> {want!r} (got {got!r})", got == want and (type(got) is int or got == BAD_MONEY))

SPRING = (date(2026, 3, 10), date(2026, 4, 9))
YEAR_END = (date(2026, 12, 5), date(2027, 1, 4))
LATE_DECEMBER = (date(2026, 11, 28), date(2026, 12, 27))
LEAP = (date(2028, 2, 10), date(2028, 3, 9))
NOT_LEAP = (date(2027, 2, 10), date(2027, 3, 9))
THIRTEEN_MONTHS = (date(2025, 3, 1), date(2026, 3, 31))
YEARS = [
    (SPRING, 3, 9, date(2026, 3, 9)),
    (SPRING, 1, 9, date(2026, 1, 9)),
    (SPRING, 1, 8, OUTSIDE),
    (SPRING, 4, 16, date(2026, 4, 16)),
    (SPRING, 4, 17, OUTSIDE),
    (YEAR_END, 12, 31, date(2026, 12, 31)),
    (YEAR_END, 1, 11, date(2027, 1, 11)),
    (YEAR_END, 1, 12, OUTSIDE),
    (YEAR_END, 11, 1, date(2026, 11, 1)),
    (YEAR_END, 10, 6, date(2026, 10, 6)),
    (YEAR_END, 10, 5, OUTSIDE),
    (LATE_DECEMBER, 1, 3, date(2027, 1, 3)),
    (LATE_DECEMBER, 1, 4, OUTSIDE),
    (LATE_DECEMBER, 9, 29, date(2026, 9, 29)),
    (LEAP, 2, 29, date(2028, 2, 29)),
    (NOT_LEAP, 2, 29, OUTSIDE),
    (SPRING, 6, 31, OUTSIDE),
    (SPRING, -1, 5, OUTSIDE),
    (THIRTEEN_MONTHS, 3, 10, AMBIGUOUS),
    (THIRTEEN_MONTHS, 6, 10, date(2025, 6, 10)),
]
for period, month, day, want in YEARS:
    got = outcome(infer_year, month, day, *period)
    check(f"year {period[0]}..{period[1]} {month}/{day} -> {want!r} (got {got!r})", got == want)

DATES = {
    "MAR 9": date(2026, 3, 9),
    "aPr 16": date(2026, 4, 16),
    "3/9": date(2026, 3, 9),
    "04-01": date(2026, 4, 1),
    " \tApr   01\n": date(2026, 4, 1),
    "Sept 30": UNRECOGNIZED,
    "Apr 1 2026": UNRECOGNIZED,
    "1 Apr": UNRECOGNIZED,
    "Apr. 1": UNRECOGNIZED,
    "4/1/": UNRECOGNIZED,
    "4//1": UNRECOGNIZED,
    "4/-1": UNRECOGNIZED,
    "４/１": UNRECOGNIZED,
    "Apr ١": UNRECOGNIZED,
    "Abc 1": UNRECOGNIZED,
    "Aug 15": OUTSIDE,
    "8/15": OUTSIDE,
    "Apr 31": OUTSIDE,
    "99/99": OUTSIDE,
}
for text, want in DATES.items():
    got = outcome(parse_month_day, text, *SPRING)
    check(f"date {text!r} -> {want!r} (got {got!r})", got == want)

for module, expected in [
    (statement_module, ["ParsedStatement", "Section", "StatementError", "StatementLine"]),
    (helpers, ["collapse_ws", "infer_year", "parse_amount", "parse_month_day"]),
]:
    public = sorted(
        name
        for name, value in vars(module).items()
        if getattr(value, "__module__", "") == module.__name__ and not name.startswith("_")
    )
    check(f"{module.__name__}: nothing extra is public {public}", public == expected)
check("StatementError is not a ValueError", not issubclass(StatementError, ValueError))
print("FAILURES", failures)
```

## 5. Progress log

`docs/progress.md` ends with the entry given in step 23 of the spec, with a real date in place of `YYYY-MM-DD`. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then two lines:

`Steps skipped or out of order: <none, or the step numbers>`

`Parts that needed a repair: <none, or Part 1 / Part 2 / Part 3 / Part 4>`

## If the verdict is FAIL

Send each repair in one of these forms, and no other:

- "Run step N of the spec again."
- "Replace the whole content of `<test file>` with the block in step N."
- For a class: "R<n> is not met: `<field or member>` must be `<what the table says>`; it is `<what was found>`. Change only that class, then run steps 19 to 30 again."
- For a function: "R<n> is not met: `<call>` gave `<got>`; it must give `<want>`. Change only the body of `<function>`, then run steps 19 to 30 again." At most three.
- For code no test reaches: "Delete lines N to M of `<file>`: no requirement asks for them. Then run steps 19 to 30 again."
- For a rule: "Line N of `<file>` has `<thing>`, which the Rules section forbids. Rewrite that line, then run steps 19 to 30 again."
