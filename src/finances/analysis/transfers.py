"""Transfer pairs and waiting pairings as data, before any view formats them."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.categorize.transfers import transfer_suggestions
from finances.db.repositories import (
    account_names,
    find_transfer_pair,
    get_transaction,
    list_transfer_pairs,
)
from finances.domain.models import Transaction, TransferPair


@dataclass(frozen=True)
class PairListing:
    pair: TransferPair
    out: Transaction
    into: Transaction
    from_account: str
    to_account: str


@dataclass(frozen=True)
class SuggestionListing:
    out: Transaction
    into: Transaction
    from_account: str
    to_account: str


def _listing(pair: TransferPair, names: dict[int, str], session: Session) -> PairListing:
    out = get_transaction(session, pair.out_transaction_id)
    into = get_transaction(session, pair.in_transaction_id)
    return PairListing(pair, out, into, names[out.account_id], names[into.account_id])


def pair_listing(session: Session) -> list[PairListing]:
    names = account_names(session)
    return [_listing(pair, names, session) for pair in list_transfer_pairs(session)]


def pair_of(session: Session, transaction_id: int) -> PairListing | None:
    pair = find_transfer_pair(session, transaction_id)
    if pair is None:
        return None
    return _listing(pair, account_names(session), session)


def suggestion_listing(session: Session) -> list[SuggestionListing]:
    names = account_names(session)
    listing = []
    for out_id, in_id in transfer_suggestions(session):
        out = get_transaction(session, out_id)
        into = get_transaction(session, in_id)
        listing.append(SuggestionListing(out, into, names[out.account_id], names[into.account_id]))
    return listing
