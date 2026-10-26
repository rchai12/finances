from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import AdviceRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
ADDED = ("dismissed_at", "DATETIME", True)


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def columns(url: str) -> list[tuple]:
    engine = get_engine(url)
    found = [
        (c["name"], str(c["type"]), c["nullable"])
        for c in inspect(engine).get_columns("advice_log")
    ]
    engine.dispose()
    return found


def notes(url: str) -> list[str]:
    engine = get_engine(url)
    with engine.connect() as connection:
        found = list(connection.execute(text("SELECT text FROM advice_log ORDER BY id")).scalars())
    engine.dispose()
    return found


def test_0023_follows_0022() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0023")
    assert script.down_revision == "0022"


def test_the_column_comes_and_goes_and_the_notes_stay(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0022")
    engine = get_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO advice_log (created_at, subject, text)"
                " VALUES ('2026-05-25 12:00:00.000000', 'budgets', 'A coffee budget.')"
            )
        )
    engine.dispose()
    command.upgrade(config, "0023")
    found = columns(url)
    assert found[-1] == ADDED
    orm = [(c.name, str(c.type), c.nullable) for c in AdviceRow.__table__.columns]
    assert orm[: len(found)] == found
    assert notes(url) == ["A coffee budget."]
    command.downgrade(config, "0022")
    assert columns(url)[-1] == ("text", "VARCHAR(1000)", False)
    assert notes(url) == ["A coffee budget."]
    command.upgrade(config, "0023")
    assert columns(url)[-1] == ADDED
