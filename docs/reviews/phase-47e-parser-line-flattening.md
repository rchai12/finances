# Review: Phase 47e

- Verdict: PASS
- Passed: 4564
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Baseline, scope and provenance (2026-11-16)

Reviewed implementation commit `0ee3a38fa37e436630a3af33dbb01ee8f0c0342f` against finalized planning baseline `51527d1e993f5ba9427a58cf533d45ea44905ccf`. Predecessor Phase 47d implementation is committed at 949e31d and its PASS review at `cf3c2c0c10522dbcaf55e5cc7243346d66715b0a`; N = 4514. Phase 47e spec/guide match their committed planning versions. Read required instructions, architecture, conventions, handoff procedure, testing strategy, remediation design section 47e, spec/guide, progress, seven production-file diffs, given and coder tests, existing helper/labeled-amount/CD tests and synthetic parser assertions.

Original checkout `/Users/richardxiaohuachai/Desktop/Projects/finances` had empty tracked diff and only unrelated untracked `.vscode/settings.json`. Preserved it. Reviewed in a fresh local clone at `/var/folders/2d/386g2_8d69915k8_pvkhdq3c0000gn/T/finances-47e-review-d8bupil1/checkout`, linking the existing venv and excluding only that symlink locally. Clone status was clean before gates. Every isolated Python invocation selected its src via explicit PYTHONPATH; pre-gate import check resolved finances.__file__ inside that clone. No dependency installation or new environment.

The baseline-to-delivery changed-path set equals exactly the ten Scope paths: seven production files, two new tests and progress. Given file bytes equal the embedded block. Earlier tests, fixtures, migration/configuration/dependency files and critical-module list remain unchanged. The only public addition is `finances.ingest.parsers.helpers.flatten`.

Independent AST comparison removed only the new helper import and replaced each flatten call with the exact predecessor expression, then compared against the predecessor AST for all six parser modules: identical. Removing the newly added flatten definition from helpers.py likewise yields the predecessor AST. Thus no existing helper, detection method, parsing rule, validation, money/sign/date logic or reconciliation code changed. No fixture-loading framework was introduced.

After verification, all 1,014 tracked original-workspace files still matched the isolated reviewed bytes and their pre-gate SHA-256 manifest (`/tmp/phase47e-review-manifest.json`). This verdict applies to those exact bytes. No tracked implementation or phase document was modified during review. Only this review report is added to the original repository; the unrelated editor setting remains preserved.

## Fresh independent acceptance

Ran the four spec acceptance steps in order from the isolated repository root with its existing `.venv/bin/python` and clone PYTHONPATH. Python 3.12.16; pytest 9.1.1; pytest-xdist 3.8.0; pytest-cov 7.1.0. Used four local workers with one coordinated coverage-producing job in this checkout; no delegated agents or concurrent coverage jobs from this review.

Requested permission up front for the established synthetic localhost-binding restriction. The permitted check succeeded; there was no failed sandbox attempt in this review. The coder's baseline and acceptance results in progress remain historical evidence, not substitutes for the fresh independent run below. No real statements, data/samples, real database, Keychain or aggregator was accessed. No tests were weakened or omitted for environment restrictions.

| Command | Fresh observation |
|---|---|
| `.venv/bin/python scripts/check.py --first parsers --workers 4` | exit 0; selected parsers `903 passed in 5.67s`; full `4564 passed in 99.21s (0:01:39)`; no failures, skips, xfails or warnings summary; `All checks passed.` |
| `.venv/bin/python -m coverage report --include="*/finances/ingest/parsers/helpers.py" --fail-under=100` | immediately after full check; exit 0; helpers and `TOTAL 66 0 24 0 100%`; no missing lines or branches |
| `.venv/bin/python -m pytest tests/unit/test_parser_flatten.py --no-cov` | exit 0; exactly `16 passed in 0.02s` |
| Status/diff/given audit | isolated status and tracked diff clean (delivery is committed); exact ten-path baseline diff, given bytes identical and all earlier tests/fixtures unchanged |

Overall configured coverage is 99.98%, above 85%; all mandatory critical modules pass. No search gate or independent probe is specified. Fresh full output retained at `/tmp/phase47e-review-check.log`.

Full-run section table:

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           198 passed    0 failed    0 skipped
  parsers       903 passed    0 failed    0 skipped
  sync          284 passed    0 failed    0 skipped
  core         1547 passed    0 failed    0 skipped
```

Last ten check lines:

```text
  core         1547 passed    0 failed    0 skipped
== critical coverage

Summary:
  lint: passed
  format: passed
  tests (parsers): passed
  tests: passed
  critical coverage: passed
