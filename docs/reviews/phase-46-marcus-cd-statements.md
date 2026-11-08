# Review: Phase 46

- Verdict: PASS
- Passed: 4310
- Findings: 0
- Approved deviations: module-level `_HEADINGS` tuple; given test fixed in the spec from `detect_parser(pages()[0])` to `detect_parser(pages())` after the coder stopped
- For the architect: None

## Findings

None

Parts that needed a repair: the given detection test passed a string into `detect_parser`, which takes the list of pages; the architect corrected the spec before the build finished.

Built beyond the spec: None.

## Gates

- `scripts/check.py --first parsers`: last line `All checks passed.`; summary lists `tests (parsers): passed` then `tests: passed`; 4310 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table
- Given tests with earlier Marcus files: all passed, 7 from `test_marcus_cd.py`
- Coverage include report: `TOTAL 80 0 24 0 100%`
- `git diff --stat HEAD -- tests`: nothing (new files untracked)

`git status --short` lists the spec's Scope paths, the corrected given line in the phase spec, the architect skill note, `docs/progress.md`, `docs/reviews/phase-46-marcus-cd-statements.md`, and local `.vscode/` (not part of the phase). The given fixture and test file match the corrected spec.

## Requirement checklist

- R1: gate 2

## Tests to write

None.

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/` copies, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. CD heading not added | `test_a_cd_statement_is_detected` | failed |
| 2. bank no longer required | `test_a_cd_heading_alone_or_misspelt_is_not_detected` (`CD ACCOUNT STATEMENT`) | failed |
| 3. headings compared ignoring case | the same test (`Cd Account Statement`) | failed |
| 4. looser word `STATEMENT` | the same test (`CD STATEMENT`) | failed |

## Out of scope

Absent: a `cd` account type; maturity, term, or rate parsed; a new or renamed parser.

## Probe

None. Do not open `data/samples/`.
