from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import MerchantAliasRow, to_merchant_alias
from finances.db.repositories.audit import record_change
from finances.domain.merchants import MerchantAlias, check_alias, normalize_merchant


def list_aliases(session: Session) -> list[MerchantAlias]:
    stmt = select(MerchantAliasRow).order_by(MerchantAliasRow.source)
    return [to_merchant_alias(row) for row in session.scalars(stmt).all()]


def alias_map(session: Session) -> dict[str, str]:
    return {item.source: item.target for item in list_aliases(session)}


def add_alias(session: Session, source: str, target: str) -> MerchantAlias:
    source, target = check_alias(source, target, alias_map(session))
    row = MerchantAliasRow(source=source, target=target)
    session.add(row)
    session.flush()
    record_change(
        session,
        action="alias_added",
        kind="alias",
        record_id=row.id,
        after=_alias_line(source, target),
    )
    return to_merchant_alias(row)


def delete_alias(session: Session, source: str) -> MerchantAlias:
    stmt = select(MerchantAliasRow).where(MerchantAliasRow.source == normalize_merchant(source))
    row = session.scalars(stmt).first()
    if row is None:
        raise ValueError("alias not found")
    found = to_merchant_alias(row)
    session.delete(row)
    record_change(
        session,
        action="alias_deleted",
        kind="alias",
        record_id=found.id,
        before=_alias_line(found.source, found.target),
    )
    return found


def _alias_line(source: str, target: str) -> str:
    return f"{source} -> {target}"
