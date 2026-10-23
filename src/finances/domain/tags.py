"""A person's labels on a transaction. Imports only from finances.domain."""

from dataclasses import dataclass

from finances.domain.text import NOTE_LIMIT, TAG_LIMIT, collapse_ws


@dataclass(frozen=True)
class TagCount:
    tag: str
    transactions: int


def normalize_tag(text: str) -> str:
    found = collapse_ws(text).lower()
    if not 1 <= len(found) <= TAG_LIMIT:
        raise ValueError("a tag must be 1 to 30 characters")
    return found


def clean_note(text: str) -> str:
    found = text.strip()
    if len(found) > NOTE_LIMIT:
        raise ValueError("a note is at most 500 characters")
    return found
