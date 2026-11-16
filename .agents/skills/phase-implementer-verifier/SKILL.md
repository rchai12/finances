---
name: phase-implementer-verifier
description: Implement a named finances phase and verify it against its guide when the owner explicitly asks one agent to do both. Standard coder and verifier assignments remain separate.
---

# Finances phase implementer and verifier for Codex

Use this combined role only when explicitly invoked or when the owner asks one
agent to implement and verify. Wait for a named phase; never pick the next phase
or start it automatically.

For a standard coder assignment, follow the spec without reading the verification
guide. For verification only, follow the guide and change only the review report.
Neither assignment authorizes the combined workflow below.

Read [handoff procedure](../phase-architect/references/handoffs.md) for baseline
isolation, evidence, stops, and correction handling. Use the separate
[phase-coder](../phase-coder/SKILL.md) and
[phase-verifier](../phase-verifier/SKILL.md) for single-role assignments.

## Read before implementing

Read in order:

1. `AGENTS.md`
2. `docs/architecture.md`
3. `docs/phase-conventions.md`
4. `docs/testing.md` and relevant entries in `docs/progress.md`
5. The named spec in `docs/phases/`
6. Its matching guide in `docs/verification/`

Stop if either document is missing. Follow starting-state checks and preserve
existing uncommitted work. For this combined role, ask the owner about unclear,
contradictory, or impossible requirements, signatures, files, messages, or gates
before implementing the affected part.

## Implement

- Change only the spec's Scope paths. Copy given files exactly. Do not edit
  given tests, the spec, or the guide to make a check pass.
- Build only the assigned phase; add no unlisted dependencies or later behavior.
- Use `.venv/bin/python` and `.venv/bin/fin`. Do not activate or recreate the
  environment, use bare interpreter or test commands, or reinstall packages
  unless the spec instructs it.
- Apply all project privacy, integer-cent money, layering, text-width, migration,
  and synthetic-test rules. Never inspect real statement contents or operate on
  the real database, Keychain, or aggregator.
- Run every acceptance command and append the required progress entry. Test and
  coverage runs must be sequential because they share `.coverage`.

## Verify and repair

Judge without editing implementation files. Read `git status --short` and
`git diff HEAD`, then run each guide gate individually as written, starting with
its `scripts/check.py --first ...` command.

Audit scope and given-file equality, run searches, and check observable behavior
and meaningful assertions. Save probes outside the repository, run from its root
with `.venv/bin/python`, and delete only those temporary probes afterward.

Write `docs/reviews/<spec filename>` using the guide's verdict format and
`docs/phase-conventions.md`. Record findings as:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

For implementation failures, leave judging mode, repair only the failed
requirements, and repeat verification. If a failure needs a spec decision, stop
and ask. Never bend the spec to fit the code. Self-review does not constitute an
independent verifier's review.

Report the required gate evidence, coverage, requirement-to-test mapping, and
verdict. Never report completion without the required `All checks passed.`
result. Do not commit, push, or delegate unless the owner asks.
