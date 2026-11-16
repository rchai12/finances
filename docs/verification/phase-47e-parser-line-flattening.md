# Verify Phase 47e: shared parser line flattening

Spec: docs/phases/phase-47e-parser-line-flattening.md.
Follow AGENTS.md and docs/phase-conventions.md. Independently verify; write only
`docs/reviews/phase-47e-parser-line-flattening.md`.

One new helper replaces six identical expressions, with Marcus savings and CD
sharing the same parse method. Given: one sixteen-case file; no earlier-test diff,
migration, dependency or fixture changes. New compatibility cases are coder-owned.

## Starting baseline

Confirm 47d PASS at 4514 and approved commit cf3c2c0. Confirm finalized planning
spec/guide committed and identical to HEAD, coder progress and implementation
exist, and correct isolated checkout/import provenance before gates. Missing
implementation is a baseline blocker, not a functional FAIL. Inspect status/diff
before writing report. Preserve original .vscode work; compare reviewed bytes with
delivery before transporting a verdict. Do not approve stale or different code.

## 1. Gates

Run all four spec Acceptance steps in order. First:
`.venv/bin/python scripts/check.py --first parsers --workers 4`.
Require at least 4530 full-suite passes plus coder cases, clean section table,
mandatory coverage and `All checks passed.`. Run helper coverage immediately
before another coverage producer: helpers.py and TOTAL 100%, no missing lines or
branches. Then sixteen given passes and scope/given-byte equality. A serial
resource override must be documented. Keep one coverage job per checkout.
Resolve known localhost sandbox restrictions through execution permission; retain
both failed and successful outcomes where applicable. Do not run real samples.

## 2. Scope

Only ten Scope paths plus this review. Earlier test/fixture/config/migration bytes
are unchanged. Six source substitutions and imports, one helper, no other parsing
or detection changes. No new fixture framework. Critical helper functions other
than flatten are unchanged; their existing full-branch tests remain meaningful.

## 3. Requirement checklist

| Id | Evidence and deciding observation |
|---|---|
| R1 | Eight literal given rows and nonmutation case: order, blanks, columns, fresh output, no changes to pages. Coder repetitions case preserves duplicate lines. |
| R2 | Given no-pages/empty-page/line-endings/edge-newlines and coder Unicode/adjacent-page tests: splitlines behavior, no page joining or phantom trailing line. |
| R3 | All seven given delegation cases raise the same sentinel through module.flatten exactly once with identical pages object. Successful spy matrix and empty-return refusal prove returned lines are used. Six former expressions removed by inspection. |
| R4 | Complete statement and reconciliation equality against independent predecessor expression for all seven bases, CRLF/page repartition matrix, invalid-case behavior and all unchanged earlier fixture assertions. Detection unchanged. |
| R5 | Immediate helper coverage 100% line/branch, other critical gates/full suite pass, previous helpers and tests unchanged. No real data or runtime network. |

Account for every Tests to write bullet with a named case. Comparing counts or
calling helper without observing its result is insufficient. Old-expression
comparison is permitted only as the documented legacy characterization; expected
pure-helper values must remain literal and independent of implementation.

## 4. Probe

None. Literal boundary tests, caller sentinels, full-result characterization and
unchanged existing parser/reconciliation contracts provide complementary evidence.
No search gate is specified; inspect the seven named source files directly.

## 5. Spot checks

Mutate only a fresh disposable copy of reviewed source/tests. Confirm import
provenance, discard each independent mutation afterward, never alter reviewed
files. Full given prefixes: tests/unit/test_parser_flatten.py::.

| Function and exact mutation | Deciding given suffix/input | Correct | Broken |
|---|---|---|---|
| flatten: discard lines empty after strip | test_flatten_preserves_lines[blank-lines], space then two newlines | two empty strings | empty list |
| flatten: collapse internal whitespace | test_flatten_preserves_lines[internal-columns], two merchant spaces and a tab before amount | both preserved | spaces/tab collapsed |
| flatten: iterate pages in reverse | test_flatten_preserves_lines[page-order], one then empty page then two | one, blank, two | two, one, blank |
| flatten: join pages without a separator before splitlines | test_flatten_returns_fresh_list_without_mutating_pages, pages " one " and "two\n\n" | one, two, blank | combined first line |
| MarcusSavingsParser.parse: restore inline expression instead of flatten | test_parser_uses_shared_flatten[marcus-cd], valid synthetic CD fixture | sentinel exception | normal successful parse |

Trace these through final code. Blank-lines input produces two splitlines entries;
trailing newline alone produces none extra. The columns case changes only
normalization, and page order distinguishes sequence reversal. The fresh-list
case first appends to returned lines: it also catches accidental output caching.
For the Marcus mutation, the valid CD base was verified to parse and reconcile;
a different parsing error cannot satisfy the distinct sentinel type.

## 6. Reasonable variations and exclusions

A comprehension or explicit loops inside flatten are equally valid. Import order
and a docstring are coder choices. Preserve the specified parser-module lookup
seam and exact line semantics. Do not request shared parser classes, fixture
loader extraction, new bank layouts or unrelated code cleanup. Never remove blank
lines because current parser results happen to tolerate their removal.

## 7. Progress and verdict

Use the standard report header and findings format, distinguishing baseline,
environment, spec/test and implementation defects. Record fresh gates, Sections
table/final ten lines, scope/given equality, coder matrix coverage and spot results.
Check progress names/counts/deviations. On FAIL send requirement, observation and
required result to coder; do not repair implementation or relax requirements.
No commit, push or later-phase work.
