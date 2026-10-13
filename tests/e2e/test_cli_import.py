from pathlib import Path

import pytest
from sqlalchemy import func, select
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import StatementRow, TransactionRow

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
HEADINGS = ["File", "Parser", "Account", "Period", "Lines", "Inserted", "Duplicates", "Status"]
IMPORTED = (
    "File: january.pdf\n"
    "Parser: fake_bank\n"
    "Account: Test Card\n"
    "Period: 2026-01-01 to 2026-01-31\n"
    "Lines: 4\n"
    "Inserted: 4\n"
    "Duplicates: 0\n"
)
HINT = (
    'no account ends in 1111; add one with: fin accounts add --name "NAME" '
    '--institution "Fake Bank" --type credit_card --last4 1111'
)


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    """The cells of one row of a Rich table."""
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    """Every row of a Rich table, heading first."""
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def stored(settings: Settings) -> tuple[int, int]:
    engine = get_engine(settings.effective_database_url)
    with session_scope(engine) as session:
        found = (
            session.scalar(select(func.count()).select_from(StatementRow)),
            session.scalar(select(func.count()).select_from(TransactionRow)),
        )
    engine.dispose()
    return found


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


@pytest.fixture
def migrated(tmp_settings: Settings, fake_bank) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    return tmp_settings


@pytest.fixture
def with_card(migrated: Settings) -> Settings:
    args = ["--name", "Test Card", "--institution", "Fake Bank", "--type", "credit_card"]
    assert run("accounts", "add", *args, "--last4", "1111").exit_code == 0
    return migrated


@pytest.fixture
def january(tmp_path: Path, fake_statement_pdf) -> Path:
    path = tmp_path / "inbox" / "january.pdf"
    path.parent.mkdir()
    path.write_bytes(fake_statement_pdf())
    return path


def test_import_statement_stores_it_and_reports(with_card: Settings, january: Path) -> None:
    result = run("import", "statement", january)
    assert result.exit_code == 0
    assert result.stdout == IMPORTED + "Status: imported\n"
    assert result.stderr == ""
    assert stored(with_card) == (1, 4)


def test_import_statement_twice_says_already_imported(with_card: Settings, january: Path) -> None:
    run("import", "statement", january)
    result = run("import", "statement", january)
    assert result.exit_code == 0
    assert result.stdout == "File: january.pdf\nStatus: already imported\n"
    assert stored(with_card) == (1, 4)


def test_import_statement_dry_run_stores_nothing(with_card: Settings, january: Path) -> None:
    result = run("import", "statement", january, "--dry-run")
    assert result.exit_code == 0
    assert result.stdout == IMPORTED + "Status: dry run, nothing written\n"
    assert stored(with_card) == (0, 0)


def test_import_statement_counts_duplicates(
    with_card: Settings, january: Path, tmp_path: Path, fake_statement_pdf
) -> None:
    run("import", "statement", january)
    rows = (
        "2026-01-05|2026-01-04|purchases|-4.50|2222|-|ACME COFFEE #12",
        "2026-02-03|-|purchases|-10.00|-|-|FOOBAR BOOKS",
    )
    later = tmp_path / "february.pdf"
    later.write_bytes(
        fake_statement_pdf(start="2026-02-01", end="2026-02-28", closing="-114.50", rows=rows)
    )
    result = run("import", "statement", later)
    assert result.stdout == (
        "File: february.pdf\n"
        "Parser: fake_bank\n"
        "Account: Test Card\n"
        "Period: 2026-02-01 to 2026-02-28\n"
        "Lines: 2\n"
        "Inserted: 1\n"
        "Duplicates: 1\n"
        "Status: imported\n"
    )
    assert stored(with_card) == (2, 5)


def test_import_statement_into_a_named_account(migrated: Settings, january: Path) -> None:
    for name in ("First Card", "Second Card"):
        args = ["--name", name, "--institution", "Fake Bank", "--type", "credit_card"]
        run("accounts", "add", *args, "--last4", "1111")
    refused = run("import", "statement", january)
    message = "more than one account ends in these digits; name the account"
    assert failed_cleanly(refused, message)
    result = run("import", "statement", january, "--account", "second card")
    assert result.exit_code == 0
    assert "Account: Second Card\n" in result.stdout


@pytest.mark.parametrize(
    ("changes", "options", "message"),
    [
        ({"last4": "9999"}, [], HINT.replace("1111", "9999")),
        ({}, ["--account", "Nobody"], "account not found"),
        ({"closing": "-85.00"}, [], "statement does not reconcile: off by -1 cents"),
        (
            {"totals": ("purchases -1.00", "fees 0.00")},
            [],
            "statement does not reconcile: off by 0 cents; section totals differ: purchases",
        ),
    ],
)
def test_import_statement_reports_a_failure(
    with_card: Settings, tmp_path: Path, fake_statement_pdf, changes, options, message
) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(fake_statement_pdf(**changes))
    result = run("import", "statement", path, *options)
    assert failed_cleanly(result, message)
    assert stored(with_card) == (0, 0)


