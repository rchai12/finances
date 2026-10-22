"""Find merchant and category names that look like a phrase."""

from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.spending import load_flows
from finances.db.repositories import list_categories
from finances.domain.merchants import NameMatch, closest_names


def find_names(session: Session, phrase: str, limit: int) -> list[NameMatch]:
    merchants = {(flow.merchant, "merchant") for flow in load_flows(session, date.min, date.max)}
    categories = {
        (item.name, "category") for item in list_categories(session) if item.group_id is not None
    }
    return closest_names(phrase, (*merchants, *categories), limit)
