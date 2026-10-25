from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import ProposalRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
ADDED = [
    ("group_name", "VARCHAR(50)", True),
    ("is_transfer", "BOOLEAN", True),
    ("is_income", "BOOLEAN", True),
    ("is_sensitive", "BOOLEAN", True),
    ("is_tax", "BOOLEAN", True),
    ("parent_id", "INTEGER", True),
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


def reasons(url: str) -> list[str]:
    engine = get_engine(url)
    with engine.connect() as connection:
        found = list(connection.execute(text("SELECT reason FROM proposals ORDER BY id")).scalars())
    engine.dispose()
    return found


def test_0022_follows_0021() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0022")
    assert script.down_revision == "0021"


def test_the_columns_come_and_go_and_the_rows_stay(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0021")
    engine = get_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO proposals (kind, target_id, value, reason, status, created_at)"
                " VALUES ('category', 1, 'Dining', 'a cafe', 'open', '2026-05-25 12:00:00.000000')"
            )
        )
    engine.dispose()
    command.upgrade(config, "0022")
    found = columns(url)
    assert found[-6:] == ADDED
    orm = [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns]
    assert orm[: len(found)] == found
    assert reasons(url) == ["a cafe"]
    command.downgrade(config, "0021")
    assert columns(url)[-1] == ("source", "VARCHAR(100)", True)
    assert reasons(url) == ["a cafe"]
    command.upgrade(config, "0022")
    assert columns(url)[-6:] == ADDED
