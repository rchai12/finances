# Phase 3b: statement checks and reading

## Goal

Build the four pieces that sit between a PDF file and a trusted set of transactions, each usable on its own:

1. **Reconciliation**: does a parsed statement add up to its own closing balance, to the cent?
2. **Fingerprints**: a stable key per transaction line, so importing the same statement twice adds nothing.
3. **PDF text**: the bytes of a PDF become one string per page, with the column layout kept.
4. **The parser registry**: given the first page of a statement, pick the one parser that recognizes it.

No bank parser is written here, and nothing touches the database. Phase 3c stores statements; Phase 3d joins everything into an import.

## Read first

- `AGENTS.md`: "Running commands", "Privacy rules", "Money and signs", "Architecture rules"
- `docs/testing.md`: the test layers and the list of critical modules
- `src/finances/ingest/statement.py` and `src/finances/ingest/parsers/helpers.py` (Phase 3a)
- `tests/conftest.py`

## Starting state

- Phase 3a is committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `450 passed`.
- `src/finances/ingest/statement.py` defines `StatementError`, `Section`, `StatementLine`, and `ParsedStatement`. `src/finances/ingest/parsers/helpers.py` defines `collapse_ws`, `parse_amount`, `infer_year`, and `parse_month_day`.
- `src/finances/ingest/parsers/__init__.py` exists and is empty.
- `pypdf` is not installed.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `pyproject.toml` | one new runtime dependency |
| `src/finances/ingest/reconcile.py` | new: `ReconcileResult`, `reconcile` |
| `src/finances/ingest/dedup.py` | new: `fingerprint_lines` |
| `src/finances/ingest/pdf_text.py` | new: `extract_pages` |
| `src/finances/ingest/parsers/__init__.py` | `StatementParser`, `register`, `unregister`, `registered_parsers`, `detect_parser` |
| `tests/conftest.py` | replaced with the given file (three new fixtures) |
| `tests/unit/test_reconcile.py`, `tests/unit/test_dedup.py` | given, do not change |
| `tests/unit/test_pdf_text.py`, `tests/unit/test_parser_registry.py` | new, written by you |
| `docs/progress.md` | one new entry |

You may add private helpers (names starting with `_`) inside the four source modules. Do not create any other production module, and do not change any production file that is not in this table.

## Out of scope

- Any real bank parser, and any parser registered by production code. The registry is empty when this phase ends.
- A fake parser for tests beyond what your own registry tests need. Phase 3d adds the shared one.
- Database tables, repositories, an import service, or CLI commands.
- Options, tolerances, or modes on any of these functions: no "allow one cent", no "password" argument, no "strict" flag.
- OCR, or any fallback for PDFs without extractable text.
- Changes to `statement.py`, `helpers.py`, or anything under `src/finances/domain/`, `src/finances/db/`, or `src/finances/cli/`.

## Dependencies

Add `"pypdf>=5"` to `dependencies` in `pyproject.toml`, after `"alembic>=1.13"`, and install it:

`.venv/bin/python -m pip install -e ".[dev]"`

Nothing else. Do not add `cryptography` or `pycryptodome`.

## Design

### `src/finances/ingest/reconcile.py`

```python
@dataclass(frozen=True)
class ReconcileResult:
    ok: bool
    expected_closing_cents: int
    actual_closing_cents: int
    difference_cents: int
    section_mismatches: dict[Section, tuple[int, int]]


def reconcile(statement: ParsedStatement) -> ReconcileResult
```

### `src/finances/ingest/dedup.py`

```python
def fingerprint_lines(account_id: int, lines: list[StatementLine]) -> list[str]
```

### `src/finances/ingest/pdf_text.py`

```python
def extract_pages(content: bytes) -> list[str]
```

### `src/finances/ingest/parsers/__init__.py`

