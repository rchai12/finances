import json
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finances.sync.simplefin import ProviderAnswer, SyncError, fetch_accounts

ACCESS = "https://probe-user:probe-pass@bridge.simplefin.org/simplefin"
FIXTURES = sorted((Path(__file__).parents[1] / "fixtures" / "simplefin").glob("*.json"))
UNREADABLE = "aggregator answer could not be read"

leaf = (
    st.none()
    | st.booleans()
    | st.integers(-(2**70), 2**70)
    | st.floats(allow_nan=True, allow_infinity=True)
    | st.text(max_size=8)
)
documents = st.recursive(
    leaf,
    lambda inner: (
        st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=6), inner, max_size=3)
    ),
    max_leaves=12,
)


def answer(body: bytes) -> ProviderAnswer:
    return fetch_accounts(ACCESS, date(2026, 5, 1), date(2026, 5, 31), lambda *_: (200, body))


def read_or_refuse(body: bytes) -> None:
    try:
        result = answer(body)
    except SyncError as error:
        assert str(error) == UNREADABLE
        return
    for account in result.accounts:
        assert type(account.balance_cents) is int
        assert all(type(item.amount_cents) is int for item in account.transactions)
        assert all(type(item.feed_id) is str for item in account.transactions)
    assert all(type(message) is str for message in result.messages)


@st.composite
def damaged(draw: st.DrawFn) -> object:
    document = json.loads(draw(st.sampled_from(FIXTURES)).read_text(encoding="utf-8"))
    for _ in range(draw(st.integers(1, 3))):
        node = document
        for _ in range(draw(st.integers(0, 4))):
            if isinstance(node, dict) and node:
                node = node[draw(st.sampled_from(sorted(node)))]
            elif isinstance(node, list) and node:
                node = node[draw(st.integers(0, len(node) - 1))]
            else:
                break
        if isinstance(node, dict) and node:
            key = draw(st.sampled_from(sorted(node)))
            if draw(st.booleans()):
                del node[key]
            else:
                node[key] = draw(leaf)
        elif isinstance(node, list) and node:
            index = draw(st.integers(0, len(node) - 1))
            if draw(st.booleans()):
                del node[index]
            else:
                node[index] = draw(leaf)
    return document


def test_the_fixtures_are_read() -> None:
    for path in FIXTURES:
        assert answer(path.read_bytes()).accounts


@settings(max_examples=400)
@given(documents)
def test_any_json_is_read_or_refused_as_unreadable(document: object) -> None:
    read_or_refuse(json.dumps(document).encode())


@settings(max_examples=400)
@given(damaged())
def test_a_damaged_answer_is_read_or_refused_as_unreadable(document: object) -> None:
    read_or_refuse(json.dumps(document).encode())


@pytest.mark.parametrize(
    "body",
    [
        b"[" * 100_000,
        b'{"accounts": ' + b"[" * 100_000 + b"]" * 100_000 + b"}",
        b"{" * 5_000,
        b"",
        b"\xff\xfe",
        b"null",
        b"1e999999",
        b'{"accounts": [], "errlist": [{"msg": ' + b"[" * 100_000 + b"]}]}",
    ],
    ids=[
        "deep-list",
        "deep-accounts",
        "open-braces",
        "empty",
        "not-utf8",
        "null",
        "huge",
        "deep-msg",
    ],
)
def test_answers_no_parser_can_use_are_unreadable(body: bytes) -> None:
    with pytest.raises(SyncError, match=f"^{UNREADABLE}$"):
        answer(body)
