from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finances.db.orm import ProposalRow, to_proposal
from finances.db.repositories.categories import (
    _category_row,
    create_category,
    create_group,
    set_tax_relevant,
)
from finances.db.repositories.chains import chain_out_of_date, proposed_group
from finances.db.repositories.transactions import get_transaction
from finances.domain.proposals import (
    DECLINED,
    GROUP,
    GROUP_KINDS,
    NEW_CATEGORY,
    OPEN,
    Proposal,
)
from finances.domain.text import CATEGORY_NAME_LIMIT, PROPOSAL_TEXT_LIMIT, collapse_ws


def _now() -> datetime:
    return datetime.now(UTC)


def new_is_out_of_date(session: Session, proposal: Proposal) -> bool:
    if _category_row(session, proposal.value) is not None:
        return True
    missing = False
    if proposal.kind == NEW_CATEGORY:
        parent = _category_row(session, proposal.group or "")
        missing = parent is None or parent.parent_id is not None
    return chain_out_of_date(session, proposal, target_missing=missing)


def accept_new(session: Session, row: ProposalRow) -> None:
    if row.kind == GROUP:
        create_group(
            session,
            row.value,
            transfer=bool(row.is_transfer),
            income=bool(row.is_income),
            sensitive=bool(row.is_sensitive),
        )
        return
    create_category(session, row.value, row.group_name or "")
    if row.is_tax:
        set_tax_relevant(session, row.value, True)


def _named(session: Session, name: str) -> list[ProposalRow]:
    return list(
        session.scalars(
            select(ProposalRow).where(
                ProposalRow.kind.in_((GROUP, NEW_CATEGORY)),
                func.lower(ProposalRow.value) == name.lower(),
            )
        ).all()
    )


def propose_group(
    session: Session,
    example_id: int,
    name: str,
    reason: str,
    *,
    kind: str = "spending",
    sensitive: bool = False,
) -> Proposal:
    clean = collapse_ws(reason)
    if not 1 <= len(clean) <= PROPOSAL_TEXT_LIMIT:
        raise ValueError("a reason must be 1 to 200 characters")
    stored = name.strip()
    if not 1 <= len(stored) <= CATEGORY_NAME_LIMIT:
        raise ValueError(f"a group name must be 1 to {CATEGORY_NAME_LIMIT} characters")
    if kind not in GROUP_KINDS:
        raise ValueError("a group's kind must be spending, transfer, or income")
    if get_transaction(session, example_id) is None:
        raise ValueError("transaction not found")
    if _category_row(session, stored) is not None:
        raise ValueError("a category with this name already exists")
    found = _named(session, stored)
    if any(row.status == DECLINED and row.kind == GROUP for row in found):
        raise ValueError("a person declined this proposal already")
    if any(row.status == OPEN for row in found):
        raise ValueError("this name already has an open proposal")
    row = ProposalRow(
        kind=GROUP,
        target_id=example_id,
        value=stored,
        reason=clean,
        status=OPEN,
        created_at=_now(),
        decided_at=None,
        other_id=None,
        pattern=None,
        match=None,
        priority=None,
        source=None,
        group_name=None,
        is_transfer=kind == "transfer",
        is_income=kind == "income",
        is_sensitive=sensitive,
        is_tax=None,
        parent_id=None,
    )
    session.add(row)
    session.flush()
    return to_proposal(row)


def propose_new_category(
    session: Session,
    example_id: int,
    name: str,
    group: str,
    reason: str,
    *,
    tax: bool = False,
) -> Proposal:
    clean = collapse_ws(reason)
    if not 1 <= len(clean) <= PROPOSAL_TEXT_LIMIT:
        raise ValueError("a reason must be 1 to 200 characters")
    stored = name.strip()
    if not 1 <= len(stored) <= CATEGORY_NAME_LIMIT:
        raise ValueError(f"a category name must be 1 to {CATEGORY_NAME_LIMIT} characters")
    if get_transaction(session, example_id) is None:
        raise ValueError("transaction not found")
    group_name, parent_id = proposed_group(session, group)
    if _category_row(session, stored) is not None:
        raise ValueError("a category with this name already exists")
    found = _named(session, stored)
    if any(
        row.status == DECLINED
        and row.kind == NEW_CATEGORY
        and (row.group_name or "").lower() == group_name.lower()
        for row in found
    ):
        raise ValueError("a person declined this proposal already")
    if any(row.status == OPEN for row in found):
        raise ValueError("this name already has an open proposal")
    row = ProposalRow(
        kind=NEW_CATEGORY,
        target_id=example_id,
        value=stored,
        reason=clean,
        status=OPEN,
        created_at=_now(),
        decided_at=None,
        other_id=None,
        pattern=None,
        match=None,
        priority=None,
        source=None,
        group_name=group_name,
        is_transfer=None,
        is_income=None,
        is_sensitive=None,
        is_tax=tax,
        parent_id=parent_id,
    )
    session.add(row)
    session.flush()
    return to_proposal(row)
