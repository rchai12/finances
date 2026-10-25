import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import get_category_by_name
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, run, table_rows

BOTH = "a group is for transfers or for income, not both"
TAKEN = "a category with this name already exists"


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    upgrade_to_head()
    return tmp_settings


def flags(name: str) -> tuple[bool, bool, bool, bool, bool]:
    """Whether the row is a group, and its transfer, income, sensitive, and tax flags."""
    engine = get_engine()
    with session_scope(engine) as session:
        found = get_category_by_name(session, name)
    engine.dispose()
    assert found is not None
    return (
        found.group_id is None,
        found.is_transfer,
        found.is_income,
        found.is_sensitive,
        found.is_tax,
    )


def test_a_spending_group(migrated: Settings) -> None:
    result = run("categories", "add-group", "--name", "Pets")
    assert (result.exit_code, result.output) == (0, 'Added group "Pets".\n')
    assert flags("Pets") == (True, False, False, False, False)


def test_a_group_with_flags(migrated: Settings) -> None:
    result = run("categories", "add-group", "--name", "Side Gigs", "--income", "--sensitive")
    assert (result.exit_code, result.output) == (
        0,
        'Added group "Side Gigs" (income, sensitive).\n',
    )
    assert flags("Side Gigs") == (True, False, True, True, False)


def test_a_category_takes_its_new_groups_flags(migrated: Settings) -> None:
    run("categories", "add-group", "--name", "Between Banks", "--transfer")
    result = run("categories", "add", "--name", "Wire Out", "--group", "Between Banks")
    assert (result.exit_code, result.output) == (0, 'Added category "Wire Out" to Between Banks.\n')
    assert flags("Wire Out") == (False, True, False, False, False)


def test_an_empty_group_is_listed(migrated: Settings) -> None:
    run("categories", "add-group", "--name", "Pets", "--sensitive")
    rows = table_rows(run("categories", "list").output)
    assert ["Pets", "", "sensitive"] in rows
    run("categories", "add", "--name", "Dog Food", "--group", "Pets")
    rows = table_rows(run("categories", "list").output)
    assert ["Pets", "Dog Food", "sensitive"] in rows
    assert ["Pets", "", "sensitive"] not in rows


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--name", "Moves", "--transfer", "--income"], BOTH),
        (["--name", "Food"], TAKEN),
        (["--name", "Groceries"], TAKEN),
        (["--name", "x" * 51], "a group name must be 1 to 50 characters"),
        (["--name", "   "], "a group name must be 1 to 50 characters"),
    ],
)
def test_a_refused_group(migrated: Settings, arguments: list[str], message: str) -> None:
    assert failed_cleanly(run("categories", "add-group", *arguments), message)


def test_both_kinds_are_refused_before_a_taken_name(migrated: Settings) -> None:
    result = run("categories", "add-group", "--name", "Food", "--transfer", "--income")
    assert failed_cleanly(result, BOTH)


def test_add_group_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("categories", "add-group", "--name", "Pets")
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)
