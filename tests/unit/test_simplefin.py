import base64
import json
from datetime import date
from pathlib import Path

import pytest

from finances.sync.feed import FeedTransaction
from finances.sync.simplefin import (
    NO_DESCRIPTION,
    ProviderAccount,
    ProviderAnswer,
    SyncError,
    claim_access_url,
    fetch_accounts,
    parse_account_set,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "simplefin"
ACCESS = "https://user123:secret456@bridge.simplefin.org/simplefin"
CLAIM = "https://bridge.simplefin.org/simplefin/claim/DEMO-TOKEN-1"


def payload(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def token(url: str) -> str:
    return base64.b64encode(url.encode()).decode()


class FakeTransport:
    """Answer every request with one status and body, and remember the requests."""

    def __init__(self, status: int, body: bytes) -> None:
        self.status, self.body = status, body
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, url, dict(headers)))
        return self.status, self.body


def test_a_setup_token_is_claimed_with_one_post() -> None:
    transport = FakeTransport(200, (ACCESS + "\n").encode())
    assert claim_access_url("  " + token(CLAIM) + "\n", transport) == ACCESS
    assert transport.calls == [("POST", CLAIM, {"Content-Length": "0"})]


@pytest.mark.parametrize(
    "bad",
    [
        "not base64!",
        token("http://bridge.simplefin.org/simplefin/claim/X"),
        token("https://bridge.simplefin.org.evil.example/claim/X"),
        token("https://evilsimplefin.org/claim/X"),
        token("https://simplefin.org.example/claim/X"),
        token("https://example.com/simplefin/claim/X"),
        token("https://user:pass@bridge.simplefin.org/claim/X"),
        token("ftp://bridge.simplefin.org/claim/X"),
        base64.b64encode("https://bridge.simplefin.org/é".encode()).decode(),
        "",
    ],
)
def test_a_setup_token_that_is_not_a_simplefin_https_url_is_refused_unsent(bad: str) -> None:
    transport = FakeTransport(200, ACCESS.encode())
    with pytest.raises(SyncError) as caught:
        claim_access_url(bad, transport)
    assert str(caught.value) == "setup token is not valid"
    assert transport.calls == []


def test_a_used_setup_token() -> None:
    with pytest.raises(SyncError) as caught:
        claim_access_url(token(CLAIM), FakeTransport(403, b""))
    assert str(caught.value) == "setup token was already used or does not exist"


@pytest.mark.parametrize("status", [201, 400, 404, 500])
def test_another_answer_to_a_claim(status: int) -> None:
    with pytest.raises(SyncError) as caught:
        claim_access_url(token(CLAIM), FakeTransport(status, ACCESS.encode()))
    assert str(caught.value) == "aggregator refused the setup token"


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"\xff\xfe",
        b"https://bridge.simplefin.org/simplefin",
        b"http://user:pass@bridge.simplefin.org/simplefin",
        b"https://user:pass@example.com/simplefin",
        b"https://user@bridge.simplefin.org/simplefin",
        b"<html>Error</html>",
    ],
)
def test_a_claim_answer_that_is_not_a_usable_access_url(body: bytes) -> None:
    with pytest.raises(SyncError) as caught:
        claim_access_url(token(CLAIM), FakeTransport(200, body))
    assert str(caught.value) == "aggregator answer could not be read"


def test_fetch_sends_one_get_with_basic_auth_and_no_credentials_in_the_url() -> None:
    transport = FakeTransport(200, json.dumps({"accounts": []}).encode())
    answer = fetch_accounts(ACCESS, date(2026, 5, 1), date(2026, 5, 31), transport)
    assert answer == ProviderAnswer([], [])
    assert len(transport.calls) == 1
    method, url, headers = transport.calls[0]
    assert method == "GET"
    assert url == (
        "https://bridge.simplefin.org/simplefin/accounts"
        "?start-date=1777593600&end-date=1780272000&pending=1"
    )
    assert headers == {"Authorization": "Basic " + base64.b64encode(b"user123:secret456").decode()}
    assert "secret456" not in url


def test_fetch_keeps_a_port_and_a_trailing_slash_does_not_double() -> None:
    transport = FakeTransport(200, b'{"accounts": []}')
    fetch_accounts(
        "https://a:b@beta-bridge.simplefin.org:8443/simplefin/",
        date(2026, 1, 1),
        date(2026, 1, 1),
        transport,
    )
    assert transport.calls[0][1] == (
        "https://beta-bridge.simplefin.org:8443/simplefin/accounts"
        "?start-date=1767225600&end-date=1767312000&pending=1"
    )


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "https://bridge.simplefin.org/simplefin",
        "http://a:b@bridge.simplefin.org/simplefin",
        "https://a:b@example.com/simplefin",
        "https://a:b@[bad/simplefin",
    ],
)
def test_a_stored_access_url_that_is_not_usable_is_not_sent(stored: str) -> None:
    transport = FakeTransport(200, b'{"accounts": []}')
    with pytest.raises(SyncError) as caught:
        fetch_accounts(stored, date(2026, 5, 1), date(2026, 5, 31), transport)
    assert str(caught.value) == "stored aggregator access is not valid"
    assert transport.calls == []


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (403, "aggregator access was revoked or is wrong"),
        (402, "aggregator subscription needs payment"),
        (500, "aggregator answered with an error"),
        (404, "aggregator answered with an error"),
        (204, "aggregator answered with an error"),
    ],
)
def test_fetch_statuses(status: int, message: str) -> None:
    with pytest.raises(SyncError) as caught:
        fetch_accounts(ACCESS, date(2026, 5, 1), date(2026, 5, 31), FakeTransport(status, b"{}"))
    assert str(caught.value) == message


