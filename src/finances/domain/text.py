"""How stored text is tidied, and how wide its columns are. Imports nothing from the project."""

NAME_LIMIT = 100
DESCRIPTION_LIMIT = 500
FEED_ID_LIMIT = 100
PROVIDER_ACCOUNT_ID_LIMIT = 200
CATEGORY_NAME_LIMIT = 50
RULE_PATTERN_LIMIT = 100
AUDIT_TEXT_LIMIT = 200


def collapse_ws(text: str) -> str:
    """Return text with outer whitespace removed and inner runs of whitespace made one space."""
    return " ".join(text.split())


def fit(text: str, limit: int) -> str:
    """Return text with its whitespace collapsed, cut to the limit, without trailing spaces."""
    return collapse_ws(text)[:limit].rstrip()
