from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import ProposalRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def columns(url: str) -> list[tuple]:
    engine = get_engine(url)
    found = [
        (c["name"], str(c["type"]), c["nullable"]) for c in inspect(engine).get_columns("proposals")
    ]
    engine.dispose()
    return found


def test_0014_follows_0013() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0014")
    assert script.down_revision == "0013"


def test_other_id_comes_and_goes(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0014")
    assert columns(url)[-1] == ("other_id", "INTEGER", True)
    assert [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns] == columns(
        url
    )
    command.downgrade(config, "0013")
    assert "other_id" not in [name for name, _, _ in columns(url)]
    command.upgrade(config, "0014")
    assert columns(url)[-1] == ("other_id", "INTEGER", True)
