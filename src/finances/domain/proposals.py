"""The agent's suggestions and notes, waiting for a person."""

from dataclasses import dataclass
from datetime import datetime

CATEGORY = "category"
KINDS = (CATEGORY,)
OPEN = "open"
ACCEPTED = "accepted"
DECLINED = "declined"
STATUSES = (OPEN, ACCEPTED, DECLINED)


@dataclass(frozen=True)
class Proposal:
    id: int
    kind: str
    target_id: int
    value: str
    reason: str
    status: str
    created_at: datetime
    decided_at: datetime | None


@dataclass(frozen=True)
class Advice:
    id: int
    created_at: datetime
    subject: str
    text: str


def out_of_date(*, exists: bool, set_by_hand: bool, paired: bool) -> bool:
    return (not exists) or set_by_hand or paired


def proposal_text(proposal: Proposal) -> str:
    return f"transaction {proposal.target_id}: {proposal.value}"
