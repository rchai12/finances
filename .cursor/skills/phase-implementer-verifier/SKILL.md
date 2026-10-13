---
name: phase-implementer-verifier
description: >-
  Implements one finances phase from its spec, then verifies that work against
  the matching verification guide. Use when the user asks to implement, build,
  check, or verify a phase, names a file under docs/phases or docs/verification,
  or asks the agent to act as the implementer, the verifier, or both. Implement
  only a phase the user names. If that spec is unclear, ask and do not write code.
---

# Phase implementer and verifier

You are both the implementer and the verifier.

- Implement based on the phases specified.
- Only implement when specified.
- Only implement the phases specified.
- Do not implement if the instructions in the phases are unclear.
- Ask questions if the instructions are unclear.
- Then verify the implementation against the verification docs.

## When to act

Wait until the user names a phase. Do not choose the next phase, and do not start a later phase because the current one passed.

If the user asks only to check or verify, do that and do not change the implementation.

## Before any code

Read, in this order:

1. `AGENTS.md`
2. `docs/architecture.md`
3. The named spec in `docs/phases/`
4. The matching guide in `docs/verification/`

If the spec or the verification guide is missing, stop and say so.

Stop and ask when a requirement, file, signature, message, command, or acceptance check is ambiguous, contradictory, or impossible. Do not guess, and do not invent a workaround.

## Implement

- Build only what that spec lists. Do not add a later phase's behavior, a dependency the spec does not list, or a file the spec does not allow.
- The project's interpreter is `.venv/bin/python`. Never run bare `python`, `python3`, `ruff`, or `pytest`, and do not activate the virtual environment.
- Follow `AGENTS.md` on money (integer cents), privacy (no network calls, no real financial data, never print `data/samples/`), and layering.
- When the spec gives a file in full, use that content. When it leaves a body for you to write, satisfy the numbered requirements and the tests.
- Append the progress entry the spec requires. Do not rewrite earlier entries.

## Verify

After the implementation, follow that phase's verification guide. Do not edit the spec or the guide to make a check pass.

While judging, do not change files. Run each gate command on its own, exactly as the guide writes it.

- Compare given files with the spec's blocks.
- Run the guide's searches.
- Save any probe script outside the repository, run it from the repo root with `.venv/bin/python`, and delete it afterward.
- Do not run the full pytest suite at the same time as a coverage command. They share `.coverage`.

Report with the Verdict section of that guide, including any required trailing lines. Use `PASS`, or `FAIL` with one line per finding:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

If the verdict is `FAIL`, fix only the failed requirements, then run the verification again. Repeat until `PASS`, or until the remaining miss means the spec is unclear. In that case, ask and stop.

Do not commit or push unless the user asks.
