from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from finances.analysis.insights import insights_report
from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, set_category_by_hand
from finances.domain.insights import MerchantStat, frequent_small, merchant_stats, spikes
from finances.domain.spending import SPENDING, Flow, month_bounds

MAY = date(2026, 5, 1)
CARD = 1


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Example Card Co", "credit_card")
        yield opened


def add(session: Session, day: date, cents: int, description: str) -> int:
    row = TransactionRow(
        account_id=CARD,
        posted_date=day,
        amount_cents=cents,
        description=description,
        source="statement",
        fingerprint=f"i{day}-{cents}-{description}"[:64].ljust(64, "0"),
    )
    session.add(row)
    session.flush()
    return row.id


def flow(merchant: str, day: date, cents: int, category: str = "Dining") -> Flow:
    return Flow(
        amount_cents=cents,
        day=day,
        kind=SPENDING,
        category=category,
        group="Food",
        merchant=merchant,
        person="Unassigned",
        account="Test Card",
        bank="Test Bank",
        card="No card",
    )


def test_the_baseline_is_the_three_months_before(session: Session) -> None:
    add(session, date(2026, 5, 11), -1000, "BAZ BOOKS")
    add(session, date(2026, 2, 1), -3000, "BAZ BOOKS")
    add(session, date(2026, 1, 31), -9000, "BAZ BOOKS")
    add(session, date(2026, 6, 1), -9000, "BAZ BOOKS")
    report = insights_report(session, MAY)
    assert report.month == MAY
    assert report.merchants == [MerchantStat("BAZ BOOKS", 1, 1000, 1000, 1000, 0, 0)]


def test_a_month_given_by_any_day_starts_on_its_first(session: Session) -> None:
    add(session, date(2026, 5, 10), -1000, "BAZ BOOKS")
    assert insights_report(session, date(2026, 5, 31)).month == MAY


@pytest.mark.parametrize(
    ("latest", "overlap"), [("Subscriptions & Digital", True), ("Fitness", False)]
)
def test_a_merchant_takes_the_category_of_its_latest_charge(
    session: Session, latest: str, overlap: bool
) -> None:
    for day in (date(2026, 3, 5), date(2026, 4, 5), date(2026, 5, 5)):
        item = add(session, day, -1599, "QUUX STREAMING")
        set_category_by_hand(session, item, "Subscriptions & Digital")
    for day, category in (
        (date(2026, 3, 12), "Fitness"),
        (date(2026, 4, 12), "Fitness"),
        (date(2026, 5, 12), latest),
    ):
        set_category_by_hand(session, add(session, day, -999, "BAZ VIDEO"), category)
    found = [finding.type for finding in insights_report(session, MAY).findings]
    assert ("subscription_overlap" in found) is overlap


def test_a_merchant_with_only_a_refund_this_month() -> None:
    stats = merchant_stats([flow("BAZ BOOKS", date(2026, 5, 9), 500)], [])
    assert stats == [MerchantStat("BAZ BOOKS", 0, -500, 0, 0, -500, 0)]


@pytest.mark.parametrize(
    ("earlier", "spent", "found"),
    [
        (60000, 30000, True),  # the excess is exactly half the baseline
        (60000, 29999, False),  # just below half
        (18000, 11000, True),  # the excess is exactly $50
        (18000, 10999, False),  # just below $50
    ],
)
def test_the_spike_thresholds(earlier: int, spent: int, found: bool) -> None:
    month = [flow("ACME DINER", date(2026, 5, 9), -spent)]
    before = [flow("ACME DINER", date(2026, 3, 9), -earlier)]
    assert [finding.subject for finding in spikes(MAY, month, before)] == (
        ["Dining"] if found else []
    )


def test_frequent_small_ignores_refunds() -> None:
    visits = [flow("ACME COFFEE", date(2026, 5, day), -1500) for day in range(1, 9)]
    refund = flow("ACME COFFEE", date(2026, 5, 20), 4000)
    (finding,) = frequent_small(MAY, [*visits, refund])
    assert (finding.savings_cents, finding.detail) == (
        6000,
        "ACME COFFEE: 8 visits averaging $15.00.",
    )
    assert frequent_small(MAY, [*visits[:7], refund]) == []


@pytest.mark.parametrize(
    ("command", "heading"), [("insights", "Insights"), ("merchants", "Merchants")]
)
def test_no_month_means_this_month(tmp_settings: Settings, command: str, heading: str) -> None:
    runner = CliRunner(env={"COLUMNS": "200"})
    assert runner.invoke(app, ["db", "upgrade"]).exit_code == 0
    this_month = month_bounds(date.today())[0].isoformat()[:7]
    result = runner.invoke(app, [command])
    assert result.exit_code == 0
    assert result.stdout.splitlines()[0] == f"{heading} for {this_month}."
