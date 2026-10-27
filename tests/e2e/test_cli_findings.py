import pytest

from finances.config import Settings
from tests.support import (
    CLI_NOT_MIGRATED,
    add_findings_data,
    failed_cleanly,
    plain_lines,
    run,
    table_rows,
)

MAY = ("--month", "2026-05")
JUNE = ("--month", "2026-06")
OPEN = ["Severity", "Type", "About", "Saves a month", "Detail"]
CLOSED = ["Severity", "Type", "About", "Saves a month", "Detail", "Status"]
INTEREST = ["high", "interest", "", "$23.45", "Interest charged: $23.45."]
SPIKE = [
    "medium",
    "spike",
    "Dining",
    "$140.00",
    "Dining: $200.00 this month, against $60.00 a month before.",
]
PRICE = [
    "medium",
    "price_increase",
    "QUUX STREAMING",
    "$2.00",
    "QUUX STREAMING went from $15.99 to $17.99.",
]
COFFEE = [
    "low",
    "frequent_small",
    "ACME COFFEE",
    "$20.00",
    "ACME COFFEE: 8 visits averaging $5.00.",
]
OVERLAP = [
    "low",
    "subscription_overlap",
    "Subscriptions & Digital",
    "$9.99",
    "Subscriptions & Digital: QUUX STREAMING ($17.99), BAZ VIDEO ($9.99).",
]
JUNE_INTEREST = ["high", "interest", "", "$10.00", "Interest charged: $10.00."]
TYPES = (
    "type must be one of: spike, frequent_small, subscription_overlap, price_increase, interest, "
    "fees, over_budget, duplicate, large_first_charge"
)


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    add_findings_data()
    return tmp_settings


def test_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("findings", "handle", "--type", "interest", *MAY)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_handling_a_finding_moves_it_below(money: Settings) -> None:
    result = run("findings", "handle", "--type", "spike", "--about", "dining", *MAY)
    assert (result.exit_code, result.stdout) == (
        0,
        "Marked handled: spike for Dining in 2026-05.\n",
    )
    shown = run("insights", *MAY).stdout
    assert table_rows(shown) == [
        OPEN,
        INTEREST,
        PRICE,
        COFFEE,
        OVERLAP,
        CLOSED,
        [*SPIKE, "handled"],
    ]
    assert plain_lines(shown) == [
        "Insights for 2026-05.",
        "Findings: 4. Could save up to $55.44 a month.",
        "Handled or ignored:",
    ]


def test_handled_holds_for_that_month_only(money: Settings) -> None:
    assert run("findings", "handle", "--type", "interest", *MAY).exit_code == 0
    shown = run("insights", *JUNE).stdout
    assert table_rows(shown) == [OPEN, JUNE_INTEREST]
    assert "Handled or ignored:" not in plain_lines(shown)


def test_ignored_holds_for_every_month(money: Settings) -> None:
    result = run("findings", "ignore", "--type", "interest", *MAY)
    assert (result.exit_code, result.stdout) == (0, "Ignoring: interest in every month.\n")
    shown = run("insights", *JUNE).stdout
    assert table_rows(shown) == [CLOSED, [*JUNE_INTEREST, "ignored"]]
    assert plain_lines(shown) == ["Insights for 2026-06.", "No findings.", "Handled or ignored:"]


def test_reopening_a_finding(money: Settings) -> None:
    run("findings", "ignore", "--type", "interest", *MAY)
    result = run("findings", "reopen", "--type", "interest", *JUNE)
    assert (result.exit_code, result.stdout) == (0, "Reopened: interest in 2026-06.\n")
    assert table_rows(run("insights", *MAY).stdout)[:2] == [OPEN, INTEREST]
    assert "Handled or ignored:" not in plain_lines(run("insights", *MAY).stdout)


def test_reopening_clears_the_month_and_every_month(money: Settings) -> None:
    run("findings", "handle", "--type", "spike", "--about", "Dining", *MAY)
    run("findings", "reopen", "--type", "spike", "--about", "Dining", *MAY)
    run("findings", "ignore", "--type", "spike", "--about", "Dining", *MAY)
    assert run("findings", "reopen", "--type", "spike", "--about", "DINING", *MAY).exit_code == 0
    assert "Handled or ignored:" not in plain_lines(run("insights", *MAY).stdout)


def test_history_records_each_change(money: Settings) -> None:
    run("findings", "handle", "--type", "spike", "--about", "Dining", *MAY)
    run("findings", "ignore", "--type", "interest", *MAY)
    run("findings", "reopen", "--type", "interest", *MAY)
    rows = table_rows(run("audit").stdout)
    assert [row[1:] for row in rows[1:4]] == [
        ["person", "finding_reopened", "finding 2", "interest in every month", ""],
        ["person", "finding_ignored", "finding 2", "", "interest in every month"],
        ["person", "finding_handled", "finding 1", "", "spike for Dining in 2026-05"],
    ]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("handle", "--type", "nope", *MAY), TYPES),
        (
            ("handle", "--type", "spike", "--about", "Groceries", *MAY),
            "no such finding: spike for Groceries in 2026-05",
        ),
        (
            ("ignore", "--type", "interest", "--month", "2026-04"),
            "no such finding: interest in 2026-04",
        ),
        (
            ("handle", "--type", "interest", "--month", "2026-13"),
            "month must be a year and month, like 2026-05",
        ),
        (("reopen", "--type", "interest", *MAY), "this finding is open"),
    ],
)
def test_a_refusal(money: Settings, args: tuple, message: str) -> None:
    assert failed_cleanly(run("findings", *args), message)


@pytest.mark.parametrize(
    ("first", "then", "message"),
    [
        ("handle", "handle", "this finding is already handled"),
        ("ignore", "handle", "this finding is already ignored"),
    ],
)
def test_a_finding_with_a_status_is_refused(
    money: Settings, first: str, then: str, message: str
) -> None:
    assert run("findings", first, "--type", "interest", *MAY).exit_code == 0
    assert failed_cleanly(run("findings", then, "--type", "interest", *MAY), message)
