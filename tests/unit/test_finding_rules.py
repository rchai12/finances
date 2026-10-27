from datetime import UTC, date, datetime

import pytest

from finances.domain.findings import (
    FINDING_STATUSES,
    HANDLED,
    IGNORED,
    ClosedFinding,
    FindingStatus,
    finding_text,
    split_findings,
    status_of,
)
from finances.domain.insights import Finding

MAY = date(2026, 5, 1)
JUNE = date(2026, 6, 1)
AT = datetime(2026, 6, 2, 9, 0, tzinfo=UTC)
SPIKE = Finding("spike", "medium", MAY, "Dining", 14000, "Dining: up.")
INTEREST = Finding("interest", "high", MAY, "", 2345, "Interest charged: $23.45.")
COFFEE = Finding("frequent_small", "low", MAY, "ACME COFFEE", 2000, "ACME COFFEE: 8 visits.")


def handled(type: str, subject: str, month: date, id: int = 1) -> FindingStatus:
    return FindingStatus(id, type, subject, month, HANDLED, AT)


def ignored(type: str, subject: str, id: int = 1) -> FindingStatus:
    return FindingStatus(id, type, subject, None, IGNORED, AT)


def test_the_statuses() -> None:
    assert (HANDLED, IGNORED, FINDING_STATUSES) == ("handled", "ignored", ("handled", "ignored"))


@pytest.mark.parametrize(
    ("type", "subject", "month", "text"),
    [
        ("spike", "Dining", MAY, "spike for Dining in 2026-05"),
        ("interest", "", JUNE, "interest in 2026-06"),
        ("spike", "Dining", None, "spike for Dining in every month"),
    ],
)
def test_the_text(type: str, subject: str, month: date | None, text: str) -> None:
    assert finding_text(type, subject, month) == text


@pytest.mark.parametrize(
    ("statuses", "found"),
    [
        ([], None),
        ([handled("spike", "Dining", MAY)], "handled"),
        ([handled("spike", "Dining", JUNE)], None),
        ([handled("spike", "Coffee & Dessert", MAY)], None),
        ([handled("price_increase", "Dining", MAY)], None),
        ([handled("spike", "dining", MAY)], "handled"),
        ([ignored("spike", "Dining")], "ignored"),
        ([handled("spike", "Dining", MAY, 1), ignored("spike", "Dining", 2)], "ignored"),
    ],
)
def test_the_status_of_a_finding(statuses: list[FindingStatus], found: str | None) -> None:
    assert status_of(SPIKE, statuses) == found


def test_an_empty_subject_matches_only_an_empty_one() -> None:
    assert status_of(INTEREST, [ignored("interest", "")]) == "ignored"
    assert status_of(INTEREST, [ignored("interest", "Dining")]) is None


def test_splitting_keeps_the_order() -> None:
    statuses = [handled("frequent_small", "ACME COFFEE", MAY, 1), ignored("interest", "", 2)]
    assert split_findings([INTEREST, SPIKE, COFFEE], statuses) == (
        [SPIKE],
        [ClosedFinding(INTEREST, "ignored"), ClosedFinding(COFFEE, "handled")],
    )
    assert split_findings([SPIKE], []) == ([SPIKE], [])
