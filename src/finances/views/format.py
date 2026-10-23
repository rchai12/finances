"""How a few values are written in every view."""

from finances.domain.models import FeedPull
from finances.domain.money import format_cents

BULLETS = "\u2022\u2022"


def mask_last4(last4: str | None) -> str:
    return f"{BULLETS}{last4}" if last4 else ""


def drift_text(pull: FeedPull | None) -> str:
    return "" if pull is None or pull.drift_cents is None else format_cents(pull.drift_cents)


def balance_date_text(pull: FeedPull | None) -> str:
    return "" if pull is None or pull.balance_date is None else pull.balance_date.isoformat()


def last_pull_text(pull: FeedPull | None) -> str:
    return "never" if pull is None else pull.pulled_at.strftime("%Y-%m-%d %H:%M UTC")


def change_text(cents: int) -> str:
    """A signed amount: "+$1.00" when above zero, else format_cents."""
    text = format_cents(cents)
    return f"+{text}" if cents > 0 else text


def net_text(cents: int) -> str:
    """A net spending figure: money out as usual, money back named as back."""
    return format_cents(cents) if cents >= 0 else f"{format_cents(-cents)} back"


def amount_class(text: str) -> str:
    """The class of a table cell holding this formatted amount."""
    if text.startswith("-$"):
        return "amount neg"
    if text.startswith("+$") or text.endswith(" back"):
        return "amount pos"
    return "amount"


_KB = 1024
_MB = 1024 * 1024


def size_text(size: int) -> str:
    """A file size in bytes, kilobytes (rounded down), or megabytes to one decimal (half up)."""
    if size < _KB:
        return f"{size} B"
    if size < _MB:
        return f"{size // _KB} KB"
    tenths = (20 * size + _MB) // (2 * _MB)
    return f"{tenths // 10}.{tenths % 10} MB"
