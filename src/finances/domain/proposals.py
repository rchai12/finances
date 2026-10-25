"""The agent's suggestions and notes, waiting for a person."""

from dataclasses import dataclass
from datetime import datetime

from finances.domain.audit import rule_text

CATEGORY = "category"
TRANSFER = "transfer"
NOT_TRANSFER = "not_transfer"
RULE = "rule"
ALIAS = "alias"
GROUP = "group"
NEW_CATEGORY = "new_category"
KINDS = (CATEGORY, TRANSFER, NOT_TRANSFER, RULE, ALIAS, GROUP, NEW_CATEGORY)
GROUP_KINDS = ("spending", "transfer", "income")
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
    other_id: int | None = None
    pattern: str | None = None
    match: str | None = None
    priority: int | None = None
    source: str | None = None
    group: str | None = None
    transfer: bool | None = None
    income: bool | None = None
    sensitive: bool | None = None
    tax: bool | None = None
    parent_id: int | None = None


@dataclass(frozen=True)
class Advice:
    id: int
    created_at: datetime
    subject: str
    text: str


def out_of_date(*, exists: bool, set_by_hand: bool, paired: bool) -> bool:
    return (not exists) or set_by_hand or paired


def pair_out_of_date(*, exists: bool, paired: bool, rejected: bool) -> bool:
    return (not exists) or paired or rejected


def rule_out_of_date(*, category_found: bool, rule_exists: bool) -> bool:
    return (not category_found) or rule_exists


def group_flag_words(
    *, transfer: bool | None = False, income: bool | None = False, sensitive: bool | None = False
) -> str:
    return ", ".join(
        word
        for word, flag in (("transfer", transfer), ("income", income), ("sensitive", sensitive))
        if flag
    )


def group_kind_word(*, transfer: bool | None = False, income: bool | None = False) -> str:
    if transfer:
        return "transfer"
    if income:
        return "income"
    return "spending"


def proposal_text(proposal: Proposal) -> str:
    if proposal.kind == TRANSFER:
        return f"{proposal.target_id} -> {proposal.other_id}: a transfer"
    if proposal.kind == NOT_TRANSFER:
        return f"{proposal.target_id} -> {proposal.other_id}: not a transfer"
    if proposal.kind == RULE:
        return "rule: " + rule_text(
            proposal.match or "",
            proposal.pattern or "",
            proposal.value,
            0 if proposal.priority is None else proposal.priority,
        )
    if proposal.kind == ALIAS:
        return f"alias: {proposal.source} -> {proposal.value}"
    if proposal.kind == GROUP:
        extra = group_flag_words(
            transfer=proposal.transfer, income=proposal.income, sensitive=proposal.sensitive
        )
        return f"group: {proposal.value}" + (f" ({extra})" if extra else "")
    if proposal.kind == NEW_CATEGORY:
        tax = " (tax)" if proposal.tax else ""
        return f"category: {proposal.value} in {proposal.group}{tax}"
    return f"transaction {proposal.target_id}: {proposal.value}"
