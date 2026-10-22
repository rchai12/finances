"""The accounts list, as `fin accounts list` and the Accounts page show it."""

from dataclasses import dataclass

from finances.analysis.listings import AccountListing
from finances.views.format import mask_last4


@dataclass(frozen=True)
class AccountRow:
    name: str
    institution: str
    type: str
    last4: str
    active: str
    owner: str


def account_rows(listing: list[AccountListing]) -> list[AccountRow]:
    return [
        AccountRow(
            item.account.name,
            item.account.institution,
            item.account.type.value,
            mask_last4(item.account.last4),
            "yes" if item.account.is_active else "no",
            item.owner or "",
        )
        for item in listing
    ]
