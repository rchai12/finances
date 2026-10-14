import pytest

from finances.domain.models import CategoryRule
from finances.domain.rules import MATCHES, normalize_pattern, pick_rule, rule_matches


def rule(rule_id: int, pattern: str, match: str = "contains", priority: int = 0) -> CategoryRule:
    return CategoryRule(rule_id, pattern, match, priority, 100 + rule_id)


def test_the_kinds_of_match() -> None:
    assert MATCHES == ("contains", "starts_with", "equals")


@pytest.mark.parametrize(
    ("text", "pattern"),
    [("acme  coffee", "ACME COFFEE"), ("  Foobar\tGrocery ", "FOOBAR GROCERY"), ("", "")],
)
def test_a_pattern_is_upper_case_with_single_spaces(text: str, pattern: str) -> None:
    assert normalize_pattern(text) == pattern


@pytest.mark.parametrize(
    ("match", "pattern", "merchant", "matched"),
    [
        ("contains", "COFFEE", "ACME COFFEE", True),
        ("contains", "COFFEE", "ACME TEA", False),
        ("contains", "acme  coffee", "ACME COFFEE", True),
        ("contains", "ACME", "acme coffee", True),
        ("starts_with", "ACME", "ACME COFFEE", True),
        ("starts_with", "ACME", "THE ACME", False),
        ("equals", "ACME COFFEE", "ACME COFFEE", True),
        ("equals", "ACME", "ACME COFFEE", False),
        ("equals", "ACME COFFEE", "acme  coffee", True),
        ("regex", "ACME", "ACME", False),
    ],
)
def test_rule_matches(match: str, pattern: str, merchant: str, matched: bool) -> None:
    assert rule_matches(rule(1, pattern, match), merchant) is matched


def test_the_highest_priority_wins() -> None:
    rules = [
        rule(1, "COFFEE"),
        rule(2, "ACME", "starts_with", priority=5),
        rule(3, "ACME C", priority=2),
    ]
    assert pick_rule("ACME COFFEE", rules) == rules[1]


def test_equal_priorities_go_to_the_older_rule() -> None:
    rules = [
        rule(7, "COFFEE", priority=1),
        rule(3, "ACME", priority=1),
        rule(9, "ACME COFFEE", "equals", priority=1),
    ]
    assert pick_rule("ACME COFFEE", rules) == rules[1]


def test_a_rule_that_does_not_match_is_passed_over() -> None:
    rules = [rule(1, "TEA", priority=9), rule(2, "COFFEE")]
    assert pick_rule("ACME COFFEE", rules) == rules[1]


def test_no_rule_matches() -> None:
    assert pick_rule("ACME COFFEE", [rule(1, "TEA")]) is None
    assert pick_rule("ACME COFFEE", []) is None


def test_the_rules_are_not_reordered() -> None:
    rules = [rule(2, "A"), rule(1, "A", priority=3)]
    before = list(rules)
    pick_rule("A", rules)
    assert rules == before
