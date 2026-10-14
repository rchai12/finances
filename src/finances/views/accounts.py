"""The accounts list, as `fin accounts list` and the Accounts page show it."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.analysis.people import load_attribution
from finances.db.repositories import list_accounts
from finances.views.format import mask_last4


@dataclass(frozen=True)
class AccountRow:
    name: str
    institution: str
    type: str
    last4: str
    active: str
    owner: str


def account_rows(session: Session, *, include_inactive: bool = False) -> list[AccountRow]:
    attribution = load_attribution(session)
    return [
        AccountRow(
            account.name,
            account.institution,
            account.type.value,
            mask_last4(account.last4),
            "yes" if account.is_active else "no",
            attribution.owner(account.id) or "",
        )
        for account in list_accounts(session, include_inactive=include_inactive)
    ]
