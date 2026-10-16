from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.dashboard import dashboard
from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import FeedPullRow, TransactionRow
from finances.db.repositories import (
    count_uncategorized,
    create_account,
    create_rule,
    create_statement,
    create_transfer_pair,
    list_uncategorized,
    map_feed_account,
    set_category_by_hand,
)
from finances.domain.models import CONFIRMED
from finances.web.app import create_app
from tests.support import WEB_PORT, page


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        yield opened


def add_tx(
    session: Session,
    account_id: int,
    day: date,
    cents: int,
    description: str,
    *,
    pending: bool = False,
) -> int:
    row = TransactionRow(
        account_id=account_id,
        posted_date=day,
        amount_cents=cents,
        description=description,
        source="statement",
        fingerprint=f"{account_id}-{day}-{description}-{cents}".ljust(64, "0")[:64],
        is_pending=pending,
    )
    session.add(row)
    session.flush()
    return row.id


def test_count_uncategorized_matches_the_list(session: Session) -> None:
    card = create_account(session, "Test Card", "Test Bank", "credit_card")
    checking = create_account(session, "Test Checking", "Test Bank", "checking")
    create_rule(session, "ACME", "Dining")
    out_id = add_tx(session, checking.id, date(2026, 5, 1), -5000, "PAYMENT TO CARD")
    in_id = add_tx(session, card.id, date(2026, 5, 2), 5000, "PAYMENT THANK YOU")
    create_transfer_pair(session, out_id, in_id, CONFIRMED)
    categorized = add_tx(session, card.id, date(2026, 5, 3), -400, "ACME COFFEE")
    categorize(session)
    assert set_category_by_hand(session, categorized, "Dining").name == "Dining"
    add_tx(session, card.id, date(2026, 5, 4), -100, "PENDING HOLD", pending=True)
    add_tx(session, card.id, date(2026, 5, 5), -200, "FOOBAR GROCERY")
    assert count_uncategorized(session) == len(list_uncategorized(session, 1000))
    assert count_uncategorized(session) == 2


def test_dashboard_on_the_first_day_of_january(session: Session, tmp_path) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    found = dashboard(session, date(2026, 1, 1), tmp_path)
    assert [line.start for line in found.months] == [date(2025, 12, 1), date(2026, 1, 1)]


def test_sync_statements_and_gap_problems_link_to_their_pages(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 5, 25))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        map_feed_account(session, card.id, "ACT-1")
        session.add(
            FeedPullRow(
                account_id=card.id,
                inserted=0,
                updated=0,
                removed=0,
                unchanged=0,
                feed_total_cents=0,
                balance_cents=-100,
                balance_date=date(2026, 5, 1),
                drift_cents=0,
                pulled_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            )
        )
        create_statement(
            session,
            account_id=checking.id,
            source_filename="jan.pdf",
            file_sha256="a" * 64,
            parser_name="test",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            opening_balance_cents=0,
            closing_balance_cents=0,
            lines_parsed=0,
            rows_inserted=0,
            rows_duplicate=0,
        )
        create_statement(
            session,
            account_id=checking.id,
            source_filename="mar.pdf",
            file_sha256="b" * 64,
            parser_name="test",
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            opening_balance_cents=0,
            closing_balance_cents=0,
            lines_parsed=0,
            rows_inserted=0,
            rows_duplicate=0,
        )
    engine.dispose()
    folder = tmp_settings.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / "finances-20260525-020000.db").write_bytes(b"")
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    found = page(client, "/")
    kinds = {row[0] for row in found.rows if row and row[0] in {"sync", "statements", "gap"}}
    assert kinds == {"sync", "statements", "gap"}
    links = found.links
    assert "/sync" in links
    assert "/statements" in links
