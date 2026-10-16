from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.health import account_facts, gather_health
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import FeedPullRow
from finances.db.repositories import (
    create_account,
    create_statement,
    map_feed_account,
    set_account_active,
)
from finances.domain.health import AccountFacts, health_problems
from finances.domain.models import DEFAULT_LINK
from tests.support import run

AS_OF = date(2026, 5, 20)


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        yield opened


def pull(
    session: Session,
    account_id: int,
    *,
    when: datetime,
    balance_cents: int | None = None,
    balance_date: date | None = None,
    drift_cents: int | None = None,
) -> None:
    session.add(
        FeedPullRow(
            account_id=account_id,
            inserted=0,
            updated=0,
            removed=0,
            unchanged=0,
            feed_total_cents=0,
            balance_cents=balance_cents,
            balance_date=balance_date,
            drift_cents=drift_cents,
            pulled_at=when,
        )
    )
    session.flush()


def test_account_facts_mapped_under_another_link_and_utc_pull(session: Session) -> None:
    card = create_account(session, "Test Card", "Test Bank", "credit_card")
    map_feed_account(session, card.id, "ACT-2", link="person-b")
    pull(
        session,
        card.id,
        when=datetime(2026, 5, 10, 23, 45, tzinfo=UTC),
        balance_cents=-100,
        balance_date=date(2026, 5, 10),
        drift_cents=0,
    )
    found = account_facts(session)
    assert len(found) == 1
    assert found[0].mapped is True
    assert found[0].last_pull == date(2026, 5, 10)


def test_account_facts_takes_drift_from_the_newest_pull_with_a_balance(session: Session) -> None:
    card = create_account(session, "Test Card", "Test Bank", "credit_card")
    map_feed_account(session, card.id, "ACT-1", link=DEFAULT_LINK)
    pull(
        session,
        card.id,
        when=datetime(2026, 5, 9, 12, 0, tzinfo=UTC),
        balance_cents=-50000,
        balance_date=date(2026, 5, 9),
        drift_cents=-1234,
    )
    pull(session, card.id, when=datetime(2026, 5, 10, 12, 0, tzinfo=UTC))
    found = account_facts(session)[0]
    assert found.last_pull == date(2026, 5, 10)
    assert (found.drift_cents, found.drift_date) == (-1234, date(2026, 5, 9))


def test_account_facts_leaves_out_a_closed_account(session: Session) -> None:
    open_card = create_account(session, "Open Card", "Test Bank", "credit_card")
    closed = create_account(session, "Closed Card", "Test Bank", "credit_card")
    set_account_active(session, closed.id, False)
    create_statement(
        session,
        account_id=closed.id,
        source_filename="old.pdf",
        file_sha256="c" * 64,
        parser_name="test",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        opening_balance_cents=0,
        closing_balance_cents=0,
        lines_parsed=0,
        rows_inserted=0,
        rows_duplicate=0,
    )
    names = [item.name for item in account_facts(session)]
    assert names == [open_card.name]
    assert "Closed Card" not in names


def test_gather_health_ignores_files_that_are_not_backups(
    session: Session, tmp_settings: Settings
) -> None:
    folder = tmp_settings.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / "notes.txt").write_text("not a backup")
    (folder / "finances-20260519-020000-before-restore.db").write_bytes(b"")
    (folder / "finances-20260518-020000.db").write_bytes(b"")
    problems = gather_health(session, folder, date(2026, 5, 20))
    assert not any(problem.kind == "backup" for problem in problems)


def test_a_mapped_account_has_no_statements_problem() -> None:
    account = AccountFacts(
        name="Test Card",
        mapped=True,
        last_pull=AS_OF,
        drift_cents=None,
        drift_date=None,
        newest_statement_end=date(2026, 1, 1),
        has_data=True,
        gaps=(),
    )
    assert health_problems([account], AS_OF, AS_OF) == []


def test_fin_health_without_as_of_uses_today(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    today = date.today()
    folder = tmp_settings.effective_backup_dir
    folder.mkdir(parents=True)
    stamp = today.strftime("%Y%m%d")
    (folder / f"finances-{stamp}-120000.db").write_bytes(b"")
    engine = get_engine()
    with session_scope(engine) as session:
        account = create_account(session, "Test Checking", "Test Bank", "checking")
        end = today - timedelta(days=46)
        create_statement(
            session,
            account_id=account.id,
            source_filename="old.pdf",
            file_sha256="a" * 64,
            parser_name="test",
            period_start=end - timedelta(days=30),
            period_end=end,
            opening_balance_cents=0,
            closing_balance_cents=0,
            lines_parsed=0,
            rows_inserted=0,
            rows_duplicate=0,
        )
    engine.dispose()
    result = run("health")
    assert result.exit_code == 0
    assert f"The newest statement ends {end.isoformat()} (46 days ago)." in result.stdout
