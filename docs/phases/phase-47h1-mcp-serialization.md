# Phase 47h1: extract MCP serialization

## Goal and decisions

Extract shared MCP serializers while preserving the supported tools facade and
all tool behavior. **Owner decision (2026-11-16):** split 47h into four phases:
47h1 serialization, 47h2 proposal/advice tools, 47h3 reporting tools, 47h4
accounts/queues and final size checks. Each stage needs its own committed PASS.

Architect decisions: move five cohesive helpers (about 130 existing body lines),
keep every registered tool function in tools.py for this stage, and use a validated
whole-inventory probe plus sixteen given cases. New serialization module <=400
lines now; tools.py temporarily retains a staged exception until 47h4. No new
public MCP tool or schema. No further owner decision remains.

## Read first

AGENTS.md, docs/architecture.md, docs/testing.md, docs/phase-conventions.md,
docs/progress.md, docs/audit-remediation-design.md (47h staging),
src/finances/mcp_server/{tools,server,access}.py, tests/support.py MCP inventories,
tests/integration/test_mcp_proposals.py and all proposal-kind MCP tests.

## Starting state

47g is approved at `d09bcde8b6997689cf6deeb4781504a4ed6312d0`; N=**4639**
from progress and independent review. **Sections: mcp.** Migration remains
0026_proposal_findings.py. tools.py has 861 lines and 31 registered tool functions.
server.py has 280 lines, access.py 36. The read-only module docstring in tools.py
is stale: it also contains proposal/advice writers.

The five source helpers are _transaction_item, _brief, _named, _iso and
_proposal_item. Their uses include transaction search, uncategorized/transfer
queues, coverage dates, every proposal writer/listing, and advice timestamps.
_named performs an existing repository lookup; proposal serialization performs
waits_for and proposal_out_of_date reads. These are adapter reads, not permission
to write. No existing test imports or patches these five private helpers.
Repository-import inventory scans the whole MCP package, so moving imports does
not change its allowed-name set. Public tool patch points remain in tools.py.

Sixteen given cases collected in a fresh predecessor clone: fifteen fail for the
missing serialization module, one inventory guard passes. Lint/format pass.
Twelve complete proposal outputs were captured from the existing serializer on
synthetic domain proposals, then fixed as literal expected dictionaries. The
schema/signature probe was run twice on the predecessor with identical results;
its planted description change proves sensitivity. MCP 2.3.0, pydantic 2.14.1.
No reference implementation or full-suite planning run; no real data/access.

### Isolation

Preserve unrelated .vscode/settings.json. Owner commits this finalized spec/guide
before coding. Use a fresh isolated clone of that planning commit, linked existing
venv (locally exclude symlink), explicit clone/src PYTHONPATH on every Python
command. Record full baseline and finances.__file__ provenance; finalized docs
match HEAD and starting tree is clean. Follow
.agents/skills/phase-architect/references/handoffs.md. No stashing/unrelated commits.

## Scope

| Path | Change |
|---|---|
| src/finances/mcp_server/serialization.py | new: five moved helpers |
| src/finances/mcp_server/tools.py | use module-qualified serializers, prune unused imports, correct docstring |
| tests/unit/test_mcp_serialization.py | new: given sixteen cases |
| tests/unit/test_mcp_serialization_behavior.py | new: coder edge/wiring/structure tests |
| docs/progress.md | append phase entry |

Both new tests match the existing mcp section pattern. No earlier-test diff,
fixture/schema/migration/config/dependency change. server.py/access.py unchanged.

## Out of scope

Moving tool implementations, a pure-import tools facade, area modules, changing
registration/descriptions, broader serializer redesign, transfer sorting, spending
conversion, repository/ORM splits and all later stages. No compatibility aliases
for the five moved private helpers. Do not move _month_start or _as_tool yet.

## Dependencies

None new. Keep existing package versions for the captured schema contract.

## Requirements

- **R1.** New serialization.py exposes renamed equivalents:
  `transaction_item(item: FoundTransaction, names: dict[int,str]) -> dict[str,Any]`,
  `brief(item: Transaction, names: dict[int,str]) -> dict[str,Any]`,
  `named(session: Any, transaction_id: int, names: dict[int,str]) -> dict[str,Any]`,
  `iso(day: date | None) -> str | None`, and
  `proposal_item(session: Session, proposal: Proposal) -> dict[str,Any]`.
  Preserve existing bodies except internal helper names. datetime remains accepted
  by iso as a date subclass, preserving full timestamp output.
