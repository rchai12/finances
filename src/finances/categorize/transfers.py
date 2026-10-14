"""Pair transfers between the household's own accounts: the clear ones automatically."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.db.repositories import (
    create_transfer_pair,
    list_transfer_movements,
    list_transfer_rejections,
)
from finances.domain.models import AUTO
from finances.domain.transfers import clear_pairs, transfer_candidates


@dataclass(frozen=True)
class TransferResult:
    paired: int
    waiting: int


def _candidates(session: Session) -> list[tuple[int, int]]:
    return transfer_candidates(list_transfer_movements(session), list_transfer_rejections(session))


def pair_transfers(session: Session) -> TransferResult:
    """Store every clear candidate as an automatic pair. The caller commits."""
    candidates = _candidates(session)
    clear = clear_pairs(candidates)
    for out_id, in_id in clear:
        create_transfer_pair(session, out_id, in_id, AUTO)
    return TransferResult(len(clear), len(candidates) - len(clear))


def transfer_suggestions(session: Session) -> list[tuple[int, int]]:
    """The candidates that are not clear, which wait for the household to decide."""
    candidates = _candidates(session)
    clear = set(clear_pairs(candidates))
    return [pair for pair in candidates if pair not in clear]
