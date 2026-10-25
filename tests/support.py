"""Helpers shared by tests: running a command and reading its output, and reading web pages.

New tests import these instead of copying them. Tests written before Phase 13c keep their own
copies.
"""

from html.parser import HTMLParser

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from finances.cli.main import app

CLI_NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
WEB_NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"
WEB_PORT = 8765

runner = CliRunner(env={"COLUMNS": "250"})


def run(*args: object):
    """Run `fin` with these arguments, each turned into text."""
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    """The heading and the rows of every table in the output, as lists of cell texts."""
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def plain_lines(output: str) -> list[str]:
    """The lines of the output that are not part of a table, without empty ones."""
    tables = ("│", "┃", "┏", "┡", "└")
    return [line for line in output.splitlines() if line and not line.startswith(tables)]


def failed_cleanly(result, message: str) -> bool:
    """Whether the command ended with exit code 1 and only this error message."""
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


class Page(HTMLParser):
    """The parts of a page the tests read: table rows, paragraphs, and forms (not the menu's)."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.paragraphs: list[tuple[str, str]] = []
        self.forms: list[dict] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.paragraph: str | None = None
        self.text: list[str] = []
        self.form: dict | None = None
        self.select: str | None = None
        self.links: list[str] = []
        self.in_nav = False
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "nav":
            self.in_nav = True
        if tag == "a":
            self.links.append(values.get("href", ""))
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "p":
            self.paragraph = values.get("class", "")
            self.text = []
        elif tag == "form":
            self.form = {
                "action": values.get("action", ""),
                "method": values.get("method", "get"),
                "inputs": {},
                "selects": {},
            }
            if not self.in_nav:
                self.forms.append(self.form)
        elif tag == "input" and self.form is not None:
            self.form["inputs"][values.get("name", "")] = (
                values.get("type", "text"),
                values.get("value", ""),
            )
        elif tag == "select" and self.form is not None:
            self.select = values.get("name", "")
            self.form["selects"][self.select] = []
        elif tag == "option" and self.form is not None and self.select is not None:
            self.form["selects"][self.select].append(
                (values.get("value", ""), "selected" in values)
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav":
            self.in_nav = False
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "p" and self.paragraph is not None:
            self.paragraphs.append((self.paragraph, "".join(self.text).strip()))
            self.paragraph = None
        elif tag == "form":
            self.form = None
        elif tag == "select":
            self.select = None

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
        if self.paragraph is not None:
            self.text.append(data)

    def all(self, action: str) -> list[dict]:
        return [form for form in self.forms if form["action"] == action]

    def find(self, action: str) -> dict:
        found = [form for form in self.forms if form["action"] == action]
        assert len(found) == 1, action
        return found[0]


def page(client: TestClient, path: str) -> Page:
    return Page(client.get(path).text)


def post(client: TestClient, path: str, **fields: str):
    """Post a form with the client's form token, without following the redirect."""
    return client.post(
        path, data={"csrf": client.cookies["fin_csrf"], **fields}, follow_redirects=False
    )


def texts(found: Page, kind: str) -> list[str]:
    """The texts of the page's paragraphs of this class, in order."""
    return [text for name, text in found.paragraphs if name == kind]


# Every MCP tool, and the ones that write (proposals and the advice log only).
MCP_TOOLS = [
    "data_coverage",
    "find_merchants",
    "get_balances",
    "get_budgets",
    "get_forecast",
    "get_insights",
    "get_net_worth",
    "get_recurring",
    "get_spending",
    "get_upcoming",
    "list_accounts",
    "list_advice",
    "list_categories",
    "list_proposals",
    "list_rules",
    "list_transactions",
    "list_transfer_suggestions",
    "list_transfers",
    "list_uncategorized",
    "log_advice",
    "month_over_month",
    "propose_category",
    "propose_group",
    "propose_merchant_alias",
    "propose_new_category",
    "propose_not_transfer",
    "propose_rule",
    "propose_transfer",
]
MCP_WRITERS = (
    "propose_category",
    "propose_transfer",
    "propose_not_transfer",
    "propose_rule",
    "propose_merchant_alias",
    "propose_group",
    "propose_new_category",
    "log_advice",
)
