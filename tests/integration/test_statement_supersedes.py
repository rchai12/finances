from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import FeedItemRow, StatementRow, TransactionRow
from finances.db.repositories import create_account
from finances.ingest.dedup import fingerprint_lines
from finances.ingest.service import ImportStatus, StatementImportResult, import_statement
from finances.ingest.statement import Section, StatementLine
from finances.sync.feed import AccountFeed, FeedTransaction, feed_fingerprint
from finances.sync.service import apply_feed


def may(number: int) -> date:
    return date(2026, 5, number)


def tx(feed_id: str, number: int, cents: int, text: str, **more: object) -> FeedTransaction:
    return FeedTransaction(feed_id, may(number), cents, text, **more)


def feed(*items: FeedTransaction, removed: tuple[str, ...] = ()) -> AccountFeed:
    return AccountFeed(list(items), list(removed))


def money(cents: int) -> str:
    return f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def row(number: int, cents: int, text: str, section: str = "purchases", **more: str) -> str:
    """One ROW of the fake bank's statement: posted on that day of May 2026."""
    bought = more.get("bought", "-")
    card = more.get("card", "-")
    reference = more.get("reference", "-")
    return f"2026-05-{number:02d}|{bought}|{section}|{money(cents)}|{card}|{reference}|{text}"


ROWS = (
    (3, -450, "ACME COFFEE #12"),
    (8, -2599, "FOOBAR GROCERY"),
    (20, 5000, "PAYMENT THANK YOU"),
)


