from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, set_category_by_hand, set_split
from tests.support import failed_cleanly, plain_lines, run, table_rows

HEADINGS = ["Spent", "Refunds", "Net", "Count"]
GROUPS = [
    ["Group", *HEADINGS],
    ["Health", "$130.00", "$20.00", "$110.00", "3"],
    ["Personal", "$51.00", "$0.00", "$51.00", "2"],
    ["Food", "$20.00", "$0.00", "$20.00", "1"],
]
CATEGORIES = [
    ["Category", *HEADINGS],
    ["Medical", "$130.00", "$20.00", "$110.00", "3"],
    ["Gifts & Donations", "$51.00", "$0.00", "$51.00", "2"],
    ["Groceries", "$20.00", "$0.00", "$20.00", "1"],
]
TAX = [
    ["Category", *HEADINGS],
    ["Gifts & Donations", "$51.00", "$0.00", "$51.00", "2"],
    ["Medical", "$130.00", "$20.00", "$110.00", "3"],
    ["Taxes", "$0.00", "$0.00", "$0.00", "0"],
]


@pytest.fixture
def year(tmp_settings: Settings) -> Settings:
    """2026 on a card: Medical -$120.00 and a refund of $20.00; Gifts & Donations -$50.00 and
    -$1.00 on the year's last day; -$30.00 split into Groceries -$20.00 and Medical -$10.00; a
    paycheck of $3,000.00. Medical -$99.99 on 2025-12-31 is the year before."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 2, 10), -12000, "ACME CLINIC", "Medical"),
            (date(2026, 3, 5), -5000, "BAZ CHARITY", "Gifts & Donations"),
            (date(2026, 4, 1), -3000, "FOOBAR GROCERY", None),
            (date(2026, 5, 1), 2000, "ACME CLINIC", "Medical"),
            (date(2026, 6, 1), 300000, "PAYCHECK EXAMPLE CORP", "Paycheck"),
            (date(2025, 12, 31), -9999, "ACME CLINIC", "Medical"),
            (date(2026, 12, 31), -100, "BAZ CHARITY", "Gifts & Donations"),
        ]
        for number, (day, cents, description, _) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for number, (_, _, _, category) in enumerate(rows, start=1):
            if category is not None:
                set_category_by_hand(session, number, category)
        set_split(session, 3, [(-2000, "Groceries"), (-1000, "Medical")])
    engine.dispose()
    return tmp_settings


def test_a_year(year: Settings) -> None:
    result = run("year", "--year", "2026")
    assert result.exit_code == 0
    assert plain_lines(result.stdout) == [
        "Year 2026, from 2026-01-01 to 2026-12-31.",
        "By group:",
        "By category:",
        "Tax-relevant:",
        "Spent: $201.00. Refunds: $20.00. Net: $181.00. Income: $3,000.00.",
        "Transfers left out: 0.",
    ]
    assert table_rows(result.stdout) == [*GROUPS, *CATEGORIES, *TAX]


def test_this_year_by_default(year: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("finances.clock.today", lambda: date(2024, 8, 1))
    assert plain_lines(run("year").stdout)[0] == "Year 2024, from 2024-01-01 to 2024-12-31."


def test_a_year_with_nothing(year: Settings) -> None:
    result = run("year", "--year", "2024")
    assert plain_lines(result.stdout) == [
        "Year 2024, from 2024-01-01 to 2024-12-31.",
        "By group:",
        "No spending.",
        "By category:",
        "No spending.",
        "Tax-relevant:",
        "Spent: $0.00. Refunds: $0.00. Net: $0.00. Income: $0.00.",
        "Transfers left out: 0.",
    ]
    assert table_rows(result.stdout) == [
        ["Category", *HEADINGS],
        ["Gifts & Donations", "$0.00", "$0.00", "$0.00", "0"],
        ["Medical", "$0.00", "$0.00", "$0.00", "0"],
        ["Taxes", "$0.00", "$0.00", "$0.00", "0"],
    ]


def test_marking_a_category(year: Settings) -> None:
    on = run("categories", "tax", "--name", "groceries")
    assert (on.exit_code, on.stdout) == (0, "Groceries is tax-relevant.\n")
    off = run("categories", "tax", "--name", "Taxes", "--off")
    assert (off.exit_code, off.stdout) == (0, "Taxes is not tax-relevant.\n")
    assert table_rows(run("year", "--year", "2026").stdout)[-3:] == [
        ["Gifts & Donations", "$51.00", "$0.00", "$51.00", "2"],
        ["Groceries", "$20.00", "$0.00", "$20.00", "1"],
        ["Medical", "$130.00", "$20.00", "$110.00", "3"],
    ]


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("Health", "a group cannot be tax-relevant; mark its categories"),
        ("Nope", "category not found"),
    ],
)
def test_marking_refused(year: Settings, name: str, message: str) -> None:
    assert failed_cleanly(run("categories", "tax", "--name", name), message)
