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
