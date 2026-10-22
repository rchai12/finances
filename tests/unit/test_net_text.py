import pytest

from finances.domain.spending import SpendingLine
from finances.views.format import amount_class, net_text


@pytest.mark.parametrize(
    ("cents", "text"),
    [(0, "$0.00"), (1500, "$15.00"), (-599, "$5.99 back"), (-123456, "$1,234.56 back")],
)
def test_net_spending_never_shows_a_minus(cents: int, text: str) -> None:
    assert net_text(cents) == text


@pytest.mark.parametrize(
    ("text", "classes"),
    [("$5.99 back", "amount pos"), ("$5.99", "amount"), ("-$5.99", "amount neg")],
)
def test_money_back_reads_as_a_gain(text: str, classes: str) -> None:
    assert amount_class(text) == classes


def test_purchases_are_net_spending_plus_refunds() -> None:
    assert SpendingLine("QUUX", -500, 2, 700).purchases_cents == 200
    assert SpendingLine("Food", 500, 2).purchases_cents == 500
