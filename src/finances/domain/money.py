def format_cents(cents: int) -> str:
    """Return display text for integer cents: 123456 -> "$1,234.56", -1234 -> "-$12.34"."""
    # Handle the sign
    if cents < 0:
        sign = "-"
        abs_cents = -cents
    else:
        sign = ""
        abs_cents = cents

    # Use integer arithmetic to get dollars and cents
    dollars, cents_part = divmod(abs_cents, 100)

    # Format dollars with commas
    dollars_str = f"{dollars:,}"

    # Format cents with exactly two digits
    cents_str = f"{cents_part:02d}"

    # Return the final formatted string
    return f"{sign}${dollars_str}.{cents_str}"


def parse_money(text: str) -> int:
    """Return integer cents for money text such as "$1,234.56", "(12.34)" or "12.34-"."""
    import re
    from decimal import Decimal

    s = text.strip()

    # Find the negative marker
    negative = False
    if s.startswith("(") and s.endswith(")"):
        # Parentheses at both ends
        s = s[1:-1]
        negative = True
    elif s.endswith("-"):
        # Trailing minus
        s = s[:-1]
        negative = True
    elif s.startswith("-"):
        # Leading minus
        s = s[1:]
        negative = True

    # Remove dollar sign if present
    if s.startswith("$"):
        s = s[1:]

    # Check format with regex
    _AMOUNT = re.compile(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?|\.[0-9]{1,2}")
    if not _AMOUNT.fullmatch(s):
        raise ValueError("invalid money text")

    # Remove commas and convert to cents
    s = s.replace(",", "")
    cents = int(Decimal(s) * 100)

    return -cents if negative else cents
