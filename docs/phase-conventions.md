# Phase conventions

Every phase spec and verification guide follows this document. A spec states only what is particular to its phase and points here for the rest. Where a spec says something different, the spec wins.

## For the coder

### Before you start

- The previous phase is committed: `git status --short` prints nothing.
- Run `.venv/bin/python scripts/check.py`. It must end with `All checks passed.`. Note the number passed in its `tests` step: the spec calls it **N**.

### Scope

- Change only the paths in the spec's Scope table. You may add private helpers inside them. Any other production file, existing test, template, or migration stays as it is unless the spec lists it.
- Given files (tests, migrations, templates, fixtures) are copied exactly as shown, and never changed. If a given test fails, the code is wrong. If you believe a given file itself is wrong, stop and report; do not edit it.
- Build nothing from "Out of scope", even when it would be easy.

### Rules that hold in every phase

- **Commands** start with `.venv/bin/python` (or `.venv/bin/fin`). Never type `python`, `python3`, `ruff`, or `pytest` on their own. Do not activate the virtual environment, and do not create one. Install packages only when the spec has a step for it.
- **Git.** Do not commit. Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Real data.** Do not run `fin` against the real database in `data/`, the real Keychain, or SimpleFIN. The owner does that after verification.
- **Tests** use synthetic data only (invented merchants, names, and amounts), touch no network, and set no Hypothesis seed of their own.
- **Migrations.** One per schema change; a migration that has shipped is never edited.
- **Money** is integer cents. **Layering**: `domain` imports nothing outside `finances.domain`, and `domain/models.py` only the standard library; `cli` and `web` are thin. **Text fits its column** (`finances.domain.text`).
- Everything in `AGENTS.md` applies.

### Acceptance

Unless the spec adds more, run before you report:

| Command | Must show |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; in the `tests` step 0 failed, 0 skipped, 0 xfailed, no warnings summary, and at least N plus the spec's given test count passed |
| `.venv/bin/python -m pytest <the given test files> --no-cov` | exactly the spec's given test count passed |
| the spec's coverage command | `Required test coverage of 100% reached` |
| each of the spec's searches | no output |
| `git status --short` | only the paths in the Scope table |

### Report

Add an entry at the end of `docs/progress.md` in exactly this form. Every field is one line, or `None`; the architect reads these fields instead of your final message, so keep them short and literal.

```markdown
## Phase NN: <the spec's title> (YYYY-MM-DD)
- Tests: <N> -> <passed after> (given <the spec's given count>)
- New public names: `<module>`: `<name>`, `<name>`; `<module>`: `<name>` (or None)
- Changed files: <how many paths git status --short lists>
- Deviations:
  - <one line each: a choice the spec left open, or anything the spec did not ask for> (or None)
- Follow-ups:
  - <one line each: something the next phase or the architect should know> (or None)
```

In your final message give the last ten lines of `scripts/check.py`'s output, the output line of each other acceptance command, and for each requirement the name of a test (or the probe line) that covers it.

## For the verifier

- Do not modify any file in the repository, except to write your report (below). Report findings only. The work under review is uncommitted: "the diff" is `git status --short` plus `git diff HEAD`, read before you write the report.
- Run the guide's gates exactly as written, from the repository root.
- **Scope audit**: `git status --short` shows only the spec's Scope paths; given files are identical to the blocks in the spec; no existing test, earlier migration, or unlisted module changed.
- Save the guide's probe script **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.
- Judge code by what it does, never by resemblance to another way of writing it.

### Report and verdict

Write your report to `docs/reviews/<the spec's file name>` (for `docs/phases/phase-11b-categories-on-the-web.md`, `docs/reviews/phase-11b-categories-on-the-web.md`), creating the folder if needed. It is the only file you write; the owner commits it with the phase. It starts with this block, each field on one line:

```markdown
# Review: Phase NN

- Verdict: PASS (or FAIL)
- Passed: <the count from the tests step>
- Findings: <how many>
- Approved deviations: <one line, or None>
- For the architect: <one line the architect should act on, or None>
```

Then, under `## Findings`, one line per finding in this form, or `None`:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then `Parts that needed a repair: <none, or the parts>` and `Built beyond the spec: <none, or what>`, and after that any detail you think useful (gate output, probe output).

If the verdict is FAIL, send the coder each finding as: the requirement, what was observed, and what is required. Do not prescribe the code.
