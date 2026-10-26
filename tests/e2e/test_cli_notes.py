from datetime import UTC, datetime

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import log_advice
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, plain_lines, run, table_rows

HEADINGS = ["ID", "When (UTC)", "Subject", "Note", "State"]


@pytest.fixture
def notes(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Note 1 (budgets) at 12:00 and note 2 (no subject) at 12:05; no proposals."""
    stamps = iter([datetime(2026, 5, 25, 12, minute, tzinfo=UTC) for minute in (0, 5)])
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: next(stamps))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        log_advice(session, "Suggested a coffee budget.", "budgets")
        log_advice(session, "Watch ACME COFFEE.")
    engine.dispose()
    return tmp_settings


def test_the_list_shows_the_notes_after_the_proposals(notes: Settings) -> None:
    listed = run("review", "list")
    assert listed.exit_code == 0
    assert plain_lines(listed.stdout) == ["No open proposals.", "Notes:"]
    assert table_rows(listed.stdout) == [
        HEADINGS,
        ["2", "2026-05-25 12:05", "", "Watch ACME COFFEE.", ""],
        ["1", "2026-05-25 12:00", "budgets", "Suggested a coffee budget.", ""],
    ]


def test_with_no_notes_the_list_is_as_before(tmp_settings: Settings) -> None:
    upgrade_to_head()
    assert run("review", "list").stdout == "No open proposals.\n"


def test_dismissing_a_note(notes: Settings) -> None:
    dismissed = run("review", "dismiss-note", "--id", "1")
    assert (dismissed.exit_code, dismissed.stdout) == (0, "Dismissed note 1.\n")
    rows = table_rows(run("review", "list").stdout)
    assert [row[0] + " " + row[4] for row in rows[1:]] == ["2 ", "1 dismissed"]


@pytest.mark.parametrize(
    ("ids", "message"),
    [
        (["9"], "note not found"),
        (["1", "1"], "note 1 is already dismissed"),
    ],
)
def test_a_refused_dismissal(notes: Settings, ids: list[str], message: str) -> None:
    for proposal_id in ids[:-1]:
        run("review", "dismiss-note", "--id", proposal_id)
    assert failed_cleanly(run("review", "dismiss-note", "--id", ids[-1]), message)


def test_dismiss_note_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("review", "dismiss-note", "--id", "1")
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)
