import io
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from sqlalchemy import Engine

from finances.config import Settings, get_settings
from finances.db.engine import get_engine
from finances.db.migrate import upgrade_to_head
from finances.domain.models import AccountType
from finances.ingest.parsers import register, registered_parsers, unregister
from finances.ingest.parsers.helpers import parse_amount
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

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


FAKE_ROWS = (
    "2026-01-05|2026-01-04|purchases|-4.50|2222|-|ACME COFFEE #12",
    "2026-01-06|-|purchases|-25.99|2222|7838|FOOBAR   GROCERY",
    "2026-01-05|2026-01-04|purchases|-4.50|2222|-|ACME COFFEE #12",
    "2026-01-20|-|payments_credits|50.00|-|-|PAYMENT THANK YOU",
)


class FakeBankParser:
    """A parser for a made-up text format, so import tests need no real bank layout.

    FAKEBANK STATEMENT
    ACCOUNT <last4> <account type>
    PERIOD <start> <end>
    OPENING <amount>
    CLOSING <amount>
    TOTAL <section> <amount>          (optional, any number)
    ROW <posted>|<transaction or ->|<section>|<amount>|<card last4 or ->|<reference or ->|<text>
    """

    name = "fake_bank"

    def detect(self, first_page: str) -> bool:
        return first_page.lstrip().startswith("FAKEBANK STATEMENT")

    def parse(self, pages: list[str]) -> ParsedStatement:
        try:
            return self._parse([line.strip() for page in pages for line in page.splitlines()])
        except (KeyError, ValueError, IndexError):
            raise StatementError("fake statement is malformed") from None

    def _parse(self, lines: list[str]) -> ParsedStatement:
        fields = {}
        totals = {}
        rows = []
        for line in lines:
            keyword, _, rest = line.partition(" ")
            if keyword == "TOTAL":
                section, amount = rest.split()
                totals[Section(section)] = parse_amount(amount)
            elif keyword == "ROW":
                posted, transaction, section, amount, card, reference, text = rest.split("|", 6)
                rows.append(
                    StatementLine(
                        posted_date=date.fromisoformat(posted),
                        transaction_date=None
                        if transaction == "-"
                        else date.fromisoformat(transaction),
                        description=text,
                        amount_cents=parse_amount(amount),
                        section=Section(section),
                        card_last4=None if card == "-" else card,
                        external_ref=None if reference == "-" else reference,
                    )
                )
            elif keyword in {"ACCOUNT", "PERIOD", "OPENING", "CLOSING"}:
                fields[keyword] = rest.split()
        return ParsedStatement(
            parser_name=self.name,
            institution="Fake Bank",
            account_type=AccountType(fields["ACCOUNT"][1]),
            account_last4=fields["ACCOUNT"][0],
            period_start=date.fromisoformat(fields["PERIOD"][0]),
            period_end=date.fromisoformat(fields["PERIOD"][1]),
            opening_balance_cents=parse_amount(fields["OPENING"][0]),
            closing_balance_cents=parse_amount(fields["CLOSING"][0]),
            lines=rows,
            declared_section_totals=totals,
        )


def _fake_statement_lines(
    *,
    last4: str = "1111",
    account_type: str = "credit_card",
    start: str = "2026-01-01",
    end: str = "2026-01-31",
    opening: str = "-100.00",
    closing: str = "-84.99",
    rows: tuple[str, ...] = FAKE_ROWS,
    totals: tuple[str, ...] = (),
) -> list[str]:
    return [
        "FAKEBANK STATEMENT",
        f"ACCOUNT {last4} {account_type}",
        f"PERIOD {start} {end}",
        f"OPENING {opening}",
        f"CLOSING {closing}",
        *(f"TOTAL {total}" for total in totals),
        *(f"ROW {row}" for row in rows),
    ]


@pytest.fixture
def fake_bank(parser_registry: None) -> FakeBankParser:
    """Register the fake bank parser for this test and return it."""
    parser = FakeBankParser()
    register(parser)
    return parser


@pytest.fixture
def fake_statement_pdf() -> Callable[..., bytes]:
    """Return a function that builds a fake bank statement as PDF bytes.

    With no arguments it is a balanced card statement for last4 1111: four rows (two of
    them identical), opening -100.00, closing -84.99. Keyword arguments replace parts of
    it: last4, account_type, start, end, opening, closing, rows, totals.
    """

    def build(**changes: object) -> bytes:
        return _build_pdf([_fake_statement_lines(**changes)])

    return build
