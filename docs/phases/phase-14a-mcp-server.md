# Phase 14a: the MCP server and the account tools

## Goal

The household's agent can reach the app. After this phase, `fin mcp serve` runs an MCP server on **stdio** (no port) with three read-only tools: `list_accounts`, `get_balances`, and `get_net_worth`. Each tool reads the database through a session that cannot write, returns one JSON object of plain data (integer cents, ISO dates, the holder's signs), and refuses with a fixed message when the database is not migrated. The server logs nothing.

This is the first of Phase 14's sub-phases; the later ones add tool groups (transactions and spending; findings and looking ahead; the work queues and `find_merchants`) on the same server.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/architecture.md`, "Agent interface" and "Privacy boundary"; `docs/roadmap.md`, Phase 14
- `src/finances/db/engine.py`, `src/finances/db/migrate.py`, `src/finances/analysis/balances.py`, `src/finances/analysis/networth.py`, `src/finances/cli/web.py` (a serve command), `src/finances/cli/common.py` (`require_current_schema`)
- `src/finances/db/repositories.py`: `list_accounts`, `list_people`, `list_account_owners`

## Starting state

N is `3014` when Phase 27d is the last phase built.

## Facts about the SDK (version 2.3, checked by the architect)

- In mcp 2.x the server class is `mcp.server.mcpserver.MCPServer` (1.x's `FastMCP` is gone; importing it raises). `MCPServer(name=..., instructions=..., log_level=...)`; `server.add_tool(fn, name=None, title=None, description=None, annotations=None, structured_output=None)`; `server.run("stdio")`.
- A tool whose return annotation is `dict[str, Any]` sends that dict as the result's `structured_content` (and as JSON text). A sync tool runs in a worker thread.
- Arguments are checked from the function's signature with pydantic: `Annotated[int, Field(ge=1, le=60)]` refuses 0 with `is_error` and a message starting `Error executing tool NAME: 1 validation error`.
- Raising `mcp.server.mcpserver.exceptions.ToolError("text")` gives the agent `Error executing tool NAME: text`. Any other exception gives only `Error executing tool NAME`.
- The SDK logs through loggers under `mcp`: tool failures at INFO with their message, and an unexpected exception at ERROR with its traceback. `MCPServer` also calls `logging.basicConfig` at its `log_level`.
- `mcp.client.Client(server)` connects to a server object in the same process (memory streams; no subprocess, no socket). The given tests use it.
- With empty input on stdin, `run("stdio")` returns at once and writes nothing to stdout or stderr.

## Scope

| Path | What changes |
|---|---|
| `pyproject.toml` | the dependency (R1) |
| `src/finances/db/engine.py` | `read_only` (R2) |
| `src/finances/mcp_server/__init__.py`, `access.py`, `server.py`, `tools.py` | new (R3 to R8) |
| `src/finances/cli/mcp.py`, `src/finances/cli/main.py` | `fin mcp serve` (R9) |
| `tests/integration/test_mcp_accounts.py`, `tests/e2e/test_cli_mcp.py` | new: given |
| `tests/integration/test_mcp_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Any other tool (later sub-phases); resources, prompts, sampling, or a client.
- Any transport but stdio, any port or host option, any authentication.
- Writing anything: no tool calls a repository function that adds, changes, or deletes (Phase 19 brings proposals).
- Changes to `views`, `web`, or the analysis functions the tools call.

## Dependencies

One new: `"mcp>=2.3,<3"` in `[project] dependencies`. Install it with exactly

```
.venv/bin/python -m pip install -e ".[dev]"
```

pip's default strategy installs what is missing and upgrades nothing already satisfied (the SDK's needs are met by the installed FastAPI, Starlette, pydantic, anyio, and uvicorn; it adds `mcp`, `mcp-types`, `jsonschema`, `pyjwt`, `cryptography`, and `sse-starlette`). Then run `.venv/bin/python -m pip check` (expect `No broken requirements found.`) and record the installed `mcp` version in the progress entry. No migration.

## Design

```python
# src/finances/db/engine.py
def get_engine(url: str | None = None, *, read_only: bool = False) -> Engine: ...

# src/finances/mcp_server/access.py
NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"

@contextmanager
def reading() -> Iterator[Session]: ...

# src/finances/mcp_server/tools.py  (one function per tool, each returning one JSON object)
def list_accounts(include_inactive: bool = False) -> dict[str, Any]: ...
def get_balances() -> dict[str, Any]: ...
def get_net_worth(months: Annotated[int, Field(ge=1, le=60)] = 12) -> dict[str, Any]: ...

# src/finances/mcp_server/server.py
SERVER_NAME = "finances"
INSTRUCTIONS = (
    "Read-only tools over one household's finances. Money is in integer cents. Amounts are"
    " from the account holder's side: money leaving is negative, money coming in is positive,"
    " and a card balance owed is negative. Dates are ISO (YYYY-MM-DD). Nothing here changes data."
)
READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)

