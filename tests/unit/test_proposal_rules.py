from datetime import UTC, datetime

import pytest

from finances.domain.proposals import (
    ACCEPTED,
    CATEGORY,
    DECLINED,
    KINDS,
    OPEN,
    STATUSES,
    Proposal,
    out_of_date,
    proposal_text,
)
from finances.domain.text import ADVICE_TEXT_LIMIT, PROPOSAL_TEXT_LIMIT


def test_the_lists_and_limits() -> None:
    assert (CATEGORY, KINDS) == ("category", ("category", "transfer", "not_transfer"))
    assert (OPEN, ACCEPTED, DECLINED, STATUSES) == (
        "open",
        "accepted",
        "declined",
        ("open", "accepted", "declined"),
    )
    assert (PROPOSAL_TEXT_LIMIT, ADVICE_TEXT_LIMIT) == (200, 1000)


@pytest.mark.parametrize(
    ("exists", "set_by_hand", "paired", "stale"),
    [
        (True, False, False, False),
        (False, False, False, True),
        (True, True, False, True),
        (True, False, True, True),
    ],
)
def test_out_of_date(exists: bool, set_by_hand: bool, paired: bool, stale: bool) -> None:
    assert out_of_date(exists=exists, set_by_hand=set_by_hand, paired=paired) is stale


def test_the_text_of_a_proposal() -> None:
    made = datetime(2026, 5, 25, tzinfo=UTC)
    found = Proposal(3, CATEGORY, 5, "Groceries", "FOOBAR is a grocer", OPEN, made, None)
    assert proposal_text(found) == "transaction 5: Groceries"
