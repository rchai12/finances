"""The merchant a transaction's description names. Imports only from finances.domain."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher

from finances.domain.text import MERCHANT_NAME_LIMIT, collapse_ws

MATCH_THRESHOLD = 75

_WRAPPERS = ("DEBIT CARD RECURRING PYMT ", "DEBIT CARD PURCHASE ", "POS PURCHASE ")
_TRAILING_WRAPPER = " DEBIT CARD PURCHASE"
_PROCESSORS = ("PAYPAL *", "GOOGLE *", "SQ *", "SQ*", "TST* ", "TST*", "PP*", "SP ")
_DATE = re.compile(r" [0-9]{2}-[0-9]{2}(?= |$)")
_STORE_NUMBER = re.compile(r"#[0-9]")
_NUMBERS = re.compile(r"[0-9]{3}-[0-9]{3}-[0-9]{4}|[0-9]{5,}")


def _without_prefix(text: str, prefixes: tuple[str, ...]) -> str:
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def _cut_at(text: str, pattern: re.Pattern[str]) -> str:
    found = pattern.search(text)
    return text if found is None else text[: found.start()]


def clean_merchant(description: str) -> str:
    """Return the merchant a description names, upper case, without card and store noise."""
    whole = collapse_ws(description).upper()
    text = _without_prefix(whole, _WRAPPERS)
    text = text.removesuffix(_TRAILING_WRAPPER)
    text = _without_prefix(text, _PROCESSORS)
    text = text.partition("*")[0]
    text = _cut_at(text, _DATE)
    text = _cut_at(text, _STORE_NUMBER)
    text = " ".join(word for word in text.split(" ") if "#" not in word)
    text = _NUMBERS.sub("", text)
    text = collapse_ws(text).strip(" -,.*")
    return text or whole


@dataclass(frozen=True)
class MerchantAlias:
    id: int
    source: str  # a cleaned merchant name, normalized
    target: str  # the merchant it is merged into, normalized


def normalize_merchant(text: str) -> str:
    """Return text in upper case with single spaces, as merchant aliases are stored."""
    return " ".join(text.split()).upper()


def merchant_name(description: str, aliases: Mapping[str, str]) -> str:
    cleaned = clean_merchant(description)
    return aliases.get(cleaned, cleaned)


def merchant_names(description: str, aliases: Mapping[str, str]) -> tuple[str, ...]:
    cleaned = clean_merchant(description)
    target = aliases.get(cleaned)
    if target is None:
        return (cleaned,)
    return (cleaned, target)


def check_alias(source: str, target: str, aliases: Mapping[str, str]) -> tuple[str, str]:
    source = normalize_merchant(source)
    target = normalize_merchant(target)
    if not 1 <= len(source) <= MERCHANT_NAME_LIMIT:
        raise ValueError("a merchant name must be 1 to 100 characters")
    if not 1 <= len(target) <= MERCHANT_NAME_LIMIT:
        raise ValueError("a merchant name must be 1 to 100 characters")
    if source == target:
        raise ValueError("a merchant cannot be merged into itself")
    if source in aliases:
        raise ValueError("this merchant is already merged into another")
    if target in aliases:
        raise ValueError("the merchant to merge into is itself merged into another")
    if source in aliases.values():
        raise ValueError("other merchants are merged into this one")
    return (source, target)


@dataclass(frozen=True)
class NameMatch:
    name: str
    kind: str
    score: int


def _similarity(left: str, right: str) -> int:
    total = len(left) + len(right)
    matched = sum(
        block.size
        for block in SequenceMatcher(None, left, right, autojunk=False).get_matching_blocks()
    )
    return (400 * matched + total) // (2 * total)


def match_score(phrase: str, name: str) -> int:
    """How closely phrase looks like name, 0 to 100, after normalizing spaces and case."""
    left = normalize_merchant(phrase)
    right = normalize_merchant(name)
    if not left or not right:
        return 0
    scores = [_similarity(left, right)]
    for word in left.split():
        if len(word) < 3:
            continue
        scores.extend(_similarity(word, other) for other in right.split())
    return max(scores)


def closest_names(
    phrase: str, candidates: Iterable[tuple[str, str]], limit: int = 5
) -> list[NameMatch]:
    """The closest names at or above the threshold, best first, merchants before categories."""
    found = []
    for name, kind in candidates:
        score = match_score(phrase, name)
        if score >= MATCH_THRESHOLD:
            found.append(NameMatch(name, kind, score))
    found.sort(
        key=lambda item: (
            -item.score,
            0 if item.kind == "merchant" else 1,
            item.name.lower(),
            item.name,
        )
    )
    return found[:limit]
