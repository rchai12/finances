from datetime import date
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_person,
    create_rule,
    set_account_owner,
    set_budget,
)
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_PORT

TODAY = date(2026, 5, 25)
WITH_SECTIONS = [
    "/",
    "/accounts",
    "/account?name=Test%20Card",
    "/people",
    "/transactions/1",
    "/statements",
    "/categories",
    "/transfers",
    "/reports",
    "/insights",
    "/budgets",
    "/ahead",
    "/ahead?account=Test%20Checking",
    "/sync",
    "/backups",
]
EVERY_PAGE = [*WITH_SECTIONS, "/transactions", "/categories/rules/1"]
VOID = {"input", "br", "meta", "link", "img", "hr"}


class Layout(HTMLParser):
    """Where each h2 sits, and what stands loose in main once the cards begin."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.in_main = False
        self.sections: list[list] = []
        self.cards = 0
        self.problems: list[str] = []
        self.amounts: list[tuple[set[str], str]] = []
        self.cell: tuple[set[str], list[str]] | None = None
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = set((dict(attrs).get("class") or "").split())
        if tag == "main":
            self.in_main = True
            return
        if not self.in_main:
            return
        if tag == "td" and "amount" in classes:
            self.cell = (classes, [])
        if tag == "h2":
            top = self.sections[-1] if self.sections else None
            if top is None or "card" not in top[0] or top[1]:
                self.problems.append("an h2 that does not open a card")
        elif not self.sections and self.cards and tag not in VOID and "card" not in classes:
            self.problems.append(f"a <{tag}> outside the cards")
        if self.sections:
            self.sections[-1][1] = True
        if tag == "section":
            self.sections.append([classes, False])
            if "card" in classes:
                self.cards += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self.in_main = False
        elif tag == "section" and self.sections:
            self.sections.pop()
        elif tag == "td" and self.cell is not None:
            self.amounts.append((self.cell[0], "".join(self.cell[1]).strip()))
            self.cell = None

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell[1].append(data)


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return found


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """A card, checking, and savings in April and May 2026: purchases, a refund, pay, a card
    payment that pairs, a move to savings with two possible matches, a budget, an owner."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        set_account_owner(session, card.id, create_person(session, "Pat Example").id)
        add_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.STATEMENT)
        add_balance_snapshot(session, checking.id, date(2026, 4, 30), 310000, DataSource.STATEMENT)
        rows = [
            (card, date(2026, 4, 12), -3000, "FOOBAR GROCERY"),
            (checking, date(2026, 4, 15), 300000, "PAYCHECK EXAMPLE CORP"),
            (card, date(2026, 5, 3), -1500, "BAZ BOOKS"),
            (card, date(2026, 5, 4), 1500, "BAZ BOOKS REFUND"),
            (checking, date(2026, 5, 5), -2000, "TRANSFER TO SAVINGS"),
            (savings, date(2026, 5, 5), 2000, "TRANSFER FROM CHECKING"),
            (savings, date(2026, 5, 6), 2000, "TRANSFER FROM CHECKING"),
            (checking, date(2026, 5, 10), -50000, "PAYMENT TO TEST CARD"),
            (card, date(2026, 5, 11), 50000, "PAYMENT THANK YOU"),
            (card, date(2026, 5, 10), -20000, "FOOBAR GROCERY"),
            (card, date(2026, 5, 20), -3500, "LATE FEE"),
        ] + [(card, date(2026, 5, day), -500, "ACME COFFEE") for day in (1, 2, 4, 6, 8, 11, 13, 15)]
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for pattern, category in (("FOOBAR", "Groceries"), ("PAYCHECK", "Paycheck")):
            create_rule(session, pattern, category)
        categorize(session)
        pair_transfers(session)
        set_budget(session, "Groceries", 15000)
    engine.dispose()
    return client


@pytest.mark.parametrize("path", WITH_SECTIONS)
def test_every_section_is_a_card(home: TestClient, path: str) -> None:
    response = home.get(path)
    assert response.status_code == 200
    found = Layout(response.text)
    assert found.problems == []
    assert found.cards >= 1


def test_amounts_are_coloured_by_sign(home: TestClient) -> None:
    wrong = []
    seen = set()
    for path in EVERY_PAGE:
        for classes, text in Layout(home.get(path).text).amounts:
            tone = "neg" if text.startswith("-$") else "pos" if text.startswith("+$") else None
            expected = {"amount"} | ({tone} if tone else set())
            seen.add(tone)
            if classes != expected:
                wrong.append((path, text, sorted(classes)))
    assert wrong == []
    assert seen == {"neg", "pos", None}
