import base64
import json
from datetime import UTC, datetime
from html.parser import HTMLParser

import keyring
import keyring.backend
import keyring.errors
import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import (
    create_account,
    list_accounts,
    list_feed_accounts,
)
from finances.sync import transport
from finances.web.app import create_app

PORT = 8765
SERVICE = "finances-simplefin"
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"
CLAIM = "https://bridge.simplefin.org/simplefin/claim/DEMO-1"
TOKEN = base64.b64encode(CLAIM.encode()).decode()
BAD_NAME = "a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter"
RUN_HEADINGS = [
    "Link",
    "Account",
    "SimpleFIN account",
    "New",
    "Changed",
    "Removed",
    "Same",
    "Drift",
    "Problem",
]


class Page(HTMLParser):
    """The parts of a page the tests read: table rows, paragraphs, and forms (not the menu's)."""

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
        self.in_nav = False
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "nav":
            self.in_nav = True
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
            if not self.in_nav:
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
        if tag == "nav":
            self.in_nav = False
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


def stamp(days_ago: int) -> int:
    today = datetime.now(UTC).date()
    noon = datetime(today.year, today.month, today.day, 12, tzinfo=UTC)
    return int(noon.timestamp()) - days_ago * 86400


def account(account_id: str, name: str, balance: str, *moves: tuple[str, int, str]) -> dict:
    return {
        "id": account_id,
        "name": name,
        "conn_id": "C-1",
        "currency": "USD",
        "balance": balance,
        "balance-date": stamp(0),
        "transactions": [
            {"id": feed_id, "posted": stamp(days_ago), "amount": amount, "description": "PROBE"}
            for feed_id, days_ago, amount in moves
        ],
    }


