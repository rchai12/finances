"""The people list, as `fin people list` and the People page show it."""

from dataclasses import dataclass

from finances.analysis.listings import PersonListing


@dataclass(frozen=True)
class PersonRow:
    name: str
    owns: str
    cardholders: str


def people_rows(listing: list[PersonListing]) -> list[PersonRow]:
    return [
        PersonRow(item.name, ", ".join(item.owns), ", ".join(item.cardholders)) for item in listing
    ]