```python
class StatementParser(Protocol):
    name: str

    def detect(self, first_page: str) -> bool: ...
    def parse(self, pages: list[str]) -> ParsedStatement: ...


def register(parser: StatementParser) -> None
def unregister(name: str) -> None
def registered_parsers() -> list[StatementParser]
def detect_parser(pages: list[str]) -> StatementParser
```

Parsers work on text, never on PDF bytes, so every parser can be tested with a text fixture.

## Requirements

### Part 1: reconciliation

`reconcile` is the safeguard against a parser that misreads a statement. It never raises and never changes the statement.

- **R1.** `expected_closing_cents` is the opening balance plus the sum of every line's `amount_cents`. `actual_closing_cents` is the statement's closing balance.
- **R2.** `difference_cents` is `actual_closing_cents - expected_closing_cents`. Lines that add up to one cent less than the printed closing balance give `1`.
- **R3.** For each section in `declared_section_totals`, the computed total is the sum of the lines in that section, or `0` when there are none. A section whose computed total differs from its declared total appears in `section_mismatches` as `(declared, computed)`. Entries keep the order of `declared_section_totals`.
- **R4.** A section that has lines but no declared total is not checked and never appears in `section_mismatches`.
- **R5.** `ok` is `True` only when `difference_cents` is `0` and `section_mismatches` is empty. There is no tolerance: one cent is a failure.
- **R6.** All arithmetic is on `int`. A result must be exact for amounts beyond 2 to the power 53, where `float` is not.

### Part 2: fingerprints

A fingerprint is stored with each transaction (Phase 3c) and must never change for the same input, in any later version of this code.

- **R7.** The result has one entry per line, in the same order. Each entry is the SHA-256 hex digest (64 lower-case characters) of the UTF-8 encoding of seven fields joined by a newline character:

  | # | Field |
  |---|---|
  | 1 | `str(account_id)` |
  | 2 | `posted_date.isoformat()` |
  | 3 | `str(amount_cents)` |
  | 4 | `collapse_ws(description).upper()` |
  | 5 | `card_last4`, or the empty string when it is `None` |
  | 6 | `external_ref`, or the empty string when it is `None` |
  | 7 | the occurrence number, as decimal text |

- **R8.** The occurrence number of a line is how many earlier lines **in this call** have the same first six fields: `0` for the first, `1` for the second. Two identical purchases on one day therefore get different fingerprints, and the same statement always gives the same list.
- **R9.** `transaction_date`, `section`, and `cardholder` do not affect a fingerprint. Two lines that differ only in those are repeats of each other under R8.
- **R10.** Nothing is remembered between calls, and the lines are not changed.

### Part 3: PDF text

- **R11.** `extract_pages` reads the PDF from `content` in memory with `pypdf.PdfReader` and returns one string per page, in page order, each from `page.extract_text(extraction_mode="layout")`. A page with no text gives an empty string, and it is kept. A PDF with no pages gives an empty list.
- **R12.** Layout mode is required. It keeps the wide gaps between table columns that the bank parsers rely on; the default mode joins the columns with single spaces.
- **R13.** An encrypted PDF is tried with the empty password (`reader.decrypt("")`). Many bank PDFs are encrypted only against editing and open this way. When that does not open it, raise `StatementError("PDF is password protected")`.
- **R14.** Any other failure while reading, whatever exception the library raises, becomes `StatementError("could not read PDF")`. The library's exception is not attached: raise it `from None`. Its message can quote the file's content.
- **R15.** `pypdf` reports recoverable problems through the `pypdf` logger at WARNING level. Importing `finances.ingest.pdf_text` sets that logger's level to `logging.ERROR`, so none of it reaches the console.

### Part 4: the parser registry

The registry is module-level state in `finances.ingest.parsers`. It holds parser objects, keyed by `parser.name`.

