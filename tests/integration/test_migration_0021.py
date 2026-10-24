from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import CategoryRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def columns(url: str) -> list[tuple]:
    engine = get_engine(url)
    found = [
        (c["name"], str(c["type"]), c["nullable"])
        for c in inspect(engine).get_columns("categories")
    ]
    engine.dispose()
    return found


def tax_names(url: str) -> list[str]:
    engine = get_engine(url)
    with engine.connect() as connection:
        found = connection.execute(
            text("SELECT name FROM categories WHERE is_tax ORDER BY name")
        ).scalars()
        names = list(found)
    engine.dispose()
    return names


def test_0021_follows_0020() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0021")
    assert script.down_revision == "0020"


def test_the_flag_and_the_seeded_tax_categories(url: str) -> None:
    command.upgrade(make_config(url), "0021")
    found = columns(url)
    assert found[-1] == ("is_tax", "BOOLEAN", False)
    orm = [(c.name, str(c.type), c.nullable) for c in CategoryRow.__table__.columns]
    assert orm[: len(found)] == found
    assert tax_names(url) == ["Gifts & Donations", "Medical", "Taxes"]


def test_down_and_up_again_with_rows_that_point_at_categories(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0021")
    engine = get_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO category_rules (pattern, match, priority, category_id) VALUES "
                "('ACME CLINIC', 'contains', 0, 30)"
            )
        )
    engine.dispose()
    command.downgrade(config, "0020")
    assert "is_tax" not in [name for name, _, _ in columns(url)]
    command.upgrade(config, "0021")
    assert tax_names(url) == ["Gifts & Donations", "Medical", "Taxes"]
