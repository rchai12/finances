# Phase 47c: explicit proposal-kind refusal

## Goal

Refuse unsupported proposal kinds without changing ledger or proposal state.
The accepted audit-remediation design, section 47c, fixes product behavior;
no additional owner decision is needed. Architect decisions (2026-11-16): one
small repository repair, four given refusal cases, and a coder-owned complete
supported-kind matrix. No new public API.

## Read first

AGENTS.md, docs/architecture.md, docs/phase-conventions.md, docs/testing.md,
docs/progress.md, docs/audit-remediation-design.md (47c),
src/finances/domain/proposals.py, src/finances/db/repositories/proposals.py,
src/finances/db/repositories/chains.py and existing proposal tests.

## Starting state and checked facts

Predecessor 47b is approved and committed: implementation 2d476ac, review
3edb1821d90fd09404432e795f116183c2618ece. N = 4371 from progress and review.
**Sections: core,mcp,web,cli.** Migration remains 0026_proposal_findings.py.

The repository module is below the 400-line cap. `accept_proposal(session,
proposal_id)` loads with `_open_row`, checks dependencies, checks staleness,
dispatches, then marks accepted, stamps, flushes and records an audit event.
Its final else currently assigns a category. `proposal_out_of_date(session,
proposal)` currently sends every non-category fallback to pair staleness.
`KINDS` contains twelve kinds; tests/unit/test_proposal_rules.py pins its order.
The database constraint cannot substitute for a dispatch refusal.

Given tests were formatted/linted and collected in a fresh isolated clone of
3edb182. Four cases failed because no ValueError was raised; import provenance
resolved to the clone. No reference implementation was built.

The original workspace has unrelated untracked .vscode/settings.json. Preserve
it. After the owner commits these planning docs, implement in a fresh isolated
clone of that committed baseline, linking the existing venv and setting
PYTHONPATH to its src. Record full baseline/import provenance. The spec and guide
must match their committed versions before coding; follow the isolation procedure
in .agents/skills/phase-architect/references/handoffs.md.

## Scope

| Path | What changes |
|---|---|
| src/finances/db/repositories/proposals.py | guards and exhaustive dispatch |
| tests/unit/test_proposal_dispatch.py | new: given four cases |
| tests/unit/test_proposal_dispatch_matrix.py | new: coder dispatch matrix |
| tests/integration/test_proposal_dispatch_safety.py | new: coder persistence cases |
| docs/progress.md | append phase entry |

All new test files fall in core through the existing section fallback.

## Out of scope

Reason/UTC helper consolidation (47d), new kinds, inventory changes, schema or
migration changes, dispatch frameworks, new MCP permissions, dependency changes,
changes to pairing rules, and unrelated refactors. Existing tests stay unchanged.
Boundary adapters already translate ValueError; no adapter changes are authorized.
If inspection or tests reveal a required adapter repair, return that concrete
blocker to the architect before changing its scope.

## Dependencies

None new. Use the existing venv, including the approved 47b worker dependency.

## Requirements

- **R1.** Preserve both public signatures and return types. At entry to staleness,
  refuse kinds outside domain.proposals.KINDS with exactly
  `ValueError("unsupported proposal kind")`. Acceptance first retains existing
  missing/non-open `_open_row` checks, then refuses an unknown kind before
  `waits_for`, staleness dispatch or any mutation. Never echo stored kind/value.
- **R2.** Acceptance has an explicit CATEGORY branch. Staleness has explicit
  CATEGORY, TRANSFER and NOT_TRANSFER cases (the two transfer kinds may share a
  branch). No catch-all routes a kind to category or pair behavior. Every
  remaining dispatch fallback raises the R1 error, including an inventory member
  added before a handler exists. Dependency and staleness checks for supported
  kinds keep their current order. A registered-but-unhandled kind must refuse
  before writes; it need not skip dependency reads.
- **R3.** Both refusal paths leave status, decided_at, assignments, pairs,
  rejections and audit records unchanged; no flush, commit or rollback is added.
  The caller retains transaction ownership. Refusal cannot rely on a schema
  rejection: test synthetic loaded rows and domain proposals at the dispatch seam.
- **R4.** Every current kind retains its intended acceptance handler and staleness
  handler/result, validation order, refusal text, dependency behavior and return
  shape. Matrix keys equal the full current KINDS inventory, rather than covering
  only category and transfers. Existing proposal_text and KINDS pins are unchanged.
- **R5.** Real supported category, transfer and not-transfer proposals still
  persist the intended decisions/audits. Missing/non-open acceptance refuses
  as before; an open dependent proposal still waits before staleness or mutation.
  Existing CLI/web/MCP behavior and the full previous suite remain intact.

## Given tests

Four collected cases; copy unchanged to tests/unit/test_proposal_dispatch.py.
The deliberately fake row bypasses the schema and conversion only. Acceptance
staleness is stubbed false to test its own fallback independently. Patching both
inventory bindings supports an imported constant or module-qualified lookup.
Private helper extraction is allowed provided this existing public seam remains
patchable and these tests still pass.

