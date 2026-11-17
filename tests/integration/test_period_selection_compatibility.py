import inspect
import itertools
from dataclasses import FrozenInstanceError
from datetime import date, datetime
from unittest.mock import Mock

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.client import Client

from finances import clock
from finances.cli import periods as cli
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, set_category_by_hand
from finances.domain import periods
from finances.mcp_server import helpers
from finances.mcp_server.server import build_server
from finances.web import app as web_app
from finances.web import periods as web
from tests.support import WEB_PORT, Page, run, texts


@pytest.mark.parametrize("month,start,end", list(itertools.product([False, True], repeat=3)))
def test_presence_matrix(month, start, end):
    code = "conflict" if month and (start or end) else "incomplete" if start != end else None
    if code:
        with pytest.raises(periods.PeriodError) as error:
            periods.validate_selection(month_present=month, start_present=start, end_present=end)
        assert error.value.code == code
        assert (
            str(error.value)
            == {
                "conflict": "month cannot accompany endpoints",
                "incomplete": "both endpoints are required",
            }[code]
        )
    else:
        assert (
            periods.validate_selection(month_present=month, start_present=start, end_present=end)
            is None
        )


@pytest.mark.parametrize("month", ["", "bad", "2024-00", "2024-13", "0000-01"])
def test_first_day_errors(month):
    with pytest.raises(periods.PeriodError) as error:
        periods.first_day(month, today=date.min)
    assert error.value.code == "month"
    assert str(error.value) == "month must be a year and month, like 2026-05"


def test_domain_purity_and_immutability():
    result = periods.Period(date(2024, 2, 29), date(2024, 2, 1))
    with pytest.raises(FrozenInstanceError):
        result.start = date.min
    source = inspect.getsource(periods)
    assert all(
        name not in source
        for name in ("finances.clock", "finances.cli", "finances.web", "finances.mcp_server")
    )
    assert periods.select_period(today=date.min, start=result.start, end=result.end) == result
    with pytest.raises(periods.PeriodError, match="both endpoints are required"):
        periods.select_period(today=date.min, end=date.min)


@pytest.mark.parametrize("today", [date(2024, 12, 31), date(2025, 1, 1)])
def test_defaults_and_delegation(monkeypatch, today):
    monkeypatch.setattr(clock, "today", lambda: today)
    monkeypatch.setattr(web_app, "_today", lambda: today)
    spy = Mock(wraps=periods.select_period)
    monkeypatch.setattr(periods, "select_period", spy)
    expected = periods.month_bounds(today)
    assert cli.spending_range(None, None, None) == expected
    assert web.spending_range(dict(month="", start="", end="")) == expected
    assert cli.first_day(None) == expected[0]
    assert web.first_day("") == expected[0]
    assert helpers.month_start("") == expected[0]
    assert spy.call_count == 5


def test_explicit_selections_do_not_read_clocks(monkeypatch):
    def refused():
        pytest.fail("explicit selection read calendar")

    monkeypatch.setattr(clock, "today", refused)
    monkeypatch.setattr(web_app, "_today", refused)
    assert cli.spending_range("2024-02", None, None) == (date(2024, 2, 1), date(2024, 2, 29))
    assert cli.spending_range(None, datetime(2024, 2, 3), datetime(2024, 2, 2)) == (
        date(2024, 2, 3),
        date(2024, 2, 2),
    )
    assert web.spending_range(dict(month="", start="2024-02-03", end="2024-02-02")) == (
        date(2024, 2, 3),
        date(2024, 2, 2),
    )
    assert (
        cli.first_day("2024-02")
        == web.first_day("2024-02")
        == helpers.month_start("2024-02")
        == date(2024, 2, 1)
    )
    with pytest.raises(ValueError, match="from must be a date"):
        web.spending_range(dict(month="", start="bad", end="bad"))
    with pytest.raises(ValueError, match="to must be a date"):
        web.spending_range(dict(month="", start="2024-02-01", end="bad"))


@pytest.fixture
def household(tmp_settings, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2024, 2, 15))
    monkeypatch.setattr(web_app, "_today", lambda: date(2024, 2, 15))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        account = create_account(session, "Test Card", "Test Bank", "credit_card")
        for index, day in enumerate(
            [date(2024, 1, 31), date(2024, 2, 1), date(2024, 2, 29), date(2024, 3, 1)], 1
        ):
            row = TransactionRow(
                account_id=account.id,
                posted_date=day,
                amount_cents=-100 * index,
                description="ACME COFFEE",
                source="statement",
                fingerprint=str(index).ljust(64, "0"),
            )
            session.add(row)
            session.flush()
            set_category_by_hand(session, row.id, "Coffee & Dessert")
    engine.dispose()
    return tmp_settings, TestClient(
        web_app.create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}"
    )


def call(name, arguments):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments)

    return anyio.run(go)


