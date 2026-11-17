# Verify Phase 47h3: extract MCP reporting tools

Spec: `docs/phases/phase-47h3-mcp-report-tools.md`. Follow AGENTS.md and
phase-conventions. Write only `docs/reviews/phase-47h3-mcp-report-tools.md`.

## Baseline

47h2 PASS at 713c911, 4725 tests, zero findings. Confirm finalized planning docs
are committed/unchanged and expected implementation exists before judging it.
Missing implementation is a baseline blocker. Record full planning SHA and
inspect status/diff before writing report. Use fresh isolated clone, linked
existing venv and clone/src PYTHONPATH; verify import provenance. Preserve editor
settings and compare reviewed delivery bytes before transporting verdict.

## 1. Gates

Run spec's five acceptance steps exactly, sequentially: first
`.venv/bin/python scripts/check.py --first mcp --workers 4` (>=4737 plus coder
cases), then immediate reports coverage 100%, given-only twelve passes, inventory
probe and scope/AST/size checks. Record section table, final ten lines, exit codes.
Resolve environment/localhost permission failures through execution permission,
not weakening tests. Prior coder receipts do not replace fresh verification.

## 2. Scope and requirements

Seven spec paths plus review; given file and two-file patch match supplied
content. All other source/tests unchanged. No relocation of accounts/net-worth,
transactions, coverage or queues. Check unchanged server/access/helpers/proposals/
serialization bytes, all old hashes and remaining eleven read function bodies.

| Id | Evidence |
|---|---|
| R1 | seven test_facade_identity cases, By/helper identity coder tests, unchanged AST hashes and explicit re-exports |
| R2 | test_spending_json, four test_recurring_json cases, coder full literal report dictionaries and null/active cases |
| R3 | exact call/error/cause/clock/context tests for each deciding input in spec |
| R4 | probe and existing public MCP integration, capability/repository inventories, unchanged source comparisons |
| R5 | exact earlier patch, scope and dependency review, reports <=400, tools <=512 |

Map every Tests to write item to a meaningful test. Full integration remains
required beyond mocks. Coverage obtained through no-assertion tests or unapproved
exemptions is a finding. No final global cap required before 47h4.

## 3. Independent probe

Save outside repo, run `.venv/bin/python <saved-path>` with reviewed clone import
path, delete after use. Lists registered tools in memory, no actual tool/DB/
Keychain/network calls. Expected both ok lines and FAILURES 0; validated on
predecessor before publication. Digest covers whole metadata/schemas and facade
signatures, not implementation locations. The planted-description self-check
must pass. Investigate SDK versus contract differences; do not update golden.

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

## 4. Spot checks in scratch copies only

Full given ids start `tests/unit/test_mcp_report_tools.py::`. Each input reaches
mocked analysis directly, so no database or validation can mask the mutation.

| Function mutation | Deciding test/input | Correct | Broken |
|---|---|---|---|
| get_spending: omit refund add-back in summary spent_cents | test_spending_json, net -200/refunds 900 | 700 | -200 |
| get_recurring: always use sign=1 | test_recurring_json[all-charges], inactive included | amount -300 | 300 |
| get_recurring: always keep inactive | test_recurring_json[active-income] | [] | one row |
| facade: wrap get_spending | test_facade_identity[get_spending] | identical object | different object |

Trace through exact body and literal assertion. Do not mutate reviewed code.
Unexpected failure modes require investigation, not an automatic finding.

## 5. Variations, progress and verdict

Import ordering and noncontract aliases may vary if ASTs, explicit exports and
fixed helper alias hold. No wrappers, reverse imports or new helper extraction.
Unchanged public behavior is required; fixups to financial totals are outside
this move phase. Verify standard progress entry and honest deviations.
Use standard report header/findings, fresh gates and requirement mapping.
Distinguish baseline/environment/spec errors from implementation defects.
FAIL handoff states requirement, observation and required result; no repair,
commit, push or later-stage work by verifier.
