# Verify Phase 47h2: extract MCP proposal and advice tools

Spec: `docs/phases/phase-47h2-mcp-proposal-tools.md`. Follow AGENTS.md and
phase-conventions. Write only `docs/reviews/phase-47h2-mcp-proposal-tools.md`.

## Baseline and scope

47h1 PASS at 1a7056e, 4687 tests. First verify finalized planning docs are committed
and unchanged and implementation exists. Missing implementation is a baseline
blocker. Inspect status and diff before creating report. Use a fresh clone with
linked venv and explicit clone/src PYTHONPATH; record planning SHA and import
provenance. Preserve unrelated editor settings. Compare reviewed delivery bytes
before transporting a review. Scope is seven paths plus your report; earlier-test
patch is given exactly, other tests and source remain unchanged.

## 1. Gates

Execute all five spec acceptance steps exactly and sequentially: first
`.venv/bin/python scripts/check.py --first mcp --workers 4`, minimum 4704 plus
coder cases; then immediately the exact two-module coverage command (100% both
modules, zero missing/partial branches), then given-only exactly 17 passes,
probe, and whole-diff checks. Record full section table and final ten lines.
Distinguish environmental failures from source failures; obtain execution
permission for existing localhost fixtures if needed, never weaken tests.

## 2. Requirements

| Id | Evidence required |
|---|---|
| R1 | Thirteen test_facade_identity cases, original AST pin across modules, explicit imports not wrappers |
| R2 | Month_start AST unchanged except name, fixed-clock/invalid month cases and finding lookup call assertions |
| R3 | Probe below, existing public MCP integration and package repository/writer inventory, unchanged server/access/serialization and 18 read bodies |
| R4 | Given error/advice literals; coder nondefault call arguments, full lists and context exit/error checks; existing public write-boundary tests |
| R5 | Exact given diff and hashes, seven scope paths, new module <=400, tools <=716, no facade imports from areas |

Name a coder test for each Tests to write item; missing behavioral evidence is a
finding. Synthetic marker wiring alone does not replace public MCP integration.
Check no pragma/no-assertion tests were used to reach coverage.

## 3. Independent probe

Save outside repository and run `.venv/bin/python <saved-path>` with reviewed
clone import path, then delete. Same independently validated probe as 47h1; it
lists tools in memory without executing tools, DB/Keychain/network access. It
self-checks a planted description change before comparing all generated metadata
and facade signatures, not implementation locations. Baseline run: both ok lines,
FAILURES 0. Never regenerate digest to accommodate a mismatch; investigate SDK
version versus public-contract change.

```python
import hashlib
import inspect
import json

import anyio
from mcp.client import Client

from finances.mcp_server import tools
from finances.mcp_server.server import build_server


async def snapshot():
    async with Client(build_server()) as client:
        found = (await client.list_tools()).tools
    return [
        {
            "tool": item.model_dump(mode="json", by_alias=True),
            "signature": str(inspect.signature(getattr(tools, item.name))),
        }
        for item in sorted(found, key=lambda item: item.name)
    ]


EXPECTED = "b9dabd87018443723316328d4a2b4b4af5d808e4b8f080e9b5812cdef7932ad4"


def digest(data):
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


failures = 0
try:
    data = anyio.run(snapshot)
    changed = json.loads(json.dumps(data))
    changed[0]["tool"]["description"] = "planted schema difference"
    assert digest(changed) != digest(data)
    print("oracle sensitivity ok")
    names = [item["tool"]["name"] for item in data]
    assert len(names) == len(set(names)) == 31
    assert digest(data) == EXPECTED, "tool inventory/schema/signature changed"
    print("inventory schemas signatures ok")
except Exception as error:
    failures += 1
    print("inventory FAIL", type(error).__name__, str(error))
print("FAILURES", failures)
raise SystemExit(bool(failures))
```

## 4. Spot checks in disposable copies only

Full ids are `tests/unit/test_mcp_proposal_tools.py::` plus below. Trace the exact
input through the call; no database validation can mask these synthetic inputs.

| Mutation | Given test/input | Correct | Broken |
|---|---|---|---|
| _as_tool: stop translating ValueError | test_error_translation[value], synthetic refusal | ToolError | ValueError |
| _as_tool: also catch LookupError | test_error_translation[unexpected] | LookupError | ToolError |
| log_advice: replace subject with empty string | test_advice_json, Synthetic subject | full literal subject | empty |
| Facade: wrap log_advice instead of re-export | test_facade_identity[log_advice] | identical object | different object |

Read-only verification does not mutate reviewed files. An unexpected failure
mode needs investigation; do not equate any failure with a sound mutation row.

## 5. Reasonable variations and verdict

Import formatting and dependency aliases may vary if ASTs, fixed shared helper
aliases and given tests remain satisfied. Explicit facade re-export identity is
required. Temporary tools size exception remains until 47h4; global gate, report
moves and account/queue moves are out of scope. No new-module size exception.

Use standard review header/findings and progress checks. Distinguish baseline,
spec, environment and implementation failures. FAIL handoff names requirement,
observation and required result; do not repair code, commit, push or start later
phases. Confirm all gates are fresh; coder receipts are not independent evidence.
