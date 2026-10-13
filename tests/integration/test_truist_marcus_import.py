from datetime import date

from sqlalchemy import Engine

from finances.db.engine import session_scope
from finances.db.repositories import create_account, latest_balance, list_transactions
from finances.ingest.service import ImportStatus, StatementImportResult, import_statement

TRUIST = [
    "Truist Bank, Member FDIC   Your account statement",
    "For 05/31/2026",
    "TRUIST ONE CHECKING - LEVEL 1 1000000007777",
    "Your previous balance as of 04/30/2026   $500.00",
    "Checks   - 75.00",
    "Other withdrawals, debits and service charges   - 31.75",
    "Deposits, credits and interest   + 250.00",
    "Your new balance as of 05/31/2026   = $643.25",
    "Checks",
    "05/06   2001   75.00",
    "Total checks   = $75.00",
    "Other withdrawals, debits and service charges",
    "05/04\tDEBIT CARD PURCHASE ACME GROCERY 05-02 DECATUR GA 4242   31.75",
    "Total other withdrawals, debits and service charges   = $31.75",
    "Deposits, credits and interest",
    "05/15\tACH CORP CREDIT PAYROLL EXAMPLE EMPLOYER   250.00",
    "Total deposits, credits and interest   = $250.00",
]
MARCUS = [
    "Marcus by Goldman Sachs   ONLINE SAVINGS ACCOUNT STATEMENT",
    "Goldman Sachs Bank USA, Member FDIC",
    "Statement Period   05/01/2026 to 05/31/2026",
    "Account Number   300100008888",
    "05/01/2026\tBeginning Balance   $1,000.00",
    "05/12/2026\tACHWithdrawalInternettransfertoEXAMPLE BANK   $200.00   $800.00",
    "05/31/2026\tInterestPaid   $2.75   $802.75",
    "05/31/2026\tEndingBalance   $802.75",
]


def stored(session) -> list[tuple]:
    rows = sorted(list_transactions(session), key=lambda item: item.id)
    return [
        (r.posted_date, r.transaction_date, r.amount_cents, r.description, r.section) for r in rows
    ]


def test_a_truist_pdf_is_imported(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Checking", "Truist", "checking", last4="7777")
        result = import_statement(session, filename="truist-may.pdf", content=make_pdf([TRUIST]))
    assert result == StatementImportResult(
        filename="truist-may.pdf",
        status=ImportStatus.IMPORTED,
        message="imported",
        parser_name="truist_deposit",
        account_name="Test Checking",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        lines_parsed=3,
        inserted=3,
        duplicates=0,
    )
    with session_scope(db_engine) as session:
        assert stored(session) == [
            (date(2026, 5, 6), None, -7500, "CHECK 2001", "checks"),
            (
                date(2026, 5, 4),
                date(2026, 5, 2),
                -3175,
                "DEBIT CARD PURCHASE ACME GROCERY 05-02 DECATUR GA 4242",
                "withdrawals",
            ),
            (
                date(2026, 5, 15),
                None,
                25000,
                "ACH CORP CREDIT PAYROLL EXAMPLE EMPLOYER",
                "deposits",
            ),
        ]
        rows = sorted(list_transactions(session), key=lambda item: item.id)
        assert [(r.card_last4, r.external_id) for r in rows] == [
            (None, "2001"),
            ("4242", None),
            (None, None),
        ]
        assert latest_balance(session, 1).balance_cents == 64325


def test_a_marcus_pdf_is_imported(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Savings", "Marcus by Goldman Sachs", "savings", last4="8888")
        result = import_statement(session, filename="marcus-may.pdf", content=make_pdf([MARCUS]))
    assert result == StatementImportResult(
        filename="marcus-may.pdf",
        status=ImportStatus.IMPORTED,
        message="imported",
        parser_name="marcus_savings",
        account_name="Test Savings",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        lines_parsed=2,
        inserted=2,
        duplicates=0,
    )
    with session_scope(db_engine) as session:
        assert stored(session) == [
            (
                date(2026, 5, 12),
                None,
                -20000,
                "ACHWithdrawalInternettransfertoEXAMPLE BANK",
                "withdrawals",
            ),
            (date(2026, 5, 31), None, 275, "InterestPaid", "interest"),
        ]
        assert latest_balance(session, 1).balance_cents == 80275


def test_a_marcus_statement_whose_amounts_disagree_is_not_imported(
    db_engine: Engine, make_pdf
) -> None:
    lines = [line.replace("$200.00   $800.00", "$201.00   $800.00") for line in MARCUS]
    with session_scope(db_engine) as session:
        create_account(session, "Test Savings", "Marcus by Goldman Sachs", "savings", last4="8888")
        result = import_statement(session, filename="bad.pdf", content=make_pdf([lines]))
        assert list_transactions(session) == []
    assert result.status is ImportStatus.FAILED
    assert result.message == "marcus: row 1 does not match its balance"


def test_five_banks_are_told_apart(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Checking", "Truist", "checking", last4="7777")
        create_account(session, "Test Savings", "Marcus by Goldman Sachs", "savings", last4="8888")
        first = import_statement(session, filename="a.pdf", content=make_pdf([TRUIST]))
        second = import_statement(session, filename="b.pdf", content=make_pdf([MARCUS]))
    assert (first.parser_name, first.account_name) == ("truist_deposit", "Test Checking")
    assert (second.parser_name, second.account_name) == ("marcus_savings", "Test Savings")