def build_server() -> MCPServer: ...
def serve() -> None: ...
```

Tool descriptions (each tool's `description`, exactly):

| Tool | Description |
|---|---|
| `list_accounts` | `List the household's accounts: name, institution, type, currency, last 4 digits, whether open, and owner (a person's name, or joint). Closed accounts only when include_inactive is true. No amounts.` |
| `get_balances` | `Each open account's newest balance in integer cents (a card balance owed is negative), its date and source (statement or aggregator), totals for cash, cards, and other, the net worth, and the open accounts with no balance yet.` |
| `get_net_worth` | `Net worth in integer cents at the end of each of the last N months (1 to 60, default 12), this month ending today: each open account's newest balance on or before that day, with how many accounts were counted. Months before any balance are left out.` |

## Requirements

### Part 1: the dependency and the engine

- **R1.** `pyproject.toml` lists `"mcp>=2.3,<3"` in `[project] dependencies`, installed as above. Nothing else in `pyproject.toml` changes.
- **R2.** `get_engine(..., read_only=True)` runs `PRAGMA query_only=ON` on every new connection, after `PRAGMA foreign_keys=ON`, so any write fails with SQLite's `attempt to write a readonly database`. `read_only=False` (the default) behaves exactly as today.

### Part 2: the server

- **R3.** `reading()` first compares `current_revision()` with `head_revision()` and raises `ToolError(NOT_MIGRATED)` when they differ; otherwise it opens `get_engine(read_only=True)`, yields a session from `session_scope`, and disposes of the engine when the block ends, also when it raises. Every tool reads only through `reading()`.
- **R4.** `build_server()` returns a new `MCPServer(name=SERVER_NAME, instructions=INSTRUCTIONS, log_level="WARNING")` with the three tools of `tools.py` added by `add_tool`, each with its description from the table, `annotations=READ_ONLY`, and `structured_output=True`; then it sets the logger named `mcp` to `logging.CRITICAL`, so the SDK records nothing about tool calls, arguments, results, or failures. No resources, prompts, or other tools.
- **R5.** `serve()` calls `build_server().run("stdio")`. No other transport appears anywhere in `mcp_server`.

### Part 3: the tools

