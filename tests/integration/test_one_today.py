from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances import clock
from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from tests.support import WEB_PORT, page, run, texts

TODAY = date(2026, 5, 25)


@pytest.fixture
def migrated(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr("finances.clock.today", lambda: TODAY)
    upgrade_to_head()
    return tmp_settings


def test_today_is_the_local_date() -> None:
    assert clock.today() == date.today()


@pytest.mark.parametrize(
    ("args", "first_line"),
    [
        (("budgets", "list"), "Budgets for 2026-05."),
        (("spending",), "Spending from 2026-05-01 to 2026-05-31, by category."),
        (("months",), "Months from 2025-12 to 2026-05."),
        (("insights",), "Insights for 2026-05."),
        (("merchants",), "Merchants for 2026-05."),
    ],
)
def test_every_command_reads_one_today(migrated: Settings, args, first_line: str) -> None:
    assert run(*args).stdout.splitlines()[0] == first_line


def test_health_counts_days_from_the_same_today(migrated: Settings) -> None:
    folder = migrated.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / "finances-20260524-020000.db").write_bytes(b"")
    assert run("health").stdout == "No problems found.\n"


def test_every_page_reads_the_same_today(migrated: Settings) -> None:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    assert texts(page(client, "/"), "summary")[0] == "Today is 2026-05-25."
    assert texts(page(client, "/budgets"), "summary")[0] == "Budgets for 2026-05."
    assert "Spending from 2026-05-01 to 2026-05-31, by category." in texts(
        page(client, "/reports"), "summary"
    )
    assert texts(page(client, "/insights"), "summary")[0] == "Insights for 2026-05."
