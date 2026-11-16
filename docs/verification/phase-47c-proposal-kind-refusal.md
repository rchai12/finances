# Verify Phase 47c: explicit proposal-kind refusal

Spec: docs/phases/phase-47c-proposal-kind-refusal.md.
Follow docs/phase-conventions.md; write only
`docs/reviews/phase-47c-proposal-kind-refusal.md`. This is independent verification,
not reuse of coder acceptance evidence.

## Starting baseline

Confirm approved 47b (4371 tests), committed finalized spec/guide, the coder's
progress entry, and expected implementation paths. Missing implementation is a
baseline blocker, not a functional FAIL. Read status and diff HEAD before writing
the report. Use the isolated committed-baseline checkout described in the spec;
confirm finances.__file__ resolves there. Preserve unrelated .vscode work in the
original workspace. Before transporting a verdict back, compare reviewed bytes
with the delivery. Do not approve stale or different code.

## 1. Gates

Run the spec's four acceptance steps exactly, in order. First gate:
`.venv/bin/python scripts/check.py --first core,mcp,web,cli --workers 4`.
Require at least 4375 full-suite passes plus coder cases, every section clean,
`All checks passed.` and mandatory critical coverage. Immediately run the spec's
coverage report before another coverage producer. Then require exactly four
given passes and scope/given-byte equality. Record any justified serial override.
Resolve sandbox localhost restrictions through execution permission, retaining
both outcomes; never weaken assertions. Do not run real samples.

## 2. Scope

Only the five paths in Scope plus this review. Existing tests, domain KINDS,
proposal_text, migrations, dependencies and adapters remain unchanged. No reason
or timestamp cleanup. The given file equals its embedded block. No dispatch
framework or schema weakening. A caller repair beyond Scope returns to architect.

## 3. Requirement checklist

| Id | Evidence and deciding observation |
|---|---|
| R1 | Four given cases; unknown guard before dependency/staleness; missing/non-open checks retain precedence. Error is constant and contains no sentinel/stored values. |
| R2 | Explicit category/transfer branches and terminal refusal in both functions; given future cases patch inventory yet still refuse. No default category/pair route. |
| R3 | Given spies assert unchanged status/time and zero writer/session calls; integration case catches inside transaction and compares fresh persisted snapshots without rollback masking. |
| R4 | Two complete matrices cover every KINDS member; verify expected delegate/arguments/results, both stale booleans, RULE/ALIAS local branches and absence of unintended calls. Existing pins pass. |
| R5 | Migrated DB cases assert actual category/pair/rejection and audit results; missing/closed/dependent precedence and unchanged state; previous suite and boundary sections pass. |

## 4. Probe

None. Full dispatch matrices, real persistence cases and focused seam tests add
complementary evidence without another dispatch implementation.

## 5. Coder tests and spot checks

Account for every named Tests to write case. Check assertions validate behavior,
not just executing handlers. No skipped matrix member or database-constraint-only
unknown-kind test satisfies the spec. Registered future acceptance stubs
staleness so its own fallback is reached independently.

Perform mutations only in a fresh disposable copy of reviewed source/tests;
confirm import provenance. Never mutate the reviewed tree. Each full id below is
under tests/unit/test_proposal_dispatch.py::
test_unsupported_kind_refuses_without_mutation.

| Function and exact mutation | Given suffix / deciding input | Correct | Broken |
|---|---|---|---|
| accept_proposal: replace terminal unsupported refusal with set_category_by_hand | [accept-future], inventory includes future kind, no dependency/staleness | constant ValueError, zero writes | no refusal, category writer called and accepted status |
| proposal_out_of_date: replace terminal refusal with pair_is_out_of_date | [stale-future], inventory includes future kind, pair seam returns False | constant ValueError, zero pair check | False, pair check called |
| accept_proposal: omit unknown guard and let waits_for run, retaining terminal refusal | [accept-unknown], waits_for returns None, staleness=False | ValueError with waits_for never called | same error but waits_for assertion fails |

Trace each through actual revised code before mutating; if a different earlier
defense masks the first two mutations, document that defense and remove only
redundant rejection checks in the disposable mutation so the named fallback is
reached. Never remove ordinary validation or change test inputs to claim success.
If a mutation cannot isolate the rule, report the limitation to the architect.

Reasonable variations: imported inventory versus module lookup, shared private
refusal helper, shared explicit transfer-kind branch, and early refusal of a
future unhandled member are acceptable. Preserve the given patch seams. No new
100% noncritical target is required; mandatory critical coverage stays intact.

## 6. Verdict and handoff

Use the standard report header and finding format. Separate baseline/environment,
spec/test errors, and implementation failures. Record all gates, scope, matrix
coverage, spot outcomes and progress accuracy. On FAIL send requirement,
observation and required result to coder without prescribing an implementation.
Only the owner commits; no commit/push or later-phase implementation here.
