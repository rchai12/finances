from datetime import UTC, date, datetime

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, propose_category, set_category_by_hand
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, run, table_rows

HEADINGS = ["ID", "Date", "Account", "Description", "Amount", "Now", "Proposed", "Reason", "State"]


@pytest.fixture
def proposed(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Two coffees on a card with the agent's proposals (1 and 2)."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, description in ((1, "ACME COFFEE"), (2, "BAZ CAFE")):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=-500,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
        propose_category(session, 2, "Dining", "BAZ CAFE serves lunch")
    engine.dispose()
    return tmp_settings


def test_the_open_proposals(proposed: Settings) -> None:
    result = run("review", "list")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        HEADINGS,
        [
            "2",
            "2026-05-02",
            "Test Card",
            "BAZ CAFE",
            "-$5.00",
            "",
            "Dining",
            "BAZ CAFE serves lunch",
            "open",
        ],
        [
            "1",
            "2026-05-01",
            "Test Card",
            "ACME COFFEE",
            "-$5.00",
            "",
            "Coffee & Dessert",
            "ACME is a coffee shop",
            "open",
        ],
    ]


def test_accepting_and_declining(proposed: Settings) -> None:
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: Coffee & Dessert for transaction 1.\n",
    )
    declined = run("review", "decline", "--id", "2")
    assert (declined.exit_code, declined.stdout) == (0, "Declined proposal 2.\n")
    assert run("review", "list").stdout == "No open proposals.\n"
    assert [row[1:] for row in table_rows(run("audit", "--limit", "3").stdout)[1:]] == [
        ["person", "proposal_declined", "proposal 2", "", "transaction 2: Dining"],
        ["person", "proposal_accepted", "proposal 1", "", "transaction 1: Coffee & Dessert"],
        ["person", "category_set", "transaction 1", "", "Coffee & Dessert"],
    ]


def test_an_out_of_date_proposal_shows_and_is_refused(proposed: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        set_category_by_hand(session, 1, "Dining")
    engine.dispose()
    rows = table_rows(run("review", "list").stdout)
    assert rows[2][5:] == ["Dining", "Coffee & Dessert", "ACME is a coffee shop", "out of date"]
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the transaction was decided since",
    )


def test_all_or_none(proposed: Settings) -> None:
    assert failed_cleanly(run("review", "accept", "--id", "2", "--id", "9"), "proposal not found")
    assert len(table_rows(run("review", "list").stdout)) == 3


def test_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("review", "list")
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)
