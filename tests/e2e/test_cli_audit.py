from datetime import UTC, datetime

import pytest

from finances.config import Settings
from tests.support import failed_cleanly, run, table_rows

HEADINGS = ["When (UTC)", "Who", "Action", "Record", "Before", "After"]


@pytest.fixture
def changed(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr(
        "finances.db.repositories.audit._now", lambda: datetime(2026, 5, 25, 14, 3, 59, tzinfo=UTC)
    )
    assert run("db", "upgrade").exit_code == 0
    assert (
        run(
            "accounts",
            "add",
            "--name",
            "Test Card",
            "--institution",
            "Test Bank",
            "--type",
            "credit_card",
        ).exit_code
        == 0
    )
    assert run("people", "add", "--name", "Pat Example").exit_code == 0
    assert run("budgets", "set", "--name", "Groceries", "--amount", "150").exit_code == 0
    return tmp_settings


def test_every_change_newest_first(changed: Settings) -> None:
    result = run("audit")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        HEADINGS,
        ["2026-05-25 14:03", "person", "budget_set", "category 13", "", "$150.00"],
        ["2026-05-25 14:03", "person", "person_added", "person 1", "", "Pat Example"],
        ["2026-05-25 14:03", "person", "account_added", "account 1", "", "Test Card"],
    ]


def test_one_action_and_a_limit(changed: Settings) -> None:
    assert table_rows(run("audit", "--action", "person_added").stdout)[1:] == [
        ["2026-05-25 14:03", "person", "person_added", "person 1", "", "Pat Example"]
    ]
    assert len(table_rows(run("audit", "--limit", "2").stdout)) == 3


def test_nothing_since_a_later_day(changed: Settings) -> None:
    assert run("audit", "--since", "2026-05-26").stdout == "No changes recorded.\n"


UNKNOWN = (
    "action must be one of: account_added, account_renamed, account_closed, account_r"
    "eopened, owner_set, person_added, cardholder_set, category_added, category_renam"
    "ed, category_deleted, rule_added, rule_edited, rule_deleted, category_set, categ"
    "ory_cleared, budget_set, budget_removed, transfer_confirmed, transfer_rejected, "
    "transfer_unpaired, statement_imported, backup_deleted, backup_restored, proposal"
    "_accepted, proposal_declined, alias_added, alias_deleted, tag_added, tag_removed, "
    "note_set, note_cleared, split_set, split_cleared"
)


def test_an_unknown_action(changed: Settings) -> None:
    assert failed_cleanly(run("audit", "--action", "nope"), UNKNOWN)
