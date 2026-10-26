from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import ProposalRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
ADDED = ("before", "VARCHAR(200)", True)


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


def test_0024_follows_0023() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0024")
    assert script.down_revision == "0023"


def test_the_columns_come_and_go_and_the_rows_stay(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0023")
    engine = get_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO proposals (kind, target_id, value, reason, status, created_at)"
                " VALUES ('category', 1, 'Dining', 'a cafe', 'open', '2026-05-25 12:00:00.000000')"
            )
        )
    engine.dispose()
    command.upgrade(config, "0024")
    found = columns(url)
    assert found[-1] == ADDED
    orm = [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns]
    assert orm[: len(found)] == found
    assert reasons(url) == ["a cafe"]
    command.downgrade(config, "0023")
    assert columns(url)[-1] == ("parent_id", "INTEGER", True)
    assert reasons(url) == ["a cafe"]
    command.upgrade(config, "0024")
    assert columns(url)[-1] == ADDED
