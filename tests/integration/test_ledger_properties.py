"""Statements and feed pulls arriving in any realistic order store each transaction once.

The household's transactions are generated, then shown to the app two ways: on statements
(each imported a few days after its period ends) and in feed pulls (each delivering the last 30
days). A feed may date a transaction the same day as the statement or up to three days later.
"""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select

import finances.ingest.service as ingest
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from finances.ingest.service import ImportStatus, import_statement
from finances.sync.feed import AccountFeed, FeedTransaction
from finances.sync.service import apply_feed

FIRST_DAY = date(2026, 1, 1)
PERIODS = {
    "jan": (date(2026, 1, 1), date(2026, 1, 31)),
    "feb": (date(2026, 2, 1), date(2026, 2, 28)),
}
WINDOW_DAYS = 30
STATEMENT_DELAY_DAYS = 2


@dataclass(frozen=True)
class Spending:
    number: int
    day: date
    amount_cents: int
    feed_day: date


def spending(raw: list[tuple[int, int, int]]) -> list[Spending]:
    return [
        Spending(
            number,
            FIRST_DAY + timedelta(days=offset),
            cents,
            FIRST_DAY + timedelta(days=offset + lag),
        )
        for number, (offset, cents, lag) in enumerate(raw)
    ]


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def statement_text(name: str, everything: list[Spending]) -> bytes:
    start, end = PERIODS[name]
    printed = [item for item in everything if start <= item.day <= end]
    total = sum(item.amount_cents for item in printed)
    lines = [
        "FAKEBANK STATEMENT",
        "ACCOUNT 1111 credit_card",
        f"PERIOD {start} {end}",
        "OPENING 0.00",
        f"CLOSING {money(total)}",
        *(
            f"ROW {item.day}|-|purchases|{money(item.amount_cents)}|-|-|PROBE {item.number}"
            for item in printed
        ),
    ]
    return "\n".join(lines).encode()


@pytest.fixture
def statements_as_text(fake_bank, monkeypatch: pytest.MonkeyPatch) -> None:
    """Statements are plain text here, read by the fake bank parser."""
    monkeypatch.setattr(ingest, "extract_pages", lambda content: [content.decode()])


def pull(engine, account_id: int, everything: list[Spending], today: date, order: str) -> set[int]:
    """Apply the last 30 days of the feed in the order given. Return the numbers delivered."""
    delivered = [
        item for item in everything if today - timedelta(days=WINDOW_DAYS) <= item.feed_day <= today
    ]
    delivered.sort(key=lambda item: (item.feed_day, item.number))
    if order == "newest first":
        delivered.reverse()
    feed = AccountFeed(
        [
            FeedTransaction(f"F{item.number}", item.feed_day, item.amount_cents, "PROBE")
            for item in delivered
        ]
    )
    with session_scope(engine) as session:
        apply_feed(session, account_id, feed)
    return {item.number for item in delivered}


Step = tuple[int, str | None, str | None]


def live(
    folder: Path, everything: list[Spending], steps: list[Step]
) -> tuple[Counter, Counter, dict[str, Counter]]:
    """Run the steps on a new database. Return what is stored, what should be, and per period.

    Each step moves time forward, pulls the feed in the order named (as the daily job does; no
    pull when the order is None), and then imports the statement named, if any, once its period
    ended more than two days before.
    """
    url = f"sqlite:///{(folder / f'{uuid.uuid4().hex}.db').as_posix()}"
    upgrade_to_head(url)
    engine = get_engine(url)
    with session_scope(engine) as session:
        account_id = create_account(
            session, "Probe Card", "Fake Bank", "credit_card", last4="1111"
        ).id
    imported: set[str] = set()
    seen: set[int] = set()
    today = FIRST_DAY
    for days, order, statement in steps:
        today += timedelta(days=days)
        if order is not None:
            seen |= pull(engine, account_id, everything, today, order)
        if statement is None:
            continue
        start, end = PERIODS[statement]
        if today <= end + timedelta(days=STATEMENT_DELAY_DAYS):
            continue
        with session_scope(engine) as session:
            result = import_statement(
                session, filename=f"{statement}.pdf", content=statement_text(statement, everything)
            )
        assert result.status in (ImportStatus.IMPORTED, ImportStatus.ALREADY_IMPORTED)
        imported.add(statement)
        seen |= {item.number for item in everything if start <= item.day <= end}
    with session_scope(engine) as session:
        rows = session.execute(
            select(TransactionRow.posted_date, TransactionRow.amount_cents)
        ).all()
    engine.dispose()

    def covered(day: date) -> bool:
        return any(PERIODS[name][0] <= day <= PERIODS[name][1] for name in imported)

    stored = Counter(cents for _, cents in rows)
    expected = Counter(
        item.amount_cents
        for item in everything
        if item.number in seen and (covered(item.day) or not covered(item.feed_day))
    )
    periods = {}
    for name in imported:
        start, end = PERIODS[name]
        periods[name] = Counter(
            (day, cents) for day, cents in rows if start <= day <= end
        ) - Counter(
            (item.day, item.amount_cents) for item in everything if start <= item.day <= end
        )
    return stored, expected, periods


