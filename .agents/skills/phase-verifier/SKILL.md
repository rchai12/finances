---
name: phase-verifier
description: Verify one named finances phase against its guide, inspect scope and test evidence, and write the review report. Use for independent verifier assignments.
---

# Finances phase verifier

Review the named phase. Read AGENTS.md, docs/architecture.md,
docs/phase-conventions.md, the spec including Corrections, its guide, the phase
progress entry, and the diff including untracked files. The only repository
artifact you write is docs/reviews/<spec filename>.

Read [handoff procedure](../phase-architect/references/handoffs.md) for baseline,
isolation, and permitted evidence reuse. Check that the coder ran and the
executable documents match the committed baseline before expensive gates.
Distinguish an absent implementation, an intentionally stopped coder, an
environment problem, and a mixed tree from a functional failure. Do not waive a
literal gate yourself; report its cause and concrete resolution.

Follow the guide's gates exactly, unless the owner explicitly narrows the
reassessment. A scope-only rerun does not automatically require another full
suite: apply the evidence-reuse conditions in the handoff procedure. In an
isolated clone, verify import provenance and record its baseline and file
comparison. An independent review applies to the exact bytes inspected.

Judge behavior and useful assertions. Trace spot checks through all defenses,
including schema constraints and fake clocks. Execute mutations only in scratch
copies; do not adopt tasking's in-place spot_check.py workflow. A passing mutation
can indicate a weak test rather than a broken implementation; explain which.

Write the verdict in finances' existing format, with one concrete requirement,
location, expectation and observation per finding. Include a short gate and
spot-check digest and the required section evidence. Keep reused evidence clearly
distinguished from fresh runs. Never repair the implementation, rewrite the spec,
commit, or push as part of verification.
