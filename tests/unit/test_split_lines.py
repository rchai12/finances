import pytest

from finances.domain.splits import parse_parts


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("12.00 Groceries\n8.00 Home & Garden", [(1200, "Groceries"), (800, "Home & Garden")]),
        ("\n  12.00 Groceries  \r\n\n 8 Dining\n", [(1200, "Groceries"), (800, "Dining")]),
        ("", []),
    ],
)
def test_one_part_per_line(text: str, parts: list[tuple[int, str]]) -> None:
    assert parse_parts(text) == parts


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("12.00 Groceries\n8.00", "a part is a size and a category, such as 12.00 Groceries"),
        ("12.00 Groceries\neight Dining", "invalid money text"),
    ],
)
def test_a_line_that_is_refused(text: str, message: str) -> None:
    with pytest.raises(ValueError) as raised:
        parse_parts(text)
    assert str(raised.value) == message
