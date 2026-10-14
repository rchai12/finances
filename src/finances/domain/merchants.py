"""The merchant a transaction's description names. Imports only from finances.domain."""

import re

from finances.domain.text import collapse_ws

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
