"""The SimpleFIN client: claim a setup token, fetch accounts, and read the answer.

Every request goes through the transport the caller passes in; this module opens nothing.
"""

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import SplitResult, unquote, urlsplit

from finances.domain.money import parse_money
from finances.sync.feed import FeedTransaction

Transport = Callable[[str, str, dict[str, str]], tuple[int, bytes]]
NO_DESCRIPTION = "(no description)"

_HOST = "simplefin.org"
_MESSAGE_LIMIT = 200
_EPOCH = date(1970, 1, 1)
_SECONDS_PER_DAY = 86400
_UNREADABLE = (ValueError, TypeError, KeyError, AttributeError, OverflowError)


class SyncError(Exception):
    """Raised when the aggregator cannot be reached or its answer cannot be used."""


@dataclass(frozen=True)
class ProviderAccount:
    """One account in the aggregator's answer. Amounts are from the account holder's side."""

    provider_account_id: str
    name: str
    institution: str
    currency: str
    balance_cents: int
    balance_date: date
    transactions: list[FeedTransaction]


@dataclass(frozen=True)
class ProviderAnswer:
    """The aggregator's answer: its accounts and the messages it asks to show the user."""

    accounts: list[ProviderAccount]
    messages: list[str]


def _allowed(url: str) -> SplitResult | None:
    """Return the parts of an https URL on a simplefin.org host, otherwise None."""
    try:
        parts = urlsplit(url)
        host, _ = parts.hostname or "", parts.port
    except ValueError:
        return None
    if parts.scheme == "https" and (host == _HOST or host.endswith("." + _HOST)):
        return parts
    return None


def _usable(url: str) -> SplitResult | None:
    """Return the parts of an allowed URL that carries a user name and a password."""
    parts = _allowed(url)
    if parts is None or not parts.username or not parts.password:
        return None
    return parts


def claim_access_url(setup_token: str, transport: Transport) -> str:
    """Turn a setup token into an access URL with one POST. The token works once."""
    try:
        claim_url = base64.b64decode(setup_token.strip(), validate=True).decode("ascii")
    except ValueError:
        raise SyncError("setup token is not valid") from None
    parts = _allowed(claim_url)
    if parts is None or parts.username is not None:
        raise SyncError("setup token is not valid")
    status, body = transport("POST", claim_url, {"Content-Length": "0"})
    if status == 403:
        raise SyncError("setup token was already used or does not exist")
    if status != 200:
        raise SyncError("aggregator refused the setup token")
    try:
        access_url = body.decode("ascii").strip()
    except UnicodeDecodeError:
        raise SyncError("aggregator answer could not be read") from None
    if _usable(access_url) is None:
        raise SyncError("aggregator answer could not be read")
    return access_url


def _seconds(day: date) -> int:
    """Return midnight UTC at the start of the day, in Unix seconds."""
    return (day - _EPOCH).days * _SECONDS_PER_DAY


def fetch_accounts(access_url: str, start: date, end: date, transport: Transport) -> ProviderAnswer:
    """Ask for every account with its transactions from start to end, both included."""
    parts = _usable(access_url)
    if parts is None:
        raise SyncError("stored aggregator access is not valid")
    host = parts.hostname
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    url = (
        f"https://{host}{parts.path.rstrip('/')}/accounts"
        f"?start-date={_seconds(start)}&end-date={_seconds(end + timedelta(days=1))}&pending=1"
    )
    credentials = f"{unquote(parts.username)}:{unquote(parts.password)}".encode()
    headers = {"Authorization": "Basic " + base64.b64encode(credentials).decode("ascii")}
    status, body = transport("GET", url, headers)
    if status == 403:
        raise SyncError("aggregator access was revoked or is wrong")
    if status == 402:
        raise SyncError("aggregator subscription needs payment")
    if status != 200:
        raise SyncError("aggregator answered with an error")
    try:
        return parse_account_set(json.loads(body))
    except _UNREADABLE:
        raise SyncError("aggregator answer could not be read") from None


def _clean(text: str) -> str:
    """Return a message as one short printable line."""
    printable = "".join(char for char in " ".join(text.split()) if char.isprintable())
    return " ".join(printable.split())[:_MESSAGE_LIMIT]


def _day(seconds: int) -> date:
    """Return the UTC date of a Unix time, whatever the computer's time zone."""
    return _EPOCH + timedelta(days=seconds // _SECONDS_PER_DAY)


def _transaction(item: dict, balance_date: date) -> FeedTransaction:
    transacted = item.get("transacted_at")
    transaction_date = _day(transacted) if transacted else None
    posted = item["posted"]
    return FeedTransaction(
        feed_id=str(item["id"]),
        posted_date=_day(posted) if posted else (transaction_date or balance_date),
        amount_cents=parse_money(item["amount"]),
        description=" ".join(item["description"].split()) or NO_DESCRIPTION,
        is_pending=bool(item.get("pending", False)),
        transaction_date=transaction_date,
    )


def _account(item: dict, institutions: dict[str, str]) -> ProviderAccount:
    institution = institutions.get(item.get("conn_id")) or item.get("org", {}).get("name") or ""
    balance_date = _day(item["balance-date"])
    return ProviderAccount(
        provider_account_id=str(item["id"]),
        name=_clean(item["name"]),
        institution=_clean(institution),
        currency=item["currency"],
        balance_cents=parse_money(item["balance"]),
        balance_date=balance_date,
        transactions=[
            _transaction(entry, balance_date) for entry in item.get("transactions") or []
        ],
    )


def parse_account_set(payload: dict) -> ProviderAnswer:
    """Read an Account Set of either protocol version into plain data."""
    accounts = payload["accounts"]
    if not isinstance(accounts, list):
        raise TypeError
    institutions = {
        connection["conn_id"]: connection["name"] for connection in payload.get("connections", [])
    }
    raw = [entry["msg"] for entry in payload.get("errlist", [])]
    raw += list(payload.get("errors", []))
    messages = [text for text in (_clean(entry) for entry in raw) if text]
    return ProviderAnswer([_account(item, institutions) for item in accounts], messages)
