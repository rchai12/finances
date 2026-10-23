from datetime import UTC, datetime

import pytest

from finances.domain.proposals import (
    CATEGORY,
    KINDS,
    OPEN,
    RULE,
    Proposal,
    proposal_text,
    rule_out_of_date,
)

MADE = datetime(2026, 5, 25, tzinfo=UTC)


def test_the_kinds() -> None:
    assert RULE == "rule"
    assert KINDS == ("category", "transfer", "not_transfer", "rule")


@pytest.mark.parametrize(
    ("category_found", "rule_exists", "stale"),
    [
        (True, False, False),
        (False, False, True),
        (True, True, True),
    ],
)
def test_a_rule_out_of_date(category_found: bool, rule_exists: bool, stale: bool) -> None:
    assert rule_out_of_date(category_found=category_found, rule_exists=rule_exists) is stale


def test_the_text_of_a_rule() -> None:
    found = Proposal(
        1, RULE, 1, "Dining", "a cafe", OPEN, MADE, None, None, "ACME COFFEE", "equals", 5
    )
    assert proposal_text(found) == 'rule: equals "ACME COFFEE" -> Dining (priority 5)'


def test_the_new_fields_default_to_none() -> None:
    found = Proposal(1, CATEGORY, 1, "Dining", "why", OPEN, MADE, None)
    assert (found.pattern, found.match, found.priority) == (None, None, None)
