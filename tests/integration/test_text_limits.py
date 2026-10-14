"""Every text the app stores fits its column, however long the text it is given."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import Engine, String, func, select
from typer.testing import CliRunner

import finances.ingest.service as ingest
from finances.cli.main import app as cli
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import Base, TransactionRow
from finances.db.repositories import create_account
from finances.domain.models import AccountType
from finances.ingest.parsers import register
from finances.ingest.service import ImportStatus, import_statement
from finances.ingest.statement import ParsedStatement, Section, StatementLine
from finances.sync.feed import AccountFeed, FeedTransaction
from finances.sync.service import apply_feed
from finances.web.app import create_app

runner = CliRunner(env={"COLUMNS": "200"})
NAME_TOO_LONG = "account name must be at most 100 characters"
INSTITUTION_TOO_LONG = "institution must be at most 100 characters"
BAD_CURRENCY = "currency must be three capital letters"


def too_long(session) -> list[str]:
    """Each text column holding a value longer than the column allows."""
    found = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, String) and column.type.length:
                longest = session.scalar(select(func.max(func.length(column))))
                if longest is not None and longest > column.type.length:
                    found.append(f"{table.name}.{column.name}")
    return found


# Accounts


@pytest.mark.parametrize(
    ("name", "institution"),
    [("N" * 100, "Probe Bank"), ("Probe", "I" * 100), ("  " + "N" * 100 + "  ", "Probe Bank")],
    ids=["name", "institution", "outer-spaces"],
)
def test_names_up_to_one_hundred_characters_are_kept(
    db_engine: Engine, name: str, institution: str
) -> None:
    with session_scope(db_engine) as session:
        made = create_account(session, name, institution, "other")
    assert (made.name, made.institution) == (name.strip(), institution)


@pytest.mark.parametrize(
    ("name", "institution", "message"),
    [
        ("N" * 101, "Probe Bank", NAME_TOO_LONG),
        ("Probe", "I" * 101, INSTITUTION_TOO_LONG),
        ("N" * 5000, "I" * 5000, NAME_TOO_LONG),
    ],
    ids=["name", "institution", "both"],
)
def test_longer_names_are_refused(
    db_engine: Engine, name: str, institution: str, message: str
) -> None:
    with session_scope(db_engine) as session, pytest.raises(ValueError, match=f"^{message}$"):
        create_account(session, name, institution, "other")


@pytest.mark.parametrize("currency", ["USD", "EUR", "CAD"])
def test_three_capital_letters_are_a_currency(db_engine: Engine, currency: str) -> None:
    with session_scope(db_engine) as session:
        assert (
            create_account(session, "Probe", "Probe Bank", "other", currency).currency == currency
        )


@pytest.mark.parametrize(
    "currency", ["usd", "Usd", "US", "USDX", "", " USD", "U$D", "U1D", "ＵＳＤ", "ÜSD"]
)
def test_anything_else_is_not_a_currency(db_engine: Engine, currency: str) -> None:
    with session_scope(db_engine) as session, pytest.raises(ValueError, match=f"^{BAD_CURRENCY}$"):
        create_account(session, "Probe", "Probe Bank", "other", currency)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--name", "N" * 101], NAME_TOO_LONG),
        (["--name", "Probe", "--institution", "I" * 101], INSTITUTION_TOO_LONG),
        (["--name", "Probe", "--currency", "usd"], BAD_CURRENCY),
    ],
    ids=["name", "institution", "currency"],
)
def test_the_command_reports_each_refusal(
    tmp_settings: Settings, args: list[str], message: str
) -> None:
    upgrade_to_head()
    defaults = ["--institution", "Probe Bank", "--type", "other"]
    result = runner.invoke(cli, ["accounts", "add", *defaults, *args])
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", f"Error: {message}\n")
    assert isinstance(result.exception, SystemExit)


def test_the_web_form_reports_a_long_name(tmp_settings: Settings) -> None:
    upgrade_to_head()
    client = TestClient(create_app(8765), base_url="http://127.0.0.1:8765")
    client.get("/accounts")
    fields = {"name": "N" * 101, "institution": "Probe Bank", "type": "other"}
    response = client.post("/accounts/add", data={"csrf": client.cookies["fin_csrf"], **fields})
    assert response.status_code == 400
    assert f'<p class="error">{NAME_TOO_LONG}</p>' in response.text


# Statements


class LongTextParser:
    """A parser whose one line has a description, cardholder, and reference longer than allowed."""

    name = "long_text"

    def __init__(self, description: str, cardholder: str, reference: str) -> None:
        self.line = StatementLine(
            date(2026, 4, 10),
            None,
            description,
            -450,
            Section.PURCHASES,
            "2222",
            cardholder,
            reference,
        )

    def detect(self, first_page: str) -> bool:
        return first_page == "LONG TEXT"

    def parse(self, pages: list[str]) -> ParsedStatement:
        return ParsedStatement(
            parser_name=self.name,
            institution="Probe Bank",
            account_type=AccountType.CREDIT_CARD,
            account_last4="1111",
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            opening_balance_cents=0,
            closing_balance_cents=-450,
            lines=[self.line],
        )


@pytest.fixture
def long_text(parser_registry: None, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ingest, "extract_pages", lambda content: [content.decode()])

    def use(description: str, cardholder: str, reference: str) -> None:
        register(LongTextParser(description, cardholder, reference))

    return use


def stored_line(engine: Engine) -> tuple[str, str, str, str]:
    with session_scope(engine) as session:
        row = session.scalars(select(TransactionRow)).one()
        assert too_long(session) == []
        return row.description, row.cardholder, row.external_id, row.source


@pytest.mark.parametrize("feed_first", [False, True])
def test_long_statement_text_is_cut_to_fit(db_engine: Engine, long_text, feed_first: bool) -> None:
    words = " ".join(f"WORD{n:03d}" for n in range(100))
    long_text(f"  ACM   {words}  ", "SAM " + "Q" * 200, "R" * 300)
    with session_scope(db_engine) as session:
        account = create_account(session, "Probe Card", "Probe Bank", "credit_card", last4="1111")
        if feed_first:
            apply_feed(
                session,
                account.id,
                AccountFeed([FeedTransaction("F1", date(2026, 4, 11), -450, "ACME")]),
            )
    with session_scope(db_engine) as session:
        result = import_statement(session, filename="april.pdf", content=b"LONG TEXT")
    assert result.status == ImportStatus.IMPORTED
    description, cardholder, reference, source = stored_line(db_engine)
    expected = f"ACM {words}"[:500].rstrip()
    assert (description, cardholder, reference, source) == (
        expected,
        ("SAM " + "Q" * 200)[:100],
        "R" * 100,
        "statement",
    )
    assert len(description) == 499


def test_statement_text_that_fits_is_kept_whole(db_engine: Engine, long_text) -> None:
    long_text("D" * 500, "C" * 100, "R" * 100)
    with session_scope(db_engine) as session:
        create_account(session, "Probe Card", "Probe Bank", "credit_card", last4="1111")
    with session_scope(db_engine) as session:
        import_statement(session, filename="april.pdf", content=b"LONG TEXT")
    assert stored_line(db_engine)[:3] == ("D" * 500, "C" * 100, "R" * 100)


# Web forms


FORMS = {
    "/accounts/add": ["name", "institution", "type", "last4"],
    "/accounts/owner": ["account", "owner"],
    "/people/add": ["name"],
    "/people/alias": ["person", "cardholder"],
    "/sync/unlink": ["link"],
    "/sync/map": ["link", "feed_account", "account"],
    "/sync/create": ["link", "feed_account", "account", "institution", "type", "last4"],
}
field = st.one_of(
    st.text(max_size=12),
    st.text(min_size=95, max_size=300),
    st.sampled_from(
        ["Probe", "Kim", "joint", "other", "credit_card", "1234", "", "kim", "ACT-1", "\x00", "on"]
    ),
)


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory):
    folder = tmp_path_factory.mktemp("site")
    patch = pytest.MonkeyPatch()
    patch.setenv("FIN_DATA_DIR", str(folder))
    from finances.config import get_settings

    get_settings.cache_clear()
    upgrade_to_head()
    client = TestClient(
        create_app(8765), base_url="http://127.0.0.1:8765", raise_server_exceptions=False
    )
    client.get("/accounts")
    yield client
    patch.undo()
    get_settings.cache_clear()


@settings(max_examples=300)
@given(st.sampled_from(sorted(FORMS)), st.data())
def test_no_form_input_breaks_the_site_or_overfills_a_column(site, path: str, data) -> None:
    fields = {name: data.draw(field, label=name) for name in FORMS[path]}
    response = site.post(
        path, data={"csrf": site.cookies["fin_csrf"], **fields}, follow_redirects=False
    )
    assert response.status_code in (303, 400)
    engine = get_engine()
    with session_scope(engine) as session:
        assert too_long(session) == []
    engine.dispose()
