import re
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AccountRow
from finances.db.repositories import create_account, create_person, set_account_owner
from finances.web.app import create_app

PORT = 8765
NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"
POSTS = [
    "/accounts/add",
    "/accounts/owner",
    "/people/add",
    "/people/alias",
    "/sync/link",
    "/sync/unlink",
    "/sync/map",
    "/sync/create",
    "/sync/run",
]


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


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Alex owns the card, checking has no owner, Sam owns nothing, and an old card is closed."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test <Card>", "Test Bank", "credit_card", last4="1111")
        create_account(session, "Test Checking", "Test Bank", "checking")
        old = create_account(session, "Test Old Card", "Test Bank", "credit_card")
        session.get(AccountRow, old.id).is_active = False
        alex = create_person(session, "Alex")
        create_person(session, "Sam")
        set_account_owner(session, card.id, alex.id)
    engine.dispose()
    client.get("/accounts")
    return client


def token(client: TestClient) -> str:
    return client.cookies["fin_csrf"]


def post(client: TestClient, path: str, **fields: str):
    return client.post(path, data={"csrf": token(client), **fields}, follow_redirects=False)


def accounts(client: TestClient) -> list[list[str]]:
    return Page(client.get("/accounts?closed=true").text).rows[1:]


def people(client: TestClient) -> list[list[str]]:
    return Page(client.get("/people").text).rows[1:]


def refused(response, message: str) -> bool:
    page = Page(response.text)
    return response.status_code == 400 and ("error", message) in page.paragraphs


# The form token


def test_a_page_gives_the_browser_a_form_token(client: TestClient) -> None:
    upgrade_to_head()
    first = client.get("/accounts")
    cookie = first.headers["set-cookie"]
    assert cookie.startswith("fin_csrf=")
    assert "HttpOnly" in cookie and "Path=/" in cookie
    assert "samesite=strict" in cookie.lower()
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token(client))
    assert "set-cookie" not in client.get("/people").headers


@pytest.mark.parametrize("path", ["/accounts", "/people", "/sync"])
def test_every_form_that_changes_data_carries_the_token(home: TestClient, path: str) -> None:
    posts = [form for form in Page(home.get(path).text).forms if form["method"] == "post"]
    assert posts
    for form in posts:
        assert form["inputs"]["csrf"] == ("hidden", token(home))


@pytest.mark.parametrize("cookie", ["", "short", "x" * 42 + "!"])
def test_a_missing_or_malformed_cookie_is_replaced(client: TestClient, cookie: str) -> None:
    upgrade_to_head()
    client.cookies.set("fin_csrf", cookie)
    response = client.get("/accounts")
    fresh = response.headers["set-cookie"].split(";")[0].removeprefix("fin_csrf=")
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", fresh)
    assert Page(response.text).find("/accounts/add")["inputs"]["csrf"] == ("hidden", fresh)


@pytest.mark.parametrize("path", POSTS)
def test_a_form_path_does_nothing_on_get(home: TestClient, path: str) -> None:
    assert home.get(path).status_code == 405


@pytest.mark.parametrize("path", POSTS)
def test_a_form_without_the_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.parametrize("path", POSTS)
def test_a_form_with_another_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={"csrf": "A" * 43}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