- **R2.** Preserve every JSON key/value/type, null/default/boolean rule, field order,
  date/timestamp format and integer cent conversion. All twelve proposal kinds
  retain complete JSON; dependency and staleness reads occur once with original
  session/proposal. Preserve unknown-kind rendering behavior; this is no new
  dispatch validator. Keep transaction refund, uncategorized/unassigned conversion,
  card and pending fields identical. brief/named do not acquire new merchant logic.
- **R3.** tools.py imports the serialization module and replaces all uses of the
  five removed helpers with module-qualified calls. Delete their definitions and
  unused imports, with no old private-name aliases/wrappers. Tool functions stay
  defined in tools.py with unchanged names/signatures/annotations/defaults and
  bodies except serializer call references. Serializer may import analysis/domain/
  repository dependencies but never tools or server. No new session/clock/config
  access, write, network call or change in exception propagation.
- **R4.** Keep public inventory and all generated input/output schemas, descriptions,
  annotations, order-independent registration and signatures unchanged. access.py
  and server.py remain byte-identical. All read-only and proposal/advice permission
  tests still pass. Correct tools.py docstring to describe read tools and permitted
  proposal/advice writers, without claiming ledger-write capabilities.
- **R5.** New serialization.py is <=400 lines; tools.py <=861 for this interim
  stage. No arbitrary helper relocation. Coder tests enforce those limits and no
  facade import from serialization. Global MCP <=400/final facade gate belongs
  to 47h4, and this exception expires there. Existing files/previous tests unchanged.

## Given tests

Sixteen cases; copy unchanged to tests/unit/test_mcp_serialization.py. Expected
proposal JSON is literal predecessor output; test runtime never computes its
oracle from either implementation. Inputs are synthetic proposals, not live data.

```python
from datetime import UTC, date, datetime
from importlib import import_module
from unittest.mock import Mock

import pytest

from finances.domain.proposals import KINDS, Proposal


def proposal(kind):
    return Proposal(
        id=11,
        kind=kind,
        target_id=7,
        other_id=8,
        value="handled" if kind == "finding_status" else "Synthetic value",
        reason="Synthetic reason",
        status="open",
        created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        decided_at=None,
        pattern="ACME",
        match="contains",
        priority=5,
        source="ACME SOURCE",
        group="Synthetic group",
        transfer=True,
        income=False,
        sensitive=True,
        tax=True,
        before="Synthetic before",
        finding_type="fee",
        finding_subject="Synthetic subject",
        finding_month=date(2026, 1, 1),
    )


CASES = [
    (
        "category",
        {
            "id": 11,
            "kind": "category",
            "transaction_id": 7,
            "in_id": 8,
            "category": "Synthetic value",
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "transfer",
        {
            "id": 11,
            "kind": "transfer",
            "transaction_id": 7,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "not_transfer",
        {
            "id": 11,
            "kind": "not_transfer",
            "transaction_id": 7,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "rule",
        {
            "id": 11,
            "kind": "rule",
            "transaction_id": 7,
            "in_id": 8,
            "category": "Synthetic value",
            "rule": {"match": "contains", "pattern": "ACME", "priority": 5},
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "alias",
        {
            "id": 11,
            "kind": "alias",
            "transaction_id": 7,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": {"source": "ACME SOURCE", "target": "Synthetic value"},
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "group",
        {
            "id": 11,
            "kind": "group",
            "transaction_id": 7,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": {
                "name": "Synthetic value",
                "group": None,
                "kind": "transfer",
                "sensitive": True,
                "tax": None,
            },
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "new_category",
        {
            "id": 11,
            "kind": "new_category",
            "transaction_id": 7,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": {
                "name": "Synthetic value",
                "group": "Synthetic group",
                "kind": None,
                "sensitive": None,
                "tax": True,
            },
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "rule_edit",
        {
            "id": 11,
            "kind": "rule_edit",
            "transaction_id": None,
            "in_id": 8,
            "category": "Synthetic value",
            "rule": {"match": "contains", "pattern": "ACME", "priority": 5},
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": {"rule_id": 7, "before": "Synthetic before", "delete": False},
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "rule_delete",
        {
            "id": 11,
            "kind": "rule_delete",
            "transaction_id": None,
            "in_id": 8,
            "category": "Synthetic value",
            "rule": {"match": "contains", "pattern": "ACME", "priority": 5},
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": {"rule_id": 7, "before": "Synthetic before", "delete": True},
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "category_rename",
        {
            "id": 11,
            "kind": "category_rename",
            "transaction_id": None,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": {
                "name": "Synthetic before",
                "rename_to": "Synthetic value",
                "delete": False,
                "move_to": None,
            },
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "category_delete",
        {
            "id": 11,
            "kind": "category_delete",
            "transaction_id": None,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": {
                "name": "Synthetic before",
                "rename_to": None,
                "delete": True,
                "move_to": "Synthetic value",
            },
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "finding_status",
        {
            "id": 11,
            "kind": "finding_status",
            "transaction_id": None,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": {
                "type": "fee",
                "about": "Synthetic subject",
                "month": "2026-01",
                "status": "handled",
            },
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
]


@pytest.mark.parametrize(("kind", "expected"), CASES, ids=[case[0] for case in CASES])
def test_proposal_json_is_preserved(monkeypatch, kind, expected):
    module = import_module("finances.mcp_server.serialization")
    session = Mock()
    item = proposal(kind)
    waiting = Mock(return_value=None)
    stale = Mock(return_value=False)
    monkeypatch.setattr(module, "waits_for", waiting)
    monkeypatch.setattr(module, "proposal_out_of_date", stale)
    assert module.proposal_item(session, item) == expected
    waiting.assert_called_once_with(session, item)
    stale.assert_called_once_with(session, item)
    assert session.mock_calls == []


def test_all_kinds_are_represented():
    assert tuple(kind for kind, _ in CASES) == KINDS


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (date(2026, 1, 2), "2026-01-02"),
        (datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC), "2026-01-02T03:04:05+00:00"),
    ],
    ids=["none", "date", "timestamp"],
)
def test_iso_preserves_value(value, expected):
    module = import_module("finances.mcp_server.serialization")
    assert module.iso(value) == expected
```

