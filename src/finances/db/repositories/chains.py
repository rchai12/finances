from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finances.db.orm import ProposalRow, to_proposal
from finances.db.repositories.assignments import _assigned_name, _assignment_row
from finances.db.repositories.categories import _category_row
from finances.db.repositories.splits import _is_split
from finances.db.repositories.transactions import get_transaction
from finances.db.repositories.transfers import find_transfer_pair, list_transfer_rejections
from finances.domain.models import MANUAL
from finances.domain.proposals import GROUP, NEW_CATEGORY, OPEN, Proposal, pair_out_of_date


def _target_exists(session: Session, proposal: Proposal) -> bool:
    if proposal.kind == NEW_CATEGORY:
        found = _category_row(session, proposal.group or "")
        return found is not None and found.parent_id is None
    found = _category_row(session, proposal.value)
    return found is not None and found.parent_id is not None


def _open_named(session: Session, kind: str, name: str) -> ProposalRow | None:
    return session.scalars(
        select(ProposalRow).where(
            ProposalRow.kind == kind,
            ProposalRow.status == OPEN,
            func.lower(ProposalRow.value) == name.strip().lower(),
        )
    ).first()


def proposed_category(session: Session, name: str) -> tuple[str, int | None]:
    row = _category_row(session, name)
    if row is not None and row.parent_id is not None:
        return row.name, None
    if row is not None:
        raise ValueError("rules and transactions take a category, not a group")
    found = _open_named(session, NEW_CATEGORY, name)
    if found is not None:
        return found.value, found.id
    raise ValueError("category not found")


def proposed_group(session: Session, name: str) -> tuple[str, int | None]:
    row = _category_row(session, name)
    if row is not None and row.parent_id is None:
        return row.name, None
    if row is not None:
        raise ValueError("group not found")
    found = _open_named(session, GROUP, name)
    if found is not None:
        return found.value, found.id
    raise ValueError("group not found")


def waits_for(session: Session, proposal: Proposal) -> int | None:
    if proposal.status != OPEN or proposal.parent_id is None:
        return None
    parent = session.get(ProposalRow, proposal.parent_id)
    if parent is None or parent.status != OPEN:
        return None
    if _target_exists(session, proposal):
        return None
    return proposal.parent_id


def chain_out_of_date(session: Session, proposal: Proposal, *, target_missing: bool) -> bool:
    if waits_for(session, proposal) is not None:
        return False
    if proposal.parent_id is not None and not _target_exists(session, proposal):
        return True
    return target_missing


def _split_or_paired(session: Session, transaction_id: int) -> bool:
    if _is_split(session, transaction_id):
        return True
    return find_transfer_pair(session, transaction_id) is not None


def category_is_out_of_date(session: Session, proposal: Proposal) -> bool:
    if get_transaction(session, proposal.target_id) is None:
        return True
    if _split_or_paired(session, proposal.target_id):
        return True
    row = _assignment_row(session, proposal.target_id)
    if (
        row is not None
        and row.source == MANUAL
        and _assigned_name(session, proposal.target_id) != proposal.before
    ):
        return True
    found = _category_row(session, proposal.value)
    missing = found is None or found.parent_id is None
    return chain_out_of_date(session, proposal, target_missing=missing)


def pair_is_out_of_date(session: Session, proposal: Proposal) -> bool:
    in_id = proposal.other_id
    exists = (
        get_transaction(session, proposal.target_id) is not None
        and in_id is not None
        and get_transaction(session, in_id) is not None
    )
    paired = find_transfer_pair(session, proposal.target_id) is not None or (
        in_id is not None and find_transfer_pair(session, in_id) is not None
    )
    rejected = in_id is not None and (proposal.target_id, in_id) in list_transfer_rejections(
        session
    )
    return pair_out_of_date(exists=exists, paired=paired, rejected=rejected)


def _ancestors_in(
    session: Session, proposal_id: int, wanted: set[int], rows: dict[int, ProposalRow | None]
) -> list[int]:
    chain: list[int] = []
    current = proposal_id
    while True:
        if current not in rows:
            rows[current] = session.get(ProposalRow, current)
        row = rows[current]
        if row is None or row.parent_id is None:
            break
        current = row.parent_id
        if current in wanted:
            chain.append(current)
    chain.reverse()
    return chain


def accepting_order(session: Session, proposal_ids: list[int]) -> list[int]:
    wanted: list[int] = []
    seen: set[int] = set()
    for proposal_id in proposal_ids:
        if proposal_id not in seen:
            wanted.append(proposal_id)
            seen.add(proposal_id)
    rows: dict[int, ProposalRow | None] = {}
    placed: list[int] = []
    placed_set: set[int] = set()

    def place(proposal_id: int) -> None:
        if proposal_id in placed_set:
            return
        for ancestor in _ancestors_in(session, proposal_id, seen, rows):
            place(ancestor)
        placed.append(proposal_id)
        placed_set.add(proposal_id)

    for proposal_id in wanted:
        place(proposal_id)
    return placed


def decline_proposals(session: Session, proposal_ids: list[int]) -> list[tuple[Proposal, bool]]:
    from finances.db.repositories.proposals import decline_proposal

    declined: set[int] = set()
    found: list[tuple[Proposal, bool]] = []

    def cascade(parent_id: int) -> None:
        children = list(
            session.scalars(
                select(ProposalRow)
                .where(ProposalRow.status == OPEN, ProposalRow.parent_id == parent_id)
                .order_by(ProposalRow.id)
            ).all()
        )
        for child in children:
            if _target_exists(session, to_proposal(child)):
                continue
            item = decline_proposal(session, child.id)
            declined.add(child.id)
            found.append((item, True))
            cascade(child.id)

    for proposal_id in proposal_ids:
        if proposal_id in declined:
            continue
        item = decline_proposal(session, proposal_id)
        declined.add(proposal_id)
        found.append((item, False))
        cascade(proposal_id)
    return found