@pytest.mark.parametrize(
    "args,query",
    [
        ((), ""),
        (("--month", "2024-02"), "?month=2024-02"),
        (("--from", "2024-02-01", "--to", "2024-02-29"), "?from=2024-02-01&to=2024-02-29"),
    ],
)
def test_public_report_export_inclusive_parity(household, args, query):
    settings, client = household
    report = run("spending", *args)
    assert report.exit_code == 0
    assert "Coffee & Dessert" in report.stdout and "5.00" in report.stdout
    exported = run("export", "spending", *args)
    assert exported.exit_code == 0
    csv = (
        (settings.data_dir / "exports" / "spending-by-category-2024-02-01-to-2024-02-29.csv")
        .read_bytes()
        .decode()
    )
    assert csv == "Category,Spent,Refunds,Net,Count\r\nCoffee & Dessert,5.00,0.00,5.00,2\r\n"
    response = client.get("/reports" + query)
    assert response.status_code == 200
    assert "Coffee &amp; Dessert" in response.text and "5.00" in response.text
    download = client.get("/export/spending" + query)
    assert download.status_code == 200 and download.text == csv
    assert "2024-02-01-to-2024-02-29.csv" in download.headers["content-disposition"]


@pytest.mark.parametrize(
    "args,query,message",
    [
        (
            ("--month", "bad", "--from", "2024-02-01"),
            "?month=bad&from=2024-02-01",
            "give a month, or from and to, not both",
        ),
        (("--from", "2024-02-01"), "?from=2024-02-01", "give both from and to"),
        (("--to", "2024-02-01"), "?to=2024-02-01", "give both from and to"),
        (("--month", "bad"), "?month=bad", "month must be a year and month, like 2026-05"),
        (
            ("--from", "2024-02-29", "--to", "2024-02-01"),
            "?from=2024-02-29&to=2024-02-01",
            "the start date is after the end date",
        ),
    ],
)
def test_public_refusal_matrix(household, args, query, message):
    _, client = household
    cli_message = message.replace(
        "give a month, or from and to, not both", "give --month, or --from and --to, not both"
    ).replace("give both from and to", "give both --from and --to")
    for prefix in [("spending",), ("export", "spending")]:
        result = run(*prefix, *args)
        assert result.exit_code == 1 and result.stderr == f"Error: {cli_message}\n"
    for route, status in [("/reports", 400), ("/export/spending", 400)]:
        response = client.get(route + query)
        assert response.status_code == status
        assert texts(Page(response.text), "error") == [message]
        assert "content-disposition" not in response.headers


@pytest.mark.parametrize(
    "arguments,error",
    [
        ({}, None),
        ({"start": "2024-02-01", "end": "2024-02-29"}, None),
        ({"start": "2024-02-01"}, "give both start and end, or neither"),
        ({"end": "2024-02-01"}, "give both start and end, or neither"),
        ({"start": "2024-02-29", "end": "2024-02-01"}, "the start date is after the end date"),
    ],
)
def test_actual_mcp_period_matrix(household, arguments, error, monkeypatch):
    spy = Mock(wraps=periods.select_period)
    monkeypatch.setattr(periods, "select_period", spy)
    result = call("get_spending", arguments)
    assert spy.call_count == 1
    assert result.is_error is bool(error)
    if error:
        assert result.content[0].text == f"Error executing tool get_spending: {error}"
    else:
        content = result.structured_content
        assert (content["start"], content["end"], content["summary"]["spent_cents"]) == (
            "2024-02-01",
            "2024-02-29",
            500,
        )


@pytest.mark.parametrize("month", ["", "2024-02", "bad"])
def test_actual_month_start_caller(household, month):
    result = call("get_insights", {"month": month})
    assert result.is_error is (month == "bad")
    if month == "bad":
        assert (
            result.content[0].text
            == "Error executing tool get_insights: month must be a year and month, like 2026-05"
        )


def test_schema_and_unmigrated_precedence(tmp_settings):
    async def schema():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    tool = next(tool for tool in anyio.run(schema) if tool.name == "get_spending")
    assert set(tool.input_schema["properties"]) == {"start", "end", "by"}
    assert tool.annotations.read_only_hint is True
    result = run("spending", "--month", "bad")
    assert result.stderr == "Error: database is not up to date (run: fin db upgrade)\n"
    client = TestClient(web_app.create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    for route in ["/reports", "/export/spending"]:
        response = client.get(route + "?month=bad")
        assert "The database is not up to date" in response.text


@pytest.mark.parametrize(
    "query,message",
    [
        ("?from=bad&to=2024-02-29", "from must be a date as YYYY-MM-DD"),
        ("?from=2024-02-01&to=bad", "to must be a date as YYYY-MM-DD"),
    ],
)
def test_public_bad_dates(household, query, message):
    _, client = household
    for route in ["/reports", "/export/spending"]:
        response = client.get(route + query)
        assert response.status_code == 400
        assert texts(Page(response.text), "error") == [message]
    for prefix in [("spending",), ("export", "spending")]:
        result = run(*prefix, "--from", "bad", "--to", "2024-02-29")
        assert result.exit_code == 2
        assert "Invalid value" in result.stderr


def test_mcp_explicit_no_calendar_and_web_empty(household, monkeypatch):
    _, client = household
    assert client.get("/export/spending?month=").status_code == 200

    def refused():
        pytest.fail("explicit MCP range read calendar")

    monkeypatch.setattr(clock, "today", refused)
    result = call("get_spending", {"start": "2024-02-01", "end": "2024-02-29"})
    assert result.is_error is False
    assert result.structured_content["summary"]["spent_cents"] == 500
