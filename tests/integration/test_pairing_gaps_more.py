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
    map_feed_account,
    record_seen_feed_account,
    set_account_owner,
    set_split,
)
from finances.web.app import create_app
from tests.integration.test_pairing_gaps import paired, prepare, unlinks
from tests.support import WEB_PORT, Page, failed_cleanly, page, post, run


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
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


def test_clearing_a_split_with_no_partner_pairs_nothing(client: TestClient) -> None:
    def grocery(session) -> None:
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 11),
                amount_cents=-1234,
                description="ACME COFFEE",
                source="statement",
                fingerprint="t03".ljust(64, "0"),
            )
        )
        session.flush()
        set_split(session, 3, [(-600, "Groceries"), (-634, "Dining")])

    prepare(grocery)
    response = post(client, "/transactions/3/split/clear")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/3?notice=split-removed",
    )
    engine = get_engine()
    with session_scope(engine) as session:
        found = find_transfer_pair(session, 3)
    engine.dispose()
    assert found is None


def test_removing_a_missing_share_stores_no_pair(client: TestClient) -> None:
    assert failed_cleanly(run("shared", "remove", "--id", 99), "transaction not found")
    assert not paired()


def test_mapped_and_seen_links_both_get_unlink_in_sorted_order(client: TestClient) -> None:
    def add(session) -> None:
        map_feed_account(session, 1, "ACT-0001", "alex")
        record_seen_feed_account(
            session, "bea", "ACT-0001", "EXAMPLE CHECKING", "EXAMPLE BANK", date(2026, 5, 10)
        )

    prepare(add)
    found = page(client, "/sync")
    assert [form["inputs"]["link"] for form in found.all("/sync/unlink")] == [
        ("hidden", "alex"),
        ("hidden", "bea"),
    ]


def test_the_simplefin_page_has_no_unlink_form_with_no_links(client: TestClient) -> None:
    assert page(client, "/sync").all("/sync/unlink") == []


def test_no_unlink_for_a_refused_link_name(client: TestClient) -> None:
    response = client.get("/sync/accounts?link=Bad")
    assert response.status_code == 400
    assert unlinks(Page(response.text)) == []
