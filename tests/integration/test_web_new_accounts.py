import json
from datetime import UTC, date, datetime
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AccountRow
from finances.db.repositories import (
    create_account,
    create_person,
    map_feed_account,
    record_seen_feed_account,
)
from finances.sync import transport
from finances.web.app import create_app

PORT = 8765
DAY = date(2026, 5, 9)


class Page(HTMLParser):
    """The parts of a page the tests read: table rows, paragraphs, and forms."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.paragraphs: list[tuple[str, str]] = []
        self.forms: list[dict] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.paragraph: str | None = None
        self.text: list[str] = []
        self.form: dict | None = None
        self.select: str | None = None
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "p":
            self.paragraph = values.get("class", "")
            self.text = []
        elif tag == "form":
            self.form = {
                "action": values.get("action", ""),
                "method": values.get("method", "get"),
                "inputs": {},
                "selects": {},
            }
            self.forms.append(self.form)
        elif tag == "input" and self.form is not None:
            self.form["inputs"][values.get("name", "")] = (
                values.get("type", "text"),
                values.get("value", ""),
            )
        elif tag == "select" and self.form is not None:
            self.select = values.get("name", "")
            self.form["selects"][self.select] = []
        elif tag == "option" and self.form is not None and self.select is not None:
            self.form["selects"][self.select].append(
                (values.get("value", ""), "selected" in values)
            )

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "p" and self.paragraph is not None:
            self.paragraphs.append((self.paragraph, "".join(self.text).strip()))
            self.paragraph = None
        elif tag == "form":
            self.form = None
        elif tag == "select":
            self.select = None

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
        if self.paragraph is not None:
            self.text.append(data)

    def find(self, action: str) -> dict:
        found = [form for form in self.forms if form["action"] == action]
        assert len(found) == 1, action
        return found[0]


class SeenPage(Page):
    """Also the text of each h3 heading."""

    def __init__(self, html: str) -> None:
        self.headings: list[str] = []
        self.heading: list[str] | None = None
        super().__init__(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h3":
            self.heading = []
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self.heading is not None:
            self.headings.append(" ".join("".join(self.heading).split()))
            self.heading = None
        super().handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.heading is not None:
            self.heading.append(data)
        super().handle_data(data)

    def all(self, action: str) -> list[dict]:
        return [form for form in self.forms if form["action"] == action]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Kim's link maps ACT-1 to Test Card; Test Savings ends in 4321 and is not mapped."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Probe Bank", "credit_card", last4="1111")
        map_feed_account(session, card.id, "ACT-1", "kim")
        create_account(session, "Test Savings", "Probe Bank", "savings", last4="4321")
        old = create_account(session, "Test Old", "Probe Bank", "other")
        session.get(AccountRow, old.id).is_active = False
        create_person(session, "Alex")
        create_person(session, "Kim")
    engine.dispose()
    client.get("/sync")
    return client


def see(link: str, feed_id: str, name: str, institution: str = "Probe Bank") -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        record_seen_feed_account(session, link, feed_id, name, institution, DAY)
    engine.dispose()


def post(client: TestClient, path: str, **fields: str):
    return client.post(
        path, data={"csrf": client.cookies["fin_csrf"], **fields}, follow_redirects=False
    )


def sync_page(client: TestClient) -> SeenPage:
    return SeenPage(client.get("/sync").text)


def selected(form: dict, name: str) -> list[str]:
    return [value for value, chosen in form["selects"][name] if chosen]


def accounts(client: TestClient) -> list[list[str]]:
    return Page(client.get("/accounts?closed=true").text).rows[1:]


def test_no_section_without_new_accounts(home: TestClient) -> None:
    page = sync_page(home)
    assert page.headings == []
    assert page.all("/sync/create") == page.all("/sync/ignore") == []
    see("kim", "ACT-1", "Mapped already")
    assert sync_page(home).headings == []


def test_each_new_account_is_offered_with_its_guesses(home: TestClient) -> None:
    see("kim", "ACT-2", "  Probe   Visa ...9876 ")
    see("sam", "SAM-1", "Everyday Checking", "Other Bank")
    page = sync_page(home)
    assert page.headings == [
        "Probe Bank: Probe Visa ...9876 link kim",
        "Other Bank: Everyday Checking link sam",
    ]
    first, second = page.all("/sync/create")
    assert {name: first["inputs"][name] for name in ("link", "feed_account", "next")} == {
        "link": ("hidden", "kim"),
        "feed_account": ("hidden", "ACT-2"),
        "next": ("hidden", "sync"),
    }
    assert first["inputs"]["account"] == ("text", "Probe Visa ...9876")
    assert first["inputs"]["institution"] == ("text", "Probe Bank")
    assert first["inputs"]["last4"] == ("text", "9876")
    assert selected(first, "type") == ["credit_card"]
    assert [value for value, _ in first["selects"]["owner"]] == ["", "Alex", "Kim", "joint"]
    assert selected(first, "owner") == ["Kim"]
    assert selected(second, "type") == ["checking"]
    assert second["inputs"]["last4"] == ("text", "")
    assert selected(second, "owner") == []


def test_an_existing_account_with_the_same_digits_is_suggested(home: TestClient) -> None:
    see("kim", "ACT-3", "High Yield Savings 4321")
    page = sync_page(home)
    assert (
        "notice",
        "This looks like Test Savings, which you already have."
        " Map it instead of creating a second one.",
    ) in page.paragraphs
    (mapping,) = page.all("/sync/map")
    assert mapping["selects"]["account"] == [("Test Savings", True)]
    assert mapping["inputs"]["next"] == ("hidden", "sync")


def test_without_a_suggestion_the_list_starts_empty(home: TestClient) -> None:
    see("kim", "ACT-4", "Brokerage")
    page = sync_page(home)
    assert not any(kind == "notice" for kind, _ in page.paragraphs)
    (mapping,) = page.all("/sync/map")
    assert mapping["selects"]["account"] == [("", False), ("Test Savings", False)]


def test_no_map_form_when_every_open_account_is_mapped(home: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        map_feed_account(session, 2, "SAV-1", "sam")
    engine.dispose()
    see("kim", "ACT-4", "Brokerage")
    page = sync_page(home)
    assert page.all("/sync/map") == []
    assert len(page.all("/sync/create")) == 1


def test_text_from_simplefin_is_escaped(home: TestClient) -> None:
    see("kim", "ACT-5", "<b>Bold</b> Card")
    html = home.get("/sync").text
    assert "&lt;b&gt;Bold&lt;/b&gt; Card" in html
    assert "<b>Bold</b>" not in html


@pytest.mark.parametrize(
    ("owner", "shown"), [("Kim", "Kim"), ("kim", "Kim"), ("joint", "Joint"), ("", "")]
)
def test_create_and_map_with_an_owner(home: TestClient, owner: str, shown: str) -> None:
    see("kim", "ACT-2", "Probe Visa 9876")
    response = post(
        home,
        "/sync/create",
        link="kim",
        feed_account="ACT-2",
        account="Kim Visa",
        institution="Probe Bank",
        type="credit_card",
        last4="9876",
        owner=owner,
        next="sync",
    )
    assert (response.status_code, response.headers["location"]) == (303, "/sync?notice=mapped")
    assert ["Kim Visa", "Probe Bank", "credit_card", "••9876", "yes", shown] in accounts(home)
    page = SeenPage(home.get("/sync?notice=mapped").text)
    assert page.headings == []
    assert ("notice", "Account mapped.") in page.paragraphs


def test_an_unknown_owner_creates_nothing(home: TestClient) -> None:
    see("kim", "ACT-2", "Probe Visa 9876")
    response = post(
        home,
        "/sync/create",
        link="kim",
        feed_account="ACT-2",
        account="Kim Visa",
        institution="Probe Bank",
        type="credit_card",
        owner="Nobody",
        next="sync",
    )
    assert response.status_code == 400
    assert ("error", "person not found") in Page(response.text).paragraphs
    assert "Kim Visa" not in [row[0] for row in accounts(home)]
    assert sync_page(home).headings == ["Probe Bank: Probe Visa 9876 link kim"]


def test_map_to_the_suggested_account(home: TestClient) -> None:
    see("kim", "ACT-3", "High Yield Savings 4321")
    response = post(
        home, "/sync/map", link="kim", feed_account="ACT-3", account="Test Savings", next="sync"
    )
    assert (response.status_code, response.headers["location"]) == (303, "/sync?notice=mapped")
    rows = sync_page(home).rows
    assert ["kim", "Test Savings", "ACT-3"] == rows[2][:3]


def test_mapping_without_next_still_goes_to_the_links_accounts(home: TestClient) -> None:
    see("kim", "ACT-3", "High Yield Savings 4321")
    response = post(home, "/sync/map", link="kim", feed_account="ACT-3", account="Test Savings")
    assert response.headers["location"] == "/sync/accounts?link=kim&notice=mapped"


def test_dont_track_and_track_again(home: TestClient) -> None:
    see("kim", "ACT-4", "Brokerage")
    response = post(home, "/sync/ignore", link="kim", feed_account="ACT-4")
    assert (response.status_code, response.headers["location"]) == (303, "/sync?notice=ignored")
    page = SeenPage(home.get(response.headers["location"]).text)
    assert ("notice", "That SimpleFIN account will not be tracked.") in page.paragraphs
    assert page.headings == []
    (again,) = page.all("/sync/track")
    assert (again["inputs"]["link"], again["inputs"]["feed_account"]) == (
        ("hidden", "kim"),
        ("hidden", "ACT-4"),
    )
    response = post(home, "/sync/track", link="kim", feed_account=" ACT-4 ")
    assert (response.status_code, response.headers["location"]) == (303, "/sync?notice=tracked")
    page = SeenPage(home.get(response.headers["location"]).text)
    assert ("notice", "That SimpleFIN account is offered for setup again.") in page.paragraphs
    assert page.headings == ["Probe Bank: Brokerage link kim"]
    assert page.all("/sync/track") == []


@pytest.mark.parametrize("path", ["/sync/ignore", "/sync/track"])
def test_tracking_an_unknown_account_is_refused(home: TestClient, path: str) -> None:
    response = post(home, path, link="kim", feed_account="ACT-404")
    assert response.status_code == 400
    assert ("error", "SimpleFIN account not found") in Page(response.text).paragraphs


@pytest.mark.parametrize("path", ["/sync/ignore", "/sync/track"])
def test_tracking_needs_the_form_token_and_a_post(home: TestClient, path: str) -> None:
    see("kim", "ACT-4", "Brokerage")
    response = home.post(path, data={"link": "kim", "feed_account": "ACT-4"})
    assert (response.status_code, response.text) == (403, "Bad form token")
    assert home.get(path).status_code == 405
    assert sync_page(home).headings == ["Probe Bank: Brokerage link kim"]


def test_sync_now_says_how_many_accounts_are_new(home: TestClient, keychain, monkeypatch) -> None:
    keychain.passwords[("finances-simplefin", "kim")] = "https://u:p@bridge.simplefin.org/x"
    noon = int(datetime.now(UTC).replace(hour=12, minute=0, second=0).timestamp())
    body = {
        "errlist": [],
        "connections": [{"conn_id": "C", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": feed_id,
                "name": name,
                "conn_id": "C",
                "currency": "USD",
                "balance": "1.00",
                "balance-date": noon,
                "transactions": [],
            }
            for feed_id, name in (("ACT-1", "Card"), ("ACT-2", "Visa"), ("ACT-3", "Savings"))
        ],
    }
    monkeypatch.setattr(transport, "urllib_transport", lambda *_: (200, json.dumps(body).encode()))
    html = post(home, "/sync/run").text
    page = SeenPage(html)
    assert ("notice", "New SimpleFIN accounts: kim: 2 new accounts to set up. Set them up") in (
        page.paragraphs
    )
    assert '<a href="/sync">Set them up</a>' in html
    post(home, "/sync/ignore", link="kim", feed_account="ACT-2")
    post(home, "/sync/ignore", link="kim", feed_account="ACT-3")
    page = SeenPage(post(home, "/sync/run").text)
    assert not any(text.startswith("New SimpleFIN") for _, text in page.paragraphs)


def test_sync_now_also_runs_a_link_with_only_new_accounts(
    home: TestClient, keychain, monkeypatch
) -> None:
    keychain.passwords[("finances-simplefin", "kim")] = "https://kim:k@bridge.simplefin.org/x"
    keychain.passwords[("finances-simplefin", "sam")] = "https://sam:s@bridge.simplefin.org/x"
    see("sam", "SAM-1", "Sam Checking")
    asked = []
    empty = {"errlist": [], "connections": [], "accounts": []}

    def bridge(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        asked.append(headers["Authorization"])
        return 200, json.dumps(empty).encode()

    monkeypatch.setattr(transport, "urllib_transport", bridge)
    assert post(home, "/sync/run").status_code == 200
    assert len(set(asked)) == 2