- **R16.** `register` adds a parser. A name that is already registered raises `ValueError("parser name is already registered")` and leaves the registry unchanged.
- **R17.** `unregister` removes the parser with that name. A name that is not registered raises `ValueError("parser name is not registered")`.
- **R18.** `registered_parsers` returns the parsers in the order they were registered, as a new list each time. Changing the returned list does not change the registry.
- **R19.** `detect_parser` calls `detect(pages[0])` on every registered parser, with the first page only, and returns the one parser that answers `True`.
- **R20.** When no parser answers `True`, or `pages` is empty, or the registry is empty, it raises `StatementError("unrecognized statement format")`.
- **R21.** When more than one answers `True`, it raises `StatementError` with the message `statement matches more than one parser: ` followed by the matching names in registration order, joined by `, `. For parsers named `zeta` and `alpha` registered in that order: `statement matches more than one parser: zeta, alpha`. Parser names are identifiers from this code base, so they may appear in a message; statement text may not.
- **R22.** `StatementParser` is a `typing.Protocol` with exactly the members shown under Design.

## Given tests

Create these two files exactly as shown and do not change them. They define correct behavior for the two critical modules. If one of these tests fails, the production code is wrong.

`tests/unit/test_reconcile.py`:

```python
import dataclasses
import typing
from datetime import date

import pytest

from finances.domain.models import AccountType
from finances.ingest.reconcile import ReconcileResult, reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementLine


def line(amount_cents: int, section: Section = Section.PURCHASES) -> StatementLine:
    return StatementLine(date(2026, 1, 5), None, "ACME COFFEE", amount_cents, section)


def statement(
    opening: int,
    closing: int,
    lines: list[StatementLine],
    totals: dict[Section, int] | None = None,
) -> ParsedStatement:
    return ParsedStatement(
        parser_name="fake_bank",
        institution="Fake Bank",
        account_type=AccountType.CREDIT_CARD,
        account_last4="1111",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        opening_balance_cents=opening,
        closing_balance_cents=closing,
        lines=lines,
        declared_section_totals=totals or {},
    )


CARD_LINES = [
    line(-450),
    line(-12999),
    line(2500, Section.PAYMENTS_CREDITS),
    line(-13, Section.INTEREST),
]


def test_result_is_a_frozen_dataclass_with_five_fields() -> None:
    assert [field.name for field in dataclasses.fields(ReconcileResult)] == [
        "ok",
        "expected_closing_cents",
        "actual_closing_cents",
        "difference_cents",
        "section_mismatches",
    ]
    assert typing.get_type_hints(ReconcileResult) == {
        "ok": bool,
        "expected_closing_cents": int,
        "actual_closing_cents": int,
        "difference_cents": int,
        "section_mismatches": dict[Section, tuple[int, int]],
    }
    result = reconcile(statement(0, 0, []))
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.ok = False


def test_a_balanced_statement_is_ok() -> None:
    result = reconcile(statement(-10000, -20962, CARD_LINES))
    assert result == ReconcileResult(
        ok=True,
        expected_closing_cents=-20962,
        actual_closing_cents=-20962,
        difference_cents=0,
        section_mismatches={},
    )


def test_a_statement_with_no_lines_is_ok_when_the_balance_did_not_move() -> None:
    assert reconcile(statement(5000, 5000, [])).ok is True
    assert reconcile(statement(0, 0, [])).ok is True


def test_a_statement_with_no_lines_fails_when_the_balance_moved() -> None:
    result = reconcile(statement(5000, 4000, []))
    assert result.ok is False
    assert result.expected_closing_cents == 5000
    assert result.difference_cents == -1000


@pytest.mark.parametrize(
    ("closing", "difference"),
    [(-20961, 1), (-20963, -1), (-20862, 100), (0, 20962), (20962, 41924)],
)
def test_the_difference_is_actual_minus_expected(closing: int, difference: int) -> None:
    result = reconcile(statement(-10000, closing, CARD_LINES))
    assert result.ok is False
    assert result.expected_closing_cents == -20962
    assert result.actual_closing_cents == closing
    assert result.difference_cents == difference
    assert result.section_mismatches == {}


def test_one_cent_is_never_tolerated() -> None:
    lines = [line(-1)] * 3
    assert reconcile(statement(100, 97, lines)).ok is True
    assert reconcile(statement(100, 98, lines)).ok is False
    assert reconcile(statement(100, 96, lines)).ok is False


def test_a_checking_account_with_positive_balances_reconciles() -> None:
    lines = [
        line(250000, Section.DEPOSITS),
        line(-120050, Section.WITHDRAWALS),
        line(-4500, Section.CHECKS),
    ]
    result = reconcile(statement(100000, 225450, lines))
    assert result.ok is True
    assert result.expected_closing_cents == 225450


def test_matching_section_totals_are_ok() -> None:
    totals = {Section.PURCHASES: -13449, Section.PAYMENTS_CREDITS: 2500, Section.INTEREST: -13}
    result = reconcile(statement(-10000, -20962, CARD_LINES, totals))
    assert result.ok is True
    assert result.section_mismatches == {}


def test_a_wrong_section_total_fails_even_when_the_balance_is_right() -> None:
    totals = {Section.PURCHASES: -13450, Section.PAYMENTS_CREDITS: 2500}
    result = reconcile(statement(-10000, -20962, CARD_LINES, totals))
    assert result.ok is False
    assert result.difference_cents == 0
    assert result.section_mismatches == {Section.PURCHASES: (-13450, -13449)}


def test_every_wrong_section_is_reported_as_declared_then_computed() -> None:
    totals = {Section.INTEREST: 0, Section.PURCHASES: -13449, Section.PAYMENTS_CREDITS: 2400}
    result = reconcile(statement(-10000, -20962, CARD_LINES, totals))
    assert result.ok is False
    assert result.section_mismatches == {
        Section.INTEREST: (0, -13),
        Section.PAYMENTS_CREDITS: (2400, 2500),
    }
    assert list(result.section_mismatches) == [Section.INTEREST, Section.PAYMENTS_CREDITS]


def test_a_declared_total_for_a_section_with_no_lines_is_compared_with_zero() -> None:
    assert reconcile(statement(-10000, -20962, CARD_LINES, {Section.FEES: 0})).ok is True
    result = reconcile(statement(-10000, -20962, CARD_LINES, {Section.FEES: -3500}))
    assert result.ok is False
    assert result.section_mismatches == {Section.FEES: (-3500, 0)}


def test_sections_without_a_declared_total_are_not_checked() -> None:
    result = reconcile(statement(-10000, -20962, CARD_LINES, {Section.INTEREST: -13}))
    assert result.ok is True


def test_both_kinds_of_failure_are_reported_together() -> None:
    result = reconcile(statement(-10000, -20000, CARD_LINES, {Section.PURCHASES: -1}))
    assert result.ok is False
    assert result.difference_cents == 962
    assert result.section_mismatches == {Section.PURCHASES: (-1, -13449)}


def test_reconcile_does_not_change_the_statement() -> None:
    totals = {Section.PURCHASES: -1}
    lines = list(CARD_LINES)
    subject = statement(-10000, -20962, lines, totals)
    reconcile(subject)
    assert subject.lines == CARD_LINES
    assert subject.declared_section_totals == {Section.PURCHASES: -1}


def test_large_amounts_stay_exact() -> None:
    big = 9007199254740993
    result = reconcile(statement(0, big + 1, [line(big, Section.DEPOSITS), line(1)]))
    assert result.ok is True
    assert result.expected_closing_cents == 9007199254740994
    assert type(result.expected_closing_cents) is int
```

