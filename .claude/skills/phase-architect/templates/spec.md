# Phase NNx: <name>

## Goal

What exists after this phase that did not before. Name the owner's choices with their date ("With the owner's choices (YYYY-MM-DD):") as a short list, apart from what the architect decided.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- the earlier spec whose shape this one follows, and the modules the phase touches, by path and the names in them that matter

## Starting state

N is `{{var:N}}` when Phase <previous> is the last phase built. **Sections: <sections>.** The newest migration is `<NNNN>`. Any fact about existing code the coder might get wrong: a module at the 400-line cap, a test that patches a name, a width constant `tests/unit/test_text.py` requires.

## Scope

| Path | What changes |
|---|---|
| `src/finances/<module>.py` | <what> (R1) |
| `tests/<given file>.py` | new: given |
| `tests/integration/<name>_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- What a capable coder would over-deliver, named.

## Dependencies

None new.

## Design

Every public name, signature, field, column, command option, and message, exactly. The order of checks as a table (check, refusal). What is stored. Each text as a table (the History text, the review row, the accepted text) with literal examples.

## Requirements

- **R1.** One testable statement each.

## Given migration

{{file:src/finances/db/migrations/versions/<NNNN>_<name>.py}}

## Given diff to earlier tests

Which pins change and why; what a spike showed about them.

{{file:<scratch>/given<NN>.diff}}

## Given tests

{{var:GIVEN}} tests in <n> files. Do not change them.

`tests/<path>.py`

{{file:tests/<path>.py}}

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/<name>_more.py` (section <section>):

- <behaviour> (<deciding input>);

## Rules for this phase

- The project rules this phase can break, restated.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first <sections>`;
- the given test files above, {{var:GIVEN}} tests; at least N + {{var:GIVEN}} passed in all;
- `git diff --stat HEAD -- tests` lists only <the files of the given diff>;
- <each search, with what it must print>;
- the coverage command: `{{var:COVERAGE}}`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase NNx: <name> (YYYY-MM-DD)`.
