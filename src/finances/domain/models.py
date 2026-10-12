"""Domain models. This module imports nothing from the rest of the project."""

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
