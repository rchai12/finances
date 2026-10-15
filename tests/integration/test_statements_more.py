from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from finances.analysis.statements import statement_gap_lines
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import create_account, create_statement, set_account_active
from finances.ingest.service import ImportStatus, StatementImportResult
from finances.views.statements import import_rows
from finances.web.app import _upload_name, create_app
from tests.support import WEB_PORT, Page


@pytest.fixture
def home(tmp_settings: Settings, fake_bank) -> TestClient:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/statements")
    return client


def upload(client: TestClient, name: str, content: bytes, **fields: str):
    return client.post(
        "/statements/upload",
        data={"csrf": client.cookies["fin_csrf"], "account": "", **fields},
        files={"file": (name, content, "application/pdf")},
    )


def add_statement(session, account_id: int, name: str, start: date, end: date, digest: str) -> None:
    create_statement(
        session,
        account_id=account_id,
        source_filename=name,
        file_sha256=digest.ljust(64, "0")[:64],
        parser_name="fake_bank",
        period_start=start,
        period_end=end,
        opening_balance_cents=-10000,
        closing_balance_cents=-9000,
        lines_parsed=1,
        rows_inserted=1,
        rows_duplicate=0,
    )


def test_statement_gap_lines_orders_accounts_and_includes_inactive(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        zebra = create_account(session, "Zebra Card", "Test Bank", "credit_card")
        apple = create_account(session, "apple card", "Test Bank", "credit_card")
        closed = create_account(session, "Closed Card", "Test Bank", "credit_card")
        set_account_active(session, closed.id, False)
        add_statement(session, apple.id, "a.pdf", date(2026, 1, 1), date(2026, 1, 31), "a")
        add_statement(session, apple.id, "c.pdf", date(2026, 3, 1), date(2026, 3, 31), "c")
        add_statement(session, zebra.id, "z1.pdf", date(2026, 1, 1), date(2026, 1, 15), "z1")
        add_statement(session, zebra.id, "z2.pdf", date(2026, 2, 1), date(2026, 2, 28), "z2")
        add_statement(session, closed.id, "x1.pdf", date(2026, 1, 1), date(2026, 1, 10), "x1")
        add_statement(session, closed.id, "x2.pdf", date(2026, 1, 20), date(2026, 1, 31), "x2")
        lines = statement_gap_lines(session)
    assert [(line.account, line.start, line.end) for line in lines] == [
        ("apple card", date(2026, 2, 1), date(2026, 2, 28)),
        ("Closed Card", date(2026, 1, 11), date(2026, 1, 19)),
        ("Zebra Card", date(2026, 1, 16), date(2026, 1, 31)),
    ]


@pytest.mark.parametrize(
    ("result", "rows"),
    [
        (
            StatementImportResult("a.pdf", ImportStatus.FAILED, "nope"),
            [],
        ),
        (
            StatementImportResult("a.pdf", ImportStatus.ALREADY_IMPORTED, "already imported"),
            [("File", "a.pdf"), ("Status", "already imported")],
        ),
        (
            StatementImportResult(
                "a.pdf",
                ImportStatus.IMPORTED,
                "imported",
                parser_name="fake_bank",
                account_name="Test Card",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                lines_parsed=4,
                inserted=4,
                duplicates=0,
            ),
            [
                ("File", "a.pdf"),
                ("Parser", "fake_bank"),
                ("Account", "Test Card"),
                ("Period", "2026-01-01 to 2026-01-31"),
                ("Lines", "4"),
                ("Inserted", "4"),
                ("Duplicates", "0"),
                ("Status", "imported"),
            ],
        ),
        (
            StatementImportResult(
                "a.pdf",
                ImportStatus.DRY_RUN,
                "dry run: nothing written",
                parser_name="fake_bank",
                account_name="Test Card",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                lines_parsed=4,
                inserted=4,
                duplicates=0,
            ),
            [
                ("File", "a.pdf"),
                ("Parser", "fake_bank"),
                ("Account", "Test Card"),
                ("Period", "2026-01-01 to 2026-01-31"),
                ("Lines", "4"),
                ("Inserted", "4"),
                ("Duplicates", "0"),
                ("Status", "dry run, nothing written"),
            ],
        ),
        (
            StatementImportResult(
                "a.pdf",
                ImportStatus.IMPORTED,
                "imported",
                parser_name="fake_bank",
                account_name="Test Card",
                lines_parsed=0,
            ),
            [
                ("File", "a.pdf"),
                ("Parser", "fake_bank"),
                ("Account", "Test Card"),
                ("Period", ""),
                ("Lines", "0"),
                ("Inserted", "0"),
                ("Duplicates", "0"),
                ("Status", "imported"),
            ],
        ),
    ],
)
def test_import_rows_for_each_status(
    result: StatementImportResult, rows: list[tuple[str, str]]
) -> None:
    assert import_rows(result) == rows


def test_upload_with_a_chosen_account(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    response = upload(home, "jan.pdf", fake_statement_pdf(), account="Test Card")
    assert response.status_code == 200
    assert ["Account", "Test Card"] in Page(response.text).rows
    assert Page(response.text).find("/statements/upload")["selects"]["account"] == [
        ("", False),
        ("Test Card", True),
    ]


def test_upload_with_an_unknown_account(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    response = upload(home, "jan.pdf", fake_statement_pdf(), account="Nope")
    assert response.status_code == 400
    assert ("error", "account not found") in Page(response.text).paragraphs


def test_a_long_file_name_is_cut_to_255(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    name = "a" * 300 + ".pdf"
    upload(home, name, fake_statement_pdf())
    files = [row[1] for row in Page(home.get("/statements").text).rows[1:]]
    assert files == [name[:255]]
    assert len(files[0]) == 255


def test_an_upload_writes_no_file_under_data(
    home: TestClient, fake_statement_pdf: Callable[..., bytes], tmp_settings: Settings
) -> None:
    data_dir = Path(tmp_settings.data_dir)
    before = {path.relative_to(data_dir) for path in data_dir.rglob("*") if path.is_file()}
    upload(home, "jan.pdf", fake_statement_pdf())
    after = {path.relative_to(data_dir) for path in data_dir.rglob("*") if path.is_file()}
    assert after == before


def test_a_file_name_that_is_only_a_folder_is_refused(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    response = upload(home, "/", fake_statement_pdf())
    assert response.status_code == 400
    assert ("error", "choose a PDF statement") in Page(response.text).paragraphs


def test_upload_name_drops_folders() -> None:
    assert _upload_name("../../elsewhere/jan.pdf") == "jan.pdf"
    assert _upload_name(r"C:\Users\someone\mar.pdf") == "mar.pdf"
    assert _upload_name("a" * 300) == "a" * 255