`tests/unit/test_dedup.py`:

```python
import re
from datetime import date

import pytest

from finances.ingest.dedup import fingerprint_lines
from finances.ingest.statement import Section, StatementLine

COFFEE = StatementLine(date(2026, 1, 5), None, "ACME COFFEE #12", -450, Section.PURCHASES)
GROCERY = StatementLine(
    date(2026, 1, 6),
    date(2026, 1, 4),
    "FOOBAR GROCERY",
    -2599,
    Section.PURCHASES,
    card_last4="2222",
    cardholder="JANE DOE",
    external_ref="7838",
)
COFFEE_FIRST = "8308861cce52605968528ac9ec9df4dc7e93fc406fae8ceed2c1fc905d98324b"
COFFEE_SECOND = "dc7320935e980c403d9e15b3d99e1e558129fd1f692624bb1cffb7e7cf8bde95"
GROCERY_FIRST = "d753f7f504babf6834269807c6d163b18bff87556393f29f56f77f027469ac89"
UNICODE_FIRST = "5eebeb35c6fcaf97ac1f556500cc7d24fd5c338fd5237f4b2c7e09a01459f995"


def changed(line: StatementLine, **changes: object) -> StatementLine:
    values = {
        "posted_date": line.posted_date,
        "transaction_date": line.transaction_date,
        "description": line.description,
        "amount_cents": line.amount_cents,
        "section": line.section,
        "card_last4": line.card_last4,
        "cardholder": line.cardholder,
        "external_ref": line.external_ref,
    }
    values.update(changes)
    return StatementLine(**values)


def one(account_id: int, line: StatementLine) -> str:
    return fingerprint_lines(account_id, [line])[0]


def test_no_lines_gives_no_fingerprints() -> None:
    assert fingerprint_lines(7, []) == []


def test_one_fingerprint_per_line_in_order() -> None:
    result = fingerprint_lines(7, [COFFEE, GROCERY, COFFEE])
    assert type(result) is list
    assert result == [COFFEE_FIRST, GROCERY_FIRST, COFFEE_SECOND]


def test_a_fingerprint_is_64_lower_case_hex_characters() -> None:
    for fingerprint in fingerprint_lines(7, [COFFEE, GROCERY]):
        assert type(fingerprint) is str
        assert re.fullmatch(r"[0-9a-f]{64}", fingerprint)


def test_the_exact_values_never_change() -> None:
    assert one(7, COFFEE) == COFFEE_FIRST
    assert one(7, GROCERY) == GROCERY_FIRST
    unicode_line = changed(
        COFFEE, posted_date=date(2026, 1, 7), description="Café Zürich Straße", amount_cents=1500
    )
    assert one(7, unicode_line) == UNICODE_FIRST


def test_the_same_statement_twice_gives_the_same_fingerprints() -> None:
    lines = [COFFEE, GROCERY, COFFEE, COFFEE]
    assert fingerprint_lines(7, lines) == fingerprint_lines(7, list(lines))


def test_identical_lines_get_different_fingerprints() -> None:
    result = fingerprint_lines(7, [COFFEE, COFFEE, COFFEE, GROCERY, GROCERY])
    assert len(set(result)) == 5
    assert result[:2] == [COFFEE_FIRST, COFFEE_SECOND]


def test_repeats_are_counted_per_line_not_per_position() -> None:
    assert fingerprint_lines(7, [GROCERY, COFFEE, GROCERY, COFFEE]) == [
        GROCERY_FIRST,
        COFFEE_FIRST,
        fingerprint_lines(7, [GROCERY, GROCERY])[1],
        COFFEE_SECOND,
    ]


def test_each_call_counts_repeats_from_zero() -> None:
    fingerprint_lines(7, [COFFEE, COFFEE])
    assert fingerprint_lines(7, [COFFEE]) == [COFFEE_FIRST]


@pytest.mark.parametrize(
    "description",
    ["acme coffee #12", "  ACME COFFEE #12  ", "ACME   COFFEE\t#12", "Acme\nCoffee #12"],
)
def test_case_and_spacing_of_the_description_do_not_matter(description: str) -> None:
    assert one(7, changed(COFFEE, description=description)) == COFFEE_FIRST


@pytest.mark.parametrize(
    "changes",
    [
        {"posted_date": date(2026, 1, 6)},
        {"amount_cents": -451},
        {"amount_cents": 450},
        {"description": "ACME COFFEE #13"},
        {"description": "ACMECOFFEE #12"},
        {"card_last4": "2222"},
        {"external_ref": "7838"},
    ],
)
def test_each_identifying_field_changes_the_fingerprint(changes: dict) -> None:
    assert one(7, changed(COFFEE, **changes)) != COFFEE_FIRST


@pytest.mark.parametrize(
    "changes",
    [
        {"transaction_date": date(2026, 1, 3)},
        {"section": Section.FEES},
        {"cardholder": "JOHN DOE"},
    ],
)
def test_other_fields_do_not_change_the_fingerprint(changes: dict) -> None:
    assert one(7, changed(COFFEE, **changes)) == COFFEE_FIRST


def test_lines_that_differ_only_in_other_fields_count_as_repeats() -> None:
    result = fingerprint_lines(7, [COFFEE, changed(COFFEE, section=Section.FEES)])
    assert result == [COFFEE_FIRST, COFFEE_SECOND]


def test_the_account_changes_the_fingerprint() -> None:
    assert one(8, COFFEE) != COFFEE_FIRST
    assert one(70, COFFEE) != one(7, COFFEE)


def test_a_value_cannot_slide_between_fields() -> None:
    with_card = changed(COFFEE, card_last4="1234", external_ref=None)
    with_ref = changed(COFFEE, card_last4=None, external_ref="1234")
    assert one(7, with_card) != one(7, with_ref)
    assert one(7, changed(COFFEE, description="A", external_ref="B")) != one(
        7, changed(COFFEE, description="A B", external_ref=None)
    )


def test_the_lines_are_not_changed() -> None:
    lines = [COFFEE, GROCERY]
    fingerprint_lines(7, lines)
    assert lines == [COFFEE, GROCERY]
```

