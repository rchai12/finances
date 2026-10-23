import ast
from datetime import UTC, date, datetime
from pathlib import Path

import finances.cli
import finances.views
from finances.analysis.backups import BackupFile
from finances.analysis.simplefin import MappingStatus
from finances.analysis.transfers import PairListing, SuggestionListing
from finances.domain.models import DataSource, FeedPull, Transaction, TransferPair
from finances.sync.links import keychain_state
from finances.views.backups import BackupRow, backup_rows, taken_text
from finances.views.format import change_text
from finances.views.sync import StatusRow, status_rows
from finances.views.transfers import SuggestionLine, TransferLine, suggestion_lines, transfer_lines

VIEWS = Path(finances.views.__file__).parent
CLI = Path(finances.cli.__file__).parent
CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def imported(path: Path) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
    return names


def test_no_view_loads_data() -> None:
    found = {
        path.name: name
        for path in VIEWS.glob("*.py")
        for name in imported(path)
        if name.startswith(("finances.db", "sqlalchemy", "keyring"))
        or (name.startswith("finances.sync") and name != "finances.sync.runner")
    }
    assert found == {}


def test_no_view_takes_a_session() -> None:
    takers = []
    for path in VIEWS.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef):
                for argument in node.args.args + node.args.kwonlyargs:
                    if argument.annotation is not None and "Session" in ast.unparse(
                        argument.annotation
                    ):
                        takers.append(f"{path.name}:{node.name}")
    assert takers == []


def test_one_change_text() -> None:
    assert (change_text(100), change_text(0), change_text(-250)) == ("+$1.00", "$0.00", "-$2.50")
    helpers = [
        path.name
        for path in VIEWS.glob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef) and node.name == "_change"
    ]
    assert helpers == []


def test_the_cli_tables_go_through_print_rows() -> None:
    hand_built = {
        path.name: path.read_text(encoding="utf-8").count("Table()")
        for path in CLI.glob("*.py")
        if "Table()" in path.read_text(encoding="utf-8")
    }
    assert hand_built == {"common.py": 1, "importing.py": 1, "main.py": 1, "sync.py": 1}


def test_the_keychain_state_lives_with_the_links(keychain) -> None:
    keychain.passwords[("finances-simplefin", "alex")] = "https://u:p@bridge.simplefin.org/x"
    assert (keychain_state("alex"), keychain_state("sam")) == ("yes", "no")


def test_status_rows_from_mappings() -> None:
    pulled = FeedPull(1, 1, 1, 0, 0, 0, -100, -100, date(2026, 5, 9), -250, CREATED)
    found = status_rows(
        [
            MappingStatus("alex", "Test Card", "ACT-1", "yes", pulled, pulled),
            MappingStatus("sam", "Test Checking", "ACT-2", "unknown", None, None),
        ]
    )
    assert found[0].balance_date == "2026-05-09" and found[0].drift == "-$2.50"
    assert found[1] == StatusRow("sam", "Test Checking", "ACT-2", "unknown", "never", "", "")


def transaction(id: int, account: int, day: int, cents: int) -> Transaction:
    return Transaction(
        id,
        account,
        None,
        date(2026, 5, day),
        None,
        cents,
        "TRANSFER",
        None,
        None,
        None,
        None,
        DataSource.STATEMENT,
        False,
        f"t{id:02d}".ljust(64, "0"),
        CREATED,
    )


def test_transfer_lines_sort_and_suggestions() -> None:
    early = PairListing(
        TransferPair(1, 1, 2, "confirmed"),
        transaction(1, 1, 2, -500),
        transaction(2, 2, 3, 500),
        "Test Checking",
        "Test Savings",
    )
    late = PairListing(
        TransferPair(2, 3, 4, "auto"),
        transaction(3, 1, 9, -2599),
        transaction(4, 3, 9, 2599),
        "Test Checking",
        "Test Card",
    )
    assert transfer_lines([early, late]) == [
        TransferLine("2", "2026-05-09", "Test Checking", "Test Card", "$25.99", "3", "4", "auto"),
        TransferLine(
            "1", "2026-05-02", "Test Checking", "Test Savings", "$5.00", "1", "2", "confirmed"
        ),
    ]
    waiting = SuggestionListing(
        transaction(5, 1, 5, -2000), transaction(6, 2, 6, 2000), "Test Checking", "Test Savings"
    )
    assert suggestion_lines([waiting]) == [
        SuggestionLine(
            "5", "2026-05-05", "Test Checking", "6", "2026-05-06", "Test Savings", "$20.00"
        )
    ]


def test_backup_rows_from_files() -> None:
    taken = datetime(2026, 5, 25, 2, 0, 0, tzinfo=UTC)
    assert taken_text(taken) == "2026-05-25 02:00:00"
    assert backup_rows([BackupFile("finances-20260525-020000.db", taken, 2048)]) == [
        BackupRow("finances-20260525-020000.db", "2026-05-25 02:00:00", "2 KB")
    ]
