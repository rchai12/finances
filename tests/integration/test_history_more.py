from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import create_account, list_changes
from finances.web.app import create_app
from tests.support import WEB_PORT, page, post, run

MISSING = "finances-20990101-000000.db"


def trail() -> list[tuple]:
    engine = get_engine()
    with session_scope(engine) as session:
        found = [
            (item.who, item.action, item.kind, item.record_id, item.before, item.after)
            for item in reversed(list_changes(session, limit=1000))
        ]
    engine.dispose()
    return found


def test_a_real_statement_import_through_fin_import_records_one_statement_imported(
    tmp_settings: Settings,
    fake_bank: object,
    fake_statement_pdf: Callable[..., bytes],
    tmp_path: Path,
) -> None:
    assert run("db", "upgrade").exit_code == 0
    assert (
        run(
            "accounts",
            "add",
            "--name",
            "Test Card",
            "--institution",
            "Fake Bank",
            "--type",
            "credit_card",
            "--last4",
            "1111",
        ).exit_code
        == 0
    )
    path = tmp_path / "january.pdf"
    path.write_bytes(fake_statement_pdf())
    assert run("import", "statement", path).exit_code == 0
    found = [item for item in trail() if item[1] == "statement_imported"]
    assert found == [
        (
            "system",
            "statement_imported",
            "statement",
            1,
            None,
            "fake_bank, 2026-01-01 to 2026-01-31",
        )
    ]


def test_a_refused_delete_of_an_unknown_name_records_nothing(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/backups")
    before = trail()
    response = post(client, "/backups/delete", name=MISSING)
    assert response.status_code == 400
    assert trail() == before


def test_history_with_an_empty_action_and_since_only(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    found = page(client, "/history?action=&since=2099-01-01")
    assert found.rows == []
    form = found.find("/history")
    assert form["inputs"]["since"] == ("date", "2099-01-01")
    assert ("", True) in form["selects"]["action"]


def test_the_history_menu_link_is_current_only_on_its_page(tmp_settings: Settings) -> None:
    upgrade_to_head()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    history = client.get("/history")
    backups = client.get("/backups")
    assert 'href="/history" aria-current="page">History</a>' in history.text
    assert 'href="/history">History</a>' in backups.text
    assert 'aria-current="page">History</a>' not in backups.text
