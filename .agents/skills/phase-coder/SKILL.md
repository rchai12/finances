---
name: phase-coder
description: Implement one named finances phase from its finalized spec and report acceptance evidence. Use for coder assignments; the independent verifier uses a separate skill.
---

# Finances phase coder

Implement only the phase the owner names. Read AGENTS.md, docs/architecture.md,
docs/phase-conventions.md, docs/testing.md, the relevant progress entry, then the
spec, its Corrections section, and every given test in full. Follow the spec's
Scope. Do not read the verification guide or review reports in a standard coder
assignment; use only verifier findings the owner hands back.

Read [handoff procedure](../phase-architect/references/handoffs.md) for baseline,
evidence, and stop handling. Before code, require the committed executable spec
and clean baseline in the actual checkout used for the assignment. Resolve
unrelated work through isolation; do not merely record a dirty-tree deviation
and continue.

Use .venv/bin/python and the existing environment. Copy finances' embedded given
files exactly, implement the contract, and add the named coder tests. Run focused
sections while working, then all acceptance commands in order. Use the existing
finances check.py; tasking's accept.py and --quiet option are not available here.

Append the required progress entry with actual test counts and public names.
For a correction, preserve history and avoid duplicate phase headings. Report
the exact unfinished requirement if genuinely blocked; otherwise continue until
the assignment is complete. Give gate evidence and requirement-to-test mapping.
A completed implementation hands off to the independent verifier. Do not commit,
push, or delegate unless asked.
