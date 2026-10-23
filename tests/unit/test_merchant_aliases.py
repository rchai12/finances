import pytest

from finances.domain.merchants import (
    check_alias,
    merchant_name,
    merchant_names,
    normalize_merchant,
)
from finances.domain.models import CategoryRule
from finances.domain.rules import pick_rule_for


def test_normalize_merchant() -> None:
    assert normalize_merchant("  acme   cafe ") == "ACME CAFE"


def test_merchant_name_and_names() -> None:
    description = "SQ *ACME CAFE 12345"
    assert merchant_name(description, {}) == "ACME CAFE"
    assert merchant_names(description, {}) == ("ACME CAFE",)
    aliases = {"ACME CAFE": "ACME COFFEE"}
    assert merchant_name(description, aliases) == "ACME COFFEE"
    assert merchant_names(description, aliases) == ("ACME CAFE", "ACME COFFEE")


def test_check_alias_refuses_a_long_target() -> None:
    with pytest.raises(ValueError, match="a merchant name must be 1 to 100 characters"):
        check_alias("ACME CAFE", "X" * 101, {})


def test_check_alias_returns_the_normalized_pair() -> None:
    assert check_alias("  acme   cafe ", "Acme Coffee", {}) == ("ACME CAFE", "ACME COFFEE")


def test_pick_rule_for_takes_the_highest_priority_across_names() -> None:
    cafe = CategoryRule(1, "ACME CAFE", "contains", 0, 10)
    coffee = CategoryRule(2, "ACME COFFEE", "contains", 5, 11)
    assert pick_rule_for(("ACME CAFE", "ACME COFFEE"), [cafe, coffee]) == coffee


def test_pick_rule_for_takes_the_oldest_at_equal_priority() -> None:
    cafe = CategoryRule(1, "ACME CAFE", "contains", 5, 10)
    coffee = CategoryRule(2, "ACME COFFEE", "contains", 5, 11)
    assert pick_rule_for(("ACME CAFE", "ACME COFFEE"), [cafe, coffee]) == cafe
    assert pick_rule_for(("ACME COFFEE", "ACME CAFE"), [coffee, cafe]) == cafe


def test_pick_rule_for_when_none_match() -> None:
    tea = CategoryRule(1, "TEA", "contains", 9, 10)
    assert pick_rule_for(("ACME CAFE", "ACME COFFEE"), [tea]) is None
    assert pick_rule_for(("ACME CAFE", "ACME COFFEE"), []) is None
