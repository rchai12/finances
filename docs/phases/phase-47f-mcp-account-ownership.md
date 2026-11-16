# Phase 47f: MCP account ownership from analysis

## Goal

Make the MCP account listing serialize shared analysis data, retaining its JSON
contract and distinguishing joint ownership from a sole owner's display name.
The accepted remediation design section 47f fixes product behavior; no new owner
decision is needed. Architect decisions (2026-11-16): two small production edits,
seven given cases, one exact earlier-test pin edit, and coder compatibility tests.
No change to the critical analysis.people module is needed.

## Read first

AGENTS.md, docs/architecture.md, docs/testing.md, docs/phase-conventions.md,
docs/progress.md, docs/audit-remediation-design.md (47f),
src/finances/analysis/listings.py, src/finances/analysis/people.py,
src/finances/domain/people.py, src/finances/views/accounts.py,
src/finances/mcp_server/tools.py, src/finances/mcp_server/access.py,
tests/integration/test_mcp_accounts.py, tests/integration/test_listings_more.py,
tests/unit/test_views_take_data.py and tests/integration/test_mcp_proposals.py.

## Starting state and checked facts

47e implementation 0ee3a38 is approved at
`f6897745316c5052d4f16dd5ae8234d6d1c390fa`. N = **4564** from progress and
independent PASS review. **Sections: core,mcp,web,cli.** Newest migration remains
0026_proposal_findings.py.

AccountListing is a frozen dataclass with account and owner fields. Its owner is
view attribution, not a raw ownership id. load_attribution loses the distinction
between a joint row and a sole person's name equal to the display label "Joint".
list_account_owners returns {account_id: person_id_or_None}: missing key means
unassigned, present None means joint. list_accounts orders by lower(account.name)
and excludes inactive accounts unless requested. Existing account views use
owner or empty text. Two-argument AccountListing construction must keep working.

The MCP tool currently loads accounts, people and owners itself under reading().
Those three imports are used only there. test_mcp_proposals.py pins their imported
original names in FROM_REPOSITORIES; the exact removal diff is supplied below.
Tool inventory, signature, descriptions, permissions and JSON keys are unchanged.
Person validation reserves Joint, so collision coverage uses a synthetic loader
seam without relaxing validation or database constraints.

### Baseline and validation

Seven given cases collect in a fresh predecessor clone. Five fail because joint
is missing; two because the tool ignores the shared loader. Lint/format pass;
finances.__file__ resolved to that clone. No implementation or full suite was run
for planning. No real database, samples, Keychain or network were accessed.

Preserve unrelated .vscode/settings.json. Owner commits finalized planning docs
before coding. Implement in a fresh isolated clone of that planning commit,
link/exclude the existing venv symlink locally and set PYTHONPATH to its src for
every Python invocation. Record full planning SHA/import provenance and verify
spec/guide match HEAD with clean starting status. Follow the isolation procedure
in .agents/skills/phase-architect/references/handoffs.md.

## Scope

| Path | Change |
|---|---|
| src/finances/analysis/listings.py | extend AccountListing and load raw ownership once |
| src/finances/mcp_server/tools.py | list_accounts adapter and obsolete imports only |
| tests/unit/test_account_listing_ownership.py | new: given seven cases |
| tests/integration/test_mcp_account_listing.py | new: coder compatibility cases |
| tests/integration/test_mcp_proposals.py | exact given import inventory edit |
| docs/progress.md | append phase entry |

New unit tests fall in core; integration file matches mcp. No section-config edit.

## Out of scope

Critical analysis.people/Attribution changes, schema/migrations, person validation,
new permissions, MCP splitting, transfer ordering, spending serialization, other
tools, view/CLI/web changes, new dependencies and future remediation parts.

## Dependencies

None new.

## Requirements

- **R1.** Append `joint: bool = False` to frozen AccountListing after owner.
  Preserve account and owner semantics and two-argument construction. No new
  field is exposed in CLI/web views or the MCP response beyond its existing joint.
- **R2.** account_listing retains its signature/default. Load accounts, people
  and raw ownership through repositories once each, preserving account order and
  include_inactive forwarding. For each account: absent ownership key =>
  owner=None,joint=False; present None => owner=domain.people.JOINT,joint=True;
  person id => person's exact name,joint=False. Never infer jointness by comparing
  names. Do not call load_attribution as well as raw ownership loading; remove its
  now-unused import. people_listing is unchanged. Do not load cardholder aliases
  just to list accounts.
