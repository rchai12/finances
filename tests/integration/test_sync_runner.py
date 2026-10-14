import json
from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import FeedItemRow, TransactionRow
from finances.db.repositories import create_account, latest_balance, map_feed_account
from finances.sync.runner import SYNC_DAYS, AccountSync, SyncReport, run_sync
from finances.sync.simplefin import SyncError

ACCESS = "https://user123:secret456@bridge.simplefin.org/simplefin"
TODAY = date(2026, 6, 1)


def epoch(day: date, hour: int = 12) -> int:
    from datetime import UTC, datetime

    return int(datetime(day.year, day.month, day.day, hour, tzinfo=UTC).timestamp())


def account(provider_id: str, balance: str, *transactions: dict, currency: str = "USD") -> dict:
    return {
        "id": provider_id,
        "name": f"Example {provider_id}",
        "conn_id": "CON-1",
        "currency": currency,
        "balance": balance,
        "balance-date": epoch(TODAY, 3),
        "transactions": list(transactions),
    }


def txn(feed_id: str, day: int, amount: str, text: str, pending: bool = False) -> dict:
    posted = 0 if pending else epoch(date(2026, 5, day))
    return {
        "id": feed_id,
        "posted": posted,
        "amount": amount,
        "description": text,
        "transacted_at": epoch(date(2026, 5, day), 9),
        "pending": pending,
    }


class Bridge:
    """A fake SimpleFIN Bridge that answers each GET with the next prepared account set."""

    def __init__(self, *answers: dict) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, url))
        return 200, json.dumps(self.answers.pop(0)).encode()


def answer(*accounts: dict, errors: tuple[str, ...] = ()) -> dict:
    return {
        "errlist": [{"code": "con.auth", "msg": text} for text in errors],
        "connections": [
            {"conn_id": "CON-1", "name": "Example Bank", "org_id": "O", "sfin_url": "x"}
        ],
        "accounts": list(accounts),
    }


def ledger(session: Session, account_id: int) -> list[tuple]:
    stmt = (
        select(TransactionRow, FeedItemRow.feed_id)
        .join(FeedItemRow, FeedItemRow.transaction_id == TransactionRow.id)
        .where(TransactionRow.account_id == account_id)
        .order_by(TransactionRow.id)
    )
    return [
        (feed_id, row.posted_date.day, row.amount_cents, row.is_pending)
        for row, feed_id in session.execute(stmt).all()
    ]


