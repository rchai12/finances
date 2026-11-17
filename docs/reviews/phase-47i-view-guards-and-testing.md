# Review: Phase 47i

- Verdict: PASS
- Passed: 4828
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Phase 47i: tighten view import guards and document testing conventions (2026-11-17)

Reviewed delivery `c0cb5178dc8772a3f1e16bbe9c538c0c28ad7d93` against committed planning baseline `af74d0cedf7fd77fd827adc505449942af32b230`. Predecessor 47h4 implementation 98188a8 and PASS review 733cbd4 are committed; N=4790. Spec and guide match their planning versions. Read project instructions, architecture, conventions, handoff, testing docs, spec/guide, progress, the full scoped diff and new tests.

The committed diff is exactly five Scope paths. No application source, dependency, configuration, section pattern or other earlier test changed. The given file matches the spec byte-for-byte. In `test_views_take_data.py`, the existing guard and stale constant are replaced and only private helpers/imports added; independent baseline AST comparison confirms existing formatting functions and tests are unchanged. Fixture values remain unchanged. The exact permission set contains only `(sync.py, finances.sync.runner, LinkRun)`; no file-wide exemption remains.

Fresh local clones `/tmp/47i-baseline` at the planning commit and `/tmp/47i-review` at delivery used the existing linked venv and their own `src` via PYTHONPATH; `finances.__file__` resolved inside each clone. Both were clean before gates. Independent byte comparison of all tracked files confirms review clone equals delivered workspace after gates. Original untracked `.vscode/settings.json` was preserved. Only this review report is written in the workspace.

## Fresh independent gates

The baseline collection was independently captured in the separate unmodified planning checkout before review acceptance. All four delivery gates ran fresh and sequentially with `.venv/bin/python`, Python 3.12.16, pytest 9.1.1 and four workers. Synthetic localhost fixture permission was used; no failed sandbox attempt, test weakening or dependency setup. Coder receipts are historical and were not reused.

| Gate | Fresh observation |
|---|---|
| Planning collection probe save | exit 0; `baseline collection ok 4790`; `FAILURES 0` |
| `scripts/check.py --first core --workers 4` | exit 0; selected core 1648 passed in 23.48s; full 4828 passed in 96.04s; every section zero failures/skips, no xfails/warnings summary; lint, format, critical coverage passed; `All checks passed.` |
| Given-only `pytest tests/unit/test_view_import_guard.py --no-cov` | exit 0; exactly 16 passed in 0.05s |
| Collection probe compare | exit 0; `retained collection ok 4790`; `new guard cases ok 38`; `FAILURES 0`; no duplicates, additions only in the two authorized new files |
| Collection self-check | planted fake predecessor node produced exit 1 and identified the missing node; fake snapshot removed |
| Scope/given audit | exact five paths, given bytes and pre-existing formatting ASTs match; section config and tracked delivery bytes unchanged |

No narrow source-coverage target applies to this test/documentation phase. Overall coverage is 99.98%; critical gates pass. Full check output `/tmp/47i-review-check.log`; baseline snapshot `/tmp/47i-baseline.json`.

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           361 passed    0 failed    0 skipped
  parsers       903 passed    0 failed    0 skipped
  sync          284 passed    0 failed    0 skipped
  core         1648 passed    0 failed    0 skipped
```

Final ten check lines:

```text
  core         1648 passed    0 failed    0 skipped
== critical coverage

Summary:
  lint: passed
  format: passed
  tests (core): passed
  tests: passed
  critical coverage: passed
All checks passed.
```

## Requirements and deciding evidence

| Requirement | Evidence |
|---|---|
| R1 | `test_exact_exception_and_existing_views` asserts the exact set and absence of STILL_LOADING. Given `test_forbidden_import_is_rejected` includes stale-file, mixed-import and wrong-file cases; `test_old_exemptions_reject_database_import` independently plants DB imports in each former exempt view. |
| R2 | Given matrix checks parent imports, nested file/scope and module forms. `test_edge_imports_are_rejected` checks nested sync path, wildcard, wrong module, forbidden alias, relative imports and submodules. `test_similar_names_and_text_are_allowed` checks boundaries and strings/comments; `test_guard_never_executes_synthetic_source` proves parsing does not execute planted code. |
| R3 | Given `test_result_type_import_is_permitted` covers exact LinkRun and alias plus analysis result types. `test_exact_exception_and_existing_views` scans all 29 actual view files; existing formatting assertions/fixtures and application source are unchanged. |
| R4 | `docs/testing.md` specifies behavior/layer naming, valid legacy *_more files, exact future move maps, retained front-end regressions, historical rather than measured <10s aspiration, testing-performance timing evidence and unchanged 85%/critical-100% coverage. It explains result-type coupling and that this bounded AST import check is not a dynamic execution sandbox. |
| R5 | Independent 4790-node baseline/4828-node comparison proves no old node lost or renamed, 38 additions only in authorized files; existing section configuration is unchanged and both new files resolve to core. Full suite and exact scope audit pass. |

Sixteen given and 22 coder cases explain 4790 -> 4828. The guard statically parses declared imports recursively, resolves supported relative/parent forms and checks root boundaries and every imported symbol. It does not establish that arbitrary dynamic code is IO-free. No application public names were added.

## Scratch-only spot checks

Each mutation ran in its own disposable clone with confirmed import provenance and unmodified given tests. Each designated case failed with exit 1 on the intended violation; reviewed source was not changed.

| Mutation | Given case | Broken observation |
|---|---|---|
| Restore blanket sync.py exemption | `test_forbidden_import_is_rejected[sync-db]` | guard did not raise for DB import |
| Allow all symbols alongside LinkRun | `test_forbidden_import_is_rejected[mixed-import]` | guard did not raise for mixed forbidden symbol |
| Scan direct files only | `test_forbidden_import_is_rejected[nested-file]` | nested SQLAlchemy import was missed |
| Deny all sync imports | `test_result_type_import_is_permitted[linkrun]` | allowed result type raised AssertionError |

Logs: `/tmp/47i-spot-{blanket,mixed,nested,deny}.log`. Scratch clones removed. No baseline, environment, specification/test or implementation blocker remains. PASS applies to the exact delivery bytes. No implementation, progress or phase documents changed; no commit or push.