- **R3.** MCP list_accounts calls account_listing(session,
  include_inactive=include_inactive) exactly once inside existing reading().
  Serialize account fields unchanged and preserve listing order. Emit
  `owner=None if item.joint else item.owner` and `joint=item.joint`. No direct
  account/owner/people queries or ownership rules remain in this tool; remove
  its three obsolete imports. Preserve dict envelope {"accounts": [...]}, every
  existing key/value/type, active default, signature, description and schema.
- **R4.** Inactive inclusion, empty listing and all ownership forms retain
  behavior through public MCP calls. Display attribution for CLI/web remains
  unchanged, including Joint label and empty unassigned display. Existing read-only
  transaction/session enforcement and permission/tool inventories remain intact.
- **R5.** Apply the exact given pin diff; no other existing test changes. Preserve
  full previous suite, text/privacy and capability boundaries. No extra ownership
  loader in the MCP adapter or repeated owner/people query in analysis.

## Given diff to earlier tests

Remove only the three no-longer-imported repository names; all other inventory
assertions remain. No migration or schema pin changes.

```text
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index c96fbae..596f2f8 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -20,11 +20,8 @@ FROM_REPOSITORIES = {
     "account_names",
     "count_uncategorized",
     "get_transaction",
-    "list_account_owners",
-    "list_accounts",
     "list_advice",
     "list_categories",
-    "list_people",
     "list_proposals",
     "list_rules",
     "list_transfer_pairs",
```

## Given tests

Seven cases; copy unchanged to tests/unit/test_account_listing_ownership.py.
Synthetic loader rows cover the reserved-name collision without changing person
validation. The predecessor-only load_attribution seam permits meaningful old
behavior in isolation; after refactoring it is unused. Mocked direct tool loaders
return empty data so legacy queries cannot accidentally satisfy expected JSON.

```python
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from finances.analysis import listings
from finances.analysis.people import Attribution
from finances.domain.models import Account, AccountType
from finances.mcp_server import tools

CARD = Account(
    1,
    "Synthetic Card",
    "Synthetic Bank",
    AccountType.CHECKING,
    "USD",
    None,
    True,
    datetime(2026, 1, 1, tzinfo=UTC),
)


@pytest.mark.parametrize(
    ("owners", "people", "display", "joint"),
    [
        ({}, [], None, False),
        ({1: 7}, [SimpleNamespace(id=7, name="Synthetic Person")], "Synthetic Person", False),
        ({1: None}, [], "Joint", True),
        ({1: 7}, [SimpleNamespace(id=7, name="Joint")], "Joint", False),
    ],
    ids=["unassigned", "sole", "joint", "name-collision"],
)
def test_analysis_keeps_display_and_joint_distinct(monkeypatch, owners, people, display, joint):
    session = Mock()
    accounts = Mock(return_value=[CARD])
    owner_loader = Mock(return_value=owners)
    people_loader = Mock(return_value=people)
    monkeypatch.setattr(listings, "list_accounts", accounts)
    monkeypatch.setattr(listings, "list_account_owners", owner_loader)
    monkeypatch.setattr(listings, "list_people", people_loader)
    # Predecessor seam: let its lossy display-only path run without a real DB.
    monkeypatch.setattr(
        listings,
        "load_attribution",
        lambda s: Attribution(owners={} if display is None else {1: display}, aliases={}),
        raising=False,
    )
    found = listings.account_listing(session, include_inactive=True)
    assert len(found) == 1
    assert found[0].account is CARD
    assert found[0].owner == display
    assert found[0].joint is joint
    accounts.assert_called_once_with(session, include_inactive=True)
    owner_loader.assert_called_once_with(session)
    people_loader.assert_called_once_with(session)
    assert session.mock_calls == []


def test_existing_two_argument_listing_defaults_to_nonjoint():
    assert listings.AccountListing(CARD, "Joint").joint is False


@pytest.mark.parametrize("include_inactive", [False, True], ids=["active", "all"])
def test_mcp_serializes_shared_listing_only(monkeypatch, include_inactive):
    session = Mock()
    monkeypatch.setattr(tools, "reading", lambda: nullcontext(session))
    rows = [
        SimpleNamespace(account=CARD, owner=owner, joint=joint)
        for owner, joint in [
            (None, False),
            ("Synthetic Person", False),
            ("Joint", True),
            ("Joint", False),
        ]
    ]
    loader = Mock(return_value=rows)
    monkeypatch.setattr(tools, "account_listing", loader, raising=False)
    direct = []
    for name in ("list_people", "list_account_owners", "load_accounts"):
        spy = Mock(return_value=[])
        monkeypatch.setattr(tools, name, spy, raising=False)
        direct.append(spy)
    assert tools.list_accounts(include_inactive) == {
        "accounts": [
            {
                "name": "Synthetic Card",
                "institution": "Synthetic Bank",
                "type": "checking",
                "currency": "USD",
                "last4": None,
                "active": True,
                "owner": None,
                "joint": False,
            },
            {
                "name": "Synthetic Card",
                "institution": "Synthetic Bank",
                "type": "checking",
                "currency": "USD",
                "last4": None,
                "active": True,
                "owner": "Synthetic Person",
                "joint": False,
            },
            {
                "name": "Synthetic Card",
                "institution": "Synthetic Bank",
                "type": "checking",
                "currency": "USD",
                "last4": None,
                "active": True,
                "owner": None,
                "joint": True,
            },
            {
                "name": "Synthetic Card",
                "institution": "Synthetic Bank",
                "type": "checking",
                "currency": "USD",
                "last4": None,
                "active": True,
                "owner": "Joint",
                "joint": False,
            },
        ]
    }
    loader.assert_called_once_with(session, include_inactive=include_inactive)
    for spy in direct:
        spy.assert_not_called()
    assert session.mock_calls == []
```