## Tests to write

`tests/unit/test_mcp_serialization_behavior.py` (mcp):

- R1/R2: complete literal transaction_item rows for categorized versus uncategorized,
  assigned versus unassigned, refund and purchase, pending/card-null variants,
  with transaction date different from posted day and integer cents. Use actual
  FoundTransaction/Flow/Transaction patterns from existing search tests. Assert
  full dictionaries, not just field subsets. Pin brief's complete row; named calls
  get_transaction once with original session/id, uses names map, returns brief;
  absent lookup preserves its existing AssertionError.
- R2: iso None/date/aware timestamp plus microseconds. Proposal variants exercise
  nonempty/empty dependency and staleness booleans, accepted/declined timestamps,
  group income/transfer/spending flag words, optional finding month/about fallback,
  category-delete with/without move_to, optional/null fields and rule edit/delete.
  Literal expected values and exact helper call arguments/counts. Cover every
  branch in the new module with behavior assertions, including errors propagating
  from the original read seams without writes/commit/rollback.
- R3: patch serialization.proposal_item and invoke each of the ten proposal writers
  and list_proposals with isolated existing session/repository seams. Assert the
  very same session/proposal is forwarded and returned marker goes into the same
  envelope. Successful transaction/queue/coverage/advice tests assert use of moved
  helper results; existing end-to-end tests remain the behavioral baseline.
- R3/R4/R5: AST source checks: five former definitions/aliases absent in tools,
  no serialization import of tools/server, line limits as above; no registered tool
  function moved. Compare tool function ASTs to the planning baseline modulo only
  serializer-name substitutions; other tool behavior is unchanged. Retain existing
  repository-import inventory and capability tests without broadening them.

## Rules

No application LLM/network calls, real samples/data/Keychain; synthetic tests only.
Integer cents, stdio MCP, read-only analysis and permitted proposal/advice writes
retain their existing boundaries. No critical module changes.

## Acceptance

Sequentially in isolated checkout, preserving actual output/exit codes:

1. `.venv/bin/python scripts/check.py --first mcp --workers 4`: final
   All checks passed.; at least **4655** full-suite passes (4639+16 plus coder
   cases), every section zero failures/skips, no xfails or warnings summary.
   Serial override needs a recorded resource reason; one coverage run per checkout.
2. Immediately `.venv/bin/python -m coverage report --include="*/finances/mcp_server/serialization.py" --fail-under=100`:
   module/TOTAL 100%, no missing lines/branches; overall/critical gates unchanged.
3. `.venv/bin/python -m pytest tests/unit/test_mcp_serialization.py --no-cov`:
   exactly sixteen passed.
4. Save/run the guide's inventory probe outside repo with project interpreter:
   all check lines end ok and final FAILURES 0, exit 0. The same probe is required
   for coder and independently for verifier. No automatic snapshot regeneration
   on mismatch: classify environment versus contract difference and report it.
5. Status/diff only five Scope paths plus authorized review; given byte equality,
   all earlier tests and server/access unchanged. No new search gate.

## Report

Follow phase-conventions.md, headed Phase 47h1: extract MCP serialization. Record
sixteen given/actual total, all five helper names, baseline/import provenance,
public schema digest, branch coverage and the temporary tools.py size exception.
No commit, push or 47h2 implementation.
