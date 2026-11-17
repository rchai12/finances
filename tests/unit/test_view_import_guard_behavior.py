import ast
import hashlib
import shutil
from pathlib import Path

import pytest

from tests.unit import test_views_take_data as guard


def test_exact_exception_and_existing_views():
    assert guard.PERMITTED_RESULT_IMPORTS == {("sync.py", "finances.sync.runner", "LinkRun")}
    assert not hasattr(guard, "STILL_LOADING")
    assert len(list(guard.VIEWS.rglob("*.py"))) == 29
    guard.test_only_the_frozen_views_still_load_data()


@pytest.mark.parametrize("name", ["backups.py", "sync.py", "transfers.py"])
def test_old_exemptions_reject_database_import(tmp_path, monkeypatch, name):
    shutil.copytree(guard.VIEWS, tmp_path / "views")
    path = tmp_path / "views" / name
    path.write_text(path.read_text() + "\nfrom finances.db import engine\n")
    monkeypatch.setattr(guard, "VIEWS", tmp_path / "views")
    with pytest.raises(AssertionError, match=name.replace(".", r"\.")):
        guard.test_only_the_frozen_views_still_load_data()


@pytest.mark.parametrize(
    "filename,source",
    [
        ("nested/sync.py", "from finances.sync.runner import LinkRun"),
        ("sync.py", "from finances.sync.runner import *"),
        ("sync.py", "from finances.sync.other import LinkRun"),
        ("sync.py", "from finances.sync.runner import run_links as LinkRun"),
        ("nested/extra.py", "from ...db import engine"),
        ("extra.py", "from ..db import engine"),
        ("extra.py", "from .. import db"),
        ("extra.py", "import finances.db.engine as safe"),
        ("extra.py", "from keyring import get_password"),
        ("extra.py", "from sqlalchemy.orm import Session"),
    ],
)
def test_edge_imports_are_rejected(tmp_path, monkeypatch, filename, source):
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source + "\n")
    monkeypatch.setattr(guard, "VIEWS", tmp_path)
    with pytest.raises(AssertionError, match=path.name.replace(".", r"\.")):
        guard.test_only_the_frozen_views_still_load_data()


@pytest.mark.parametrize(
    "source",
    [
        "import keyringish",
        "import sqlalchemyish",
        "import finances.sync_helpers",
        "from finances import db_helpers",
        "from finances.analysis import backups",
        'text = "import keyring"\n# from finances.db import engine',
    ],
)
def test_similar_names_and_text_are_allowed(tmp_path, monkeypatch, source):
    (tmp_path / "extra.py").write_text(source + "\n")
    monkeypatch.setattr(guard, "VIEWS", tmp_path)
    guard.test_only_the_frozen_views_still_load_data()


def test_guard_never_executes_synthetic_source(tmp_path, monkeypatch):
    (tmp_path / "extra.py").write_text(
        'raise RuntimeError("executed")\ndef later():\n    import keyring\n'
    )
    monkeypatch.setattr(guard, "VIEWS", tmp_path)
    with pytest.raises(AssertionError, match="extra.py.*keyring"):
        guard.test_only_the_frozen_views_still_load_data()


def test_existing_formatting_functions_match_baseline():
    tree = ast.parse(Path(guard.__file__).read_text())
    actual = {
        n.name: hashlib.sha256(ast.dump(n).encode()).hexdigest()[:16]
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in BASELINE
    }
    assert actual == BASELINE


BASELINE = {
    "transaction": "2550592a9bf39c0d",
    "test_account_rows_from_a_listing": "09c6232fb19c2591",
    "test_people_rows_from_a_listing": "137b1b84e90eba93",
    "test_the_category_tree_as_lines_and_choices": "45a59d5dff7c718c",
    "test_rule_lines_from_a_listing": "11085cf59d464f8b",
    "test_uncategorized_lines_and_the_card_note": "501a2b7f61998863",
    "test_the_detail_of_a_transaction": "29b8a2b8e65fcfea",
    "test_the_refund_sections": "24549054b76b1bc7",
}