## Given fixtures

Replace the whole content of `tests/conftest.py` with this. `tmp_settings`, `db_url`, and `db_engine` are unchanged. The three new fixtures are for your tests in this phase and for later phases:

- `make_pdf(pages)` builds a small real PDF from text: one inner list of lines per page. A tab inside a line starts a new column further right, as a statement table would.
- `encrypt_pdf(content, user_password)` encrypts PDF bytes. With `""` the result opens with the empty password; with any other value it does not.
- `parser_registry` gives a test an empty registry and restores the previous one afterwards. Every test that registers a parser must use it.

The file imports `finances.ingest.parsers` and `pypdf`, so no test can be collected until Part 4's functions exist and the dependency is installed.

```python
import io
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from sqlalchemy import Engine

from finances.config import Settings, get_settings
from finances.db.engine import get_engine
from finances.db.migrate import upgrade_to_head
from finances.ingest.parsers import register, registered_parsers, unregister

_ENV_KEYS = ("FIN_ENVIRONMENT", "FIN_DATA_DIR", "FIN_DATABASE_URL", "FIN_LOG_LEVEL")


@pytest.fixture
def tmp_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Settings]:
    """Settings whose data dir is under tmp_path, with no .env file in reach."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FIN_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    """URL of a SQLite database file under tmp_path. The file does not exist yet."""
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def db_engine(db_url: str) -> Iterator[Engine]:
    """Engine for a temporary database that has been migrated to the newest revision."""
    upgrade_to_head(db_url)
    engine = get_engine(db_url)
    yield engine
    engine.dispose()


def _build_pdf(pages: list[list[str]]) -> bytes:
    objects = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        operators = ["BT", "/F1 10 Tf"]
        for index, line in enumerate(lines):
            for column, cell in enumerate(line.split("\t")):
                text = cell.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                position = f"1 0 0 1 {72 + 180 * column} {720 - 14 * index} Tm"
                operators.append(f"{position} ({text}) Tj")
        operators.append("ET")
        stream = "\n".join(operators).encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        resources = b"/Resources << /Font << /F1 3 0 R >> >>"
        page = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] %s /Contents %d 0 R >>"
        objects.append(page % (resources, len(objects)))
        kids.append(len(objects))
    references = b" ".join(b"%d 0 R" % kid for kid in kids)
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (references, len(kids))
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    out += b"startxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


@pytest.fixture
def make_pdf() -> Callable[[list[list[str]]], bytes]:
    """Return a function that builds a PDF: one inner list of text lines per page.

    A tab inside a line starts a new column 180 points to the right, the way statement
    tables are printed: three separate pieces of text on one row.
    """
    return _build_pdf


@pytest.fixture
def encrypt_pdf() -> Callable[[bytes, str], bytes]:
    """Return a function that encrypts PDF bytes so that opening them needs user_password."""

    def encrypt(content: bytes, user_password: str) -> bytes:
        writer = PdfWriter(clone_from=PdfReader(io.BytesIO(content)))
        writer.encrypt(user_password=user_password, owner_password="owner", algorithm="RC4-128")
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    return encrypt


@pytest.fixture
def parser_registry() -> Iterator[None]:
    """Give the test an empty parser registry, and put the real one back afterwards."""
    saved = registered_parsers()
    for parser in saved:
        unregister(parser.name)
    yield
    for parser in registered_parsers():
        unregister(parser.name)
    for parser in saved:
        register(parser)
```

