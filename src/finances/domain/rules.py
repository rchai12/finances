"""Which rule puts a merchant in a category. Imports only from finances.domain."""

from finances.domain.models import CategoryRule
from finances.domain.text import collapse_ws

MATCHES = ("contains", "starts_with", "equals")


def normalize_pattern(text: str) -> str:
    """Return text in upper case with single spaces, as patterns are stored and compared."""
    return collapse_ws(text).upper()


def rule_matches(rule: CategoryRule, merchant: str) -> bool:
    pattern = normalize_pattern(rule.pattern)
    name = normalize_pattern(merchant)
    if rule.match == "contains":
        return pattern in name
    if rule.match == "starts_with":
        return name.startswith(pattern)
    if rule.match == "equals":
        return name == pattern
    return False


def pick_rule(merchant: str, rules: list[CategoryRule]) -> CategoryRule | None:
    """Return the matching rule with the highest priority, the oldest among equals, or None."""
    matching = [rule for rule in rules if rule_matches(rule, merchant)]
    return min(matching, key=lambda rule: (-rule.priority, rule.id), default=None)
