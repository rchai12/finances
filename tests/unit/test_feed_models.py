import dataclasses
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from finances.db.orm import FeedItemRow, FeedPullRow, StatementRow, to_feed_pull
from finances.domain.models import FeedPull
from finances.sync.feed import AccountFeed, FeedError, FeedTransaction

PULL_FIELDS = [
    ("id", int),
    ("account_id", int),
    ("inserted", int),
    ("updated", int),
    ("removed", int),
    ("unchanged", int),
    ("feed_total_cents", int),
    ("balance_cents", int | None),
    ("balance_date", date | None),
    ("drift_cents", int | None),
    ("pulled_at", datetime),
]


def names_and_types(cls: type) -> list[tuple[str, object]]:
    return [(item.name, item.type) for item in dataclasses.fields(cls)]


def test_feed_pull_fields_in_order_with_no_defaults() -> None:
    assert names_and_types(FeedPull) == PULL_FIELDS
    assert all(item.default is dataclasses.MISSING for item in dataclasses.fields(FeedPull))
    assert all(item.default_factory is dataclasses.MISSING for item in dataclasses.fields(FeedPull))


def test_feed_transaction_fields_and_defaults() -> None:
    assert names_and_types(FeedTransaction) == [
        ("feed_id", str),
        ("posted_date", date),
        ("amount_cents", int),
        ("description", str),
        ("is_pending", bool),
        ("transaction_date", date | None),
        ("card_last4", str | None),
        ("replaces_feed_id", str | None),
    ]
    item = FeedTransaction("t-1", date(2026, 5, 1), -450, "ACME COFFEE")
    assert (item.is_pending, item.transaction_date, item.card_last4, item.replaces_feed_id) == (
        False,
        None,
        None,
        None,
    )


def test_account_feed_fields_and_defaults() -> None:
    assert names_and_types(AccountFeed) == [
        ("transactions", list[FeedTransaction]),
        ("removed_feed_ids", list[str]),
        ("balance_cents", int | None),
        ("balance_date", date | None),
    ]
    feed = AccountFeed()
    assert (feed.transactions, feed.removed_feed_ids, feed.balance_cents, feed.balance_date) == (
        [],
        [],
        None,
        None,
    )


def test_two_empty_feeds_do_not_share_lists() -> None:
    first, second = AccountFeed(), AccountFeed()
    first.transactions.append(FeedTransaction("t-1", date(2026, 5, 1), -1, "ACME"))
    first.removed_feed_ids.append("t-2")
    assert (second.transactions, second.removed_feed_ids) == ([], [])


@pytest.mark.parametrize(
    ("value", "name"),
    [
        (FeedTransaction("t-1", date(2026, 5, 1), -1, "ACME"), "amount_cents"),
        (AccountFeed(), "balance_cents"),
        (FeedPull(1, 1, 0, 0, 0, 0, 0, None, None, None, datetime(2026, 5, 1, tzinfo=UTC)), "id"),
    ],
)
def test_the_feed_types_are_frozen(value: object, name: str) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(value, name, 5)


def test_feed_error_is_an_exception() -> None:
    assert issubclass(FeedError, Exception)
    assert str(FeedError("account not found")) == "account not found"


def pull_row(pulled_at: datetime) -> FeedPullRow:
    return FeedPullRow(
        id=3,
        account_id=2,
        inserted=4,
        updated=5,
        removed=6,
        unchanged=7,
        feed_total_cents=-(2**40),
        balance_cents=-1234,
        balance_date=date(2026, 5, 31),
        drift_cents=17,
        pulled_at=pulled_at,
    )


def test_to_feed_pull_with_a_naive_time_reads_it_as_utc() -> None:
    pull = to_feed_pull(pull_row(datetime(2026, 5, 31, 12, 30)))
    assert pull == FeedPull(
        3,
        2,
        4,
        5,
        6,
        7,
        -(2**40),
        -1234,
        date(2026, 5, 31),
        17,
        datetime(2026, 5, 31, 12, 30, tzinfo=UTC),
    )
    assert pull.pulled_at.tzinfo is UTC


def test_to_feed_pull_keeps_a_time_that_has_a_zone() -> None:
    eastern = timezone(timedelta(hours=-5))
    pulled_at = datetime(2026, 5, 31, 7, 30, tzinfo=eastern)
    pull = to_feed_pull(pull_row(pulled_at))
    assert pull.pulled_at == pulled_at
    assert pull.pulled_at.tzinfo is eastern


def test_to_feed_pull_with_no_balance() -> None:
    row = pull_row(datetime(2026, 5, 31, tzinfo=UTC))
    row.balance_cents = row.balance_date = row.drift_cents = None
    pull = to_feed_pull(row)
    assert (pull.balance_cents, pull.balance_date, pull.drift_cents) == (None, None, None)


def test_feed_item_row_table_and_columns() -> None:
    table = FeedItemRow.__table__
    assert table.name == "feed_items"
    assert [column.name for column in table.columns] == [
        "id",
        "account_id",
        "feed_id",
        "transaction_id",
    ]


def test_feed_pull_row_table_columns_and_default() -> None:
    table = FeedPullRow.__table__
    assert table.name == "feed_pulls"
    assert [column.name for column in table.columns] == [name for name, _ in PULL_FIELDS]
    default = table.columns["pulled_at"].default
    assert default is not None
    assert (
        default.arg.__name__ == StatementRow.__table__.columns["imported_at"].default.arg.__name__
    )
