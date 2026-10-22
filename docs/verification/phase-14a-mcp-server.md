# Verify Phase 14a: the MCP server and the account tools

Spec: `docs/phases/phase-14a-mcp-server.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added the `mcp` dependency, a read-only engine option, the `mcp_server` package (a server with three read-only tools, a read-only session that checks the schema), and `fin mcp serve`. Two test files were given; no migration.

These are correct and must not be reported: a private helper in `tools.py` that turns a dataclass into a dict; registering the tools in a loop over a table; `reading()` written with `try`/`finally` or with `contextlib.ExitStack`; newer versions of the SDK's own dependencies installed only because they were missing.

## 1. Gates

N is `3014` when Phase 27d was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 13 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pip check` | `No broken requirements found.` |
| `.venv/bin/python -m pytest tests/integration/test_mcp_accounts.py tests/e2e/test_cli_mcp.py --no-cov` | exactly `13 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.mcp_server --cov=finances.cli.mcp --cov=finances.db.engine --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(views|web|cli)" -- src/finances/mcp_server` | no output |
| `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py` | no output |
| `git grep -n --untracked -E "\.run\(|\"sse\"|streamable" -- src/finances/mcp_server` | one line, in `server.py`: `run("stdio")` |
| `git diff HEAD -- pyproject.toml` | one added line: `"mcp>=2.3,<3",` |

## 2. Scope paths

```
 M docs/progress.md
 M pyproject.toml
 M src/finances/cli/main.py
 M src/finances/db/engine.py
?? src/finances/cli/mcp.py
?? src/finances/mcp_server/
?? tests/e2e/test_cli_mcp.py
?? tests/integration/test_mcp_accounts.py
?? tests/integration/test_mcp_more.py
```

`src/finances/mcp_server/` holds exactly `__init__.py`, `access.py`, `server.py`, `tools.py`.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R9 | gates 1 to 3 | pass |
| R2, R3, R9 (edges) | the coder's `tests/integration/test_mcp_more.py` | each item of the spec's "Tests to write" has a test |
| R5 | gate `git grep -n --untracked -E "\.run\(|\"sse\"|streamable" -- src/finances/mcp_server` | one line |

## 4. Probe

One check the in-memory tests cannot make: the real command over a real pipe, against a temporary migrated database (never the owner's `data/`). Save the script below outside the repository as `probe_14a.py`, then run from the repository root, in one shell line:

```
export FIN_DATA_DIR=$(mktemp -d) && .venv/bin/fin db upgrade && .venv/bin/python <folder>/probe_14a.py
```

```python
"""Phase 14a probe: run `fin mcp serve` as a real child process and talk to it over stdio."""

import os
import sys
from pathlib import Path

import anyio
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

FIN = str(Path(".venv/bin/fin").resolve())
failures = 0


def check(name: str, ok: bool) -> None:
    global failures
    print(("ok   " if ok else "FAIL ") + name)
    failures += 0 if ok else 1


async def main() -> None:
    params = StdioServerParameters(command=FIN, args=["mcp", "serve"], env=dict(os.environ))
    async with Client(params) as client:
        names = sorted(tool.name for tool in (await client.list_tools()).tools)
        check("three tools over stdio", names == ["get_balances", "get_net_worth", "list_accounts"])
        result = await client.call_tool("get_balances", {})
        check("balances on an empty database", result.structured_content is not None
              and result.structured_content.get("accounts") == [])
        result = await client.call_tool("get_net_worth", {"months": 0})
        check("months 0 refused", result.is_error is True)


if not os.environ.get("FIN_DATA_DIR"):
    print("FAIL FIN_DATA_DIR is not set")
    sys.exit(1)
try:
    anyio.run(main)
except Exception as error:  # the probe never crashes
    check(f"stdio session ({type(error).__name__})", False)
print(f"FAILURES {failures}")
```

Expected: `FAILURES 0`.

## 5. Spot checks

Each line names the function and the given input that decides it. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `reading()` calls `get_engine()` without `read_only=True` | `test_the_tools_read_through_a_session_that_cannot_write` | `OperationalError` | no error |
| 2. `build_server()` leaves the `mcp` logger's level alone | `test_a_tool_that_crashes_logs_nothing` | no `mcp` records | `Tool 'crash' raised an unexpected exception` |
| 3. `get_net_worth` uses `date.today()` | `test_get_net_worth_follows_the_app_clock` | `as_of` 2026-05-25 | today's real date |
| 4. `list_accounts` ignores `include_inactive` | `test_list_accounts`, second call | Test Old present, `active` false | absent |
| 5. `list_accounts` sets `joint` when there is no owner row | `test_list_accounts` (Test Savings) | `joint` false | true |
| 6. `get_net_worth` clamps `months` in the body instead of the signature | `test_get_net_worth_refuses_months_out_of_range[61]` | `is_error` | 60 months of points |
| 7. `reading()` skips the schema check | `test_a_database_that_is_not_migrated` | the fixed message | a SQL error text, or none |
| 8. `fin mcp serve` prints a banner | `test_serve_runs_on_stdio_and_prints_nothing` | stdout empty | the banner |

## 6. Out of scope

Each must be absent: any tool but the three; a resource or prompt; an option on `fin mcp serve`; a transport but stdio; a write repository function called from `mcp_server`; a migration.
