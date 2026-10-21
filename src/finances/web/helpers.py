"""Field readers and small helpers shared by several areas."""

import re
from datetime import date

from sqlalchemy.orm import Session

from finances.db.repositories import create_account
from finances.domain.models import Account, AccountType

ACCOUNT_TYPES = tuple(item.value for item in AccountType)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_WHOLE = re.compile(r"[0-9]+")
_ID = re.compile(r"[0-9]{1,18}")


def _day(text: str, name: str) -> date | None:
    if not text:
        return None
    if _DATE.fullmatch(text) is not None:
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
    raise ValueError(f"{name} must be a date as YYYY-MM-DD")


def _id(text: str) -> int | None:
    return int(text) if _ID.fullmatch(text) is not None else None


def _rule_form(
    pattern: str = "", match: str = "contains", priority: str = "0", category: str = ""
) -> dict[str, str]:
    return {"pattern": pattern, "match": match, "priority": priority, "category": category}


def _add_account(session: Session, name: str, institution: str, kind: str, last4: str) -> Account:
    return create_account(session, name, institution, kind, last4=last4.strip() or None)