@pytest.mark.parametrize("path", POSTS)
def test_a_form_without_the_cookie_is_refused(home: TestClient, path: str) -> None:
    sent = token(home)
    home.cookies.clear()
    response = home.post(path, data={"csrf": sent}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


@pytest.mark.parametrize(
    "origin",
    ["http://evil.example", "null", f"http://127.0.0.1:{PORT + 1}", f"https://127.0.0.1:{PORT}"],
)
def test_a_form_sent_from_another_site_is_refused(home: TestClient, origin: str) -> None:
    response = home.post(
        "/accounts/add",
        data={"csrf": token(home), "name": "Probe", "institution": "Probe Bank", "type": "other"},
        headers={"origin": origin},
        follow_redirects=False,
    )
    assert (response.status_code, response.text) == (403, "Bad origin")
    assert len(accounts(home)) == 3


@pytest.mark.parametrize("origin", [f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"])
def test_a_form_sent_from_this_site_is_accepted(home: TestClient, origin: str) -> None:
    response = home.post(
        "/accounts/add",
        data={"csrf": token(home), "name": "Probe", "institution": "Probe Bank", "type": "other"},
        headers={"origin": origin},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.parametrize("path", POSTS)
def test_forms_need_a_migrated_database(client: TestClient, path: str) -> None:
    client.get("/accounts")
    response = post(client, path)
    assert response.status_code == 503
    assert ("error", NOT_MIGRATED) in Page(response.text).paragraphs


def test_an_unknown_notice_shows_nothing(home: TestClient) -> None:
    page = Page(home.get("/accounts?notice=<b>hello</b>").text)
    assert [kind for kind, _ in page.paragraphs if kind == "notice"] == []


# Accounts


def test_add_an_account(home: TestClient) -> None:
    response = post(
        home,
        "/accounts/add",
        name="  Probe Visa ",
        institution=" Probe Bank ",
        type="credit_card",
        last4="1234",
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/accounts?notice=account-added",
    )
    page = Page(home.get(response.headers["location"]).text)
    assert ("notice", "Account added.") in page.paragraphs
    assert ["Probe Visa", "Probe Bank", "credit_card", "••1234", "yes", ""] in page.rows


def test_add_an_account_without_last_four_digits(home: TestClient) -> None:
    post(home, "/accounts/add", name="Probe Savings", institution="Probe Bank", type="savings")
    assert ["Probe Savings", "Probe Bank", "savings", "", "yes", ""] in accounts(home)


def test_the_add_form_offers_every_type(home: TestClient) -> None:
    form = Page(home.get("/accounts").text).find("/accounts/add")
    assert form["selects"]["type"] == [
        ("checking", False),
        ("savings", False),
        ("credit_card", True),
        ("other", False),
    ]
    assert set(form["inputs"]) == {"csrf", "name", "institution", "last4"}


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (
            {"name": " ", "institution": "Probe Bank", "type": "other"},
            "account name must not be empty",
        ),
        ({"name": "Probe", "institution": "", "type": "other"}, "institution must not be empty"),
        (
            {"name": "Probe", "institution": "Probe Bank", "type": "loan"},
            "type must be one of: checking, savings, credit_card, other",
        ),
        (
            {"name": "Probe", "institution": "Probe Bank", "type": "other", "last4": "12a4"},
            "last4 must be exactly 4 digits",
        ),
        (
            {"name": "test <CARD>", "institution": "Probe Bank", "type": "other"},
            "an account with this name already exists",
        ),
    ],
)
def test_a_refused_account_keeps_the_form(home: TestClient, fields: dict, message: str) -> None:
    response = post(home, "/accounts/add", **fields)
    assert refused(response, message)
    form = Page(response.text).find("/accounts/add")
    assert form["inputs"]["name"] == ("text", fields["name"])
    assert form["inputs"]["institution"] == ("text", fields["institution"])
    assert form["inputs"]["last4"] == ("text", fields.get("last4", ""))
    assert len(accounts(home)) == 3


def test_a_refused_account_keeps_the_chosen_type(home: TestClient) -> None:
    response = post(home, "/accounts/add", name="", institution="Probe Bank", type="savings")
    selected = [
        value
        for value, chosen in Page(response.text).find("/accounts/add")["selects"]["type"]
        if chosen
    ]
    assert selected == ["savings"]


def test_the_owner_form_lists_every_account_and_person(home: TestClient) -> None:
    form = Page(home.get("/accounts").text).find("/accounts/owner")
    assert [value for value, _ in form["selects"]["account"]] == [
        "Test <Card>",
        "Test Checking",
        "Test Old Card",
    ]
    assert [value for value, _ in form["selects"]["owner"]] == ["Alex", "Sam", "joint"]


def test_no_owner_form_without_accounts(client: TestClient) -> None:
    upgrade_to_head()
    actions = [form["action"] for form in Page(client.get("/accounts").text).forms]
    assert actions == ["/accounts/add"]


@pytest.mark.parametrize(
    ("account", "owner", "shown"),
    [
        ("test checking", " sam ", "Sam"),
        ("Test <Card>", "joint", "Joint"),
        ("Test Old Card", "JOINT", "Joint"),
    ],
)
def test_set_an_owner(home: TestClient, account: str, owner: str, shown: str) -> None:
    response = post(home, "/accounts/owner", account=account, owner=owner)
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/accounts?notice=owner-set",
    )
    rows = {row[0].lower(): row[5] for row in accounts(home)}
    assert rows[account.lower()] == shown
    assert ("notice", "Owner saved.") in Page(
        home.get(response.headers["location"]).text
    ).paragraphs


@pytest.mark.parametrize(
    ("account", "owner", "message"),
    [
        ("Nope", "Alex", "account not found"),
        ("Test Checking", "Nobody", "person not found"),
        ("Test Checking", "", "person not found"),
    ],
)
def test_a_refused_owner(home: TestClient, account: str, owner: str, message: str) -> None:
    assert refused(post(home, "/accounts/owner", account=account, owner=owner), message)
    assert accounts(home)[1][5] == ""


# People


def test_add_a_person(home: TestClient) -> None:
    response = post(home, "/people/add", name="  Kim ")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/people?notice=person-added",
    )
    page = Page(home.get(response.headers["location"]).text)
    assert ("notice", "Person added.") in page.paragraphs
    assert ["Kim", "", ""] in page.rows


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("alex", "a person with this name already exists"),
        ("  ", "a person's name must be 1 to 100 characters"),
        ("Joint", "joint and unassigned are reserved names"),
    ],
)
def test_a_refused_person(home: TestClient, name: str, message: str) -> None:
    assert refused(post(home, "/people/add", name=name), message)
    assert [row[0] for row in people(home)] == ["Alex", "Sam"]