@pytest.fixture
def session(db_engine: Engine, fake_bank):
    """A session on a migrated database with a card (id 1) and a checking account (id 2)."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Fake Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Fake Bank", "checking", last4="2222")
        yield opened


@pytest.fixture
def statement(fake_statement_pdf):
    """Return a function that builds a May 2026 statement of account 1111 from ROW texts."""

    def build(*rows: str, start: str = "2026-05-01", end: str = "2026-05-31", **more) -> bytes:
        total = sum(
            int(text.split("|")[3].replace(".", "").replace("-", ""))
            * (-1 if text.split("|")[3].startswith("-") else 1)
            for text in rows
        )
        return fake_statement_pdf(
            start=start,
            end=end,
            opening="-100.00",
            closing=money(-10000 + total),
            rows=rows,
            **more,
        )

    return build


def default_rows() -> tuple[str, ...]:
    return (
        row(3, -450, "ACME COFFEE #12", bought="2026-05-02", card="1111", reference="7001"),
        row(8, -2599, "FOOBAR GROCERY"),
        row(20, 5000, "PAYMENT THANK YOU", section="payments_credits"),
    )


def ledger(session: Session, account_id: int = 1) -> list[tuple]:
    """Every stored transaction of the account with its feed id, in id order."""
    stmt = (
        select(TransactionRow, FeedItemRow.feed_id)
        .outerjoin(FeedItemRow, FeedItemRow.transaction_id == TransactionRow.id)
        .where(TransactionRow.account_id == account_id)
        .order_by(TransactionRow.id)
    )
    return [
        (item.id, feed_id, item.posted_date.day, item.amount_cents, item.description, item.source)
        for item, feed_id in session.execute(stmt).all()
    ]


def outcome(session: Session, account_id: int = 1) -> list[tuple]:
    """What the ledger says, without the ids: the same for either order of arrival."""
    return sorted(
        (day, cents, text, source, feed_id)
        for _, feed_id, day, cents, text, source in ledger(session, account_id)
    )


def counts(result: StatementImportResult) -> tuple[int, int, int, int]:
    return (result.inserted, result.upgraded, result.dropped, result.duplicates)


def test_the_result_has_two_new_counts_that_default_to_zero() -> None:
    result = StatementImportResult("a.pdf", ImportStatus.FAILED, "x")
    assert (result.upgraded, result.dropped) == (0, 0)
    assert (
        StatementImportResult("a.pdf", ImportStatus.IMPORTED, "imported", upgraded=2).upgraded == 2
    )


def test_a_statement_upgrades_the_rows_the_feed_brought(session: Session, statement) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("f-coffee", 2, -450, "Acme Coffee", transaction_date=may(1), card_last4="9999"),
            tx("f-grocery", 9, -2599, "FOOBAR GROCERY ONLINE", card_last4="1111"),
            tx("f-payment", 20, 5000, "PAYMENT"),
        ),
    )
    result = import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    assert result.status is ImportStatus.IMPORTED
    assert counts(result) == (0, 3, 0, 0)
    assert result.lines_parsed == 3
    assert ledger(session) == [
        (1, "f-coffee", 3, -450, "ACME COFFEE #12", "statement"),
        (2, "f-grocery", 8, -2599, "FOOBAR GROCERY", "statement"),
        (3, "f-payment", 20, 5000, "PAYMENT THANK YOU", "statement"),
    ]
    rows = session.scalars(select(TransactionRow).order_by(TransactionRow.id)).all()
    assert [(item.statement_id, item.is_pending, item.section) for item in rows] == [
        (1, False, "purchases"),
        (1, False, "purchases"),
        (1, False, "payments_credits"),
    ]
    assert [(item.transaction_date, item.card_last4, item.external_id) for item in rows] == [
        (may(2), "1111", "7001"),
        (None, "1111", None),
        (None, None, None),
    ]
    lines = [
        StatementLine(
            may(3), may(2), "ACME COFFEE #12", -450, Section.PURCHASES, "1111", None, "7001"
        ),
        StatementLine(may(8), None, "FOOBAR GROCERY", -2599, Section.PURCHASES),
        StatementLine(may(20), None, "PAYMENT THANK YOU", 5000, Section.PAYMENTS_CREDITS),
    ]
    assert [item.fingerprint for item in rows] == fingerprint_lines(1, lines)
    stored = session.scalars(select(StatementRow)).one()
    assert (stored.lines_parsed, stored.rows_inserted, stored.rows_duplicate) == (3, 0, 0)


def test_what_the_statement_does_not_say_is_kept_from_the_feed(session: Session, statement) -> None:
    apply_feed(
        session, 1, feed(tx("f-1", 8, -2599, "FOOBAR", transaction_date=may(6), card_last4="1111"))
    )
    import_statement(
        session, filename="may.pdf", content=statement(row(8, -2599, "FOOBAR GROCERY"))
    )
    stored = session.get(TransactionRow, 1)
    assert (stored.transaction_date, stored.card_last4) == (may(6), "1111")
    assert (stored.cardholder, stored.external_id, stored.source) == (None, None, "statement")


def test_lines_without_a_feed_row_are_inserted_and_leftover_feed_rows_are_dropped(
    session: Session, statement
) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("f-coffee", 3, -450, "ACME COFFEE"),
            tx("f-wrong-amount", 8, -2600, "FOOBAR GROCERY"),
            tx("f-unknown", 15, -999, "NOT ON THE STATEMENT"),
        ),
    )
    result = import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    assert counts(result) == (2, 1, 2, 0)
    assert ledger(session)[0] == (1, "f-coffee", 3, -450, "ACME COFFEE #12", "statement")
    assert [entry[1:] for entry in ledger(session)[1:]] == [
        (None, 8, -2599, "FOOBAR GROCERY", "statement"),
        (None, 20, 5000, "PAYMENT THANK YOU", "statement"),
    ]
    assert session.scalars(select(FeedItemRow.feed_id)).all() == ["f-coffee"]
    stored = session.scalars(select(StatementRow)).one()
    assert (stored.lines_parsed, stored.rows_inserted, stored.rows_duplicate) == (3, 2, 0)


def test_feed_rows_outside_the_period_wait_for_their_own_statement(
    session: Session, statement
) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("f-before", 9, -100, "BEFORE THE PERIOD"),
            tx("f-first", 10, -200, "FIRST DAY UNMATCHED"),
            tx("f-last", 20, -300, "LAST DAY UNMATCHED"),
            tx("f-after", 21, -400, "AFTER THE PERIOD"),
            tx("f-early", 7, -450, "MATCHES FROM BEFORE"),
            tx("f-late", 25, -2599, "MATCHES FROM AFTER"),
            tx("f-too-early", 2, 5000, "TOO FAR BEFORE"),
        ),
    )
    content = statement(
        row(12, -450, "ACME COFFEE #12"),
        row(20, -2599, "FOOBAR GROCERY"),
        row(10, 5000, "PAYMENT THANK YOU", section="payments_credits"),
        start="2026-05-10",
        end="2026-05-20",
    )
    result = import_statement(session, filename="mid-may.pdf", content=content)
    assert counts(result) == (1, 2, 2, 0)
    assert ledger(session) == [
        (1, "f-before", 9, -100, "BEFORE THE PERIOD", "aggregator"),
        (4, "f-after", 21, -400, "AFTER THE PERIOD", "aggregator"),
        (5, "f-early", 12, -450, "ACME COFFEE #12", "statement"),
        (6, "f-late", 20, -2599, "FOOBAR GROCERY", "statement"),
        (7, "f-too-early", 2, 5000, "TOO FAR BEFORE", "aggregator"),
        (8, None, 10, 5000, "PAYMENT THANK YOU", "statement"),
    ]


def test_pending_rows_are_neither_upgraded_nor_dropped(session: Session, statement) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("f-pending-same", 3, -450, "ACME COFFEE", is_pending=True),
            tx("f-pending-other", 15, -999, "HOTEL HOLD", is_pending=True),
        ),
    )
    result = import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    assert counts(result) == (3, 0, 0, 0)
    rows = session.scalars(select(TransactionRow).order_by(TransactionRow.id)).all()
    assert [(item.source, item.is_pending) for item in rows] == [
        ("aggregator", True),
        ("aggregator", True),
        ("statement", False),
        ("statement", False),
        ("statement", False),
    ]


def test_equal_amounts_pair_by_the_closest_day_and_each_row_once(
    session: Session, statement
) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("f-a", 12, -450, "COFFEE A"),
            tx("f-b", 4, -450, "COFFEE B"),
            tx("f-c", 5, -450, "COFFEE C"),
        ),
    )
    content = statement(row(3, -450, "ACME COFFEE ONE"), row(11, -450, "ACME COFFEE TWO"))
    result = import_statement(session, filename="may.pdf", content=content)
    assert counts(result) == (0, 2, 1, 0)
    assert ledger(session) == [
        (1, "f-a", 11, -450, "ACME COFFEE TWO", "statement"),
        (2, "f-b", 3, -450, "ACME COFFEE ONE", "statement"),
    ]


def test_another_accounts_feed_rows_are_not_touched(session: Session, statement) -> None:
    apply_feed(session, 2, feed(tx("f-1", 3, -450, "ACME COFFEE"), tx("f-2", 15, -999, "OTHER")))
    result = import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    assert counts(result) == (3, 0, 0, 0)
    assert [entry[5] for entry in ledger(session, 2)] == ["aggregator", "aggregator"]
    pull = apply_feed(session, 2, feed(tx("f-3", 8, -2599, "FOOBAR"), tx("f-4", 9, -1, "ACME")))
    assert (pull.inserted, pull.unchanged) == (2, 0)
    assert len(ledger(session, 2)) == 4
    assert [entry[1] for entry in ledger(session, 1)] == [None, None, None]


def test_a_dry_run_reports_the_counts_and_writes_nothing(session: Session, statement) -> None:
    apply_feed(
        session, 1, feed(tx("f-coffee", 3, -450, "ACME COFFEE"), tx("f-unknown", 15, -999, "OTHER"))
    )
    before = ledger(session)
    content = statement(*default_rows())
    result = import_statement(session, filename="may.pdf", content=content, dry_run=True)
    assert result.status is ImportStatus.DRY_RUN
    assert counts(result) == (2, 1, 1, 0)
    assert ledger(session) == before
    assert session.scalars(select(StatementRow)).all() == []
    assert counts(import_statement(session, filename="may.pdf", content=content)) == (2, 1, 1, 0)


def test_a_statement_that_does_not_reconcile_changes_no_feed_row(
    session: Session, fake_statement_pdf
) -> None:
    apply_feed(session, 1, feed(tx("f-coffee", 5, -450, "ACME COFFEE")))
    before = ledger(session)
    content = fake_statement_pdf(
        start="2026-05-01",
        end="2026-05-31",
        opening="-100.00",
        closing="-999.00",
        rows=(row(5, -450, "ACME COFFEE #12"),),
    )
    result = import_statement(session, filename="bad.pdf", content=content)
    assert result.status is ImportStatus.FAILED
    assert counts(result) == (0, 0, 0, 0)
    assert ledger(session) == before


def test_lines_already_stored_are_duplicates_and_claim_no_feed_row(
    session: Session, statement
) -> None:
    first = statement(row(3, -450, "ACME COFFEE"), end="2026-05-04")
    import_statement(session, filename="first.pdf", content=first)
    apply_feed(session, 1, feed(tx("f-old", 3, -450, "ACME COFFEE")))
    apply_feed(session, 1, feed(tx("f-new", 7, -450, "ACME COFFEE AGAIN")))
    assert [entry[1] for entry in ledger(session)] == ["f-old", "f-new"]
    content = statement(
        row(3, -450, "ACME COFFEE"), row(8, -2599, "FOOBAR GROCERY"), end="2026-05-30"
    )
    result = import_statement(session, filename="second.pdf", content=content)
    assert counts(result) == (1, 0, 1, 1)
    assert [entry[1:] for entry in ledger(session)] == [
        ("f-old", 3, -450, "ACME COFFEE", "statement"),
        (None, 8, -2599, "FOOBAR GROCERY", "statement"),
    ]


def test_after_an_upgrade_the_feed_leaves_the_row_alone(session: Session, statement) -> None:
    items = (tx("f-coffee", 3, -450, "Acme Coffee"), tx("f-unknown", 15, -999, "OTHER"))
    apply_feed(session, 1, feed(*items))
    import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    before = ledger(session)
    june = FeedTransaction("f-june", date(2026, 6, 1), -100, "NEXT MONTH")
    pull = apply_feed(session, 1, feed(*items, june))
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (1, 0, 0, 2)
    assert ledger(session)[:3] == before
    assert ledger(session)[3][1:] == ("f-june", 1, -100, "NEXT MONTH", "aggregator")


def test_a_feed_that_arrives_after_the_statement_is_linked_not_stored_twice(
    session: Session, statement
) -> None:
    import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    before = [entry[2:] for entry in ledger(session)]
    pull = apply_feed(
        session,
        1,
        feed(
            tx("f-coffee", 2, -450, "Acme Coffee"),
            tx("f-grocery", 13, -2599, "FOOBAR GROCERY ONLINE"),
            tx("f-payment", 20, 5000, "PAYMENT"),
        ),
    )
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (0, 0, 0, 3)
    assert pull.feed_total_cents == 1951
    assert ledger(session) == [
        (1, "f-coffee", 3, -450, "ACME COFFEE #12", "statement"),
        (2, "f-grocery", 8, -2599, "FOOBAR GROCERY", "statement"),
        (3, "f-payment", 20, 5000, "PAYMENT THANK YOU", "statement"),
    ]
    assert [entry[2:] for entry in ledger(session)] == before
    again = apply_feed(session, 1, feed(tx("f-coffee", 2, -450, "Acme Coffee")))
    assert (again.inserted, again.unchanged) == (0, 1)


def test_a_late_feed_row_inside_a_statement_period_with_no_line_is_not_stored(
    session: Session, statement
) -> None:
    import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    pull = apply_feed(
        session,
        1,
        feed(
            tx("f-wrong-amount", 8, -2600, "FOOBAR GROCERY"),
            tx("f-first-day", 1, -100, "FIRST DAY"),
            tx("f-last-day", 31, -200, "LAST DAY"),
            FeedTransaction("f-april", date(2026, 4, 30), -300, "DAY BEFORE THE PERIOD"),
            FeedTransaction("f-june", date(2026, 6, 1), -400, "DAY AFTER THE PERIOD"),
            tx("f-pending", 15, -999, "HOLD IN THE PERIOD", is_pending=True),
        ),
    )
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (3, 0, 0, 3)
    assert [entry[1] for entry in ledger(session)] == [
        None,
        None,
        None,
        "f-april",
        "f-june",
        "f-pending",
    ]
    assert pull.feed_total_cents == -700
    again = apply_feed(session, 1, feed(tx("f-wrong-amount", 8, -2600, "FOOBAR GROCERY")))
    assert (again.inserted, again.unchanged) == (0, 1)
    assert len(ledger(session)) == 6


def test_a_late_feed_row_takes_the_closest_unlinked_statement_row(
    session: Session, statement
) -> None:
    content = statement(
        row(3, -450, "COFFEE ONE"), row(11, -450, "COFFEE TWO"), row(12, -450, "COFFEE THREE")
    )
    import_statement(session, filename="may.pdf", content=content)
    apply_feed(session, 1, feed(tx("f-a", 12, -450, "A")))
    apply_feed(session, 1, feed(tx("f-b", 12, -450, "B"), tx("f-c", 8, -450, "C")))
    pull = apply_feed(session, 1, feed(tx("f-d", 12, -450, "D")))
    assert [(entry[0], entry[1]) for entry in ledger(session)] == [
        (1, "f-c"),
        (2, "f-b"),
        (3, "f-a"),
    ]
    assert (pull.inserted, pull.unchanged) == (0, 1)


def test_a_hold_that_posts_after_its_statement_gives_way_to_the_statement_row(
    session: Session, statement
) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("hold-1", 2, -450, "ACME COFFEE", is_pending=True),
            tx("hold-2", 7, -2599, "FOOBAR", is_pending=True),
            tx("hold-3", 14, -999, "HOTEL HOLD", is_pending=True),
        ),
    )
    import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    pull = apply_feed(
        session,
        1,
        feed(
            tx("hold-1", 3, -450, "ACME COFFEE"),
            tx("post-2", 8, -2599, "FOOBAR GROCERY", replaces_feed_id="hold-2"),
            tx("hold-3", 15, -1050, "HOTEL"),
            removed=("hold-2",),
        ),
    )
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (0, 0, 3, 0)
    assert ledger(session) == [
        (4, "hold-1", 3, -450, "ACME COFFEE #12", "statement"),
        (5, "post-2", 8, -2599, "FOOBAR GROCERY", "statement"),
        (6, None, 20, 5000, "PAYMENT THANK YOU", "statement"),
    ]


def test_a_hold_that_posts_outside_every_statement_is_updated_as_before(
    session: Session, statement
) -> None:
    import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    apply_feed(session, 1, feed(FeedTransaction("hold-1", date(2026, 6, 2), -450, "X", True)))
    pull = apply_feed(
        session, 1, feed(FeedTransaction("hold-1", date(2026, 6, 9), -450, "X POSTED"))
    )
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (0, 1, 0, 0)
    assert ledger(session)[3] == (4, "hold-1", 9, -450, "X POSTED", "aggregator")
    assert session.get(TransactionRow, 4).fingerprint == feed_fingerprint(1, "hold-1")


@pytest.mark.parametrize("statement_first", [True, False])
def test_the_ledger_is_the_same_whichever_arrives_first(
    session: Session, statement, statement_first: bool
) -> None:
    content = statement(
        row(3, -450, "ACME COFFEE #12", bought="2026-05-02"),
        row(3, -450, "ACME COFFEE #12", bought="2026-05-02"),
        row(8, -2599, "FOOBAR GROCERY"),
        row(20, 5000, "PAYMENT THANK YOU", section="payments_credits"),
        row(28, -1500, "ACME GAS"),
        end="2026-05-28",
    )
    delivered = feed(
        tx("f-1", 2, -450, "Acme Coffee"),
        tx("f-2", 4, -450, "Acme Coffee"),
        tx("f-3", 9, -2599, "Foobar"),
        tx("f-4", 20, 5000, "Payment"),
        tx("f-5", 15, -777, "Not on the statement"),
        tx("f-6", 30, -1500, "Acme Gas"),
        tx("f-7", 30, -888, "After the period"),
        tx("f-8", 12, -321, "Hold", is_pending=True),
    )
    if statement_first:
        import_statement(session, filename="may.pdf", content=content)
        apply_feed(session, 1, delivered)
    else:
        apply_feed(session, 1, delivered)
        import_statement(session, filename="may.pdf", content=content)
    apply_feed(session, 1, delivered)
    found = outcome(session)
    assert [(day, cents, source) for day, cents, _, source, _ in found] == [
        (3, -450, "statement"),
        (3, -450, "statement"),
        (8, -2599, "statement"),
        (12, -321, "aggregator"),
        (20, 5000, "statement"),
        (28, -1500, "statement"),
        (30, -888, "aggregator"),
    ]
    assert sorted(feed_id for *_, feed_id in found) == [
        "f-1",
        "f-2",
        "f-3",
        "f-4",
        "f-6",
        "f-7",
        "f-8",
    ]
    assert [text for _, _, text, source, _ in found if source == "statement"] == [
        "ACME COFFEE #12",
        "ACME COFFEE #12",
        "FOOBAR GROCERY",
        "PAYMENT THANK YOU",
        "ACME GAS",
    ]


def test_a_posted_feed_row_is_settled_only_when_it_first_arrives(
    session: Session, statement
) -> None:
    apply_feed(session, 1, feed(tx("f-early", 9, -100, "DAY BEFORE THE PERIOD")))
    content = statement(row(12, -450, "ACME COFFEE #12"), start="2026-05-10", end="2026-05-20")
    import_statement(session, filename="mid-may.pdf", content=content)
    pull = apply_feed(session, 1, feed(tx("f-early", 11, -450, "NOW INSIDE THE PERIOD")))
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (0, 1, 0, 0)
    assert ledger(session) == [
        (1, "f-early", 11, -450, "NOW INSIDE THE PERIOD", "aggregator"),
        (2, None, 12, -450, "ACME COFFEE #12", "statement"),
    ]
