import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
ADD = ["accounts", "add", "--name", "Test Checking", "--institution", "Test Bank"]


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 0
    return tmp_settings


def stored(settings: Settings) -> list[tuple]:
    engine = get_engine(settings.effective_database_url)
    with session_scope(engine) as session:
        rows = session.scalars(select(AccountRow).order_by(AccountRow.id)).all()
        found = [(r.name, r.institution, r.type, r.currency, r.last4, r.is_active) for r in rows]
    engine.dispose()
    return found


def deactivate(settings: Settings, name: str) -> None:
    engine = get_engine(settings.effective_database_url)
    with session_scope(engine) as session:
        session.scalars(select(AccountRow).where(AccountRow.name == name)).one().is_active = False
    engine.dispose()


def add(name: str, account_type: str = "checking", last4: str | None = None) -> None:
    args = ["accounts", "add", "--name", name, "--institution", "Test Bank", "--type", account_type]
    if last4 is not None:
        args += ["--last4", last4]
    result = runner.invoke(app, args)
    assert result.exit_code == 0


def test_accounts_add_stores_the_account(migrated: Settings) -> None:
    result = runner.invoke(app, [*ADD, "--type", "checking"])
    assert result.exit_code == 0
    assert result.stdout == 'Added account "Test Checking" (id 1)\n'
    assert stored(migrated) == [("Test Checking", "Test Bank", "checking", "USD", None, True)]


def test_accounts_add_takes_currency_and_last4(migrated: Settings) -> None:
    args = [*ADD, "--type", "credit_card", "--currency", "CAD", "--last4", "0042"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    assert stored(migrated) == [("Test Checking", "Test Bank", "credit_card", "CAD", "0042", True)]


def test_accounts_add_numbers_accounts_in_order(migrated: Settings) -> None:
    add("First")
    result = runner.invoke(app, [*ADD, "--type", "savings"])
    assert result.stdout == 'Added account "Test Checking" (id 2)\n'


def test_accounts_add_shows_the_stored_name(migrated: Settings) -> None:
    args = [
        "accounts",
        "add",
        "--name",
        "  Spaced  ",
        "--institution",
        "Test Bank",
        "--type",
        "other",
    ]
    result = runner.invoke(app, args)
    assert result.stdout == 'Added account "Spaced" (id 1)\n'


def test_accounts_add_rejects_a_duplicate_name(migrated: Settings) -> None:
    add("Test Checking")
    result = runner.invoke(
        app, ["accounts", "add", "--name", "test checking", "--institution", "X", "--type", "other"]
    )
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == "Error: an account with this name already exists\n"
    assert result.stdout == ""
    assert len(stored(migrated)) == 1


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--last4", "12a4", "last4 must be exactly 4 digits"),
        ("--last4", "12345", "last4 must be exactly 4 digits"),
        ("--name", "   ", "account name must not be empty"),
        ("--institution", "", "institution must not be empty"),
    ],
)
def test_accounts_add_reports_bad_input(
    migrated: Settings, option: str, value: str, message: str
) -> None:
    result = runner.invoke(app, [*ADD, "--type", "checking", option, value])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == f"Error: {message}\n"
    assert result.stdout == ""
    assert stored(migrated) == []


def test_accounts_add_rejects_an_unknown_type(migrated: Settings) -> None:
    result = runner.invoke(app, [*ADD, "--type", "brokerage"])
    assert result.exit_code == 2
    assert stored(migrated) == []


def test_accounts_add_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = runner.invoke(app, [*ADD, "--type", "checking"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == NOT_MIGRATED
    assert result.stdout == ""


def test_accounts_list_says_when_there_are_none(migrated: Settings) -> None:
    result = runner.invoke(app, ["accounts", "list"])
    assert result.exit_code == 0
    assert result.stdout == "No accounts.\n"


def test_accounts_list_shows_a_table(migrated: Settings) -> None:
    add("Test Card", "credit_card", "0042")
    result = runner.invoke(app, ["accounts", "list"])
    assert result.exit_code == 0
    for heading in ["Name", "Institution", "Type", "Last 4", "Active"]:
        assert heading in result.stdout
    for cell in ["Test Card", "Test Bank", "credit_card", "••0042", "yes"]:
        assert cell in result.stdout
    assert "No accounts." not in result.stdout


def test_accounts_list_leaves_last4_empty_when_unknown(migrated: Settings) -> None:
    add("No Digits")
    result = runner.invoke(app, ["accounts", "list"])
    assert "No Digits" in result.stdout
    assert "•" not in result.stdout
    assert "None" not in result.stdout


def test_accounts_list_is_sorted_by_name(migrated: Settings) -> None:
    for name in ["cherry", "Banana", "apple"]:
        add(name)
    output = runner.invoke(app, ["accounts", "list"]).stdout
    assert output.index("apple") < output.index("Banana") < output.index("cherry")


def test_accounts_list_hides_inactive_accounts(migrated: Settings) -> None:
    add("Open Account")
    add("Closed Account")
    deactivate(migrated, "Closed Account")
    result = runner.invoke(app, ["accounts", "list"])
    assert "Open Account" in result.stdout
    assert "Closed Account" not in result.stdout


def test_accounts_list_all_shows_inactive_accounts(migrated: Settings) -> None:
    add("Open Account")
    add("Closed Account")
    deactivate(migrated, "Closed Account")
    result = runner.invoke(app, ["accounts", "list", "--all"])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    closed = next(line for line in lines if "Closed Account" in line)
    opened = next(line for line in lines if "Open Account" in line)
    assert "no" in closed.split("Test Bank")[1]
    assert "yes" in opened.split("Test Bank")[1]


def test_accounts_list_says_none_when_all_are_inactive(migrated: Settings) -> None:
    add("Closed Account")
    deactivate(migrated, "Closed Account")
    assert runner.invoke(app, ["accounts", "list"]).stdout == "No accounts.\n"


def test_accounts_list_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = runner.invoke(app, ["accounts", "list"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == NOT_MIGRATED
    assert result.stdout == ""
