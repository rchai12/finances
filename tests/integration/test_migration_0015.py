from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import ProposalRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
ADDED = [
    ("pattern", "VARCHAR(100)", True),
    ("match", "VARCHAR(12)", True),
    ("priority", "INTEGER", True),
]


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


def test_0015_follows_0014() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0015")
    assert script.down_revision == "0014"


def test_the_rule_columns_come_and_go(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0015")
    found = columns(url)
    assert found[-3:] == ADDED
    orm = [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns]
    assert orm[: len(found)] == found
    command.downgrade(config, "0014")
    assert columns(url)[-1] == ("other_id", "INTEGER", True)
    command.upgrade(config, "0015")
    assert columns(url)[-3:] == ADDED
