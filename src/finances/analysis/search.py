"""Find transactions by the same labels the reports group them by."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.people import JOINT_FILTER, UNASSIGNED_FILTER
from finances.analysis.spending import flows_for
from finances.db.repositories import (
    get_account_by_name,
    get_person_by_name,
    list_transactions_by_day,
    splits_for,
)
from finances.domain.models import Transaction
from finances.domain.spending import REFUND, SEARCH_KINDS, Flow, is_refund

_LABELS = ("account", "category", "group", "merchant", "bank", "card", "person")


@dataclass(frozen=True)
class TransactionQuery:
    text: str = ""
    account: str = ""
    person: str = ""
    category: str = ""
    group: str = ""
    merchant: str = ""
    bank: str = ""
    card: str = ""
    kind: str = ""
    start: date | None = None
    end: date | None = None
    limit: int = 50


@dataclass(frozen=True)
class FoundTransaction:
    transaction: Transaction
    flow: Flow


def _check(session: Session, query: TransactionQuery) -> None:
    if query.kind.strip() and query.kind not in SEARCH_KINDS:
        raise ValueError(f"kind must be one of: {', '.join(SEARCH_KINDS)}")
    if query.account.strip() and get_account_by_name(session, query.account) is None:
        raise ValueError("account not found")
    person = query.person.strip().lower()
    if person and person not in (JOINT_FILTER, UNASSIGNED_FILTER):
        if get_person_by_name(session, query.person) is None:
            raise ValueError("person not found")


def _matches(item: FoundTransaction, wanted: dict[str, str]) -> bool:
    flow = item.flow
    for name, value in wanted.items():
        if name == "text":
            if value.lower() not in item.transaction.description.lower():
                return False
        elif name == "kind":
            if value == REFUND:
                if not is_refund(flow):
                    return False
            elif flow.kind != value:
                return False
        elif getattr(flow, name).lower() != value.lower():
            return False
    return True


def search_transactions(session: Session, query: TransactionQuery) -> list[FoundTransaction]:
    """The transactions whose flow matches every field given, at most `limit`, latest first.

    A person of `joint` or `unassigned` matches the flow's `Joint` or `Unassigned`, since the
    labels are compared ignoring case."""
    _check(session, query)
    given = {name: getattr(query, name).strip() for name in ("text", "kind", *_LABELS)}
    wanted = {name: value for name, value in given.items() if value}
    transactions = list_transactions_by_day(session, query.start, query.end)
    split = splits_for(session, [item.id for item in transactions])
    flows = flows_for(session, transactions, parts=True)
    found = []
    index = 0
    for transaction in transactions:
        count = len(split[transaction.id]) if transaction.id in split else 1
        for _ in range(count):
            item = FoundTransaction(transaction, flows[index])
            index += 1
            if _matches(item, wanted):
                found.append(item)
                if len(found) == query.limit:
                    return found
    return found