@pytest.mark.parametrize(
    ("content", "message"),
    [(b"not a pdf", "could not read PDF"), (None, "unrecognized statement format")],
)
def test_import_statement_reports_an_unusable_file(
    with_card: Settings, tmp_path: Path, make_pdf, content, message
) -> None:
    path = tmp_path / "odd.pdf"
    path.write_bytes(content or make_pdf([["SOME OTHER DOCUMENT"]]))
    assert failed_cleanly(run("import", "statement", path), message)


def test_import_statement_needs_an_existing_file(with_card: Settings, tmp_path: Path) -> None:
    assert run("import", "statement", tmp_path / "missing.pdf").exit_code == 2
    assert run("import", "statement", tmp_path).exit_code == 2
    assert run("import", "statement").exit_code == 2


def test_import_commands_need_a_migrated_database(
    tmp_settings: Settings, january: Path, fake_bank
) -> None:
    for args in (["statement", january], ["folder", january.parent]):
        result = run("import", *args)
        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert result.stderr == NOT_MIGRATED
        assert result.stdout == ""


def test_import_folder_shows_one_row_per_pdf(
    with_card: Settings, january: Path, fake_statement_pdf, make_pdf
) -> None:
    inbox = january.parent
    (inbox / "broken.pdf").write_bytes(b"not a pdf")
    (inbox / "copy of january.PDF").write_bytes(fake_statement_pdf(opening="-100.00 "))
    (inbox / "notes.txt").write_text("not a statement")
    result = run("import", "folder", inbox)
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert table_rows(result.stdout) == [
        HEADINGS,
        ["broken.pdf", "", "", "", "0", "0", "0", "failed"],
        [
            "copy of january.PDF",
            "fake_bank",
            "Test Card",
            "2026-01-01 to 2026-01-31",
            "4",
            "4",
            "0",
            "imported",
        ],
        [
            "january.pdf",
            "fake_bank",
            "Test Card",
            "2026-01-01 to 2026-01-31",
            "4",
            "0",
            "4",
            "imported",
        ],
    ]
    assert result.stderr == "Error: broken.pdf: could not read PDF\n"
    assert stored(with_card) == (2, 4)


def test_import_folder_succeeds_when_nothing_fails(with_card: Settings, january: Path) -> None:
    first = run("import", "folder", january.parent)
    assert first.exit_code == 0
    assert first.stderr == ""
    second = run("import", "folder", january.parent)
    assert second.exit_code == 0
    assert table_rows(second.stdout)[1] == [
        "january.pdf",
        "",
        "",
        "",
        "0",
        "0",
        "0",
        "already imported",
    ]


def test_import_folder_dry_run_stores_nothing(with_card: Settings, january: Path) -> None:
    result = run("import", "folder", january.parent, "--dry-run")
    assert result.exit_code == 0
    assert table_rows(result.stdout)[1][-1] == "dry run, nothing written"
    assert stored(with_card) == (0, 0)


def test_import_folder_reports_every_failure(
    with_card: Settings, tmp_path: Path, fake_statement_pdf
) -> None:
    inbox = tmp_path / "bad"
    inbox.mkdir()
    (inbox / "a.pdf").write_bytes(fake_statement_pdf(last4="9999"))
    (inbox / "b.pdf").write_bytes(fake_statement_pdf(closing="-80.00"))
    result = run("import", "folder", inbox)
    assert result.exit_code == 1
    assert result.stderr == (
        f"Error: a.pdf: {HINT.replace('1111', '9999')}\n"
        "Error: b.pdf: statement does not reconcile: off by 499 cents\n"
    )
    assert [row[-1] for row in table_rows(result.stdout)[1:]] == ["failed", "failed"]
    assert table_rows(result.stdout)[2][:4] == [
        "b.pdf",
        "fake_bank",
        "Test Card",
        "2026-01-01 to 2026-01-31",
    ]


def test_import_folder_with_no_pdfs(with_card: Settings, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / "notes.txt").write_text("nothing")
    result = run("import", "folder", tmp_path / "empty")
    assert result.exit_code == 0
    assert result.stdout == "No PDF files.\n"


def test_import_folder_needs_an_existing_folder(with_card: Settings, january: Path) -> None:
    assert run("import", "folder", january.parent / "missing").exit_code == 2
    assert run("import", "folder", january).exit_code == 2