@pytest.fixture
def session(db_engine: Engine):
    """A card (id 1) fed by ACT-card and a checking account (id 2) fed by ACT-chk."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Example Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Example Bank", "checking", last4="2222")
        create_account(opened, "Test Unfed", "Example Bank", "savings", last4="3333")
        map_feed_account(opened, 1, "ACT-card")
        map_feed_account(opened, 2, "ACT-chk")
        yield opened


def run(session: Session, bridge: Bridge, **more) -> SyncReport:
    return run_sync(session, ACCESS, today=TODAY, transport=bridge, **more)


def test_the_window_is_thirty_days() -> None:
    assert SYNC_DAYS == 30


def test_one_request_for_the_last_thirty_days(session: Session) -> None:
    bridge = Bridge(answer())
    run(session, bridge)
    assert bridge.calls == [
        (
            "GET",
            "https://bridge.simplefin.org/simplefin/accounts"
            f"?start-date={epoch(date(2026, 5, 2), 0)}"
            f"&end-date={epoch(date(2026, 6, 2), 0)}&pending=1",
        )
    ]
    bridge = Bridge(answer())
    run(session, bridge, days=7)
    assert f"start-date={epoch(date(2026, 5, 25), 0)}&" in bridge.calls[0][1]


def test_each_mapped_account_is_applied(session: Session) -> None:
    bridge = Bridge(
        answer(
            account(
                "ACT-card",
                "-29.49",
                txn("C-1", 20, "-4.50", "ACME COFFEE"),
                txn("C-2", 25, "-24.99", "FOOBAR"),
            ),
            account("ACT-chk", "1500.00", txn("K-1", 28, "1500.00", "PAYROLL")),
        )
    )
    report = run(session, bridge)
    assert report.messages == []
    assert [
        (item.provider_account_id, item.account_id, item.problem) for item in report.accounts
    ] == [
        ("ACT-card", 1, None),
        ("ACT-chk", 2, None),
    ]
    card, checking = report.accounts[0].pull, report.accounts[1].pull
    assert (card.inserted, card.feed_total_cents, card.balance_cents, card.balance_date) == (
        2,
        -2949,
        -2949,
        TODAY,
    )
    assert (checking.inserted, checking.balance_cents) == (1, 150000)
    assert ledger(session, 1) == [("C-1", 20, -450, False), ("C-2", 25, -2499, False)]
    assert ledger(session, 2) == [("K-1", 28, 150000, False)]
    assert latest_balance(session, 1).balance_cents == -2949


def test_unmapped_missing_and_foreign_accounts_are_reported_not_applied(session: Session) -> None:
    map_feed_account(session, 3, "ACT-gone")
    bridge = Bridge(
        answer(
            account("ACT-new", "1.00", txn("N-1", 20, "1.00", "X")),
            account("ACT-card", "-1.00", txn("C-1", 20, "-1.00", "ACME"), currency="EUR"),
            account("ACT-chk", "0.00"),
        )
    )
    report = run(session, bridge)
    assert report.accounts == [
        AccountSync("ACT-new", None, None, "not mapped"),
        AccountSync("ACT-card", 1, None, "currency is not USD"),
        AccountSync("ACT-chk", 2, report.accounts[2].pull, None),
        AccountSync("ACT-gone", 3, None, "not in the aggregator's answer"),
    ]
    assert report.accounts[2].pull.inserted == 0
    assert session.scalars(select(TransactionRow)).all() == []


def test_a_hold_that_is_no_longer_delivered_is_removed(session: Session) -> None:
    first = answer(
        account(
            "ACT-card",
            "-4.50",
            txn("C-1", 20, "-4.50", "ACME COFFEE"),
            txn("H-1", 30, "-80.00", "HOTEL HOLD", pending=True),
            txn("H-2", 31, "-5.00", "GAS HOLD", pending=True),
        )
    )
    second = answer(
        account(
            "ACT-card",
            "-87.25",
            txn("C-1", 20, "-4.50", "ACME COFFEE"),
            txn("C-3", 31, "-82.75", "HOTEL"),
            txn("H-2", 31, "-5.00", "GAS HOLD", pending=True),
        )
    )
    bridge = Bridge(first, second)
    run(session, bridge)
    assert ledger(session, 1) == [
        ("C-1", 20, -450, False),
        ("H-1", 30, -8000, True),
        ("H-2", 31, -500, True),
    ]
    pull = run(session, bridge).accounts[0].pull
    assert (pull.inserted, pull.removed, pull.unchanged, pull.drift_cents) == (1, 1, 2, 0)
    assert ledger(session, 1) == [
        ("C-1", 20, -450, False),
        ("H-2", 31, -500, True),
        ("C-3", 31, -8275, False),
    ]


def test_holds_are_kept_when_the_answer_carries_a_message(session: Session) -> None:
    first = answer(account("ACT-card", "0.00", txn("H-1", 30, "-80.00", "HOLD", pending=True)))
    second = answer(account("ACT-card", "0.00"), errors=("Example Bank: incomplete listing",))
    bridge = Bridge(first, second)
    run(session, bridge)
    report = run(session, bridge)
    assert report.messages == ["Example Bank: incomplete listing"]
    assert report.accounts[0].pull.removed == 0
    assert ledger(session, 1) == [("H-1", 30, -8000, True)]


def test_holds_older_than_the_window_are_not_removed(session: Session) -> None:
    bridge = Bridge(
        answer(account("ACT-card", "0.00", txn("H-old", 1, "-1.00", "OLD HOLD", pending=True))),
        answer(account("ACT-card", "0.00")),
    )
    run(session, bridge, days=40)
    pull = run(session, bridge).accounts[0].pull
    assert pull.removed == 0
    assert ledger(session, 1) == [("H-old", 1, -100, True)]


def test_holds_of_another_account_are_not_removed(session: Session) -> None:
    bridge = Bridge(
        answer(account("ACT-chk", "0.00", txn("H-1", 30, "-1.00", "HOLD", pending=True))),
        answer(
            account("ACT-card", "0.00"),
            account("ACT-chk", "0.00", txn("H-1", 30, "-1.00", "HOLD", pending=True)),
        ),
    )
    run(session, bridge)
    report = run(session, bridge)
    assert [item.pull.removed for item in report.accounts] == [0, 0]
    assert ledger(session, 2) == [("H-1", 30, -100, True)]


def test_a_feed_one_account_cannot_take_does_not_stop_the_others(session: Session) -> None:
    bridge = Bridge(
        answer(
            account("ACT-card", "-1.00", txn("X" * 101, 20, "-1.00", "ACME")),
            account("ACT-chk", "5.00", txn("K-1", 20, "5.00", "DEPOSIT")),
        )
    )
    report = run(session, bridge)
    assert report.accounts[0] == AccountSync(
        "ACT-card", 1, None, "feed has an unusable transaction id"
    )
    assert report.accounts[1].pull.inserted == 1
    assert ledger(session, 1) == []
    assert latest_balance(session, 1) is None


def test_a_failed_fetch_raises_and_writes_nothing(session: Session) -> None:
    def refused(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        return 403, b""

    with pytest.raises(SyncError) as caught:
        run_sync(session, ACCESS, today=TODAY, transport=refused)
    assert str(caught.value) == "aggregator access was revoked or is wrong"
    assert session.scalars(select(TransactionRow)).all() == []


def test_with_no_mapping_nothing_is_applied(db_engine: Engine) -> None:
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Example Bank", "credit_card", last4="1111")
        report = run_sync(
            opened,
            ACCESS,
            today=TODAY,
            transport=Bridge(answer(account("ACT-card", "1.00", txn("C-1", 20, "1.00", "X")))),
        )
        assert report == SyncReport([AccountSync("ACT-card", None, None, "not mapped")], [])
        assert opened.scalars(select(TransactionRow)).all() == []


def test_posted_rows_that_are_not_delivered_again_are_kept(session: Session) -> None:
    bridge = Bridge(
        answer(account("ACT-card", "-4.50", txn("C-1", 20, "-4.50", "ACME COFFEE"))),
        answer(account("ACT-card", "-4.50")),
    )
    run(session, bridge)
    pull = run(session, bridge).accounts[0].pull
    assert (pull.removed, pull.unchanged) == (0, 0)
    assert ledger(session, 1) == [("C-1", 20, -450, False)]
