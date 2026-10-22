from datetime import date

import pytest

from finances.domain.merchants import MATCH_THRESHOLD, NameMatch, closest_names, match_score
from finances.domain.periods import joined_periods

CANDIDATES = [
    ("ACME COFFEE", "merchant"),
    ("ACME UTILITY", "merchant"),
    ("FOOBAR GROCERY", "merchant"),
    ("BAZ BOOKS", "merchant"),
    ("Coffee & Dessert", "category"),
    ("Groceries", "category"),
]


@pytest.mark.parametrize(
    ("phrase", "name", "score"),
    [
        ("cofee", "ACME COFFEE", 91),
        ("groceries", "FOOBAR GROCERY", 75),
        ("groceries", "Groceries", 100),
        ("that coffee place", "ACME UTILITY", 67),
        ("xyz", "BAZ BOOKS", 33),
        ("  Foobar   grocery ", "FOOBAR GROCERY", 100),
        ("ed", "Education", 36),
        ("   ", "BAZ BOOKS", 0),
    ],
)
def test_the_score(phrase: str, name: str, score: int) -> None:
    assert match_score(phrase, name) == score


def test_best_first_merchants_before_categories_on_a_tie() -> None:
    assert MATCH_THRESHOLD == 75
    assert closest_names("cofee", CANDIDATES) == [
        NameMatch("ACME COFFEE", "merchant", 91),
        NameMatch("Coffee & Dessert", "category", 91),
    ]
    assert closest_names("groceries", CANDIDATES) == [
        NameMatch("Groceries", "category", 100),
        NameMatch("FOOBAR GROCERY", "merchant", 75),
    ]


def test_a_tie_of_the_same_kind_goes_by_name() -> None:
    assert closest_names("acme", CANDIDATES) == [
        NameMatch("ACME COFFEE", "merchant", 100),
        NameMatch("ACME UTILITY", "merchant", 100),
    ]


def test_the_limit_and_nothing_close() -> None:
    assert closest_names("acme", CANDIDATES, limit=1) == [NameMatch("ACME COFFEE", "merchant", 100)]
    assert closest_names("xyz", CANDIDATES) == []
    assert closest_names("that coffee place", [("ACME UTILITY", "merchant")]) == []


@pytest.mark.parametrize(
    ("periods", "joined"),
    [
        ([], []),
        (
            [(date(2026, 4, 1), date(2026, 4, 30)), (date(2026, 1, 1), date(2026, 1, 31))],
            [(date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 4, 1), date(2026, 4, 30))],
        ),
        (
            [(date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 2, 1), date(2026, 2, 28))],
            [(date(2026, 1, 1), date(2026, 2, 28))],
        ),
        (
            [(date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 1, 15), date(2026, 1, 20))],
            [(date(2026, 1, 1), date(2026, 1, 31))],
        ),
        (
            [(date(2026, 1, 1), date(2026, 1, 30)), (date(2026, 2, 1), date(2026, 2, 28))],
            [(date(2026, 1, 1), date(2026, 1, 30)), (date(2026, 2, 1), date(2026, 2, 28))],
        ),
    ],
    ids=["none", "out of order", "next day joins", "inside joins", "one day apart stays"],
)
def test_joined_periods(periods: list, joined: list) -> None:
    assert joined_periods(periods) == joined
