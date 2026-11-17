import pytest

from tests.unit import test_views_take_data as guard


@pytest.mark.parametrize(
    "filename,source",
    [
        ("backups.py", "from finances.db import engine"),
        ("sync.py", "from finances.db.engine import get_engine"),
        ("transfers.py", "from sqlalchemy import select"),
        ("accounts.py", "import keyring"),
        ("sync.py", "from finances.sync.runner import run_links"),
        ("sync.py", "from finances.sync.runner import LinkRun, run_links"),
        ("backups.py", "from finances.sync.runner import LinkRun"),
        ("sync.py", "import finances.sync.runner"),
        ("backups.py", "from finances import db"),
        ("transfers.py", "from finances import sync"),
        ("nested/extra.py", "import sqlalchemy.orm"),
        ("sync.py", "def later():\n    import keyring"),
    ],
    ids=[
        "backups-db",
        "sync-db",
        "transfers-sql",
        "keyring",
        "runner-function",
        "mixed-import",
        "wrong-file",
        "module-import",
        "parent-db",
        "parent-sync",
        "nested-file",
        "nested-scope",
    ],
)
def test_forbidden_import_is_rejected(tmp_path, monkeypatch, filename, source):
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source + "\n", encoding="utf-8")
    monkeypatch.setattr(guard, "VIEWS", tmp_path)
    with pytest.raises(AssertionError):
        guard.test_only_the_frozen_views_still_load_data()


@pytest.mark.parametrize(
    "filename,source",
    [
        ("sync.py", "from finances.sync.runner import LinkRun"),
        ("sync.py", "from finances.sync.runner import LinkRun as Result"),
        ("backups.py", "from finances.analysis.backups import BackupFile"),
        ("transfers.py", "from finances.analysis.transfers import PairListing, SuggestionListing"),
    ],
    ids=["linkrun", "alias", "backup-type", "transfer-types"],
)
def test_result_type_import_is_permitted(tmp_path, monkeypatch, filename, source):
    path = tmp_path / filename
    path.write_text(source + "\n", encoding="utf-8")
    monkeypatch.setattr(guard, "VIEWS", tmp_path)
    guard.test_only_the_frozen_views_still_load_data()
