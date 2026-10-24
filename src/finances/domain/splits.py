"""Whether parts add up to a transaction. Imports only from finances.domain."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from finances.domain.money import parse_money

MAX_PARTS = 10
SPLIT = "Split"
_FIRST_WORD = re.compile(r"\s+")


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


def signed_parts(amount_cents: int, sizes: Sequence[int]) -> list[int]:
    if any(size <= 0 for size in sizes):
        raise ValueError("each part's size must be more than zero")
    sign = -1 if amount_cents < 0 else 1
    return [sign * size for size in sizes]


def parse_part(text: str) -> tuple[int, str]:
    found = _FIRST_WORD.split(text.strip(), maxsplit=1)
    if len(found) < 2:
        raise ValueError("a part is a size and a category, such as 12.00 Groceries")
    return parse_money(found[0]), found[1].strip()
