import json
from datetime import UTC, date, datetime
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, map_feed_account
from finances.sync import transport
from finances.web.app import create_app

PORT = 8765
GROUP_GIVEN = "rules and transactions take a category, not a group"
POSTS = [
    "/categories/add",
    "/categories/rules/add",
    "/categories/rules/delete",
    "/transactions/1/category",
    "/transactions/1/category/clear",
]
GROUPS = [
    "Entertainment",
    "Financial",
    "Food",
    "Health",
    "Home",
    "Income",
    "Personal",
    "Shopping",
    "Subscriptions",
    "Transfers",
    "Transport",
    "Travel",
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
        self.links: list[str] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "a":
            self.links.append(values.get("href", ""))
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

    def all(self, action: str) -> list[dict]:
        return [form for form in self.forms if form["action"] == action]

    def find(self, action: str) -> dict:
        found = [form for form in self.forms if form["action"] == action]
        assert len(found) == 1, action
        return found[0]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Transactions 1 to 4 on Test Card, posted on 1 to 4 May 2026, none categorized."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card", last4="9999")
        for day, cents, description in (
            (1, -450, "SQ *ACME COFFEE"),
            (2, -500, "ACME COFFEE #12"),
            (3, -2599, "FOOBAR GROCERY #77 DECATUR GA"),
            (4, 300000, "PAYCHECK EXAMPLE CORP"),
        ):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{day}".ljust(64, "0"),
                )
            )
    engine.dispose()
    client.get("/categories")
    return client


def post(client: TestClient, path: str, **fields: str):
    return client.post(
        path, data={"csrf": client.cookies["fin_csrf"], **fields}, follow_redirects=False
    )


def page(client: TestClient, path: str) -> Page:
    return Page(client.get(path).text)


def uncategorized_ids(client: TestClient) -> list[str]:
    """The ids in the Uncategorized table, which is the page's first and has five columns."""
    rows = page(client, "/categories").rows
    if rows[0] != ["ID", "Date", "Account", "Merchant", "Amount"]:
        return []
    ids = []
    for row in rows[1:]:
        if len(row) != 5:
            break
        ids.append(row[0])
    return ids


def detail(client: TestClient, transaction_id: int) -> dict[str, str]:
    return dict(
        row for row in page(client, f"/transactions/{transaction_id}").rows if len(row) == 2
    )


# The menu and the pages


def test_the_menu_has_categories(home: TestClient) -> None:
    html = home.get("/categories").text
    assert 'href="/categories" aria-current="page">Categories</a>' in html
    assert html.count('aria-current="page"') == 1
    html = home.get("/transactions/1").text
    assert 'href="/transactions" aria-current="page">Transactions</a>' in html


def test_the_categories_page(home: TestClient) -> None:
    found = page(home, "/categories")
    assert found.rows[:2] == [
        ["ID", "Date", "Account", "Merchant", "Amount"],
        ["4", "2026-05-04", "Test Card", "PAYCHECK EXAMPLE CORP", "$3,000.00"],
    ]
    assert [f"/transactions/{n}" for n in (4, 3, 2, 1)] == [
        link for link in found.links if link.startswith("/transactions/")
    ]
    assert ("empty", "No rules.") in found.paragraphs
    tree_start = found.rows.index(["Group", "Category", "Kind"])
    assert len(found.rows) - tree_start - 1 == 34
    assert ["Health", "Fitness", "sensitive"] in found.rows
    category_form = found.find("/categories/add")
    assert [value for value, _ in category_form["selects"]["group"]] == GROUPS
    rule_form = found.find("/categories/rules/add")
    assert [value for value, _ in rule_form["selects"]["match"]] == [
        "contains",
        "starts_with",
        "equals",
    ]
    options = rule_form["selects"]["category"]
    assert options[0] == ("", True)
    assert len(options) == 35
    assert ("Dining", False) in options and ("Food", False) not in options
    assert rule_form["inputs"]["priority"] == ("text", "0")
    assert "back" not in rule_form["inputs"]


def test_every_form_carries_the_token(home: TestClient) -> None:
    for path in ("/categories", "/transactions/1"):
        forms = [form for form in page(home, path).forms if form["method"] == "post"]
        assert forms
        assert all(form["inputs"]["csrf"] == ("hidden", home.cookies["fin_csrf"]) for form in forms)


@pytest.mark.parametrize("path", POSTS)
def test_a_form_without_the_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
    assert home.get(path).status_code == 405


# Categories


