import pytest

from finances.domain.splits import MAX_PARTS, SPLIT, SplitPart, check_split


def test_the_constants_and_a_part() -> None:
    assert (MAX_PARTS, SPLIT) == (10, "Split")
    assert SplitPart(4, 2, -800, 7) == SplitPart(
        transaction_id=4, position=2, amount_cents=-800, category_id=7
    )


@pytest.mark.parametrize(
    ("amount", "parts"),
    [
        (-2000, [-1200, -800]),
        (5000, [2500, 2500]),
        (-1000, [-100] * 10),
        (-3, [-1, -1, -1]),
    ],
)
def test_a_split_that_adds_up(amount: int, parts: list[int]) -> None:
    assert check_split(amount, parts) is None


@pytest.mark.parametrize(
    ("amount", "parts", "message"),
    [
        (0, [0, 0], "a transaction of zero cannot be split"),
        (0, [100], "a transaction of zero cannot be split"),
        (-2000, [-2000], "a split has 2 to 10 parts"),
        (-1100, [-100] * 11, "a split has 2 to 10 parts"),
        (-2000, [100], "a split has 2 to 10 parts"),
        (-2000, [-2100, 100], "each part must have the transaction's sign and not be zero"),
        (-2000, [-2000, 0], "each part must have the transaction's sign and not be zero"),
        (2000, [2100, -100], "each part must have the transaction's sign and not be zero"),
        (-2000, [-1200, -799], "the parts must add up to the transaction"),
        (-2000, [-1201, -800], "the parts must add up to the transaction"),
        (2000, [1000, 1001], "the parts must add up to the transaction"),
    ],
)
def test_a_split_that_is_refused(amount: int, parts: list[int], message: str) -> None:
    with pytest.raises(ValueError) as raised:
        check_split(amount, parts)
    assert str(raised.value) == message
