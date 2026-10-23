"""Whether parts add up to a transaction. Imports only from finances.domain."""

from collections.abc import Sequence
from dataclasses import dataclass

MAX_PARTS = 10
SPLIT = "Split"


@dataclass(frozen=True)
class SplitPart:
    transaction_id: int
    position: int
    amount_cents: int
    category_id: int


def check_split(amount_cents: int, parts: Sequence[int]) -> None:
    if amount_cents == 0:
        raise ValueError("a transaction of zero cannot be split")
    if not 2 <= len(parts) <= MAX_PARTS:
        raise ValueError("a split has 2 to 10 parts")
    if any(part == 0 or (part > 0) != (amount_cents > 0) for part in parts):
        raise ValueError("each part must have the transaction's sign and not be zero")
    if sum(parts) != amount_cents:
        raise ValueError("the parts must add up to the transaction")