def account_json(**changes: object) -> dict:
    account = {"id": "A", "name": "N", "currency": "USD", "balance": "1", "balance-date": 1}
    account.update(changes)
    return account


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b"{}",
        b'{"accounts": {}}',
        b'{"accounts": [{"id": "A"}]}',
        b'{"accounts": [7]}',
        json.dumps({"accounts": [account_json(balance="1.234")]}).encode(),
        json.dumps({"accounts": [account_json(**{"balance-date": "x"})]}).encode(),
        json.dumps(
            {
                "accounts": [
                    account_json(
                        transactions=[{"id": "T", "posted": 1, "amount": "abc", "description": "D"}]
                    )
                ]
            }
        ).encode(),
        json.dumps(
            {
                "accounts": [
                    account_json(transactions=[{"id": "T", "amount": "1.00", "description": "D"}])
                ]
            }
        ).encode(),
        b'{"accounts": [], "errlist": [{"code": "gen.api"}]}',
        b'{"accounts": [], "connections": [{"name": "X"}]}',
    ],
)
def test_an_answer_that_cannot_be_read(body: bytes) -> None:
    with pytest.raises(SyncError) as caught:
        fetch_accounts(ACCESS, date(2026, 5, 1), date(2026, 5, 31), FakeTransport(200, body))
    assert str(caught.value) == "aggregator answer could not be read"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_a_version_2_account_set() -> None:
    answer = parse_account_set(payload("account_set_v2"))
    assert answer.messages == ["Example Savings Bank needs you to sign in again."]
    assert answer.accounts == [
        ProviderAccount(
            provider_account_id="ACT-card-1",
            name="Example Rewards Card",
            institution="Example Card Bank",
            currency="USD",
            balance_cents=-123456,
            balance_date=date(2026, 6, 1),
            transactions=[
                FeedTransaction(
                    "TRN-1", date(2026, 5, 29), -450, "ACME COFFEE #12", False, date(2026, 5, 28)
                ),
                FeedTransaction(
                    "TRN-2", date(2026, 5, 31), -2599, "FOOBAR GROCERY", True, date(2026, 5, 31)
                ),
                FeedTransaction("TRN-3", date(2026, 6, 1), -1000, NO_DESCRIPTION, True, None),
                FeedTransaction(
                    "TRN-4", date(2026, 5, 31), 50000, "PAYMENT THANK YOU", False, None
                ),
            ],
        ),
        ProviderAccount(
            "ACT-sav-1",
            "Example Savings",
            "Example Savings Bank",
            "USD",
            1000000,
            date(2026, 5, 31),
            [],
        ),
        ProviderAccount(
            "ACT-eur-1",
            "Example Euro Account",
            "Example Savings Bank",
            "EUR",
            100,
            date(2026, 6, 1),
            [],
        ),
    ]


def test_a_version_1_account_set() -> None:
    answer = parse_account_set(payload("account_set_v1"))
    assert answer == ProviderAnswer(
        accounts=[
            ProviderAccount(
                "ACT-card-1",
                "Example Rewards Card",
                "Example Card Bank",
                "USD",
                -9901,
                date(2026, 6, 2),
                [FeedTransaction("TRN-9", date(2026, 6, 1), -9901, "ACME HARDWARE", False, None)],
            )
        ],
        messages=["Example Card Bank: connection may need attention"],
    )


def test_no_description_is_the_placeholder() -> None:
    assert NO_DESCRIPTION == "(no description)"


def test_messages_are_made_printable_short_and_blank_ones_are_left_out() -> None:
    raw = {
        "accounts": [],
        "errlist": [{"code": "gen.api", "msg": "x" * 300}, {"code": "gen.api", "msg": " \n\t "}],
        "errors": ["\u001b[31mRED\u001b[0m   alert"],
    }
    assert parse_account_set(raw).messages == ["x" * 200, "[31mRED[0m alert"]


def test_an_account_whose_institution_is_unknown_has_an_empty_institution() -> None:
    raw = {
        "accounts": [
            {
                "id": 7,
                "name": "N",
                "conn_id": "MISSING",
                "currency": "USD",
                "balance": "0",
                "balance-date": 0,
            }
        ]
    }
    account = parse_account_set(raw).accounts[0]
    assert (account.provider_account_id, account.institution, account.balance_date) == (
        "7",
        "",
        date(1970, 1, 1),
    )


def test_amounts_without_cents_and_with_one_decimal() -> None:
    raw = {
        "accounts": [
            {
                "id": "A",
                "name": "N",
                "currency": "USD",
                "balance": "-12",
                "balance-date": 0,
                "transactions": [{"id": "T", "posted": 86400, "amount": "3.5", "description": "D"}],
            }
        ]
    }
    account = parse_account_set(raw).accounts[0]
    assert (account.balance_cents, account.transactions[0].amount_cents) == (-1200, 350)
    assert account.transactions[0].posted_date == date(1970, 1, 2)