def test_add_a_category(home: TestClient) -> None:
    response = post(home, "/categories/add", name="  Therapy ", group="Health")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/categories?notice=category-added",
    )
    found = page(home, response.headers["location"])
    assert ("notice", "Category added.") in found.paragraphs
    assert ["Health", "Therapy", "sensitive"] in found.rows


@pytest.mark.parametrize(
    ("name", "group", "message"),
    [
        ("dining", "Food", "a category with this name already exists"),
        ("  ", "Food", "a category name must be 1 to 50 characters"),
        ("Therapy", "Dining", "group not found"),
    ],
)
def test_a_refused_category_keeps_the_form(
    home: TestClient, name: str, group: str, message: str
) -> None:
    response = post(home, "/categories/add", name=name, group=group)
    found = Page(response.text)
    assert response.status_code == 400
    assert ("error", message) in found.paragraphs
    assert found.find("/categories/add")["inputs"]["name"] == ("text", name)


# Rules


def test_add_a_rule_and_the_rules_run_again(home: TestClient) -> None:
    response = post(
        home,
        "/categories/rules/add",
        pattern="acme coffee",
        match="contains",
        priority="",
        category="Coffee & Dessert",
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/categories?notice=rule-added",
    )
    found = page(home, response.headers["location"])
    assert ("notice", "Rule added, and the rules were run again.") in found.paragraphs
    assert ["1", "0", "contains", "ACME COFFEE", "Coffee & Dessert", "Delete"] in found.rows
    assert uncategorized_ids(home) == ["4", "3"]
    assert detail(home, 1)["Category"] == "Coffee & Dessert"
    assert detail(home, 1)["Set"] == "by rule 1"
    assert page(home, "/transactions/1").all("/transactions/1/category/clear") == []


def test_a_rule_made_from_a_transaction_returns_to_it(home: TestClient) -> None:
    rule_form = page(home, "/transactions/3").find("/categories/rules/add")
    assert rule_form["inputs"]["pattern"] == ("text", "FOOBAR GROCERY")
    assert rule_form["inputs"]["back"] == ("hidden", "3")
    response = post(
        home,
        "/categories/rules/add",
        pattern="FOOBAR GROCERY",
        match="equals",
        priority="2",
        category="Groceries",
        back="3",
    )
    assert response.headers["location"] == "/transactions/3?notice=rule-added"
    assert detail(home, 3)["Category"] == "Groceries"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"priority": "high"}, "priority must be a whole number"),
        ({"priority": "1.5"}, "priority must be a whole number"),
        ({"category": ""}, "category not found"),
        ({"category": "Food"}, GROUP_GIVEN),
        ({"match": "regex"}, "match must be one of: contains, starts_with, equals"),
        ({"pattern": "  "}, "a rule pattern must be 1 to 100 characters"),
    ],
)
def test_a_refused_rule_keeps_the_form(home: TestClient, fields: dict, message: str) -> None:
    sent = {"pattern": "ACME", "match": "contains", "priority": "0", "category": "Dining", **fields}
    response = post(home, "/categories/rules/add", **sent)
    found = Page(response.text)
    assert response.status_code == 400
    assert ("error", message) in found.paragraphs
    assert found.find("/categories/rules/add")["inputs"]["pattern"] == ("text", sent["pattern"])
    assert ("empty", "No rules.") in found.paragraphs


def test_negative_priorities_are_whole_numbers(home: TestClient) -> None:
    response = post(
        home,
        "/categories/rules/add",
        pattern="ACME",
        match="contains",
        priority="-3",
        category="Dining",
    )
    assert response.status_code == 303
    assert ["1", "-3", "contains", "ACME", "Dining", "Delete"] in page(home, "/categories").rows


def test_delete_a_rule_and_the_rules_run_again(home: TestClient) -> None:
    post(
        home,
        "/categories/rules/add",
        pattern="ACME",
        match="contains",
        priority="0",
        category="Dining",
    )
    delete = page(home, "/categories").find("/categories/rules/delete")
    assert delete["inputs"]["rule"] == ("hidden", "1")
    response = post(home, "/categories/rules/delete", rule="1")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/categories?notice=rule-deleted",
    )
    found = page(home, response.headers["location"])
    assert ("notice", "Rule deleted, and the rules were run again.") in found.paragraphs
    assert uncategorized_ids(home) == ["4", "3", "2", "1"]


@pytest.mark.parametrize("rule", ["9", "abc", ""])
def test_deleting_an_unknown_rule(home: TestClient, rule: str) -> None:
    response = post(home, "/categories/rules/delete", rule=rule)
    assert response.status_code == 400
    assert ("error", "rule not found") in Page(response.text).paragraphs