## Tests to write

Unit tests, with synthetic text only (invented merchants such as ACME COFFEE and FOOBAR GROCERY; no real names or account numbers). Every requirement in Parts 3 and 4 needs at least one test that fails when the requirement is broken.

`tests/unit/test_pdf_text.py`:

- one string per page, in order, with an empty page kept and a PDF without pages giving `[]` (R11)
- a line with tab-separated columns comes back with gaps of several spaces between the columns, which fails if the default extraction mode is used (R12)
- a PDF encrypted with the empty user password is read (R13)
- a PDF encrypted with a real user password raises the exact message (R13)
- several kinds of unreadable bytes (empty, plain text, a valid PDF cut short, binary noise) each raise the exact message, with `__cause__` being `None` and `__suppress_context__` being `True` (R14)
- the `pypdf` logger's effective level (R15)

`tests/unit/test_parser_registry.py`, using small parser classes defined in the test file:

- registering, listing in order, and the returned list being a copy (R16, R18)
- a duplicate name, with the exact message and the registry unchanged (R16)
- unregistering, the exact message for an unknown name, and registering the same name again afterwards (R17)
- a single match is returned, and each parser was offered the first page only (R19)
- no match, a match that is only on a later page, an empty list of pages, and an empty registry, each with the exact message (R20)
- two matches, with the names in registration order when that differs from alphabetical order (R21)
- the registry is empty outside the `parser_registry` fixture, which shows that no test leaks a parser

