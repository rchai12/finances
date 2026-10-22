import ast
from datetime import UTC, date, datetime
from pathlib import Path

import finances.views
from finances.analysis.categories import (
    RuleListing,
    TransactionFacts,
    UncategorizedItem,
    card_credit_count,
)
from finances.analysis.listings import AccountListing, PersonListing
from finances.analysis.refunds import RefundFacts
from finances.domain.models import (
    MANUAL,
    Account,
    AccountType,
    Category,
    CategoryAssignment,
    CategoryRule,
    DataSource,
    Transaction,
)
from finances.views.accounts import AccountRow, account_rows
from finances.views.categories import (
    CategoryLine,
    RuleLine,
    TransactionDetail,
    UncategorizedLine,
    card_credits_note,
    category_choices,
    category_lines,
    rule_lines,
    transaction_detail,
    uncategorized_lines,
)
from finances.views.people import PersonRow, people_rows
from finances.views.refunds import RefundLine, RefundView, refund_view, refunded_lines

VIEWS = Path(finances.views.__file__).parent
STILL_LOADING = {"backups.py", "sync.py", "transfers.py"}
CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
CARD = Account(1, "Test Card", "Test Bank", AccountType.CREDIT_CARD, "USD", "1111", True, CREATED)
CHECKING = Account(
    2, "Test Checking", "Test Bank", AccountType.CHECKING, "USD", None, False, CREATED
)
FOOD = Category(1, "Food", None, False, False, False)
GROCERIES = Category(2, "Groceries", 1, False, False, False)
INCOME = Category(3, "Income", None, False, True, False)
PAYCHECK = Category(4, "Paycheck", 3, False, True, False)


def transaction(id: int, account: int, cents: int, *, card: str | None = None) -> Transaction:
    return Transaction(
        id,
        account,
        None,
        date(2026, 5, id),
        None,
        cents,
        "SQ *ACME COFFEE #12",
        None,
        card,
        None,
        None,
        DataSource.STATEMENT,
        False,
        f"t{id:02d}".ljust(64, "0"),
        CREATED,
    )


def test_account_rows_from_a_listing() -> None:
    listing = [AccountListing(CARD, "Alex"), AccountListing(CHECKING, None)]
    assert account_rows(listing) == [
        AccountRow("Test Card", "Test Bank", "credit_card", "••1111", "yes", "Alex"),
        AccountRow("Test Checking", "Test Bank", "checking", "", "no", ""),
    ]


def test_people_rows_from_a_listing() -> None:
    listing = [PersonListing("Alex", ["Test Card", "Test Old Card"], ["A DOE", "ALEX DOE"])]
    assert people_rows(listing) == [
        PersonRow("Alex", "Test Card, Test Old Card", "A DOE, ALEX DOE")
    ]


def test_the_category_tree_as_lines_and_choices() -> None:
    tree = [(FOOD, [GROCERIES]), (INCOME, [PAYCHECK])]
    assert category_lines(tree) == [
        CategoryLine("Food", "Groceries", ""),
        CategoryLine("Income", "Paycheck", "income"),
    ]
    assert category_choices(tree) == [("Food", ["Groceries"]), ("Income", ["Paycheck"])]


def test_rule_lines_from_a_listing() -> None:
    rule = CategoryRule(7, "ACME COFFEE", "contains", 5, 2)
    assert rule_lines([RuleListing(rule, "Groceries")]) == [
        RuleLine("7", "5", "contains", "ACME COFFEE", "Groceries")
    ]


def test_uncategorized_lines_and_the_card_note() -> None:
    items = [
        UncategorizedItem(transaction(3, 1, 599), CARD),
        UncategorizedItem(transaction(4, 1, -599), CARD),
        UncategorizedItem(transaction(5, 2, 2500), CHECKING),
    ]
    assert uncategorized_lines(items[:1]) == [
        UncategorizedLine("3", "2026-05-03", "Test Card", "ACME COFFEE", "$5.99")
    ]
    assert card_credit_count(items) == 1
    assert card_credits_note(1) == (
        "Money in on a card: 1, likely a refund or a card payment."
        " Set a category, or pair it on the Transfers page."
    )
    assert card_credits_note(0) is None


def test_the_detail_of_a_transaction() -> None:
    assignment = CategoryAssignment(3, 2, MANUAL, None)
    facts = TransactionFacts(
        transaction(3, 1, -2599, card="4321"), "Test Card", "Groceries", assignment
    )
    assert transaction_detail(facts) == TransactionDetail(
        3,
        "2026-05-03",
        "Test Card",
        "SQ *ACME COFFEE #12",
        "ACME COFFEE",
        "-$25.99",
        "••4321",
        "Groceries",
        "by hand",
    )


def test_the_refund_sections() -> None:
    purchase = transaction(2, 1, -2599)
    refund = RefundFacts(True, purchase, [])
    assert refund_view(refund, "$5.99") == RefundView(
        "$5.99", RefundLine(2, "2026-05-02", "-$25.99")
    )
    assert refund_view(RefundFacts(True, None, []), "$5.99") == RefundView("$5.99", None)
    assert refund_view(RefundFacts(False, None, [transaction(9, 1, 599)]), "-$25.99") is None
    assert refunded_lines(RefundFacts(False, None, [transaction(9, 1, 599)])) == [
        RefundLine(9, "2026-05-09", "$5.99")
    ]


def test_only_the_frozen_views_still_load_data() -> None:
    loading = set()
    for path in VIEWS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                if name.startswith(("finances.db", "finances.sync", "keyring", "sqlalchemy")):
                    loading.add(path.name)
    assert loading <= STILL_LOADING
    assert {"accounts.py", "people.py", "categories.py", "refunds.py"}.isdisjoint(loading)