```python
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from finances.db.repositories import proposals as repo
from finances.domain import proposals as domain


@pytest.mark.parametrize("registered", [False, True], ids=["unknown", "future"])
@pytest.mark.parametrize("operation", ["accept", "stale"])
def test_unsupported_kind_refuses_without_mutation(monkeypatch, registered, operation):
    kind = "future_kind_PRIVATE_SENTINEL"
    row = SimpleNamespace(
        id=17,
        kind=kind,
        target_id=23,
        other_id=24,
        value="Synthetic category",
        reason="Synthetic reason",
        status=domain.OPEN,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        decided_at=None,
    )
    if registered:
        kinds = (*domain.KINDS, kind)
        monkeypatch.setattr(domain, "KINDS", kinds)
        monkeypatch.setattr(repo, "KINDS", kinds, raising=False)
    session = Mock()
    monkeypatch.setattr(repo, "_open_row", lambda session, number: row)
    monkeypatch.setattr(repo, "to_proposal", lambda item: item)
    waiting = Mock(return_value=None)
    monkeypatch.setattr(repo, "waits_for", waiting)
    category_check = Mock(return_value=False)
    pair_check = Mock(return_value=False)
    monkeypatch.setattr(repo, "category_is_out_of_date", category_check)
    monkeypatch.setattr(repo, "pair_is_out_of_date", pair_check)
    writers = []
    for name in (
        "set_category_by_hand",
        "create_transfer_pair",
        "reject_transfer",
        "record_change",
    ):
        writer = Mock()
        monkeypatch.setattr(repo, name, writer)
        writers.append(writer)
    if operation == "accept":
        # Reach acceptance dispatch for a future inventory member even if staleness
        # dispatch has already been repaired. Unknown kinds still require an early guard.
        monkeypatch.setattr(repo, "proposal_out_of_date", Mock(return_value=False))
    with pytest.raises(ValueError, match="^unsupported proposal kind$"):
        if operation == "accept":
            repo.accept_proposal(session, 17)
        else:
            repo.proposal_out_of_date(session, row)
    assert row.status == domain.OPEN
    assert row.decided_at is None
    for writer in writers:
        writer.assert_not_called()
    session.assert_not_called()
    assert session.mock_calls == []
    category_check.assert_not_called()
    pair_check.assert_not_called()
    if not registered:
        waiting.assert_not_called()
```

## Tests to write

`tests/unit/test_proposal_dispatch_matrix.py` (core):

- R4: complete twelve-kind acceptance matrix with otherwise valid synthetic rows,
  waits_for=None and staleness=False. Assert exactly the intended writer and its
  arguments, no other writer, accepted status/stamp, audit event and returned
  proposal. Patch lazy-import handlers at their defining modules. Expected paths:
  CATEGORY=set_category_by_hand; TRANSFER=create_transfer_pair with CONFIRMED;
  NOT_TRANSFER=reject_transfer; RULE=create_rule; ALIAS=add_alias;
  GROUP/NEW_CATEGORY=accept_new; CATEGORY_RENAME/CATEGORY_DELETE=accept_category_change;
  RULE_EDIT/RULE_DELETE=accept_rule_change; FINDING_STATUS=accept_finding_status.
- R4: full twelve-kind staleness matrix. Delegate GROUP/NEW_CATEGORY to
  new_is_out_of_date, category changes to category_change_is_out_of_date, finding
  status to finding_status_is_out_of_date, rule changes to rule_change_is_out_of_date,
  CATEGORY to category_is_out_of_date, and transfer kinds to pair_is_out_of_date.
  Exercise true and false delegate results. RULE must cover existing rule, missing
  or group-only category, and valid leaf/dependency results. ALIAS covers valid
  mapping and check_alias ValueError. Assert no unintended delegate or write.
- R1/R3: a genuine synthetic domain Proposal with an unknown kind refuses
  staleness without querying; unknown acceptance with waits_for returning an id
  still gets the constant unsupported error, never a dependency refusal.

`tests/integration/test_proposal_dispatch_safety.py` (core):

- R3: create valid synthetic category/transactions in migrated db_engine. Substitute
  an unknown loaded proposal row only at _open_row, retaining real downstream
  repository writers and real session. Catch refusal inside the transaction and
  compare persisted assignments, pairs, rejections, audits and proposal status
  before/after in a fresh session. This rules out rollback hiding mutations.
- R5: actual category, transfer and not-transfer proposals accepted through public
  repository APIs; assert persisted manual category, confirmed pair or rejection,
  accepted result/status and proposal_accepted audit respectively.
- R5: missing and already-decided ids preserve exact existing refusals; valid open
  dependent proposal reports its parent before staleness/mutation. Assert state
  remains unchanged. Reuse existing synthetic fixture patterns, never real data.

## Rules for this phase

No migration or earlier-test diff. Integer cents and synthetic data only.
No network, real samples, Keychain or aggregator access. No critical module is
modified. Preserve privacy, session ownership, repository layering and text limits.

## Acceptance

Run from the isolated checkout sequentially, preserving output and exit codes:

1. `.venv/bin/python scripts/check.py --first core,mcp,web,cli --workers 4`
   must end `All checks passed.`, at least 4375 full-suite passes (N+4 plus coder
   cases), every section zero failures/skips, no xfails or warnings summary.
   Four local workers follow the accepted machine recommendation; serial remains
   permitted if resource contention is recorded. One coverage run per checkout.
2. Immediately `.venv/bin/python -m coverage report --include="*/finances/db/repositories/proposals.py"`.
   Exit 0; record line/branch totals and missing locations. No new artificial 100%
   target for this noncritical module: full configured coverage and all critical
   gates remain mandatory. Explain uncovered new guard/fallback branches; tests
   must cover every new refusal and every existing dispatch kind.
3. `.venv/bin/python -m pytest tests/unit/test_proposal_dispatch.py --no-cov`:
   exactly 4 passed.
4. `git status --short --untracked-files=all` and `git diff HEAD`: only Scope paths
   (verifier additionally writes its authorized report). Existing tests unchanged;
   compare the new given file byte-for-byte with this block. No search gate or
   migration/probe is specified.

## Report

Follow phase-conventions.md, headed Phase 47c: explicit proposal-kind refusal.
Record actual test count, full baseline, requirement-to-test mapping and any
isolation/environment issues. Do not commit or push.
