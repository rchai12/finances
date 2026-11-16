# Phase 47a: categorize and pair

## Goal

A person who changes a rule, merchant alias, or manual category on the web gets eligible transfers paired as part of the same operation. The owner accepted the November audit findings and chose staged remediation (2026-11-15). Phase 38 observed that these actions do not themselves make a transaction eligible; a pair can nevertheless be waiting before the action. This phase runs existing pairing for that waiting pair.

## Read first

- `docs/phase-conventions.md`, `docs/testing.md`, and `docs/audit-remediation-design.md` (47a).
- `finances.categorize.service`, `finances.categorize.transfers`, `finances.cli.categories`, and web routes `categories`, `transactions`, `statements`, `sync`, and `review`.
- `tests/integration/test_pairing_gaps.py` and `tests/support.py`.

## Starting state

N is 4310 after Phase 46. Sections: `web,cli,core`. Newest migration: `0026_proposal_findings.py`. The prior baseline must be committed and `git status --short` empty before implementation. Run the starting check in `docs/phase-conventions.md`.

The architect's baseline check passed all 4,310 tests on 2026-11-15. The existing `categorize/service.py` coverage is 100% (83 statements, 22 branches). The first sandboxed run could not bind the loopback transport-test server; the required rerun passed with loopback permission.

## Scope

| Path | Change |
|---|---|
| `src/finances/categorize/service.py` | Shared operation and acceptance integration (R1, R4) |
| `src/finances/cli/categories.py` | CLI adapter (R2) |
| `src/finances/web/routes/categories.py` | Rules and aliases (R3) |
| `src/finances/web/routes/transactions.py` | Category clearing and split clearing (R3, R5) |
| `src/finances/web/routes/statements.py`, `src/finances/web/routes/sync.py` | Existing paired operations (R5) |
| `tests/integration/test_web_pair_after_rules.py` | Given below |
| `tests/unit/test_categorize_and_pair.py` | Coder tests below; core section |
| `tests/integration/test_web_pair_after_rules_more.py` | Coder tests below; web section |
| `tests/integration/test_pair_after_acceptance.py` | Coder tests below; core section |
| `docs/progress.md` | Append the phase entry |

No other paths may change. New test names match existing section patterns. No migration or new dependency.

## Requirements

- **R1.** In `finances.categorize.service`, add `categorize_and_pair(session: Session) -> CategorizeResult`: run `categorize(session)`, then `pair_transfers(session)` once, return the same result object. Pass the same session. Do not open, commit, or roll back a session; propagate errors. Keep `categorize` as a standalone operation.
- **R2.** `finances.cli.categories.categorize_all()` keeps its signature, session boundary, output, and return value, and uses the shared operation.
- **R3.** Rule add/edit/delete, alias add/delete, bulk "Leave to the rules", and single category clear run the shared operation in the existing session after the write. Their existing validation, responses, notices, and redirects stay unchanged.
- **R4.** `accept_proposals` uses the shared operation when an accepted kind in its existing set (`RULE`, `ALIAS`, `RULE_EDIT`, `RULE_DELETE`) triggers categorization. Preserve acceptance order and the `Accepted` result; other kinds do not trigger it. Proposal submission alone does not categorize or pair.
- **R5.** Web statement import, sync, and split clear each use the shared operation in place of adjacent categorize/pair calls; no second pairing call. Keep pair-only operations, including unshare and explicit transfer finding, unchanged.
- **R6.** The initiating web write, categorization, pairing, and audit writes share the existing session. An exception from pairing rolls them all back. Do not change CLI import/sync session boundaries.
- **R7.** No pairing rules, matching, amounts, schemas, or MCP write capabilities change. Preserve manual/split/shared exclusions, rejected and confirmed pairs, privacy, and all previous tests.

## Given test

Seven parameterized cases. Copy this file exactly; do not change it.

