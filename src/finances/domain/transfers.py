"""Find money moved between the household's own accounts. Pure: no database."""

from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import date

TRANSFER_MAX_DAYS = 5


@dataclass(frozen=True)
class Movement:
    transaction_id: int
    account_id: int
    amount_cents: int
    day: date


def transfer_candidates(
    movements: Iterable[Movement],
    rejected: Collection[tuple[int, int]] = frozenset(),
    max_days: int = TRANSFER_MAX_DAYS,
) -> list[tuple[int, int]]:
    """Every (out id, in id) of the same amount, other accounts, at most max_days apart."""
    found = list(movements)
    inflows: dict[int, list[Movement]] = defaultdict(list)
    for item in found:
        if item.amount_cents > 0:
            inflows[item.amount_cents].append(item)
    candidates = [
        (out.transaction_id, into.transaction_id)
        for out in found
        if out.amount_cents < 0
        for into in inflows.get(-out.amount_cents, ())
        if into.account_id != out.account_id
        and abs((into.day - out.day).days) <= max_days
        and (out.transaction_id, into.transaction_id) not in rejected
    ]
    return sorted(candidates)


def clear_pairs(candidates: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """The candidates with no other choice on either side, in their order."""
    outs = Counter(out_id for out_id, _ in candidates)
    ins = Counter(in_id for _, in_id in candidates)
    return [pair for pair in candidates if outs[pair[0]] == 1 and ins[pair[1]] == 1]