All checks passed.
```

## Requirement and coder-case evidence

| Requirement | Deciding evidence and observation |
|---|---|
| R1 | Eight literal rows in given `test_flatten_preserves_lines` pin page/line ordering, blanks, internal columns and newline edges. `test_flatten_returns_fresh_list_without_mutating_pages` mutates output and checks unchanged input plus fresh result. Coder `test_literal_boundaries_and_repeated_lines` pins duplicate lines across pages and literal Unicode-whitespace results; `test_empty_and_nonempty_calls_have_no_shared_state` checks independent output state. Source is exactly splitlines/strip comprehension, with no shared state or input mutation. |
| R2 | Given no-pages/empty-page/line-endings/no-final-newline/edge-newlines cases and coder literal boundaries cover CRLF, CR, Unicode line separators, whitespace-only Unicode lines and adjacent non-newline pages. No page joining, separator insertion, phantom final line, normalization or new validation policy. |
| R3 | Seven given `test_parser_uses_shared_flatten` cases reach the exact distinct exception through the module seam once with the identical pages object. `test_successful_spy_and_empty_return_use` wraps the actual helper and asserts complete successful result, exact one call/object identity, detection independence, and parser-specific missing-header StatementError when the seam returns empty lines. Six source substitutions occur at the former expression position; Marcus basic/CD share that method. |
| R4 | `test_full_statements_and_reconciliation_match_legacy` compares complete ParsedStatement equality and reconciliation against the exact predecessor expression for all seven bases. `test_crlf_repagination_preserves_complete_results` retains original lines/internal whitespace, distributes them over CRLF pages including an empty page and checks complete result/reconciliation; detection uses original first_page. `test_cross_bank_refusal_matches_legacy` checks exact historical parser errors and negative detection across all seven bases. Marcus mismatch case below preserves parse refusal. Existing independent literal fixture assertions remain unchanged and pass. |
| R5 | All pre-existing helpers and tests are unchanged; helper coverage is 100% line/branch and every critical/full-suite gate passes. No real-data, runtime network, dependency or broader parsing change. |

The seven bases are Capital One single_card, BoA card two_pages, Citi two_cardholders, Truist checking, BoA deposit checking, Marcus basic and Marcus cd. Dataclass equality covers header/account/period/balance fields, ordered line values including dates, cents, cardholders and sections, and declared section totals; these tests do not merely compare counts or totals. The legacy function uses the literal predecessor expression, independently of the new helper. Existing literal assertions supply the additional independent fixture contract.

`test_marcus_amount_mismatch_is_parse_refusal_not_reconciliation` asserts exact `marcus: row 2 does not match its balance` under both old-expression and new-helper paths. It correctly distinguishes this existing parse failure from a failed reconciliation; no stricter rule was invented. Cross-bank cases similarly compare exact refusals, not arbitrary exceptions.

Coder compatibility file has 34 cases: four literal boundary rows, one state-isolation case, seven full-result legacy cases, seven CRLF cases, seven spy/empty-return cases, seven cross-bank cases and one Marcus mismatch case. Sixteen given plus 34 coder cases add 50: 4514 -> 4564; parsers section grows 853 -> 903. Both new files match existing parser-section patterns without configuration edits. Assertions validate observable results and precise seams, rather than just exercising helper lines.

## Fresh scratch-only spot checks

Copied reviewed source/tests/config into a fresh disposable directory outside both checkouts and confirmed finances import provenance inside scratch src. Mutated independently and restored each scratch file before the next check; reviewed source was never modified. Each named given case ran with `--no-cov` and failed as required:

| Exact mutation | Deciding given case | Fresh broken observation |
|---|---|---|
| discard lines empty after strip | `test_flatten_preserves_lines[blank-lines]` | exit 1; expected two empty strings, received no lines |
| collapse internal whitespace | `test_flatten_preserves_lines[internal-columns]` | exit 1; literal merchant spaces/tab assertion fails |
| iterate pages in reverse | `test_flatten_preserves_lines[page-order]` | exit 1; page order differs |
| join pages without separator before splitlines | `test_flatten_returns_fresh_list_without_mutating_pages` | exit 1; first two lines merge |
| Marcus parse restores inline expression | `test_parser_uses_shared_flatten[marcus-cd]` | exit 1; required distinct sentinel not raised; valid CD parses normally |

No earlier defense masks these checks, and no test input or assertion was changed. Unmodified given cases pass in the fresh sixteen-case gate. Scratch directory cleaned up; logs retained at `/tmp/phase47e-review-spot-{blank,columns,order,join,marcus-cd}.log`.

## Progress and result

Progress accurately records N/final/given counts, the sole public helper, ten scoped paths, six caller methods/seven bases, 34 coder compatibility cases and no deviations. Its coder acceptance timing (93.27s) is historical; fresh independent full-suite time was 99.21s. Missing implementation, stale bytes, baseline or unresolved environment restrictions do not block this delivery, and no functional defect was identified.

PASS for the exact reviewed commit and bytes above. Only this report was written in the original repository. No implementation, progress, phase document or unrelated work was changed; no commit, push or later-phase work was performed.
