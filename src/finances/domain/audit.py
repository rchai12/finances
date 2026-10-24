"""Who changed what: the lists, a stored change, and the short texts kept with it."""

from dataclasses import dataclass
from datetime import datetime

PERSON = "person"
SYSTEM = "system"
WHO = (PERSON, SYSTEM)
ACTIONS = (
    "account_added",
    "account_renamed",
    "account_closed",
    "account_reopened",
    "owner_set",
    "person_added",
    "cardholder_set",
    "category_added",
    "category_renamed",
    "category_deleted",
    "rule_added",
    "rule_edited",
    "rule_deleted",
    "category_set",
    "category_cleared",
    "budget_set",
    "budget_removed",
    "transfer_confirmed",
    "transfer_rejected",
    "transfer_unpaired",
    "statement_imported",
    "backup_deleted",
    "backup_restored",
    "proposal_accepted",
    "proposal_declined",
    "alias_added",
    "alias_deleted",
    "tag_added",
    "tag_removed",
    "note_set",
    "note_cleared",
    "split_set",
    "split_cleared",
    "share_set",
    "share_cleared",
    "settlement_added",
    "settlement_deleted",
    "category_tax_set",
)
KINDS = (
    "account",
    "person",
    "category",
    "rule",
    "transaction",
    "transfer",
    "statement",
    "backup",
    "proposal",
    "alias",
    "settlement",
)


@dataclass(frozen=True)
class Change:
    id: int
    at: datetime
    who: str
    action: str
    kind: str
    record_id: int | None
    before: str | None
    after: str | None


def rule_text(match: str, pattern: str, category: str, priority: int) -> str:
    return f'{match} "{pattern}" -> {category} (priority {priority})'


def pair_text(out_id: int, in_id: int) -> str:
    return f"{out_id} -> {in_id}"
