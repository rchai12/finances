from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, list_categories, list_category_assignments
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, plain_lines, run, table_rows

LINE = "Categorized 4 transactions: {} changed, {} without a category."


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """Card: 1 and 2 coffee, 3 groceries; checking: 4 a paycheck. Rule 1 ACME COFFEE to
    Coffee & Dessert, rule 2 FOOBAR to Groceries; 4 is set to Dining by hand."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        for number, (account, cents, description) in enumerate(
            (
                (card, -450, "SQ *ACME COFFEE"),
                (card, -500, "ACME COFFEE #12"),
                (card, -2599, "FOOBAR GROCERY #77"),
                (checking, 300000, "PAYCHECK EXAMPLE CORP"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    assert (
        run("rules", "add", "--pattern", "ACME COFFEE", "--category", "Coffee & Dessert").exit_code
        == 0
    )
    assert run("rules", "add", "--pattern", "FOOBAR", "--category", "Groceries").exit_code == 0
    assert run("transactions", "set-category", "--id", "4", "--category", "Dining").exit_code == 0
    return tmp_settings


def categories_of() -> dict[int, str]:
    """Each categorized transaction's category name."""
    engine = get_engine()
    with session_scope(engine) as session:
        names = {category.id: category.name for category in list_categories(session)}
        found = {
            transaction_id: names[assignment.category_id]
            for transaction_id, assignment in list_category_assignments(session).items()
        }
    engine.dispose()
    return found


@pytest.mark.parametrize(
    "args",
    [
        ("categories", "rename", "--name", "Dining", "--to", "Eating out"),
        ("categories", "delete", "--name", "Gaming"),
        ("rules", "edit", "--id", "1", "--priority", "2"),
    ],
)
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


# Categories


def test_rename_a_category_and_a_group(money: Settings) -> None:
    result = run("categories", "rename", "--name", "coffee & dessert", "--to", " Coffee ")
    assert (result.exit_code, result.stdout) == (0, 'Renamed "Coffee & Dessert" to "Coffee".\n')
    assert table_rows(run("rules", "list").stdout)[1][4] == "Coffee"
    assert categories_of()[1] == "Coffee"
    result = run("categories", "rename", "--name", "food", "--to", "Eating")
    assert result.stdout == 'Renamed "Food" to "Eating".\n'
    assert ["Eating", "Dining", ""] in table_rows(run("categories", "list").stdout)
    assert run("categories", "rename", "--name", "dining", "--to", "DINING").stdout == (
        'Renamed "Dining" to "DINING".\n'
    )


@pytest.mark.parametrize(
    ("name", "to", "message"),
    [
        ("Nope", "Other", "category not found"),
        ("Dining", "groceries", "a category with this name already exists"),
        ("Dining", "food", "a category with this name already exists"),
        ("Dining", "  ", "a category name must be 1 to 50 characters"),
        ("Dining", "N" * 51, "a category name must be 1 to 50 characters"),
    ],
)
def test_a_refused_rename(money: Settings, name: str, to: str, message: str) -> None:
    assert failed_cleanly(run("categories", "rename", "--name", name, "--to", to), message)


def test_delete_an_unused_category_and_an_empty_group(money: Settings) -> None:
    assert run("categories", "delete", "--name", "gaming").stdout == 'Deleted category "Gaming".\n'
    result = run("categories", "delete", "--name", "Subscriptions & Digital")
    assert result.stdout == 'Deleted category "Subscriptions & Digital".\n'
    assert run("categories", "delete", "--name", "subscriptions").stdout == (
        'Deleted group "Subscriptions".\n'
    )
    names = [row[1] for row in table_rows(run("categories", "list").stdout)[1:]]
    assert "Gaming" not in names and "Subscriptions & Digital" not in names
    assert "Subscriptions" not in [row[0] for row in table_rows(run("categories", "list").stdout)]


def test_a_category_in_use_moves_before_it_goes(money: Settings) -> None:
    assert failed_cleanly(
        run("categories", "delete", "--name", "Coffee & Dessert"),
        "Coffee & Dessert is in use (transactions: 2, rules: 1); choose a category to move them to",
    )
    result = run("categories", "delete", "--name", "Coffee & Dessert", "--move-to", "dining")
    assert (result.exit_code, result.stdout) == (
        0,
        'Deleted category "Coffee & Dessert"; moved its transactions (2) and rules (1)'
        ' to "Dining".\n',
    )
    assert categories_of() == {1: "Dining", 2: "Dining", 3: "Groceries", 4: "Dining"}
    assert table_rows(run("rules", "list").stdout)[1] == [
        "1",
        "0",
        "contains",
        "ACME COFFEE",
        "Dining",
    ]
    assert run("categorize").stdout == LINE.format(0, 0) + "\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--name", "Nope"), "category not found"),
        (("--name", "Food"), "a group can be deleted only when it has no categories"),
        (("--name", "Dining", "--move-to", "dining"), "a category cannot be moved to itself"),
        (
            ("--name", "Dining", "--move-to", "Food"),
            "rules and transactions take a category, not a group",
        ),
        (("--name", "Dining", "--move-to", "Nope"), "category not found"),
    ],
)
def test_a_refused_delete(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("categories", "delete", *args), message)
    assert categories_of()[4] == "Dining"


# Rules


def test_edit_a_rule_and_the_rules_run_again(money: Settings) -> None:
    result = run("rules", "edit", "--id", "2", "--category", "dining")
    assert (result.exit_code, result.stdout) == (
        0,
        'Changed rule 2: contains "FOOBAR" -> Dining.\n' + LINE.format(1, 0) + "\n",
    )
    assert categories_of()[3] == "Dining"
    result = run("rules", "edit", "--id", "2", "--priority", "7", "--pattern", " foobar ")
    assert (
        result.stdout == 'Changed rule 2: contains "FOOBAR" -> Dining.\n' + LINE.format(0, 0) + "\n"
    )
    assert table_rows(run("rules", "list").stdout)[1] == ["2", "7", "contains", "FOOBAR", "Dining"]
    result = run("rules", "edit", "--id", "2", "--match", "equals", "--pattern", "FOOBAR GROCERY")
    assert plain_lines(result.stdout) == [
        'Changed rule 2: equals "FOOBAR GROCERY" -> Dining.',
        LINE.format(0, 0),
    ]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--id", "9", "--priority", "1"), "rule not found"),
        (
            (
                "--id",
                "2",
            ),
            "give at least one of --pattern, --match, --priority, --category",
        ),
        (
            ("--id", "2", "--pattern", "acme coffee"),
            "a rule with this pattern and match already exists",
        ),
        (("--id", "2", "--match", "regex"), "match must be one of: contains, starts_with, equals"),
        (
            ("--id", "2", "--category", "Food"),
            "rules and transactions take a category, not a group",
        ),
    ],
)
def test_a_refused_rule_edit(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("rules", "edit", *args), message)
    assert table_rows(run("rules", "list").stdout)[2] == [
        "2",
        "0",
        "contains",
        "FOOBAR",
        "Groceries",
    ]
