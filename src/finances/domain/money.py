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
