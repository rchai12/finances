import pytest

from finances.ingest.parsers.helpers import find_labeled_amount

SUMMARY = [
    "Rewards      Previous Balance      1,234 points",
    "Payment Due Date      Feb 20, 2026              Previous Balance      $250.00",
    "New Balance      $242.58                    Payments      - $250.00",
    "Minimum Payment Due      $25.00            Other Credits      - $15.65",
    "Credits                               -$43.28",
    "Purchases                             +$759.22",
    "Fees                                  +$0.00",
    "New balance                           = - $67.50",
    "JANE DOE #1111: Payments, Credits and Adjustments",
    "Standard Purchases",
    "Fees Charged",
    "TOTAL FEES FOR THIS PERIOD                      $9.00",
    "Total Transactions for This Period                    $1,258.10",
    "Previous Balance      $999.99",
]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Previous Balance", 25000),
        ("New Balance", 24258),
        ("Payments", -25000),
        ("Other Credits", -1565),
        ("Credits", -4328),
        ("Purchases", 75922),
        ("Fees", 0),
        ("New balance", -6750),
        ("Minimum Payment Due", 2500),
        ("TOTAL FEES FOR THIS PERIOD", 900),
        ("Total Transactions for This Period", 125810),
    ],
)
def test_finds_the_amount_after_a_label(label: str, expected: int) -> None:
    result = find_labeled_amount(SUMMARY, label)
    assert result == expected
    assert type(result) is int


@pytest.mark.parametrize(
    "label",
    [
        "Interest",
        "Transactions",
        "Payment",
        "Balance",
        "Standard Purchases",
        "previous balance",
    ],
)
def test_returns_none_when_no_line_fits(label: str) -> None:
    assert find_labeled_amount(SUMMARY, label) is None


def test_no_lines() -> None:
    assert find_labeled_amount([], "Previous Balance") is None


def test_the_first_fitting_line_wins() -> None:
    assert find_labeled_amount(["Total   $1.00", "Total   $2.00"], "Total") == 100


@pytest.mark.parametrize(
    "line",
    [
        "Fees $5.00",
        "Fees\t$5.00",
        "Fees      $5.00",
        "Other      Fees      $5.00      more text",
        "x  Fees $5.00",
    ],
)
def test_the_label_is_at_the_start_or_after_two_spaces(line: str) -> None:
    assert find_labeled_amount([line], "Fees") == 500


@pytest.mark.parametrize(
    "line",
    [
        "Total Fees $5.00",
        "LateFees $5.00",
        "Fees: $5.00",
        "Fees Charged $5.00",
        "Fees 5.00",
        "Fees $5",
        "Fees $5.0",
        "Fees $ 5.00",
        "Fees",
        "$5.00 Fees",
    ],
)
def test_lines_that_do_not_fit(line: str) -> None:
    assert find_labeled_amount([line], "Fees") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1,234.56", 123456),
        ("-$1,234.56", -123456),
        ("- $1,234.56", -123456),
        ("+$0.07", 7),
        ("+ $0.07", 7),
        ("= $10.00", 1000),
        ("= - $67.50", -6750),
        ("$1234.56", 123456),
    ],
)
def test_money_forms(text: str, expected: int) -> None:
    assert find_labeled_amount([f"Total      {text}"], "Total") == expected


def test_a_line_whose_money_cannot_be_read_is_passed_over() -> None:
    lines = ["Total      + - $5.00", "Total      = = $6.00", "Total      $7.00"]
    assert find_labeled_amount(lines, "Total") == 700


def test_a_label_with_special_characters_is_matched_literally() -> None:
    assert find_labeled_amount(["Fees (est.)   $3.00"], "Fees (est.)") == 300
    assert find_labeled_amount(["Fees (estX)   $3.00"], "Fees (est.)") is None


def test_ascii_digits_only() -> None:
    assert find_labeled_amount(["Total   $١٢.٣٤"], "Total") is None