## Rules for this phase

- **Money is `int` cents.** `float`, `/` division, and `round` do not appear in `reconcile.py`.
- **Constant messages.** The six messages above are the only ones raised. Apart from the parser names in R21, no message contains input: no statement text, amount, description, or bytes.
- **Nothing is logged or printed** by these modules. Amounts and descriptions must never reach a log (`AGENTS.md` privacy rule 4).
- **Layering.** `finances.ingest` may import from `finances.domain` and from itself. It does not import `finances.db` or `finances.cli`.
- **Synthetic data only** in tests. Do not read anything under `data/`.
- **No shipped code changes.** Phase 3a's modules and all earlier tests stay as they are.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`. The user commits after verification.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least `495 passed`, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_reconcile.py tests/unit/test_dedup.py --no-cov` | exactly `45 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| the search below | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "float|round\(|print\(|logging\.(debug|info|warning|error)|finances\.(db|cli)" -- src/finances/ingest`

The coverage command measures the whole `finances.ingest` package, which this phase completes to 100% including branches. A line no test reaches is either missing a test or is code no requirement asks for.

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 3b: statement checks and reading (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give the final passed count. Under "Deviations", list every design choice the spec left to you (private helpers, how the registry is stored) and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command, and for each of R11 to R22 the name of the test that covers it.
