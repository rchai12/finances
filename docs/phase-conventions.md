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

Add an entry at the end of `docs/progress.md`:

```markdown
## Phase NN: <the spec's title> (YYYY-MM-DD)
- Built: ... (give N and the final passed count)
- Deviations from spec (and why): ... (your design choices and anything the spec did not ask for, or None)
- Follow-ups / known issues: ...
```

In your final message give the last ten lines of `scripts/check.py`'s output, the output line of each other acceptance command, and for each requirement the name of a test (or the probe line) that covers it.

## For the verifier

- Do not modify any file in the repository. Report findings only. The work under review is uncommitted: "the diff" is `git status --short` plus `git diff HEAD`.
- Run the guide's gates exactly as written, from the repository root.
- **Scope audit**: `git status --short` shows only the spec's Scope paths; given files are identical to the blocks in the spec; no existing test, earlier migration, or unlisted module changed.
- Save the guide's probe script **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.
- Judge code by what it does, never by resemblance to another way of writing it.

### Verdict

`PASS`, or `FAIL` followed by one line per finding:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then:

`Total passed: <the count from the tests step>`

`Parts that needed a repair: <none, or the parts>`

`Built beyond the spec: <none, or what>`

If the verdict is FAIL, send the coder each finding as: the requirement, what was observed, and what is required. Do not prescribe the code.