## Tests to write

`tests/integration/test_mcp_account_listing.py` (mcp):

- R2/R4: migrated db_engine with synthetic unassigned, sole, joint and closed
  accounts created out of alphabetical order. Set owners through existing public
  APIs using valid invented person names. Assert complete AccountListing values,
  default filtering and include_inactive, and unchanged account_rows output.
- R3/R4: call actual MCP server list_accounts with omitted, false and true flags;
  assert exact complete JSON rows/key sets/order for those accounts, plus empty
  database. Reuse existing in-memory MCP helpers; no socket or real data.
- R4: confirm actual CLI accounts list and web accounts page retain their exact
  established columns/owner labels for all supported ownership forms and closed
  account filtering. Reuse tests/support.py helpers and existing fixture patterns.
- R1/R4: pin tool name/signature/description and input/output schema to predecessor
  public contract (or explicitly point to existing tests that already pin each).
  Preserve the existing read-only MCP tests; add evidence that this adapter enters
  reading and forwards the very same session to shared analysis, never writing.
- R2/R5: empty and inactive-only analysis results do not repeat repository calls;
  loader spies assert accounts/owners/people once each and no cardholder alias
  load. Can use focused synthetic loader seams in this file. Successful public
  calls above must still exercise real repositories and cannot all be mocked.

## Rules for this phase

Integer cents and synthetic data only. No runtime network, real samples, Keychain,
new migration or dependency. No critical module is touched. Thin read-only MCP
adapter; data assembly stays in analysis. Existing test changes only as given.

## Acceptance

Sequentially in the isolated checkout, with actual exit codes/output retained:

1. `.venv/bin/python scripts/check.py --first core,mcp,web,cli --workers 4`:
   ends All checks passed.; at least **4571** full-suite passes (4564+7 plus coder
   cases), every section zero failures/skips, no xfails or warnings summary.
   Document a serial override only for resource contention; one coverage run per
   checkout, bounded machine-wide workers.
2. Immediately `.venv/bin/python -m coverage report --include="*/finances/analysis/listings.py" --fail-under=100`:
   listing module and TOTAL at 100%, no missing lines/branches. Overall and all
   critical gates must also pass. No artificial whole-tools.py 100% target.
3. `.venv/bin/python -m pytest tests/unit/test_account_listing_ownership.py --no-cov`:
   exactly seven passed.
4. Inspect status/diff HEAD: only six Scope paths plus authorized verifier report;
   given new file and earlier-test diff match embedded bytes, other tests unchanged.
   No new search gate or independent probe. Inspect the two production modules for
   only the listed changes, without modifying critical attribution or other tools.

## Report

Use phase-conventions.md, headed Phase 47f: MCP account ownership from analysis.
Record AccountListing.joint, N/final/given counts, import provenance, compatibility
and loader-call evidence. Do not commit or push.
