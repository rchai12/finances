from datetime import date

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import plain_lines, run, table_rows


def test_uncategorized_money_in_on_a_card_is_flagged(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        rows = [
            (card, date(2026, 6, 5), 2500, "QUUX CREDIT"),
            (card, date(2026, 6, 6), 1200, "BAZ CREDIT"),
            (card, date(2026, 6, 7), -900, "BAZ BOX"),
            (checking, date(2026, 6, 1), 300000, "ACME DEPOSIT"),
        ]
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    result = run("uncategorized")
    assert table_rows(result.stdout)[0] == ["ID", "Date", "Account", "Merchant", "Amount"]
    assert plain_lines(result.stdout) == [
        "Money in on a card: 2, likely a refund or a card payment."
        " Set a category, or pair it on the Transfers page."
    ]


def test_no_flag_without_money_in_on_a_card(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        session.add(
            TransactionRow(
                account_id=checking.id,
                posted_date=date(2026, 6, 1),
                amount_cents=300000,
                description="ACME DEPOSIT",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
    engine.dispose()
    assert plain_lines(run("uncategorized").stdout) == []