def assert_each_stored_once(folder: Path, raw, steps) -> None:
    stored, expected, periods = live(folder, spending(raw), steps)
    assert stored == expected
    assert all(not extra for extra in periods.values())


transactions = st.lists(
    st.tuples(
        st.integers(0, 58),
        st.sampled_from([-450, -450, -450, -1299, 2500]),
        st.sampled_from([0, 0, 1, 2, 3]),
    ),
    min_size=1,
    max_size=12,
)
steps = st.lists(
    st.tuples(
        st.integers(1, 20),
        st.sampled_from(["newest first", "oldest first"]),
        st.sampled_from([None, None, "jan", "feb"]),
    ),
    min_size=1,
    max_size=10,
)


@settings(max_examples=150)
@given(transactions, steps)
def test_any_order_of_statements_and_pulls_stores_each_transaction_once(
    statements_as_text: None, tmp_path: Path, raw, order
) -> None:
    assert_each_stored_once(tmp_path, raw, order)


def test_the_order_a_pull_lists_its_transactions_in_changes_nothing(
    statements_as_text: None, tmp_path: Path
) -> None:
    raw = [(28, -450, 0), (31, -450, 0)]
    for order in ("newest first", "oldest first"):
        stored, expected, _ = live(tmp_path, spending(raw), [(33, None, "jan"), (1, order, None)])
        assert stored == expected == Counter({-450: 2})


def test_a_tie_at_import_does_not_push_a_later_transaction_out(
    statements_as_text: None, tmp_path: Path
) -> None:
    raw = [(0, -450, 0)] * 3 + [(15, -450, 3), (23, -450, 0), (28, -450, 3), (9, -450, 3)]
    order = [
        (1, "newest first", None),
        (12, "newest first", None),
        (20, None, "jan"),
        (1, "oldest first", None),
    ]
    assert_each_stored_once(tmp_path, raw, order)


def test_a_statement_pairs_as_many_feed_rows_as_it_can(
    statements_as_text: None, tmp_path: Path
) -> None:
    raw = [(51, -450, 3), (56, -450, 3)]
    assert_each_stored_once(tmp_path, raw, [(59, "newest first", None), (2, "newest first", "feb")])


def test_a_tie_across_a_period_edge_goes_to_the_transaction_inside_the_period(
    statements_as_text: None, tmp_path: Path
) -> None:
    raw = [(25, -450, 3), (31, -450, 3)]
    assert_each_stored_once(
        tmp_path, raw, [(41, "newest first", None), (20, "newest first", "feb")]
    )


def test_a_pull_pairs_only_the_transactions_that_settle_in_it(
    statements_as_text: None, tmp_path: Path
) -> None:
    raw = [(26, -450, 0), (28, -450, 3)]
    order = [(27, "newest first", None), (6, None, "jan"), (1, "newest first", None)]
    assert_each_stored_once(tmp_path, raw, order)


def test_a_pull_breaks_a_tie_across_a_period_edge_in_favour_of_the_period(
    statements_as_text: None, tmp_path: Path
) -> None:
    everything = spending([(29, -450, 0), (32, -450, 3)])
    url = f"sqlite:///{(tmp_path / 'edge.db').as_posix()}"
    upgrade_to_head(url)
    engine = get_engine(url)
    with session_scope(engine) as session:
        account_id = create_account(
            session, "Probe Card", "Fake Bank", "credit_card", last4="1111"
        ).id
        import_statement(session, filename="feb.pdf", content=statement_text("feb", everything))
    for order in ("newest first", "oldest first"):
        pull(engine, account_id, everything, date(2026, 2, 10), order)
    with session_scope(engine) as session:
        rows = session.execute(
            select(TransactionRow.posted_date, TransactionRow.source).order_by(
                TransactionRow.posted_date
            )
        ).all()
    engine.dispose()
    assert rows == [(date(2026, 1, 30), "aggregator"), (date(2026, 2, 2), "statement")]