def test_add_a_cardholder_name(home: TestClient) -> None:
    response = post(home, "/people/alias", person="sam", cardholder="  sam   q doe ")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/people?notice=alias-set",
    )
    page = Page(home.get(response.headers["location"]).text)
    assert ("notice", "Cardholder name saved.") in page.paragraphs
    assert ["Sam", "", "SAM Q DOE"] in page.rows


def test_a_cardholder_name_moves_to_another_person(home: TestClient) -> None:
    post(home, "/people/alias", person="Sam", cardholder="A DOE")
    post(home, "/people/alias", person="Alex", cardholder="a doe")
    assert people(home) == [["Alex", "Test <Card>", "A DOE"], ["Sam", "", ""]]


@pytest.mark.parametrize(
    ("person", "cardholder", "message"),
    [
        ("Nobody", "A DOE", "person not found"),
        ("Sam", "   ", "a cardholder name must be 1 to 100 characters"),
    ],
)
def test_a_refused_cardholder_name(
    home: TestClient, person: str, cardholder: str, message: str
) -> None:
    assert refused(post(home, "/people/alias", person=person, cardholder=cardholder), message)
    assert people(home) == [["Alex", "Test <Card>", ""], ["Sam", "", ""]]


def test_the_cardholder_form_lists_people(home: TestClient) -> None:
    form = Page(home.get("/people").text).find("/people/alias")
    assert form["selects"]["person"] == [("Alex", False), ("Sam", False)]


def test_no_cardholder_form_without_people(client: TestClient) -> None:
    upgrade_to_head()
    actions = [form["action"] for form in Page(client.get("/people").text).forms]
    assert actions == ["/people/add"]
