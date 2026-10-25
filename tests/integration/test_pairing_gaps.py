from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    find_transfer_pair,
    record_seen_feed_account,
    set_account_owner,
    set_split,
    share_transaction,
)
from finances.sync.links import save_access_url
from finances.sync.simplefin import ProviderAnswer
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, run

ACCESS = "https://user:secret@bridge.example/simplefin"


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    """Sam owns a checking and a savings account; $500.00 leaves checking (1) and reaches
    savings (2) on the same day, a clear transfer that nothing has paired yet."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        sam = create_person(session, "Sam")
        create_person(session, "Alex")
        for number, (name, kind, cents) in enumerate(
            (("Test Checking", "checking", -50000), ("Test Savings", "savings", 50000)), start=1
        ):
            account = create_account(session, name, "Test Bank", kind)
            set_account_owner(session, account.id, sam.id)
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, 10),
                    amount_cents=cents,
                    description="ONLINE TRANSFER",
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
    engine.dispose()
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    found.get("/sync")
    return found


def paired() -> bool:
    engine = get_engine()
    with session_scope(engine) as session:
        found = find_transfer_pair(session, 1)
    engine.dispose()
    return found is not None


def prepare(change) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        change(session)
    engine.dispose()


def test_clearing_a_split_on_the_web_pairs_the_transfer(client: TestClient) -> None:
    prepare(lambda session: set_split(session, 1, [(-30000, "Groceries"), (-20000, "Dining")]))
    response = post(client, "/transactions/1/split/clear")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/1?notice=split-removed",
    )
    assert paired()


def test_unsharing_on_the_web_pairs_the_transfer(client: TestClient) -> None:
    prepare(lambda session: share_transaction(session, 1, "Alex"))
    response = post(client, "/transactions/1/share/clear")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/1?notice=share-removed",
    )
    assert paired()


def test_unsharing_in_the_terminal_pairs_the_transfer(client: TestClient) -> None:
    prepare(lambda session: share_transaction(session, 1, "Alex"))
    result = run("shared", "remove", "--id", 1)
    assert (result.exit_code, result.output) == (0, "Transaction 1: no longer shared.\n")
    assert paired()


def test_unlink_is_offered_for_the_links_the_database_knows(client: TestClient) -> None:
    save_access_url("alex", ACCESS)
    prepare(
        lambda session: record_seen_feed_account(
            session, "bea", "ACT-0001", "EXAMPLE CHECKING", "EXAMPLE BANK", date(2026, 5, 10)
        )
    )
    found = page(client, "/sync")
    assert [form["inputs"]["link"] for form in found.all("/sync/unlink")] == [("hidden", "bea")]


def unlinks(found: Page) -> list[tuple[str, tuple[str, str]]]:
    return [(form["method"], form["inputs"]["link"]) for form in found.all("/sync/unlink")]


def test_the_accounts_page_offers_unlink_right_after_linking(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_access_url("alex", ACCESS)
    monkeypatch.setattr(
        "finances.web.routes.sync.fetch_accounts",
        lambda *args: ProviderAnswer(accounts=[], messages=[]),
    )
    assert unlinks(page(client, "/sync/accounts?link=alex")) == [("get", ("hidden", "alex"))]


def test_the_accounts_page_offers_unlink_when_simplefin_refuses(client: TestClient) -> None:
    save_access_url("alex", "not an access url")
    response = client.get("/sync/accounts?link=alex")
    assert response.status_code == 502
    assert unlinks(Page(response.text)) == [("get", ("hidden", "alex"))]


def test_no_unlink_for_a_link_that_is_not_set_up(client: TestClient) -> None:
    response = client.get("/sync/accounts?link=bea")
    assert response.status_code == 400
    assert unlinks(Page(response.text)) == []
