from datetime import UTC, datetime

import pytest

from finances.domain.proposals import (
    CATEGORY,
    NOT_TRANSFER,
    OPEN,
    TRANSFER,
    Proposal,
    pair_out_of_date,
    proposal_text,
)

MADE = datetime(2026, 5, 25, tzinfo=UTC)


def test_the_kinds() -> None:
    assert (TRANSFER, NOT_TRANSFER) == ("transfer", "not_transfer")


@pytest.mark.parametrize(
    ("exists", "paired", "rejected", "stale"),
    [
        (True, False, False, False),
        (False, False, False, True),
        (True, True, False, True),
        (True, False, True, True),
    ],
)
def test_a_pair_out_of_date(exists: bool, paired: bool, rejected: bool, stale: bool) -> None:
    assert pair_out_of_date(exists=exists, paired=paired, rejected=rejected) is stale


@pytest.mark.parametrize(
    ("kind", "other_id", "value", "text"),
    [
        (TRANSFER, 2, "", "1 -> 2: a transfer"),
        (NOT_TRANSFER, 3, "", "1 -> 3: not a transfer"),
        (CATEGORY, None, "Dining", "transaction 1: Dining"),
    ],
)
def test_the_text_of_each_kind(kind: str, other_id: int | None, value: str, text: str) -> None:
    found = Proposal(4, kind, 1, value, "why", OPEN, MADE, None, other_id)
    assert proposal_text(found) == text


def test_a_category_proposal_has_no_other_id() -> None:
    assert Proposal(1, CATEGORY, 1, "Dining", "why", OPEN, MADE, None).other_id is None