- **R6.** `list_accounts` returns `{"accounts": [...]}`, from `list_accounts(session, include_inactive=...)` in its order, each item with `name`, `institution`, `type` (the type's value), `currency`, `last4` (or null), `active`, `owner` (the person's name, or null), and `joint` (true only when the account's owner row names no person). An account with no owner row has `owner` null and `joint` false.
- **R7.** `get_balances` returns Phase 12b's `balance_report`: `accounts` (one item per line: `name`, `type`, `balance_cents`, `as_of` as an ISO date, `source`, each null when the account has no balance), `cash_cents`, `cards_cents`, `other_cents`, `net_worth_cents`, `without_balance`.
- **R8.** `get_net_worth` returns `{"as_of": today, "points": [...]}` from Phase 27d's `net_worth_over_time(session, today, months)`, each point with `day` (ISO), `net_worth_cents`, `accounts`. Today is `finances.clock.today()`, looked up through the module when the tool runs. `months` outside 1 to 60 is refused by the signature, before any database access.

### Part 4: the terminal

- **R9.** `fin mcp serve` (a Typer group `mcp` with the help `Serve the agent's tools over stdio.`, added in `cli/main.py`) takes no options and calls `finances.mcp_server.server.serve()` through the module. It prints nothing: stdout carries the protocol. It does not check the schema itself (each tool does, so a server started before `fin db upgrade` recovers without a restart).

Refusals are `ToolError`s with constant text: no tool echoes an argument, a name, or an amount in an error.

## Given tests

13 tests in two files. The tool tests call the server in process through `mcp.client.Client`; `finances.clock.today` is replaced with 2026-05-25.

`tests/integration/test_mcp_accounts.py`

```python
import logging
from datetime import date

import anyio
import pytest
from mcp.client import Client
from sqlalchemy.exc import OperationalError

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_person,
    set_account_active,
    set_account_owner,
)
from finances.domain.models import DataSource
from finances.mcp_server.access import reading
from finances.mcp_server.server import INSTRUCTIONS, build_server

READ_ONLY = {
    "read_only_hint": True,
    "destructive_hint": False,
    "idempotent_hint": True,
    "open_world_hint": False,
}


def call(server, name: str, arguments: dict | None = None):
    async def go():
        async with Client(server) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def money(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """A card Pat owns, a joint checking account, savings with no owner and no balance, and a
    closed account."""
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 25))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        pat = create_person(session, "Pat Example")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card", last4="4321")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        create_account(session, "Test Savings", "Test Bank", "savings")
        old = create_account(session, "Test Old", "Test Bank", "checking")
        set_account_owner(session, card.id, pat.id)
        set_account_owner(session, checking.id, None)
        for account, day, cents, source in (
            (card, date(2026, 4, 30), -30000, DataSource.STATEMENT),
            (card, date(2026, 5, 24), -45000, DataSource.AGGREGATOR),
            (checking, date(2026, 4, 30), 250000, DataSource.STATEMENT),
            (checking, date(2026, 5, 20), 300000, DataSource.AGGREGATOR),
            (old, date(2026, 1, 31), 500000, DataSource.STATEMENT),
        ):
            add_balance_snapshot(session, account.id, day, cents, source)
        set_account_active(session, old.id, False)
    engine.dispose()
    return tmp_settings


def test_the_server_and_its_tools(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return client.server_info.name, client.instructions, (await client.list_tools()).tools

    name, instructions, tools = anyio.run(go)
    assert (name, instructions) == ("finances", INSTRUCTIONS)
    assert sorted(tool.name for tool in tools) == ["get_balances", "get_net_worth", "list_accounts"]
    for tool in tools:
        assert tool.annotations.model_dump(include=set(READ_ONLY)) == READ_ONLY, tool.name
        assert "cents" in tool.description or tool.name == "list_accounts", tool.name


def test_list_accounts(money: Settings) -> None:
    card = {
        "name": "Test Card",
        "institution": "Example Card Co",
        "type": "credit_card",
        "currency": "USD",
        "last4": "4321",
        "active": True,
        "owner": "Pat Example",
        "joint": False,
    }
    checking = {
        "name": "Test Checking",
        "institution": "Test Bank",
        "type": "checking",
        "currency": "USD",
        "last4": None,
        "active": True,
        "owner": None,
        "joint": True,
    }
    old = {
        "name": "Test Old",
        "institution": "Test Bank",
        "type": "checking",
        "currency": "USD",
        "last4": None,
        "active": False,
        "owner": None,
        "joint": False,
    }
    savings = {
        "name": "Test Savings",
        "institution": "Test Bank",
        "type": "savings",
        "currency": "USD",
        "last4": None,
        "active": True,
        "owner": None,
        "joint": False,
    }
    server = build_server()
    result = call(server, "list_accounts")
    assert result.is_error is False
    assert result.structured_content == {"accounts": [card, checking, savings]}
    found = call(server, "list_accounts", {"include_inactive": True}).structured_content
    assert found == {"accounts": [card, checking, old, savings]}


def test_get_balances(money: Settings) -> None:
    assert call(build_server(), "get_balances").structured_content == {
        "accounts": [
            {
                "name": "Test Card",
                "type": "credit_card",
                "balance_cents": -45000,
                "as_of": "2026-05-24",
                "source": "aggregator",
            },
            {
                "name": "Test Checking",
                "type": "checking",
                "balance_cents": 300000,
                "as_of": "2026-05-20",
                "source": "aggregator",
            },
            {
                "name": "Test Savings",
                "type": "savings",
                "balance_cents": None,
                "as_of": None,
                "source": None,
            },
        ],
        "cash_cents": 300000,
        "cards_cents": -45000,
        "other_cents": 0,
        "net_worth_cents": 255000,
        "without_balance": ["Test Savings"],
    }


def test_get_net_worth_follows_the_app_clock(money: Settings) -> None:
    assert call(build_server(), "get_net_worth", {"months": 3}).structured_content == {
        "as_of": "2026-05-25",
        "points": [
            {"day": "2026-04-30", "net_worth_cents": 220000, "accounts": 2},
            {"day": "2026-05-25", "net_worth_cents": 255000, "accounts": 2},
        ],
    }


@pytest.mark.parametrize("months", [0, 61])
def test_get_net_worth_refuses_months_out_of_range(money: Settings, months: int) -> None:
    result = call(build_server(), "get_net_worth", {"months": months})
    assert result.is_error is True
    assert result.content[0].text.startswith(
        "Error executing tool get_net_worth: 1 validation error"
    )


@pytest.mark.parametrize("tool", ["list_accounts", "get_balances", "get_net_worth"])
def test_a_database_that_is_not_migrated(tmp_settings: Settings, tool: str) -> None:
    result = call(build_server(), tool)
    assert result.is_error is True
    assert [item.text for item in result.content] == [
        f"Error executing tool {tool}: The database is not up to date. Run: fin db upgrade"
    ]


def test_the_tools_read_through_a_session_that_cannot_write(money: Settings) -> None:
    with pytest.raises(OperationalError, match="readonly database"):
        with reading() as session:
            create_account(session, "Test New", "Test Bank", "checking")
            session.flush()


def test_a_tool_that_crashes_logs_nothing(
    money: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    server = build_server()

    def crash() -> dict:
        raise RuntimeError("ACME COFFEE 1234")

    server.add_tool(crash)
    caplog.set_level(logging.DEBUG)
    result = call(server, "crash")
    assert (result.is_error, [item.text for item in result.content]) == (
        True,
        ["Error executing tool crash"],
    )
    assert [record.getMessage() for record in caplog.records if record.name.startswith("mcp")] == []
    assert "ACME" not in caplog.text
```

`tests/e2e/test_cli_mcp.py`

```python
import pytest

from finances.config import Settings
from tests.support import run


def test_serve_runs_on_stdio_and_prints_nothing(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = []
    monkeypatch.setattr(
        "mcp.server.mcpserver.MCPServer.run",
        lambda self, transport="stdio", **options: started.append((self.name, transport, options)),
    )
    result = run("mcp", "serve")
    assert (result.exit_code, result.stdout, result.stderr) == (0, "", "")
    assert started == [("finances", "stdio", {})]


def test_serve_takes_no_options(tmp_settings: Settings) -> None:
    result = run("mcp", "serve", "--port", "8000")
    assert result.exit_code == 2
    assert "--port" in result.stderr
```

## Tests to write

`tests/integration/test_mcp_more.py`: `get_engine(read_only=True)` still enforces foreign keys; `reading()` disposes of the engine when its block raises; `list_accounts` and `get_balances` with no accounts; `get_net_worth` with no arguments gives 12 months; each tool's description is the table's text; `fin mcp --help` lists `serve`.

## Rules for this phase

- `mcp_server` is thin: no sums, sorting, or filtering in it; it calls `balance_report`, `net_worth_over_time`, and the three read repository functions, and turns their results into dicts.
- `mcp_server` imports nothing from `views`, `web`, or `cli`; `cli/mcp.py` imports only `mcp_server.server`.
- No logging calls and no `print` in `mcp_server` or `cli/mcp.py`.
- No network: the SDK's stdio transport only. Tests use the in-memory client and never start a subprocess or open a socket.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- `.venv/bin/python -m pip check`: `No broken requirements found.`;
- the given test files: `tests/integration/test_mcp_accounts.py tests/e2e/test_cli_mcp.py`, 13 tests;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.mcp_server --cov=finances.cli.mcp --cov=finances.db.engine --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(views|web|cli)" -- src/finances/mcp_server` (no output), `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py` (no output), and `git grep -n --untracked -E "\.run\(|\"sse\"|streamable" -- src/finances/mcp_server` (one line: `serve`'s `run("stdio")` in `server.py`).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 14a: the MCP server and the account tools (YYYY-MM-DD)`, with the installed `mcp` version.
