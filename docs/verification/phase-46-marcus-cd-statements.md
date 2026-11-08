# Verify Phase 46: Marcus CD statements

Spec: `docs/phases/phase-46-marcus-cd-statements.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder let `MarcusSavingsParser.detect` accept `CD ACCOUNT STATEMENT` beside `ONLINE SAVINGS ACCOUNT STATEMENT`, with `Goldman Sachs Bank USA` still required. A synthetic fixture and one test file were given.

These are correct and must not be reported: the two headings held in a module-level tuple; the parser's class and name unchanged.

## 1. Gates

N is `4302` when Phase 45c was the last phase built. Sections: parsers.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first parsers` | last line `All checks passed.`; the summary lists `tests (parsers): passed`; at least N + 7 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/unit/test_marcus_cd.py tests/unit/test_marcus_parser.py tests/unit/test_marcus_parser_more.py --no-cov` | all passed, 7 of them from `test_marcus_cd.py` |
| `.venv/bin/python -m coverage report --include="*/finances/ingest/parsers/marcus.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | nothing |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `src/finances/ingest/parsers/marcus.py`, the given fixture, and the given test file. Both given files equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 | pass |

## 4. Probe

None. Do not open `data/samples/`. After the verdict, the owner may run `.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`, which reports pass or fail per sample only.

## 5. Spot checks

Each row below is one change to `detect`. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. the CD heading not added | given `test_a_cd_statement_is_detected` | True | False |
| 2. the bank no longer required | given `test_a_cd_heading_alone_or_misspelt_is_not_detected` (`CD ACCOUNT STATEMENT` alone) | False | True |
| 3. headings compared ignoring case | the same test (`Cd Account Statement`) | False | True |
| 4. a looser word such as `STATEMENT` | the same test (`CD STATEMENT`) | False | True |

## 6. Out of scope

Each must be absent: a new account type; a maturity date, term, or rate read from the statement; a new parser or a renamed one.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
