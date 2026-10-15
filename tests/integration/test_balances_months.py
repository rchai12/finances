from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from finances.analysis.balances import BalanceLine, balance_report
from finances.analysis.months import month_report
from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import session_scope
from finances.db.orm import AccountRow, FeedPullRow, TransactionRow
from finances.db.repositories import (
    account_data_span,
    add_balance_snapshot,
    create_account,
    create_statement,
)
from finances.domain.models import DataSource
from finances.domain.spending import month_bounds

CHECKING, CARD = 1, 2


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """Test Checking (1) and Test Card (2), both active and empty."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Checking", "Test Bank", "checking")
        create_account(opened, "Test Card", "Example Card Co", "credit_card")
        yield opened


def statement(session: Session, account: int, number: int, start: date, end: date) -> None:
    create_statement(
        session,
        account_id=account,
        source_filename=f"statement-{number}.pdf",
        file_sha256=f"s{number:02d}".ljust(64, "0"),
        parser_name="test",
        period_start=start,
        period_end=end,
        opening_balance_cents=0,
        closing_balance_cents=0,
        lines_parsed=0,
        rows_inserted=0,
        rows_duplicate=0,
    )


def add(
    session: Session,
    account: int,
    posted: date,
    *,
    bought: date | None = None,
    pending: bool = False,
    cents: int = -100,
) -> None:
    session.add(
        TransactionRow(
            account_id=account,
            posted_date=posted,
            transaction_date=bought,
            amount_cents=cents,
            description="ACME COFFEE",
            is_pending=pending,
            source="statement",
            fingerprint=f"p{account}-{posted}-{bought}-{pending}".ljust(64, "0"),
        )
    )
    session.flush()


def pull(session: Session, account: int, at: datetime) -> None:
    session.add(
        FeedPullRow(
            account_id=account,
            inserted=0,
            updated=0,
            removed=0,
            unchanged=0,
            feed_total_cents=0,
            balance_cents=None,
            balance_date=None,
            drift_cents=None,
            pulled_at=at,
        )
    )
    session.flush()


def deactivate(session: Session, account: int) -> None:
    row = session.get(AccountRow, account)
    assert row is not None
    row.is_active = False
    session.flush()


def test_no_data_has_no_span(session: Session) -> None:
    assert account_data_span(session, CHECKING) is None


def test_statements_alone_give_the_span(session: Session) -> None:
    statement(session, CHECKING, 1, date(2026, 4, 1), date(2026, 4, 30))
    statement(session, CHECKING, 2, date(2026, 3, 1), date(2026, 3, 31))
    statement(session, CARD, 3, date(2026, 1, 1), date(2026, 6, 30))
    assert account_data_span(session, CHECKING) == (date(2026, 3, 1), date(2026, 4, 30))


def test_a_day_bought_before_the_statement_widens_the_span(session: Session) -> None:
    statement(session, CARD, 1, date(2026, 3, 5), date(2026, 4, 4))
    add(session, CARD, date(2026, 3, 6), bought=date(2026, 3, 2))
    assert account_data_span(session, CARD) == (date(2026, 3, 2), date(2026, 4, 4))


def test_a_pending_transaction_is_left_out_of_the_span(session: Session) -> None:
    add(session, CHECKING, date(2026, 3, 10))
    add(session, CHECKING, date(2026, 3, 20), pending=True)
    add(session, CHECKING, date(2026, 2, 20), pending=True)
    assert account_data_span(session, CHECKING) == (date(2026, 3, 10), date(2026, 3, 10))


def test_a_feed_pull_after_every_transaction_ends_the_span(session: Session) -> None:
    add(session, CARD, date(2026, 5, 3))
    pull(session, CARD, datetime(2026, 5, 20, 23, 30, tzinfo=UTC))
    pull(session, CARD, datetime(2026, 5, 10, 8, 0, tzinfo=UTC))
    assert account_data_span(session, CARD) == (date(2026, 5, 3), date(2026, 5, 20))


def test_feed_pulls_alone_give_the_span(session: Session) -> None:
    pull(session, CARD, datetime(2026, 5, 10, 8, 0, tzinfo=UTC))
    assert account_data_span(session, CARD) == (date(2026, 5, 10), date(2026, 5, 10))


def test_an_inactive_account_is_left_out_of_balances(session: Session) -> None:
    add_balance_snapshot(session, CHECKING, date(2026, 4, 30), 50000, DataSource.STATEMENT)
    add_balance_snapshot(session, CARD, date(2026, 4, 30), -20000, DataSource.STATEMENT)
    deactivate(session, CARD)
    report = balance_report(session)
    assert [line.account for line in report.lines] == ["Test Checking"]
    assert (report.cash_cents, report.cards_cents, report.net_worth_cents) == (50000, 0, 50000)


def test_the_newest_of_two_snapshots_is_the_balance(session: Session) -> None:
    add_balance_snapshot(session, CARD, date(2026, 5, 20), -61234, DataSource.AGGREGATOR)
    add_balance_snapshot(session, CARD, date(2026, 4, 4), -45000, DataSource.STATEMENT)
    report = balance_report(session)
    assert report.lines == [
        BalanceLine("Test Card", "credit_card", -61234, date(2026, 5, 20), "aggregator"),
        BalanceLine("Test Checking", "checking", None, None, None),
    ]
    assert (report.cards_cents, report.net_worth_cents) == (-61234, -61234)
    assert report.without_balance == ["Test Checking"]


def test_an_inactive_account_is_never_uncovered(session: Session) -> None:
    statement(session, CHECKING, 1, date(2026, 3, 1), date(2026, 4, 30))
    deactivate(session, CARD)
    lines = month_report(session, date(2026, 4, 15), 2)
    assert [(line.start, line.uncovered) for line in lines] == [
        (date(2026, 3, 1), []),
        (date(2026, 4, 1), []),
    ]


def test_an_account_with_no_data_is_uncovered_every_month(session: Session) -> None:
    statement(session, CHECKING, 1, date(2026, 3, 1), date(2026, 4, 30))
    lines = month_report(session, date(2026, 4, 15), 2)
    assert [line.uncovered for line in lines] == [["Test Card"], ["Test Card"]]


def test_a_month_report_takes_spent_and_income_from_the_flows(session: Session) -> None:
    add(session, CARD, date(2026, 4, 3), cents=-2500)
    add(session, CHECKING, date(2026, 4, 9), cents=4000)
    (line,) = month_report(session, date(2026, 4, 1), 1)
    assert (line.spent_cents, line.income_cents) == (2500, 0)


def test_a_bad_count_is_refused_before_reading(session: Session) -> None:
    with pytest.raises(ValueError) as caught:
        month_report(session, date(2026, 4, 1), 25)
    assert str(caught.value) == "count must be from 1 to 24"


def test_fin_months_without_to_ends_at_this_month(tmp_settings: Settings) -> None:
    runner = CliRunner(env={"COLUMNS": "200"})
    assert runner.invoke(app, ["db", "upgrade"]).exit_code == 0
    this_month = month_bounds(date.today())[0].isoformat()[:7]
    result = runner.invoke(app, ["months", "--count", "1"])
    assert result.exit_code == 0
    assert result.stdout.splitlines()[0] == f"Months from {this_month} to {this_month}."
