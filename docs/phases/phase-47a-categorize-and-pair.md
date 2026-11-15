# Phase 47a: categorize and pair

**Draft — not ready for implementation.** Given tests, their failure checks,
the earlier-test diff, exact scope, coverage baseline, and spot checks remain to
be prepared. Do not use this document as a coder handoff yet.

## Goal

After an action runs categorization, pair eligible transfers before the action
finishes. The owner accepted the November audit findings and chose staged
remediation (2026-11-15). The phase follows
[`audit-remediation-design.md`](../audit-remediation-design.md#47a-categorize-and-pair-as-one-operation).

Phase 38 described rule and category changes as unable to create a pairing
candidate. This phase does not rely on such a change creating a candidate: an
eligible pair can already be waiting when a person performs one of these actions.
The desired result is to run the existing pairing operation at that point.

## Starting state

Phase 46 passed with 4,310 tests; the latest migration is
`0026_proposal_findings.py`. Sections: `web, cli, core`. Confirm the clean
committed baseline and test count when issuing the final spec. Existing
uncommitted project work must be preserved.

## Proposed contract

1. Add `categorize_and_pair(session: Session) -> CategorizeResult` to
   `finances.categorize.service`. Call `categorize(session)` first and then
   `pair_transfers(session)` once. Return the categorization result unchanged.
   Neither open nor commit a session; propagate failures.
2. Keep the CLI `categorize_all()` interface and output. Its own session calls
   the shared operation. Existing CLI import, sync, alias, and split callers
   continue through that adapter.
3. In web routes, use the shared operation after rule add, edit, and delete;
   alias add and delete; bulk category clear; and single-transaction category
   clear. Preserve existing input validation, notices, redirects, and refusals.
4. Replace adjacent categorization and pairing in web statement import, sync,
   and split removal with one shared call. Do not add a second pairing call.
   Share removal and explicit transfer finding remain pair-only operations.
5. In `accept_proposals`, use the shared operation only where accepted rule or
   alias changes already trigger categorization. Preserve the `Accepted` result
   and its conditional `categorized` field. Creating an agent proposal remains
   inert; acceptance stays a person's action.
6. Web mutation, categorization, pairing, and audit writes use the existing
   request session and commit together. A pairing exception rolls all back.
   Do not change CLI import or sync transaction boundaries.

## Expected implementation scope

- `src/finances/categorize/service.py`, `src/finances/cli/categories.py`.
- `src/finances/web/routes/categories.py`, `transactions.py`, `statements.py`,
  and `sync.py`.
- New focused tests, any specifically identified earlier test patch changes,
  and the phase entry in `docs/progress.md`.

This list is provisional until existing tests and patch points have been checked.
No migration, dependency, pairing-algorithm change, session-helper rename, or
other Phase 47 work belongs here.

## Deciding cases to prepare

- A waiting, synthetic eligible pair is paired immediately after each of the
  seven web actions in requirement 3. Check resulting stored pair and the
  action's existing response; repeat without creating a duplicate.
- A forced pairing exception during a rule action rolls back its rule, category
  changes, pair, and audit records. Check persisted state in a fresh session.
- Direct operation returns the original result, calls in order with the same
  session, leaves commit to the caller, and propagates exceptions.
- CLI text remains unchanged; import, sync, and split-removal routes pair once.
- Accepted rule/alias changes recategorize and pair; proposal submission alone
  does neither. Acceptance of a kind that does not currently recategorize stays
  unchanged.
- Existing manual decisions, splits, shares, rejected transfers, and confirmed
  pairs retain their behavior; reports exclude newly paired transfers.

## Acceptance to complete before handoff

Prepare and embed given tests after checking each against the predecessor in an
isolated clone. Pin the exact count and failure reasons, any earlier-test diff,
the per-module coverage command, scope, searches, and the guide's spot checks.
Run the standard gates in `docs/phase-conventions.md` when the phase is built.
