from datetime import date

from sqlalchemy import Engine

from finances.db.engine import session_scope
from finances.db.repositories import create_account, latest_balance, list_transactions
from finances.ingest.service import ImportStatus, StatementImportResult, import_statement

BOA = [
    "Bank of America   www.bankofamerica.com",
    "Account# 4400 0000 0000 7777",
    "May 1 - May 31, 2026",
    "Previous Balance   $50.00",
    "Payments and Other Credits   -$50.00",
    "Purchases and Adjustments   $31.75",
    "Fees Charged   $0.00",
    "Interest Charged   $1.10",
    "New Balance Total   $32.85",
    "Payments and Other Credits",
    "05/10  05/10\tPAYMENT FROM CHK 9999 CONF#M00000000   4733  7777  -50.00",
    "TOTAL PAYMENTS AND OTHER CREDITS FOR THIS PERIOD   -$50.00",
    "Purchases and Adjustments",
    "05/02  05/03\tACME GROCERY #123 DECATUR GA   7838  7777  31.75",
    "TOTAL PURCHASES AND ADJUSTMENTS FOR THIS PERIOD   $31.75",
    "Interest Charged",
    "05/31  05/31\tINTEREST CHARGED ON PURCHASES   1.10",
    "TOTAL INTEREST CHARGED FOR THIS PERIOD   $1.10",
]
CITI = [
    "Citi   www.citicards.com",
    "Account number ending in: 8888",
    "Billing Period: 05/01/26-05/31/26",
    "Previous balance   $20.00",
    "Payments   -$20.00",
    "Credits   -$0.00",
    "Purchases   +$64.40",
    "Fees   +$0.00",
    "Interest   +$0.00",
    "New balance   $64.40",
    "CARDHOLDER SUMMARY",
    "JANE DOE   Card ending in 8888   New Charges   $64.40",
    "Payments, Credits and Adjustments",
    "05/15  05/15\tONLINE PAYMENT, THANK YOU   -$20.00",
    "JANE DOE",
    "Standard Purchases",
    "05/04  05/05\tACME WHSE #1234 ALLEN TX   $60.00",
    "\t05/20   FOOBAR CAFE   $4.40",
    "Fees Charged",
    "TOTAL FEES FOR THIS PERIOD   $0.00",
]


def stored(session) -> list[tuple]:
    rows = sorted(list_transactions(session), key=lambda item: item.id)
    return [
        (r.posted_date, r.transaction_date, r.amount_cents, r.description, r.section) for r in rows
    ]


def test_a_bank_of_america_pdf_is_imported(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Cash Rewards", "Bank of America", "credit_card", last4="7777")
        result = import_statement(session, filename="boa-may.pdf", content=make_pdf([BOA]))
    assert result == StatementImportResult(
        filename="boa-may.pdf",
        status=ImportStatus.IMPORTED,
        message="imported",
        parser_name="boa_card",
        account_name="Test Cash Rewards",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        lines_parsed=3,
        inserted=3,
        duplicates=0,
    )
    with session_scope(db_engine) as session:
        assert stored(session) == [
            (
                date(2026, 5, 10),
                date(2026, 5, 10),
                5000,
                "PAYMENT FROM CHK 9999 CONF#M00000000",
                "payments_credits",
            ),
            (
                date(2026, 5, 3),
                date(2026, 5, 2),
                -3175,
                "ACME GROCERY #123 DECATUR GA",
                "purchases",
            ),
            (
                date(2026, 5, 31),
                date(2026, 5, 31),
                -110,
                "INTEREST CHARGED ON PURCHASES",
                "interest",
            ),
        ]
        rows = sorted(list_transactions(session), key=lambda item: item.id)
        assert [(r.card_last4, r.external_id, r.cardholder) for r in rows] == [
            ("7777", "4733", None),
            ("7777", "7838", None),
            (None, None, None),
        ]
        assert latest_balance(session, 1).balance_cents == -3285


def test_a_citi_pdf_is_imported(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Costco Visa", "Citi", "credit_card", last4="8888")
        result = import_statement(session, filename="citi-may.pdf", content=make_pdf([CITI]))
    assert result == StatementImportResult(
        filename="citi-may.pdf",
        status=ImportStatus.IMPORTED,
        message="imported",
        parser_name="citi_card",
        account_name="Test Costco Visa",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        lines_parsed=3,
        inserted=3,
        duplicates=0,
    )
    with session_scope(db_engine) as session:
        assert stored(session) == [
            (
                date(2026, 5, 15),
                date(2026, 5, 15),
                2000,
                "ONLINE PAYMENT, THANK YOU",
                "payments_credits",
            ),
            (date(2026, 5, 5), date(2026, 5, 4), -6000, "ACME WHSE #1234 ALLEN TX", "purchases"),
            (date(2026, 5, 20), None, -440, "FOOBAR CAFE", "purchases"),
        ]
        rows = sorted(list_transactions(session), key=lambda item: item.id)
        assert [(r.card_last4, r.cardholder) for r in rows] == [
            (None, None),
            ("8888", "JANE DOE"),
            ("8888", "JANE DOE"),
        ]
        assert latest_balance(session, 1).balance_cents == -6440


def test_each_statement_goes_to_its_own_bank(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Cash Rewards", "Bank of America", "credit_card", last4="7777")
        create_account(session, "Test Costco Visa", "Citi", "credit_card", last4="8888")
        first = import_statement(session, filename="a.pdf", content=make_pdf([BOA]))
        second = import_statement(session, filename="b.pdf", content=make_pdf([CITI]))
    assert (first.parser_name, first.account_name) == ("boa_card", "Test Cash Rewards")
    assert (second.parser_name, second.account_name) == ("citi_card", "Test Costco Visa")