class Bridge:
    """A fake SimpleFIN Bridge: claims give an access URL; each access URL has its answer."""

    def __init__(self) -> None:
        self.claim = (200, ALEX.encode())
        self.answers: dict[str, tuple[int, dict]] = {}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, url))
        if method == "POST":
            return self.claim
        status, body = self.answers[headers["Authorization"]]
        return status, json.dumps(body).encode()

    def answer(self, access: str, *accounts: dict, status: int = 200, messages=()) -> None:
        user, password = access.split("//")[1].split("@")[0].split(":")
        key = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        body = {
            "errlist": [{"code": "con.auth", "msg": text} for text in messages],
            "connections": [
                {"conn_id": "C-1", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}
            ],
            "accounts": list(accounts),
        }
        self.answers[key] = (status, body)


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringError("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.KeyringError("locked")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.KeyringError("locked")


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> Bridge:
    fake = Bridge()
    monkeypatch.setattr(transport, "urllib_transport", fake)
    return fake


@pytest.fixture
def home(tmp_settings: Settings, bridge: Bridge) -> TestClient:
    """Two accounts, nothing mapped, nothing in the Keychain."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_account(session, "Test Checking", "Test Bank", "checking")
    engine.dispose()
    client = TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")
    client.get("/sync")
    return client


def post(client: TestClient, path: str, **fields: str):
    return client.post(
        path, data={"csrf": client.cookies["fin_csrf"], **fields}, follow_redirects=False
    )


def mappings() -> list[tuple[str, str, str]]:
    engine = get_engine()
    with session_scope(engine) as session:
        names = {item.id: item.name for item in list_accounts(session, include_inactive=True)}
        found = [
            (item.link, item.provider_account_id, names[item.account_id])
            for item in list_feed_accounts(session)
        ]
    engine.dispose()
    return found


def refused(response, status: int, message: str) -> bool:
    return response.status_code == status and ("error", message) in Page(response.text).paragraphs


# Linking a SimpleFIN subscription


def test_link_claims_the_token_and_keeps_the_access_in_the_keychain(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-1.00"))
    response = post(home, "/sync/link", link="alex", token=TOKEN)
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/sync/accounts?link=alex&notice=linked",
    )
    assert bridge.calls == [("POST", CLAIM)]
    assert keychain.passwords == {(SERVICE, "alex"): ALEX}
    page = home.get(response.headers["location"])
    assert ("notice", "Link saved. Map each SimpleFIN account below.") in Page(page.text).paragraphs
    assert "alex-pass" not in page.text and TOKEN not in page.text


def test_the_link_form_hides_the_token(home: TestClient) -> None:
    form = Page(home.get("/sync").text).find("/sync/link")
    assert form["inputs"]["token"] == ("password", "")
    assert form["inputs"]["replace"] == ("checkbox", "on")
    assert 'autocomplete="off"' in home.get("/sync").text


def test_a_link_that_exists_is_replaced_only_when_asked(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    keychain.passwords[(SERVICE, "alex")] = SAM
    response = post(home, "/sync/link", link="alex", token=TOKEN)
    assert refused(response, 400, "link alex is already set up; tick Replace to set it up again")
    assert bridge.calls == []
    assert keychain.passwords == {(SERVICE, "alex"): SAM}
    response = post(home, "/sync/link", link="alex", token=TOKEN, replace="on")
    assert response.status_code == 303
    assert keychain.passwords == {(SERVICE, "alex"): ALEX}


@pytest.mark.parametrize(
    ("link", "token", "claim", "message"),
    [
        ("Alex", TOKEN, (200, ALEX.encode()), BAD_NAME),
        ("", TOKEN, (200, ALEX.encode()), BAD_NAME),
        ("alex", "not a token", (200, ALEX.encode()), "setup token is not valid"),
        ("alex", TOKEN, (403, b""), "setup token was already used or does not exist"),
    ],
)
def test_a_refused_link_keeps_the_name_and_never_the_token(
    home: TestClient,
    bridge: Bridge,
    keychain,
    link: str,
    token: str,
    claim: tuple[int, bytes],
    message: str,
) -> None:
    bridge.claim = claim
    response = post(home, "/sync/link", link=link, token=token)
    assert refused(response, 400, message)
    form = Page(response.text).find("/sync/link")
    assert form["inputs"]["link"] == ("text", link)
    assert form["inputs"]["token"] == ("password", "")
    assert TOKEN not in response.text
    assert keychain.passwords == {}


def test_link_when_the_keychain_fails(home: TestClient, bridge: Bridge) -> None:
    keyring.set_keyring(BrokenKeyring())
    response = post(home, "/sync/link", link="alex", token=TOKEN)
    assert refused(response, 400, "could not use the system keychain")
    assert bridge.calls == []


# Unlinking


def test_unlink_forgets_the_access_and_keeps_the_mappings(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    response = post(home, "/sync/unlink", link="alex")
    assert (response.status_code, response.headers["location"]) == (303, "/sync?notice=unlinked")
    assert keychain.passwords == {}
    assert mappings() == [("alex", "ACT-1", "Test Card")]
    page = Page(home.get(response.headers["location"]).text)
    assert ("notice", "Link removed from the Keychain.") in page.paragraphs
    assert page.rows[1][:4] == ["alex", "Test Card", "ACT-1", "no"]
    assert bridge.calls == []


@pytest.mark.parametrize(
    ("link", "message"), [("sam", "link sam is not set up"), ("Sam", BAD_NAME)]
)
def test_a_refused_unlink(home: TestClient, keychain, link: str, message: str) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    assert refused(post(home, "/sync/unlink", link=link), 400, message)
    assert keychain.passwords == {(SERVICE, "alex"): ALEX}


def test_unlink_when_the_keychain_fails(home: TestClient) -> None:
    keyring.set_keyring(BrokenKeyring())
    assert refused(
        post(home, "/sync/unlink", link="alex"), 400, "could not use the system keychain"
    )


def test_the_sync_page_lists_each_mapped_link_with_its_buttons(home: TestClient, keychain) -> None:
    post(home, "/sync/map", link="sam", feed_account="ACT-2", account="Test Checking")
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    page = Page(home.get("/sync").text)
    unlinks = [form for form in page.forms if form["action"] == "/sync/unlink"]
    assert [form["inputs"]["link"] for form in unlinks] == [("hidden", "alex"), ("hidden", "sam")]
    assert [form["action"] for form in page.forms if form["action"] == "/sync/run"] == ["/sync/run"]
    assert '<a href="/sync/accounts?link=alex">' in home.get("/sync").text


def test_no_run_or_unlink_buttons_with_nothing_mapped(home: TestClient) -> None:
    actions = [form["action"] for form in Page(home.get("/sync").text).forms]
    assert actions == ["/sync/link", "/sync/accounts"]


# A link's SimpleFIN accounts


def test_a_links_accounts_with_what_each_is_mapped_to(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    post(home, "/sync/map", link="sam", feed_account="ACT-2", account="Test Checking")
    bridge.answer(
        ALEX,
        account("ACT-1", "Probe <Card>", "-1.00"),
        account("ACT-2", "Probe Savings", "5.00"),
        messages=("Probe note",),
    )
    response = home.get("/sync/accounts?link=alex")
    page = Page(response.text)
    assert response.status_code == 200
    assert page.rows == [
        ["SimpleFIN account", "Institution", "Name", "Currency", "Mapped to"],
        ["ACT-1", "Probe Bank", "Probe <Card>", "USD", "Test Card"],
        ["ACT-2", "Probe Bank", "Probe Savings", "USD", ""],
    ]
    assert ("notice", "SimpleFIN: Probe note") in page.paragraphs
    assert "Probe &lt;Card&gt;" in response.text
    assert "alex-pass" not in response.text
    method, url = bridge.calls[0]
    assert method == "GET" and url.startswith(
        ALEX.replace("alex-user:alex-pass@", "") + "/accounts"
    )


def test_each_account_can_be_mapped_from_a_list(home: TestClient, bridge: Bridge, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Checking")
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-1.00"), account("ACT-2", "Probe X", "0"))
    page = Page(home.get("/sync/accounts?link=alex").text)
    maps = [form for form in page.forms if form["action"] == "/sync/map"]
    assert [form["inputs"]["feed_account"] for form in maps] == [
        ("hidden", "ACT-1"),
        ("hidden", "ACT-2"),
    ]
    assert all(form["inputs"]["link"] == ("hidden", "alex") for form in maps)
    assert maps[0]["selects"]["account"] == [("Test Card", False), ("Test Checking", True)]
    assert maps[1]["selects"]["account"] == [("Test Card", False), ("Test Checking", False)]


def test_only_an_unmapped_account_offers_create_and_map(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-1.00"), account("ACT-2", "Probe X", "0"))
    page = Page(home.get("/sync/accounts?link=alex").text)
    creates = [form for form in page.forms if form["action"] == "/sync/create"]
    assert len(creates) == 1
    inputs = creates[0]["inputs"]
    assert inputs["feed_account"] == ("hidden", "ACT-2")
    assert inputs["account"] == ("text", "Probe X")
    assert inputs["institution"] == ("text", "Probe Bank")
    assert [value for value, _ in creates[0]["selects"]["type"]] == [
        "checking",
        "savings",
        "credit_card",
        "other",
    ]


@pytest.mark.parametrize(
    ("query", "status", "message"),
    [
        ("", 400, BAD_NAME),
        ("?link=Alex", 400, BAD_NAME),
        ("?link=sam", 400, "link sam is not set up"),
        ("?link=alex", 502, "aggregator access was revoked or is wrong"),
    ],
)
def test_a_links_accounts_refused(
    home: TestClient, bridge: Bridge, keychain, query: str, status: int, message: str
) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    bridge.answer(ALEX, status=403)
    response = home.get(f"/sync/accounts{query}")
    assert refused(response, status, message)
    assert Page(response.text).rows == []


def test_a_links_accounts_need_a_migrated_database(tmp_settings: Settings, bridge: Bridge) -> None:
    client = TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")
    response = client.get("/sync/accounts?link=alex")
    assert refused(response, 503, "The database is not up to date. Run: fin db upgrade")
    assert bridge.calls == []


def test_a_links_accounts_when_the_keychain_fails(home: TestClient, bridge: Bridge) -> None:
    keyring.set_keyring(BrokenKeyring())
    assert refused(home.get("/sync/accounts?link=alex"), 502, "could not use the system keychain")
    assert bridge.calls == []


# Mapping


def test_map_an_account(home: TestClient, bridge: Bridge) -> None:
    response = post(home, "/sync/map", link="alex", feed_account=" ACT-1 ", account="test card")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/sync/accounts?link=alex&notice=mapped",
    )
    assert mappings() == [("alex", "ACT-1", "Test Card")]
    response = post(home, "/sync/map", link="alex", feed_account="ACT-7", account="Test Card")
    assert mappings() == [("alex", "ACT-7", "Test Card")]
    assert bridge.calls == []


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"link": "alex", "feed_account": "ACT-1", "account": "Nope"}, "account not found"),
        (
            {"link": "alex", "feed_account": "  ", "account": "Test Card"},
            "feed account id must be 1 to 200 characters",
        ),
        (
            {"link": "alex", "feed_account": "X" * 201, "account": "Test Card"},
            "feed account id must be 1 to 200 characters",
        ),
        (
            {"link": "alex", "feed_account": "ACT-9", "account": "Test Checking"},
            "feed account is already mapped to another account",
        ),
        ({"link": "Alex", "feed_account": "ACT-1", "account": "Test Card"}, BAD_NAME),
    ],
)
def test_a_refused_mapping(home: TestClient, fields: dict, message: str) -> None:
    post(home, "/sync/map", link="alex", feed_account="ACT-9", account="Test Card")
    response = post(home, "/sync/map", **fields)
    assert refused(response, 400, message)
    assert '<a href="/sync">Back</a>' in response.text
    assert mappings() == [("alex", "ACT-9", "Test Card")]


def test_create_an_account_and_map_it(home: TestClient, bridge: Bridge) -> None:
    response = post(
        home,
        "/sync/create",
        link="sam",
        feed_account="ACT-5",
        account=" Probe Savings ",
        institution="Probe Bank",
        type="savings",
        last4="5555",
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/sync/accounts?link=sam&notice=mapped",
    )
    assert mappings() == [("sam", "ACT-5", "Probe Savings")]
    rows = Page(home.get("/accounts").text).rows
    assert ["Probe Savings", "Probe Bank", "savings", "••5555", "yes", ""] in rows
    assert bridge.calls == []


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"account": "test card"}, "an account with this name already exists"),
        ({"type": "loan"}, "type must be one of: checking, savings, credit_card, other"),
        ({"last4": "55"}, "last4 must be exactly 4 digits"),
        ({"feed_account": ""}, "feed account id must be 1 to 200 characters"),
        ({"feed_account": "ACT-9"}, "feed account is already mapped to another account"),
        ({"link": "Sam"}, BAD_NAME),
        ({"institution": " "}, "institution must not be empty"),
    ],
)
def test_a_refused_create_changes_nothing(home: TestClient, fields: dict, message: str) -> None:
    post(home, "/sync/map", link="sam", feed_account="ACT-9", account="Test Card")
    sent = {
        "link": "sam",
        "feed_account": "ACT-5",
        "account": "Probe Savings",
        "institution": "Probe Bank",
        "type": "savings",
        **fields,
    }
    response = post(home, "/sync/create", **sent)
    assert refused(response, 400, message)
    assert mappings() == [("sam", "ACT-9", "Test Card")]
    assert len(Page(home.get("/accounts?closed=true").text).rows) == 3


# Sync now


def test_sync_now_pulls_every_link(home: TestClient, bridge: Bridge, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    keychain.passwords[(SERVICE, "sam")] = SAM
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    post(home, "/sync/map", link="sam", feed_account="ACT-1", account="Test Checking")
    bridge.answer(
        ALEX,
        account("ACT-1", "Probe Card", "-12.50", ("A-1", 3, "-12.50")),
        account("ACT-9", "Probe Unmapped", "1.00"),
    )
    bridge.answer(
        SAM,
        account("ACT-1", "Probe Checking", "-4.00", ("S-1", 2, "-4.00")),
        messages=("Sam bank note",),
    )
    response = post(home, "/sync/run")
    page = Page(response.text)
    assert response.status_code == 200
    assert page.rows == [
        RUN_HEADINGS,
        ["alex", "Test Card", "ACT-1", "1", "0", "0", "0", "", ""],
        ["alex", "", "ACT-9", "", "", "", "", "", "not mapped"],
        ["sam", "Test Checking", "ACT-1", "1", "0", "0", "0", "", ""],
    ]
    assert ("notice", "SimpleFIN sam: Sam bank note") in page.paragraphs
    assert [kind for kind, _ in page.paragraphs if kind == "error"] == []
    assert [
        len(Page(home.get(f"/transactions?account={name}").text).rows)
        for name in (
            "Test Card",
            "Test Checking",
        )
    ] == [2, 2]


def test_sync_now_keeps_what_was_pulled(home: TestClient, bridge: Bridge, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-12.50", ("A-1", 3, "-12.50")))
    post(home, "/sync/run")
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-15.00", ("A-1", 3, "-12.50")))
    rows = Page(post(home, "/sync/run").text).rows
    assert rows[1:] == [["alex", "Test Card", "ACT-1", "0", "0", "0", "1", "-$2.50", ""]]
    status = Page(home.get("/sync").text).rows
    assert status[1][-1] == "-$2.50"


def test_one_link_failing_does_not_stop_the_others(
    home: TestClient, bridge: Bridge, keychain
) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    keychain.passwords[(SERVICE, "sam")] = SAM
    post(home, "/sync/map", link="alex", feed_account="ACT-1", account="Test Card")
    post(home, "/sync/map", link="bob", feed_account="ACT-1", account="Test Checking")
    post(
        home,
        "/sync/create",
        link="sam",
        feed_account="ACT-1",
        account="Test Other",
        institution="Probe Bank",
        type="other",
    )
    bridge.answer(ALEX, status=403)
    bridge.answer(SAM, account("ACT-1", "Probe Other", "-4.00", ("S-1", 2, "-4.00")))
    page = Page(post(home, "/sync/run").text)
    assert [text for kind, text in page.paragraphs if kind == "error"] == [
        "link alex: aggregator access was revoked or is wrong",
        "link bob is not set up",
    ]
    assert page.rows == [RUN_HEADINGS, ["sam", "Test Other", "ACT-1", "1", "0", "0", "0", "", ""]]


def test_sync_now_with_nothing_mapped(home: TestClient, bridge: Bridge) -> None:
    response = post(home, "/sync/run")
    assert response.status_code == 200
    assert ("empty", "No mapped accounts.") in Page(response.text).paragraphs
    assert bridge.calls == []
