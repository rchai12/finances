"""The registry of statement parsers. It is empty until a parser registers itself."""

from typing import Protocol

from finances.ingest.statement import ParsedStatement, StatementError


class StatementParser(Protocol):
    name: str

    def detect(self, first_page: str) -> bool: ...

    def parse(self, pages: list[str]) -> ParsedStatement: ...


_parsers: dict[str, StatementParser] = {}


def register(parser: StatementParser) -> None:
    if parser.name in _parsers:
        raise ValueError("parser name is already registered")
    _parsers[parser.name] = parser


def unregister(name: str) -> None:
    try:
        del _parsers[name]
    except KeyError:
        raise ValueError("parser name is not registered") from None


def registered_parsers() -> list[StatementParser]:
    return list(_parsers.values())


def detect_parser(pages: list[str]) -> StatementParser:
    if not pages:
        raise StatementError("unrecognized statement format")
    first_page = pages[0]
    matches = [parser for parser in _parsers.values() if parser.detect(first_page)]
    if not matches:
        raise StatementError("unrecognized statement format")
    if len(matches) == 1:
        return matches[0]
    names = ", ".join(parser.name for parser in matches)
    raise StatementError(f"statement matches more than one parser: {names}")


from finances.ingest.parsers.capital_one import CapitalOneCardParser  # noqa: E402

register(CapitalOneCardParser())

from finances.ingest.parsers.boa import BoaCardParser  # noqa: E402
from finances.ingest.parsers.citi import CitiCardParser  # noqa: E402

register(BoaCardParser())
register(CitiCardParser())

from finances.ingest.parsers.boa_deposit import BoaDepositParser  # noqa: E402
from finances.ingest.parsers.marcus import MarcusSavingsParser  # noqa: E402
from finances.ingest.parsers.truist import TruistDepositParser  # noqa: E402

register(TruistDepositParser())
register(MarcusSavingsParser())
register(BoaDepositParser())
