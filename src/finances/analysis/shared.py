from sqlalchemy.orm import Session

from finances.db.repositories import list_settlements, list_shares
from finances.domain.shared import Owed, balances


def owed_report(session: Session) -> list[Owed]:
    """Who owes whom after every stored share and settlement."""
    return balances(list_shares(session), list_settlements(session))
