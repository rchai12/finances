"""SQLAlchemy ORM tables. From this project, this module imports only the domain models."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from finances.domain.models import Account, AccountType

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class of every ORM table."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class AccountRow(Base):
    """One row of the accounts table."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    institution: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


def to_account(row: AccountRow) -> Account:
    """Return the domain Account for a row of the accounts table."""
    if row.created_at.tzinfo is None:
        created_at = row.created_at.replace(tzinfo=UTC)
    else:
        created_at = row.created_at

    return Account(
        id=row.id,
        name=row.name,
        institution=row.institution,
        type=AccountType(row.type),
        currency=row.currency,
        last4=row.last4,
        is_active=row.is_active,
        created_at=created_at,
    )
