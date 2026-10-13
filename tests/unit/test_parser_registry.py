import inspect
from typing import Protocol

import pytest

from finances.ingest.parsers import (
    StatementParser,
    detect_parser,
    register,
    registered_parsers,
    unregister,
)
from finances.ingest.statement import ParsedStatement, StatementError

UNKNOWN = "unrecognized statement format"


class _Parser:
    def __init__(self, name: str, word: str) -> None:
        self.name = name
        self.word = word
        self.seen: list[str] = []

    def detect(self, first_page: str) -> bool:
        self.seen.append(first_page)
        return self.word in first_page

    def parse(self, pages: list[str]) -> ParsedStatement:
        raise AssertionError("parse is not used by the registry")


def test_register_lists_parsers_in_order_and_returns_a_copy(parser_registry: None) -> None:
    zeta = _Parser("zeta", "ZETA")
    alpha = _Parser("alpha", "ALPHA")
    register(zeta)
    register(alpha)
    listed = registered_parsers()
    assert [parser.name for parser in listed] == ["zeta", "alpha"]
    listed.append(_Parser("junk", "JUNK"))
    assert [parser.name for parser in registered_parsers()] == ["zeta", "alpha"]


def test_a_duplicate_name_is_rejected_and_the_registry_is_unchanged(parser_registry: None) -> None:
    register(_Parser("alpha", "ALPHA"))
    with pytest.raises(ValueError) as excinfo:
        register(_Parser("alpha", "OTHER"))
    assert str(excinfo.value) == "parser name is already registered"
    assert [parser.name for parser in registered_parsers()] == ["alpha"]


def test_unregister_removes_a_name_and_it_can_be_registered_again(parser_registry: None) -> None:
    register(_Parser("alpha", "ALPHA"))
    register(_Parser("zeta", "ZETA"))
    unregister("alpha")
    assert [parser.name for parser in registered_parsers()] == ["zeta"]
    with pytest.raises(ValueError) as excinfo:
        unregister("alpha")
    assert str(excinfo.value) == "parser name is not registered"
    register(_Parser("alpha", "ALPHA"))
    assert [parser.name for parser in registered_parsers()] == ["zeta", "alpha"]


def test_detect_returns_the_one_match_and_offers_only_the_first_page(parser_registry: None) -> None:
    alpha = _Parser("alpha", "ALPHA")
    zeta = _Parser("zeta", "ZETA")
    register(alpha)
    register(zeta)
    found = detect_parser(["page one has ALPHA", "ZETA is only here"])
    assert found is alpha
    assert alpha.seen == ["page one has ALPHA"]
    assert zeta.seen == ["page one has ALPHA"]


@pytest.mark.parametrize(
    "pages",
    [[], ["nothing here"], ["nothing here", "ALPHA on page two"]],
    ids=["empty list", "no match", "match only on a later page"],
)
def test_no_recognizing_parser_raises_the_exact_message(
    parser_registry: None, pages: list[str]
) -> None:
    register(_Parser("alpha", "ALPHA"))
    with pytest.raises(StatementError) as excinfo:
        detect_parser(pages)
    assert str(excinfo.value) == UNKNOWN


def test_an_empty_registry_raises_the_exact_message(parser_registry: None) -> None:
    with pytest.raises(StatementError) as excinfo:
        detect_parser(["ALPHA"])
    assert str(excinfo.value) == UNKNOWN


def test_two_matches_name_parsers_in_registration_order(parser_registry: None) -> None:
    register(_Parser("zeta", "BOTH"))
    register(_Parser("alpha", "BOTH"))
    with pytest.raises(StatementError) as excinfo:
        detect_parser(["BOTH"])
    assert str(excinfo.value) == "statement matches more than one parser: zeta, alpha"


def test_the_registry_is_empty_outside_the_fixture() -> None:
    assert registered_parsers() == []


def test_statement_parser_is_a_protocol_with_exactly_those_members() -> None:
    assert StatementParser.__bases__ == (Protocol,)
    assert StatementParser.__annotations__ == {"name": str}
    public = [name for name in StatementParser.__dict__ if not name.startswith("_")]
    assert public == ["detect", "parse"]
    detect_sig = inspect.signature(StatementParser.detect)
    assert list(detect_sig.parameters) == ["self", "first_page"]
    assert detect_sig.parameters["first_page"].annotation is str
    assert detect_sig.return_annotation is bool
    parse_sig = inspect.signature(StatementParser.parse)
    assert list(parse_sig.parameters) == ["self", "pages"]
    assert parse_sig.parameters["pages"].annotation == list[str]
    assert parse_sig.return_annotation is ParsedStatement
