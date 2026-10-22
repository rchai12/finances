"""Which purchase a refund most likely returns. Pure: no database."""

from dataclasses import dataclass
from datetime import date, timedelta

REFUND_WINDOW_DAYS = 90


@dataclass(frozen=True)
class Purchase:
    id: int
    day: date
    amount_cents: int


def likely_purchase(day: date, cents: int, purchases: list[Purchase]) -> int | None:
    """The latest covering purchase in the 90 days up to `day`, highest id on that day."""
    start = day - timedelta(days=REFUND_WINDOW_DAYS)
    fits = [
        item
        for item in purchases
        if item.amount_cents < 0 and -item.amount_cents >= cents and start <= item.day <= day
    ]
    if not fits:
        return None
    latest = max(item.day for item in fits)
    return max(item.id for item in fits if item.day == latest)