# One transaction


def test_a_transaction_page(home: TestClient) -> None:
    assert detail(home, 3) == {
        "Date": "2026-05-03",
        "Account": "Test Card",
        "Description": "FOOBAR GROCERY #77 DECATUR GA",
        "Merchant": "FOOBAR GROCERY",
        "Amount": "-$25.99",
        "Card": "",
        "Category": "",
        "Set": "",
    }
    assert page(home, "/transactions/3").find("/transactions/3/category")["selects"]["category"][
        0
    ] == ("", True)
    assert page(home, "/transactions/3").all("/transactions/3/category/clear") == []


@pytest.mark.parametrize("path", ["/transactions/99", "/transactions/abc", "/transactions/0"])
def test_an_unknown_transaction(home: TestClient, path: str) -> None:
    response = home.get(path)
    assert response.status_code == 404
    assert ("error", "transaction not found") in Page(response.text).paragraphs


def test_set_a_category_by_hand_and_leave_it_to_the_rules(home: TestClient) -> None:
    post(
        home,
        "/categories/rules/add",
        pattern="FOOBAR",
        match="contains",
        priority="0",
        category="Dining",
    )
    response = post(home, "/transactions/3/category", category="groceries")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/3?notice=category-set",
    )
    found = page(home, response.headers["location"])
    assert ("notice", "Category saved.") in found.paragraphs
    assert (detail(home, 3)["Category"], detail(home, 3)["Set"]) == ("Groceries", "by hand")
    assert (
        found.find("/transactions/3/category")["selects"]["category"].count(("Groceries", True))
        == 1
    )
    response = post(home, "/transactions/3/category/clear")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/3?notice=category-cleared",
    )
    found = page(home, response.headers["location"])
    assert ("notice", "Category left to the rules.") in found.paragraphs
    assert (detail(home, 3)["Category"], detail(home, 3)["Set"]) == ("Dining", "by rule 1")


@pytest.mark.parametrize(
    ("category", "message"),
    [("Food", GROUP_GIVEN), ("", "category not found"), ("Nope", "category not found")],
)
def test_a_refused_category_by_hand(home: TestClient, category: str, message: str) -> None:
    response = post(home, "/transactions/3/category", category=category)
    assert response.status_code == 400
    assert ("error", message) in Page(response.text).paragraphs
    assert detail(home, 3)["Category"] == ""


@pytest.mark.parametrize("path", ["/transactions/99/category", "/transactions/99/category/clear"])
def test_setting_an_unknown_transaction(home: TestClient, path: str) -> None:
    response = post(home, path, category="Dining")
    assert response.status_code == 404
    assert ("error", "transaction not found") in Page(response.text).paragraphs


# Transactions page and Sync now


def test_each_date_on_the_transactions_page_opens_the_transaction(home: TestClient) -> None:
    found = page(home, "/transactions")
    assert found.rows[1][0] == "2026-05-04"
    assert [link for link in found.links if link.startswith("/transactions/")] == [
        "/transactions/4",
        "/transactions/3",
        "/transactions/2",
        "/transactions/1",
    ]


def test_sync_now_categorizes_new_transactions(
    home: TestClient, keychain, monkeypatch: pytest.MonkeyPatch
) -> None:
    keychain.passwords[("finances-simplefin", "kim")] = "https://u:p@bridge.simplefin.org/x"
    engine = get_engine()
    with session_scope(engine) as session:
        map_feed_account(session, 1, "ACT-1", "kim")
    engine.dispose()
    post(
        home,
        "/categories/rules/add",
        pattern="ACME BAKERY",
        match="contains",
        priority="0",
        category="Coffee & Dessert",
    )
    noon = int(datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0).timestamp())
    body = {
        "errlist": [],
        "connections": [{"conn_id": "C", "name": "Test Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": "ACT-1",
                "name": "Card",
                "conn_id": "C",
                "currency": "USD",
                "balance": "-3.25",
                "balance-date": noon,
                "transactions": [
                    {"id": "F1", "posted": noon, "amount": "-3.25", "description": "ACME BAKERY"}
                ],
            }
        ],
    }
    monkeypatch.setattr(transport, "urllib_transport", lambda *_: (200, json.dumps(body).encode()))
    assert post(home, "/sync/run").status_code == 200
    assert uncategorized_ids(home) == ["4", "3", "2", "1"]
