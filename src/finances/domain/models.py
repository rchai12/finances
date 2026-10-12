"""Domain models. This module imports nothing from the rest of the project."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AccountType(StrEnum):
    """Kind of bank or card account."""

    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    OTHER = "other"


@dataclass(frozen=True)
class Account:
    """One bank or card account, as stored."""

    id: int
    name: str
    institution: str
    type: AccountType
    currency: str
    last4: str | None
    is_active: bool
    created_at: datetime


def validate_last4(last4: str | None) -> str | None:
    """Return last4 unchanged if it is None or exactly four ASCII digits; otherwise raise."""
    if last4 is None:
        return None

    if not re.fullmatch(r"[0-9]{4}", last4):
        raise ValueError("last4 must be exactly 4 digits")

    return last4
