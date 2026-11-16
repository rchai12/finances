# Verify Phase NNx: <name>

Spec: `docs/phases/phase-NNx-<slug>.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

What the coder built, in two or three sentences, and what was given (a migration, a template diff, a diff to N earlier test files, M test files).

These are correct and must not be reported: <the reasonable variations: a private helper moved for the 400-line cap, an import inside a function to avoid a cycle, ...>.

## 1. Gates

N is `{{var:N}}` when Phase <previous> was the last phase built. Sections: <sections>.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first <sections>` | last line `All checks passed.`; the summary lists `tests (<sections>): passed`; at least N + {{var:GIVEN}} passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest <given files> --no-cov` | exactly `{{var:GIVEN}} passed` |
| `{{var:COVERAGE}}` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | <the given diff's files>, no other |
| <each search> | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, the files of the given diff, and the new test files. The given files and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`<test name>`); the coder's <case> | pass |

## 4. Probe

None, or the script and what it must print.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `<function>`: <the exact mutation> | given `<test>` (<input>) | <short value> | <short value> |

## 6. Out of scope

Each must be absent: <the spec's out-of-scope items>.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
