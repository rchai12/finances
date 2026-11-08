import anyio
import pytest
from mcp.client import Client

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.mcp_server.server import build_server
from tests.support import add_findings_data, failed_cleanly, plain_lines, run, table_rows

MAY = ("--month", "2026-05")
HANDLE_SPIKE = {
    "type": "spike",
    "about": "dining",
    "month": "2026-05",
    "status": "handled",
    "reason": "a one-off dinner",
}
IGNORE_INTEREST = {"type": "interest", "month": "2026-05", "status": "ignored", "reason": "known"}
SPIKE_DETAIL = "Dining: $200.00 this month, against $60.00 a month before."
TYPES = (
    "type must be one of: spike, frequent_small, subscription_overlap, price_increase, interest, "
    "fees, over_budget, duplicate, large_first_charge"
)


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def made(arguments: dict) -> dict:
    return call("propose_finding_status", arguments).structured_content["proposal"]


def error(arguments: dict) -> list[str]:
    return [item.text for item in call("propose_finding_status", arguments).content]


def rows() -> list[list[str]]:
    return table_rows(run("review", "list").stdout)[1:]


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    upgrade_to_head()
    add_findings_data()
    return tmp_settings


def test_the_agent_proposes_a_finding_handled(money: Settings) -> None:
    proposal = made(HANDLE_SPIKE)
    assert (
        proposal["kind"],
        proposal["transaction_id"],
        proposal["category"],
        proposal["finding"],
    ) == (
        "finding_status",
        None,
        None,
        {"type": "spike", "about": "Dining", "month": "2026-05", "status": "handled"},
    )
    assert rows() == [
        [
            "1",
            "",
            "",
            "",
            "",
            "spike for Dining in 2026-05",
            "mark handled",
            "a one-off dinner",
            "open",
        ]
    ]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: spike for Dining in 2026-05 is handled.\n",
    )
    assert table_rows(run("insights", *MAY).stdout)[-1] == [
        "medium",
        "spike",
        "Dining",
        "$140.00",
        SPIKE_DETAIL,
        "handled",
    ]


def test_the_agent_proposes_a_finding_ignored(money: Settings) -> None:
    assert made(IGNORE_INTEREST)["finding"] == {
        "type": "interest",
        "about": "",
        "month": "2026-05",
        "status": "ignored",
    }
    assert rows()[0][5:7] == ["interest in 2026-05", "ignore in every month"]
    accepted = run("review", "accept", "--id", "1")
    assert accepted.stdout == "Accepted proposal 1: interest in every month is ignored.\n"
    assert plain_lines(run("insights", "--month", "2026-06").stdout) == [
        "Insights for 2026-06.",
        "No findings.",
        "Handled or ignored:",
    ]


def test_accepting_records_the_status_in_history(money: Settings) -> None:
    made(HANDLE_SPIKE)
    run("review", "accept", "--id", "1")
    found = table_rows(run("audit").stdout)
    assert [row[1:] for row in found[1:3]] == [
        [
            "person",
            "proposal_accepted",
            "proposal 1",
            "",
            "finding spike for Dining in 2026-05: handled",
        ],
        ["person", "finding_handled", "finding 1", "", "spike for Dining in 2026-05"],
    ]


def test_get_insights_lists_the_set_aside_findings(money: Settings) -> None:
    run("findings", "handle", "--type", "spike", "--about", "Dining", *MAY)
    found = call("get_insights", {"month": "2026-05"}).structured_content
    assert [item["type"] for item in found["findings"]] == [
        "interest",
        "price_increase",
        "frequent_small",
        "subscription_overlap",
    ]
    assert found["set_aside"] == [
        {
            "type": "spike",
            "severity": "medium",
            "subject": "Dining",
            "savings_cents": 14000,
            "detail": SPIKE_DETAIL,
            "status": "handled",
        }
    ]


def test_a_person_setting_the_status_first_puts_it_out_of_date(money: Settings) -> None:
    made(IGNORE_INTEREST)
    run("findings", "handle", "--type", "interest", *MAY)
    assert rows()[0][8] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: a person set this finding's status since",
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({**HANDLE_SPIKE, "about": "Groceries"}, "no such finding: spike for Groceries in 2026-05"),
        (
            {**HANDLE_SPIKE, "type": "nope"},
            TYPES,
        ),
        ({**HANDLE_SPIKE, "month": "2026-13"}, "month must be a year and month, like 2026-05"),
        ({**HANDLE_SPIKE, "status": "done"}, "status must be one of: handled, ignored"),
        ({**HANDLE_SPIKE, "reason": " "}, "a reason must be 1 to 200 characters"),
    ],
)
def test_a_refused_proposal(money: Settings, arguments: dict, message: str) -> None:
    assert error(arguments) == [f"Error executing tool propose_finding_status: {message}"]


def test_a_finding_with_a_status_is_refused(money: Settings) -> None:
    run("findings", "ignore", "--type", "interest", *MAY)
    assert error(IGNORE_INTEREST) == [
        "Error executing tool propose_finding_status: this finding is already ignored"
    ]


def test_one_open_proposal_for_a_finding(money: Settings) -> None:
    made(HANDLE_SPIKE)
    assert error({**HANDLE_SPIKE, "status": "ignored"}) == [
        "Error executing tool propose_finding_status: this finding already has an open proposal"
    ]


def test_a_declined_proposal_is_not_made_again(money: Settings) -> None:
    made(IGNORE_INTEREST)
    run("review", "decline", "--id", "1")
    assert error(IGNORE_INTEREST) == [
        "Error executing tool propose_finding_status: a person declined this proposal already"
    ]
    assert made({**IGNORE_INTEREST, "status": "handled"})["id"] == 2
