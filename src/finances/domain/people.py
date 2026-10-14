"""Who a transaction belongs to. Imports nothing from the project outside the domain."""

from collections.abc import Mapping

from finances.domain.text import NAME_LIMIT

JOINT = "Joint"
RESERVED_NAMES = ("joint", "unassigned")


def normalize_cardholder(text: str) -> str:
    """Return a cardholder name as one upper-case line with single spaces."""
    return " ".join(text.split()).upper()


def validate_person_name(name: str) -> str:
    """Return the name without outer whitespace, or raise ValueError when it cannot be used."""
    clean = name.strip()
    if not 1 <= len(clean) <= NAME_LIMIT:
        raise ValueError("a person's name must be 1 to 100 characters")
    if clean.lower() in RESERVED_NAMES:
        raise ValueError("joint and unassigned are reserved names")
    return clean


def person_for(cardholder: str | None, owner: str | None, aliases: Mapping[str, str]) -> str | None:
    """Return the cardholder's person when the name is known, otherwise the account's owner."""
    if cardholder is not None:
        found = aliases.get(normalize_cardholder(cardholder))
        if found is not None:
            return found
    return owner
