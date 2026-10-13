from datetime import date

from sqlalchemy import Engine

from finances.db.engine import session_scope
from finances.db.repositories import (
    create_account,
    latest_balance,
    list_statements,
    list_transactions,
)
from finances.ingest.service import ImportStatus, StatementImportResult, import_statement

FEBRUARY = [
    "Capital One\tcapitalone.com",
    "Quicksilver Credit Card\tVisa Signature ending in 1111",
    "Feb 1, 2026 - Feb 28, 2026\t28 days in Billing Cycle",
    "Previous Balance\t$100.00",
    "Payments\t- $100.00",
    "Other Credits\t- $0.00",
    "Transactions\t+ $42.50",
    "Fees Charged\t+ $0.00",
    "Interest Charged\t+ $0.00",
    "New Balance\t= $42.50",
    "JANE DOE #1111: Payments, Credits and Adjustments",
    "Feb 10  Feb 11\tCAPITAL ONE MOBILE PYMT\t- $100.00",
    "JANE DOE #1111: Transactions",
    "Feb 3  Feb 4\tACME COFFEE\t$4.50",
    "Feb 14  Feb 15\tFOOBAR GROCERY #45\t$38.00",
    "JANE DOE #1111: Total Transactions\t$42.50",
    "Total Transactions for This Period\t$42.50",
]


def test_a_capital_one_pdf_is_imported_through_the_real_registry(
    db_engine: Engine, make_pdf
) -> None:
    content = make_pdf([FEBRUARY])
    with session_scope(db_engine) as session:
        create_account(session, "Test Quicksilver", "Capital One", "credit_card", last4="1111")
        result = import_statement(session, filename="february.pdf", content=content)
    assert result == StatementImportResult(
        filename="february.pdf",
        status=ImportStatus.IMPORTED,
        message="imported",
        parser_name="capital_one_card",
        account_name="Test Quicksilver",
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
        lines_parsed=3,
        inserted=3,
        duplicates=0,
    )
    with session_scope(db_engine) as session:
        rows = sorted(list_transactions(session), key=lambda item: item.id)
        found = [
            (r.posted_date, r.amount_cents, r.description, r.section, r.cardholder) for r in rows
        ]
        assert found == [
            (date(2026, 2, 11), 10000, "CAPITAL ONE MOBILE PYMT", "payments_credits", "JANE DOE"),
            (date(2026, 2, 4), -450, "ACME COFFEE", "purchases", "JANE DOE"),
            (date(2026, 2, 15), -3800, "FOOBAR GROCERY #45", "purchases", "JANE DOE"),
        ]
        assert [r.card_last4 for r in rows] == ["1111", "1111", "1111"]
        statement = list_statements(session)[0]
        assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-10000, -4250)
        assert latest_balance(session, 1).balance_cents == -4250


def test_the_same_capital_one_pdf_is_not_imported_twice(db_engine: Engine, make_pdf) -> None:
    content = make_pdf([FEBRUARY])
    with session_scope(db_engine) as session:
        create_account(session, "Test Quicksilver", "Capital One", "credit_card", last4="1111")
        import_statement(session, filename="february.pdf", content=content)
    with session_scope(db_engine) as session:
        again = import_statement(session, filename="february.pdf", content=content)
        assert again.status is ImportStatus.ALREADY_IMPORTED
        assert len(list_transactions(session)) == 3


def test_a_capital_one_pdf_that_does_not_add_up_is_refused(db_engine: Engine, make_pdf) -> None:
    lines = [line.replace("= $42.50", "= $43.50") for line in FEBRUARY]
    with session_scope(db_engine) as session:
        create_account(session, "Test Quicksilver", "Capital One", "credit_card", last4="1111")
        result = import_statement(session, filename="february.pdf", content=make_pdf([lines]))
        assert result.status is ImportStatus.FAILED
        assert result.message == "statement does not reconcile: off by -100 cents"
        assert list_transactions(session) == []
