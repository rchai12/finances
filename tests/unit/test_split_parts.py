import pytest

from finances.domain.splits import parse_part, signed_parts


@pytest.mark.parametrize(
    ("amount", "sizes", "signed"),
    [
        (-2000, [1200, 800], [-1200, -800]),
        (5000, [2500, 2500], [2500, 2500]),
        (0, [100, 100], [100, 100]),
    ],
)
def test_sizes_take_the_transaction_sign(amount: int, sizes: list[int], signed: list[int]) -> None:
    assert signed_parts(amount, sizes) == signed


@pytest.mark.parametrize("sizes", [[1200, 0], [-1200, 800]])
def test_a_size_must_be_more_than_zero(sizes: list[int]) -> None:
    with pytest.raises(ValueError) as raised:
        signed_parts(-2000, sizes)
    assert str(raised.value) == "each part's size must be more than zero"


@pytest.mark.parametrize(
    ("text", "part"),
    [
        ("12.00 Groceries", (1200, "Groceries")),
        ("  $8   Home & Garden  ", (800, "Home & Garden")),
        ("1,234.56\tRent & Mortgage", (123456, "Rent & Mortgage")),
        ("-12.00 Groceries", (-1200, "Groceries")),
    ],
)
def test_a_part_as_typed(text: str, part: tuple[int, str]) -> None:
    assert parse_part(text) == part


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("12.00", "a part is a size and a category, such as 12.00 Groceries"),
        ("   ", "a part is a size and a category, such as 12.00 Groceries"),
        ("twelve Groceries", "invalid money text"),
    ],
)
def test_a_part_that_is_refused(text: str, message: str) -> None:
    with pytest.raises(ValueError) as raised:
        parse_part(text)
    assert str(raised.value) == message
