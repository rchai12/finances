from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import create_account, create_rule
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

STATEMENTS = ["Account", "File", "Parser", "Period", "Opening", "Closing", "Lines", "New"]
JANUARY = [
    "Test Card",
    "jan.pdf",
    "fake_bank",
    "2026-01-01 to 2026-01-31",
    "-$100.00",
    "-$84.99",
    "4",
    "4",
]
IMPORTED = [
    ["File", "jan.pdf"],
    ["Parser", "fake_bank"],
    ["Account", "Test Card"],
    ["Period", "2026-01-01 to 2026-01-31"],
    ["Lines", "4"],
    ["Inserted", "4"],
    ["Duplicates", "0"],
    ["Status", "imported"],
]
MARCH_ROW = "2026-03-05|-|purchases|-10.00|2222|-|ACME COFFEE #12"


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient, fake_bank) -> TestClient:
    """Test Card ends in 1111 (the fake statement's card); a rule sends ACME COFFEE to Dining."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_rule(session, "ACME COFFEE", "Dining")
    engine.dispose()
    client.get("/statements")
    return client


def upload(client: TestClient, name: str, content: bytes, **fields: str):
    return client.post(
        "/statements/upload",
        data={"csrf": client.cookies["fin_csrf"], "account": "", **fields},
        files={"file": (name, content, "application/pdf")},
    )


def test_the_menu_has_statements(home: TestClient) -> None:
    html = home.get("/statements").text
    assert 'href="/statements" aria-current="page">Statements</a>' in html
    assert html.count('aria-current="page"') == 1
    assert 'href="/statements">Statements</a>' in home.get("/accounts").text
    assert "<script" not in html


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/statements")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_the_empty_page(home: TestClient) -> None:
    found = page(home, "/statements")
    assert ("empty", "No statements.") in found.paragraphs
    assert ("empty", "No gaps between statements.") in found.paragraphs
    form = found.find("/statements/upload")
    assert form["inputs"]["file"] == ("file", "")
    assert form["inputs"]["dry_run"] == ("checkbox", "yes")
    assert form["selects"]["account"] == [("", True), ("Test Card", False)]
    assert 'enctype="multipart/form-data"' in home.get("/statements").text


def test_upload_a_statement(home: TestClient, fake_statement_pdf: Callable[..., bytes]) -> None:
    response = upload(home, "jan.pdf", fake_statement_pdf())
    assert response.status_code == 200
    found = Page(response.text)
    assert found.rows == [*IMPORTED, STATEMENTS, JANUARY]
    acme = page(home, "/transactions?text=acme").rows
    assert [row[3] for row in acme[1:]] == ["Dining", "Dining"]


def test_a_dry_run_writes_nothing(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    response = upload(home, "jan.pdf", fake_statement_pdf(), dry_run="yes")
    assert response.status_code == 200
    found = Page(response.text)
    assert found.rows == [*IMPORTED[:-1], ["Status", "dry run, nothing written"]]
    assert ("empty", "No statements.") in found.paragraphs
    assert found.find("/statements/upload")["inputs"]["dry_run"] == ("checkbox", "yes")
    assert 'value="yes" checked' in response.text


def test_the_same_file_twice(home: TestClient, fake_statement_pdf: Callable[..., bytes]) -> None:
    upload(home, "jan.pdf", fake_statement_pdf())
    response = upload(home, "again.pdf", fake_statement_pdf())
    assert response.status_code == 200
    assert Page(response.text).rows == [
        ["File", "again.pdf"],
        ["Status", "already imported"],
        STATEMENTS,
        JANUARY,
    ]


def test_only_the_file_name_is_kept(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    upload(home, "../../elsewhere/jan.pdf", fake_statement_pdf())
    upload(
        home,
        "C:\\Users\\someone\\mar.pdf",
        fake_statement_pdf(
            start="2026-03-01",
            end="2026-03-31",
            opening="-84.99",
            closing="-94.99",
            rows=(MARCH_ROW,),
        ),
    )
    files = [row[1] for row in page(home, "/statements").rows[1:3]]
    assert files == ["mar.pdf", "jan.pdf"]


def test_gaps_between_statements(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    upload(home, "jan.pdf", fake_statement_pdf())
    upload(
        home,
        "mar.pdf",
        fake_statement_pdf(
            start="2026-03-01",
            end="2026-03-31",
            opening="-84.99",
            closing="-94.99",
            rows=(MARCH_ROW,),
        ),
    )
    found = page(home, "/statements")
    assert found.rows[-2:] == [
        ["Account", "Missing from", "Missing to"],
        ["Test Card", "2026-02-01", "2026-02-28"],
    ]
    assert (
        texts(found, "hint")[-1]
        == "Days between two statements of the same account that neither covers."
    )


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("jan.pdf", b"", "choose a PDF statement"),
        ("notes.txt", b"just some text", "the file is not a PDF"),
        ("big.pdf", b"%PDF-" + b"0" * (20 * 1024 * 1024), "a statement must be at most 20 MB"),
    ],
)
def test_a_refused_upload(home: TestClient, name: str, content: bytes, message: str) -> None:
    response = upload(home, name, content)
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", message) in found.paragraphs
    assert ("empty", "No statements.") in found.paragraphs


def test_no_file_at_all(home: TestClient) -> None:
    response = home.post(
        "/statements/upload", data={"csrf": home.cookies["fin_csrf"], "account": ""}
    )
    assert response.status_code == 400
    assert ("error", "choose a PDF statement") in Page(response.text).paragraphs


def test_a_statement_the_import_refuses(
    home: TestClient, fake_statement_pdf: Callable[..., bytes], make_pdf
) -> None:
    response = upload(home, "x.pdf", fake_statement_pdf(last4="9999"))
    assert response.status_code == 400
    assert (
        "error",
        'no account ends in 9999; add one with: fin accounts add --name "NAME" --institution'
        ' "Fake Bank" --type credit_card --last4 9999',
    ) in Page(response.text).paragraphs
    response = upload(home, "bad.pdf", make_pdf([["NOT A STATEMENT"]]))
    assert response.status_code == 400
    assert ("error", "unrecognized statement format") in Page(response.text).paragraphs
    assert ("empty", "No statements.") in Page(response.text).paragraphs


def test_the_form_needs_its_token(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    response = home.post(
        "/statements/upload", files={"file": ("jan.pdf", fake_statement_pdf(), "application/pdf")}
    )
    assert (response.status_code, response.text) == (403, "Bad form token")
    assert home.get("/statements/upload").status_code == 405
