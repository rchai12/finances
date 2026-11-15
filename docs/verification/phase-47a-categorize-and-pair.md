# Verify Phase 47a: categorize and pair

**Draft — not ready for verifier handoff.** This guide needs validated given
tests, exact gates and counts, scope, and traced spot checks before use.

Spec: [phase-47a-categorize-and-pair.md](../phases/phase-47a-categorize-and-pair.md).
Follow `docs/phase-conventions.md` for the verifier's read-only procedure.

## Review plan

1. Confirm the coder ran against the intended committed baseline. Inspect
   `git status --short` and `git diff HEAD`; distinguish unrelated existing work
   from the phase diff before applying scope gates.
2. Run the final spec's `scripts/check.py --first web,cli,core` command and
   its given-test, coverage, and search gates in the specified order. Record
   exact results and the `Sections:` table.
3. Check each listed web action against a waiting eligible synthetic transfer;
   inspect the stored pair and existing response. Confirm no duplicate on repeat.
4. Confirm a failure in pairing rolls back the initiating change and audit writes
   by inspecting a fresh database session. Confirm no hidden session or commit in
   the shared operation.
5. Check proposal submission remains inert, while accepting rule/alias changes
   pairs once. Check CLI output and previously paired web paths remain stable.
6. Trace each final spot check through its deciding test. Run any mutation only
   in a scratch copy. Judge behavior, not the implementation's internal shape.
7. Verify the progress entry and write the verdict in the format required by
   `docs/phase-conventions.md`. Only the review report is written during review.

## Before this guide is issued

Add the exact given-test count, coverage paths and baseline, earlier-test diff,
requirement-to-test mapping, searches validated with planted violations, and
spot-check rows with distinct correct and broken results. A probe is optional
only if it adds evidence beyond these tests; validate any oracle independently.
