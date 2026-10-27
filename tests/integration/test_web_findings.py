import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, add_findings_data, page, post, texts

CLOSED = ["Severity", "Type", "About", "Saves a month", "Detail", "Status", ""]
SPIKE = [
    "medium",
    "spike",
    "Dining",
    "$140.00",
    "Dining: $200.00 this month, against $60.00 a month before.",
]
JUNE_INTEREST = ["high", "interest", "", "$10.00", "Interest charged: $10.00."]


@pytest.fixture
def home(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    add_findings_data()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/insights")
    return client


def closed(found: Page) -> list[list[str]]:
    """The rows of the Handled or ignored table, without its heading."""
    if CLOSED not in found.rows:
        return []
    rows = found.rows[found.rows.index(CLOSED) + 1 :]
    end = next((i for i, row in enumerate(rows) if row[-1:] != ["Reopen"]), len(rows))
    return rows[:end]


def fields(form: dict) -> dict:
    return {name: value for name, (_, value) in form["inputs"].items() if name != "csrf"}


def test_two_buttons_beside_each_open_finding(home: TestClient) -> None:
    found = page(home, "/insights?month=2026-05")
    forms = found.all("/findings/status")
    assert len(forms) == 10
    assert [fields(form) for form in forms[:4]] == [
        {"type": "interest", "about": "", "month": "2026-05", "status": "handled"},
        {"type": "interest", "about": "", "month": "2026-05", "status": "ignored"},
        {"type": "spike", "about": "Dining", "month": "2026-05", "status": "handled"},
        {"type": "spike", "about": "Dining", "month": "2026-05", "status": "ignored"},
    ]
    assert forms[0]["inputs"]["csrf"] == ("hidden", home.cookies["fin_csrf"])
    assert (closed(found), found.all("/findings/reopen")) == ([], [])


def test_handling_a_finding_on_the_page(home: TestClient) -> None:
    response = post(
        home, "/findings/status", type="spike", about="Dining", month="2026-05", status="handled"
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/insights?month=2026-05&notice=finding-handled",
    )
    found = page(home, response.headers["location"])
    assert texts(found, "notice") == ["Finding marked handled."]
    assert closed(found) == [[*SPIKE, "handled", "Reopen"]]
    assert "Findings: 4. Could save up to $55.44 a month." in texts(found, "summary")
    assert [fields(form) for form in found.all("/findings/reopen")] == [
        {"type": "spike", "about": "Dining", "month": "2026-05"}
    ]
    assert len(found.all("/findings/status")) == 8


def test_ignoring_a_finding_holds_in_every_month(home: TestClient) -> None:
    response = post(
        home, "/findings/status", type="interest", about="", month="2026-05", status="ignored"
    )
    assert response.headers["location"] == "/insights?month=2026-05&notice=finding-ignored"
    assert texts(page(home, response.headers["location"]), "notice") == [
        "Finding ignored in every month."
    ]
    june = page(home, "/insights?month=2026-06")
    assert closed(june) == [[*JUNE_INTEREST, "ignored", "Reopen"]]
    assert "No findings." in texts(june, "empty")


def test_reopening_a_finding_on_the_page(home: TestClient) -> None:
    post(home, "/findings/status", type="interest", about="", month="2026-05", status="ignored")
    response = post(home, "/findings/reopen", type="interest", about="", month="2026-06")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/insights?month=2026-06&notice=finding-reopened",
    )
    found = page(home, response.headers["location"])
    assert texts(found, "notice") == ["Finding reopened."]
    assert closed(found) == []


@pytest.mark.parametrize(
    ("path", "form", "message"),
    [
        (
            "/findings/status",
            {"type": "spike", "about": "Groceries", "month": "2026-05", "status": "handled"},
            "no such finding: spike for Groceries in 2026-05",
        ),
        (
            "/findings/status",
            {"type": "spike", "about": "Dining", "month": "2026-05", "status": "done"},
            "status must be one of: handled, ignored",
        ),
        (
            "/findings/reopen",
            {"type": "interest", "about": "", "month": "2026-05"},
            "this finding is open",
        ),
    ],
)
def test_a_refusal_shows_the_page_with_its_message(
    home: TestClient, path: str, form: dict, message: str
) -> None:
    response = post(home, path, **form)
    assert (response.status_code, texts(Page(response.text), "error")) == (400, [message])
