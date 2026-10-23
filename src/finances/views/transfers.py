"""Transfer pairs and the candidates waiting for review, as plain text."""

from dataclasses import dataclass

from finances.analysis.transfers import PairListing, SuggestionListing
from finances.domain.money import format_cents


@dataclass(frozen=True)
class TransferLine:
    pair: str
    date: str
    from_account: str
    to_account: str
    amount: str
    out_id: str
    in_id: str
    how: str


@dataclass(frozen=True)
class SuggestionLine:
    out_id: str
    out_date: str
    from_account: str
    in_id: str
    in_date: str
    to_account: str
    amount: str


def transfer_line(item: PairListing) -> TransferLine:
    return TransferLine(
        str(item.pair.id),
        item.out.posted_date.isoformat(),
        item.from_account,
        item.to_account,
        format_cents(item.into.amount_cents),
        str(item.out.id),
        str(item.into.id),
        item.pair.status,
    )


def transfer_lines(listing: list[PairListing]) -> list[TransferLine]:
    """One line per pair, latest outflow date first, then highest pair id first."""
    lines = [transfer_line(item) for item in listing]
    return sorted(lines, key=lambda line: (line.date, int(line.pair)), reverse=True)


def suggestion_lines(listing: list[SuggestionListing]) -> list[SuggestionLine]:
    return [
        SuggestionLine(
            str(item.out.id),
            item.out.posted_date.isoformat(),
            item.from_account,
            str(item.into.id),
            item.into.posted_date.isoformat(),
            item.to_account,
            format_cents(item.into.amount_cents),
        )
        for item in listing
    ]
