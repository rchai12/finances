# Verify Phase 47h4: finalize the MCP tool facade

Spec: docs/phases/phase-47h4-mcp-facade.md. Follow AGENTS.md and phase-conventions;
write only docs/reviews/phase-47h4-mcp-facade.md.

## Baseline

Before implementation review confirm committed 47h3 delivery, successful progress
4761 and unchanged PASS review; a review-only commit without reports.py is not
an implementation baseline. Confirm finalized planning spec/guide are committed
and unchanged, implementation exists, record both SHAs. Use fresh isolated clone,
linked venv, explicit clone/src PYTHONPATH and verified imports. Inspect diff/status
before report. Preserve editor settings; compare reviewed delivery bytes before
transporting verdict. Do not include predecessor delivery in 47h4's scope diff.

## 1. Gates

Run all five spec acceptance steps fresh and sequentially: first check.py --first
mcp --workers 4 (>=4775 plus coder cases), immediate two-module coverage100,
given-only14, probe, scope/AST/layering. All eight sections clean, critical gate,
no skips/xfails/warnings summary, final All checks passed. Record section table,
last ten lines and exits. Resolve existing localhost fixture permission failures
as environment issues, never weaken tests or reuse coder results as verification.

## 2. Scope and checklist

Nine implementation paths plus report. Given patch affects exactly three earlier
tests, preserving every assertion/hash. Old 47f given file migration is explicit;
no additional private facade shim. Inspect all source including new untracked
files. Accounts/queues bodies unchanged; reports/proposals/helpers/serialization/
server/access bytes unchanged. Facade is docstring/imports only, identities hold.

| Requirement | Evidence |
|---|---|
| R1 | eleven test_facade_identity cases, facade-only test, unchanged old AST hashes across all modules |
| R2 | given transfer order/limit literal plus coder full JSON, paging/filter/null/clock cases |
| R3 | exact args/query/session/context/error assertions, retained public read-only integration |
| R4 | probe below and unchanged capability/repository/public integration inventories |
| R5 | global recursive size test, temporary copied 400/401 boundary, scope/given audit and source dependencies |

Map every Tests to write item to a test; missing deciding assertion is a finding.
No facade exception or monolith exception remains; include newly created/future
MCP source files in cap. A pytest gate included in normal full check is sufficient;
no scripts/check.py change is required. No no-op tests or coverage exclusions.

## 3. Independent metadata probe

Save outside repository, run .venv/bin/python <saved-path> with reviewed PYTHONPATH,
delete afterwards. Whole generated metadata/signatures for31 tools, same validated
probe as47h3; no actual tool/DB/Keychain/network calls. Both ok lines then FAILURES0.
Planted description self-check must work. Investigate dependency versus contract
mismatches, never regenerate golden to match incorrect metadata.

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

## 4. Scratch-only spot checks

Ids prefix tests/unit/test_mcp_facade_contract.py::. Never mutate reviewed source.

| Mutation | Deciding case/input | Correct | Broken |
|---|---|---|---|
| list_transfers: remove reverse=True | test_transfer_order_and_limit, loader ids1,3,2 limit2 |3,2|1,2|
| list_transfers: total after slicing | same, total three |3|2|
| facade: wrap get_balances | test_facade_identity[accounts-get_balances] |same object|different|
| add one 401-line .py source | test_all_mcp_sources_fit |no oversize files|listed failure|

No DB or later validation masks these direct synthetic calls. Investigate any
unexpected failure mechanism. Facade-only assertions prevent hidden dynamic
reexports; scope review prevents arbitrary unrelated helper relocation.

## 5. Variations and verdict

Import order/formatting may vary; exact function ASTs, ownership, facade identity
and given tests remain fixed. No source cap exemptions, semantic bug repairs,
new dependencies or later phase cleanup. Check standard progress and honest
deviations, final removal of interim exception. Standard review header/findings;
distinguish baseline/spec/environment/implementation failure. FAIL handoff states
requirement, observation, required result. Do not repair code, commit or push.
