# Verify Phase 47h1: extract MCP serialization

Spec: docs/phases/phase-47h1-mcp-serialization.md. Read AGENTS.md and
phase-conventions. Independently verify; write only
`docs/reviews/phase-47h1-mcp-serialization.md`.

## Baseline

Confirm 47g PASS at 4639, committed d09bcde. Finalized planning docs match committed
HEAD; expected implementation/progress exists. Missing implementation is a baseline
blocker. Inspect status/diff before report, use isolated clone and verify source
import provenance. Preserve original editor settings; compare reviewed bytes with
delivery before transporting verdict. Owner authorized four stages; this is only
serialization. No tooling or dependency installation is needed.

## 1. Gates

Run all five spec acceptance steps exactly, first
`.venv/bin/python scripts/check.py --first mcp --workers 4`.
Require >=4655 full-suite passes plus coder cases, clean section table, critical
gates and All checks passed. Immediately require serializer 100% line/branch;
then sixteen given passes, independent probe and scope/given equality. Record
resource override if serial. Resolve known localhost sandbox restrictions through
execution permission; preserve real outcomes and never weaken tests.

## 2. Scope

Only five Scope paths plus report. Given bytes identical, previous tests unchanged,
server/access bytes unchanged. Existing tool functions stay in tools.py. Source
ASTs differ only by new module imports, removed five helpers, their internal call
names, serializer references and docstring. No stale private aliases. No serializer
import of facade/registration. No change in transfer/spending selection/order.
New module <=400 and interim tools <=861; final global cap waits for 47h4.

## 3. Requirement checklist

| Id | Deciding observation |
|---|---|
| R1 | Five exact helper contracts; existing bodies moved with internal names only. named's lookup/absence behavior and all literal row tests pass. |
| R2 | Twelve whole proposal dictionaries, inventory equality, three iso cases plus coder branch variants; complete transaction rows and original read/count/error behavior. |
| R3 | No former private definitions/aliases, module-qualified call wiring; writer/list/queue/coverage/advice marker tests use returned data and same session. Tool AST comparison permits only named substitutions. |
| R4 | Probe confirms whole public metadata/signatures, existing capability/import inventory passes, access/server unchanged, docstring accurately covers writers. |
| R5 | Coder AST/line-cap tests and explicit interim exception, no unrelated relocation or old-test changes. |

Name the coder test for every Tests to write item. Lines merely executed are not
coverage evidence. Stubbed serializer tests alone cannot replace the existing
public in-memory MCP suite or full JSON assertions. The twelve literal examples
were captured from predecessor and are independent of new code at test runtime.

## 4. Independent inventory probe

Save outside repository, execute `.venv/bin/python <saved-path>` from reviewed
root with clone PYTHONPATH. No DB/Keychain/network or application tool calls; only
in-memory SDK registration/listing. Delete script after use. Baseline MCP 2.3.0,
pydantic 2.14.1. The digest covers complete generated schemas/descriptions/
annotations and signatures for all 31 tools, sorted by name with canonical JSON.
A copy with planted description difference self-checks sensitivity first.
Any mismatch requires inspection, never updating EXPECTED to match broken code.

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

Expected: oracle sensitivity ok; inventory schemas signatures ok; FAILURES 0.
The baseline ran twice with identical digest; probe ran with FAILURES 0 before
publication. A registration/schema failure is separate from missing implementation.

## 5. Scratch-only spot checks

Use a disposable copy with confirmed import provenance, never reviewed code.
Each full given id starts tests/unit/test_mcp_serialization.py::.

| Mutation | Deciding test/input | Correct | Broken |
|---|---|---|---|
| proposal_item: expose target_id for RULE_EDIT | test_proposal_json_is_preserved[rule_edit], target 7 | transaction_id None | 7 |
| proposal_item: suppress alias dictionary | test_proposal_json_is_preserved[alias] | complete source/target | None |
| proposal_item: drop finding month formatting | test_proposal_json_is_preserved[finding_status] | month 2026-01 | missing/wrong month |
| iso: truncate datetime to date before isoformat | test_iso_preserves_value[timestamp] | 2026-01-02T03:04:05+00:00 | 2026-01-02 |

Trace through moved helper body, supplied inputs and literal expected dict. These
mutations change only the named value, so no unrelated validation masks them.
Report actual deciding failures and investigate a failure for another reason.

## 6. Variations and verdict

Import formatting and local aliases for non-helper dependencies are coder-owned.
Five module helper names and module-qualified tool calls are fixed for later
stages. Tools' public signatures and private month/error helpers remain in place;
no compatibility wrapper for the five moved helpers. No global cap demanded early.

Use standard report header/finding format, fresh gates/Sections/final ten lines,
probe output, whole-diff/scope/AST evidence and requirement/test mapping. Check
progress reflects 47h1 only and explicit temporary exception. Distinguish baseline,
environment, spec/test and implementation defects. FAIL handoff states requirement,
observation, required result; no code repair, commit, push or later-stage work.
