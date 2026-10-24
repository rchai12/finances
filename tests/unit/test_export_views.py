from datetime import UTC, date, datetime

from finances.analysis.export import ExportLine
from finances.analysis.search import FoundTransaction
from finances.analysis.spending import SpendingReport
from finances.analysis.yearend import YearReport
from finances.domain.models import DataSource, Transaction
from finances.domain.spending import (
    UNASSIGNED,
    UNCATEGORIZED,
    Flow,
    SpendingLine,
    SpendingSummary,
)
from finances.views.export import spending_csv, transactions_csv, year_csv

CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
EMPTY = SpendingSummary(0, 0, 0, 0, 0, 0)
BACK = SpendingLine("Refunds", -500, 1, 500)


def _transaction(*, description: str, last4: str | None) -> Transaction:
    return Transaction(
        1,
        1,
        None,
        date(2026, 5, 1),
        None,
        -1234,
        description,
        None,
        last4,
        None,
        None,
        DataSource.STATEMENT,
        False,
        "t01".ljust(64, "0"),
        CREATED,
    )


def test_a_quoted_description_blanks_a_card_and_two_tags() -> None:
    found = FoundTransaction(
        _transaction(description='He said "hello, there"', last4="4321"),
        Flow(
            -1234,
            date(2026, 5, 1),
            "spending",
            UNCATEGORIZED,
            UNCATEGORIZED,
            "ACME COFFEE",
            UNASSIGNED,
            "Test Card",
            "Test Bank",
            "4321",
        ),
        None,
    )
    text = transactions_csv([ExportLine(found, "Test Card", ["a", "b"], None)])
    assert text == (
        "ID,Posted,Date,Account,Description,Merchant,Category,Group,Kind,Amount,Card,"
        "Person,Part,Tags,Note\r\n"
        '1,2026-05-01,2026-05-01,Test Card,"He said ""hello, there""",ACME COFFEE,,,'
        "spending,-12.34,\u2022\u20224321,,,a; b,\r\n"
    )


def test_year_and_spending_csv_write_money_back() -> None:
    year = YearReport(2026, date(2026, 1, 1), date(2026, 12, 31), EMPTY, [BACK], [BACK], [BACK])
    spending = SpendingReport(date(2026, 5, 1), date(2026, 5, 31), "category", [BACK], EMPTY)
    amounts = "Refunds,0.00,5.00,-5.00,1\r\n"
    assert year_csv(year) == (
        f"Section,Label,Spent,Refunds,Net,Count\r\ngroup,{amounts}category,{amounts}tax,{amounts}"
    )
    assert spending_csv(spending) == (f"Category,Spent,Refunds,Net,Count\r\n{amounts}")