`tests/integration/test_web_pair_after_rules.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_alias,
    create_account,
    create_rule,
    find_transfer_pair,
    list_transfer_pairs,
    set_category_by_hand,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, post


@pytest.mark.parametrize(
    ("case", "path", "fields", "location"),
    [
        (
            "add",
            "/categories/rules/add",
            {"pattern": "NEW", "match": "contains", "priority": "0", "category": "Groceries"},
            "/categories?notice=rule-added",
        ),
        (
            "edit",
            "/categories/rules/1",
            {"pattern": "NEW", "match": "contains", "priority": "0", "category": "Groceries"},
            "/categories?notice=rule-changed",
        ),
        ("delete", "/categories/rules/delete", {"rule": "1"}, "/categories?notice=rule-deleted"),
        (
            "alias_add",
            "/categories/aliases/add",
            {"source": "FIRST", "target": "SECOND"},
            "/categories?notice=merchant-merged",
        ),
        (
            "alias_delete",
            "/categories/aliases/delete",
            {"source": "FIRST"},
            "/categories?notice=merchant-unmerged",
        ),
        (
            "bulk",
            "/transactions/bulk",
            {"id": "1", "action": "clear"},
            "/transactions?notice=bulk-cleared",
        ),
        ("clear", "/transactions/1/category/clear", {}, "/transactions/1?notice=category-cleared"),
    ],
    ids=[
        "rule-add",
        "rule-edit",
        "rule-delete",
        "alias-add",
        "alias-delete",
        "bulk-clear",
        "single-clear",
    ],
)
def test_action_pairs_waiting_transfer(
    tmp_settings: Settings, case: str, path: str, fields: dict[str, str], location: str
) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        for number, (name, cents) in enumerate(
            (("Test Checking", -12345), ("Test Savings", 12345)), start=1
        ):
            account = create_account(session, name, "Test Bank", "checking")
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, 10),
                    amount_cents=cents,
                    description="SYNTHETIC TRANSFER",
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        if case in ("edit", "delete"):
            create_rule(session, "OLD", "Groceries")
        if case == "alias_delete":
            add_alias(session, "FIRST", "SECOND")
        if case in ("bulk", "clear"):
            set_category_by_hand(session, 1, "Groceries")
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/categories")
    response = post(client, path, **fields)
    assert (response.status_code, response.headers.get("location")) == (303, location)
    with session_scope(engine) as session:
        assert find_transfer_pair(session, 1) is not None
        assert len(list_transfer_pairs(session)) == 1
    engine.dispose()
```

## Tests to write

Use synthetic data and assert persisted behavior. Put each test in the listed file.

`tests/unit/test_categorize_and_pair.py`:
- A controlled session and stubbed operations: order, same session, exactly one call each, and identity of the returned `CategorizeResult`.
- A pairing exception propagates and no hidden commit or rollback is called.

`tests/integration/test_web_pair_after_rules_more.py`:
- Force pairing to raise after adding a rule; a fresh session sees no rule, changed categorization, transfer pair, or added audit row. Compare pre/post values, not merely the response.
- Run category clear twice on a pairable transaction: one pair remains. A rejected pair, an existing confirmed pair, and a split/shared movement remain governed by the existing pairing rules.
- A web import, a sync, and a split clear each invoke pairing once in their existing operation; use synthetic data and stubs, no network or real Keychain. The CLI `categorize_all` returns the categorization result with unchanged displayed text. Verify reports exclude an automatically paired transfer.

`tests/integration/test_pair_after_acceptance.py`:
- Accept a rule proposal and an alias proposal with a waiting pair; each returns its categorization result and stores the pair. Submitting either proposal alone leaves it unpaired.
- Accept a proposal of a kind outside the four listed in R4 and show categorization and pairing are not invoked.

Add sufficient behavior tests to meet coverage; do not alter given tests or earlier tests. If an earlier test needs a change, stop and report it rather than changing an unlisted path.

## Acceptance

Follow `docs/phase-conventions.md`. Run:

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first web,cli,core` | `All checks passed.`; every section 0 failed; tests at least 4317 passed, no failures, skips, xfails or warnings summary |
| `.venv/bin/python -m coverage report --include="*/finances/categorize/service.py" --fail-under=100` | Immediately after the check, exit 0, TOTAL 100% |
| `.venv/bin/python -m pytest tests/integration/test_web_pair_after_rules.py --no-cov` | 7 passed |
| `git grep -n -F 'categorize(session)' -- src/finances/web/routes/categories.py src/finances/web/routes/transactions.py src/finances/web/routes/statements.py src/finances/web/routes/sync.py` | no output |
| `git status --short` | only Scope paths |

The project's required `scripts/check.py` gate is included above. The coverage command checks the shared operation's module; the full check separately enforces every critical-module threshold.

## Report

Append the exact progress entry required by `docs/phase-conventions.md` and provide its required acceptance evidence and requirement-to-test mapping.
