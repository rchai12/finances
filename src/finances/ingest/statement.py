"""What a parser produces from one statement. This module holds data only, no parsing."""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from finances.domain.models import AccountType


class StatementError(Exception):
    """Raised when a statement cannot be read, recognized, or parsed."""


class Section(StrEnum):
    """The part of a statement a line was printed in."""

    PAYMENTS_CREDITS = "payments_credits"
    PURCHASES = "purchases"
    FEES = "fees"
    INTEREST = "interest"
    DEPOSITS = "deposits"
    WITHDRAWALS = "withdrawals"
    CHECKS = "checks"


@dataclass(frozen=True)
class StatementLine:
    """One transaction as printed. Amounts are from the account holder's side."""

    posted_date: date
    transaction_date: date | None
    description: str
    amount_cents: int
    section: Section
    card_last4: str | None = None
    cardholder: str | None = None
    external_ref: str | None = None


@dataclass(frozen=True)
class ParsedStatement:
    """One statement: its header, its balances, and its lines."""

    parser_name: str
    institution: str
    account_type: AccountType
    account_last4: str
    period_start: date
    period_end: date
    opening_balance_cents: int
    closing_balance_cents: int
    lines: list[StatementLine]
    declared_section_totals: dict[Section, int] = field(default_factory=dict)
