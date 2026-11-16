# Review: Phase 47d

- Verdict: PASS
- Passed: 4514
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Baseline, scope and provenance (2026-11-16)

Reviewed committed delivery `949e31d146311dee2c2e9c514201471c9b7a8508` against finalized planning baseline `61b8e90c5bde8d04e764fb918c87f61c3bae60d6`. Predecessor Phase 47c implementation and PASS review are committed at `69294abde1d9622c5cda52bc314888e11aef3bc7`; N = 4426. Phase 47d's spec and guide match their committed planning versions. Read project instructions, architecture, conventions, testing strategy, handoff procedure, phase spec/guide, remediation design section 47d, progress entry, full source diff, new tests and given migration.

The original workspace was `/Users/richardxiaohuachai/Desktop/Projects/finances`; entry tracked diff was empty and status showed only unrelated untracked `.vscode/settings.json`. Preserved it. Cloned the committed delivery to `/var/folders/2d/386g2_8d69915k8_pvkhdq3c0000gn/T/finances-47d-review-mfj8gecz/checkout`, linked the existing venv and excluded only that symlink locally. The review clone was clean before gates. Each Python invocation there used explicit `PYTHONPATH` pointing at its src, and the pre-gate import check resolved `finances.__file__` inside the review clone. This establishes the actual tested source rather than relying on the shared venv's editable install.

The implementation commit changes exactly the 45 Scope paths: eleven production files, thirty supplied earlier-test migrations, three new test files and progress. No other production/test/configuration path, migration, dependency, adapter, ORM default, web/auth clock or local-calendar clock changed. No repository facade export or permission was added. Two public helpers are `finances.domain.proposals.clean_reason` and `finances.db.time.utc_now`.

Compared the entire embedded thirty-file diff against `git diff 61b8e90 HEAD -- <those thirty paths>`: exact text equality. Also compared all assertion ASTs before/after in every migrated file: identical. The supplied edits preserve test identities/parameterizations and all expected rows/messages; no removal, rename or assertion weakening. The new given file is byte-for-byte identical to its Python block. Notes fixture creation timestamps remain distinct, later dismissal has the supplied fallback, and notes_more switches from KEPT to GONE after setup exactly as specified.

Before transporting this verdict, all 1,009 tracked original-workspace files still matched the isolated reviewed bytes and their pre-gate SHA-256 manifest. Manifest retained at `/tmp/phase47d-review-manifest.json`. The original tracked diff remained empty. Only this review report is written in the original repository; unrelated editor settings remain untouched.

## Fresh independent gates

Ran the guide's acceptance commands sequentially from the isolated root with `.venv/bin/python` and explicit clone PYTHONPATH. Python 3.12.16, pytest 9.1.1, pytest-xdist 3.8.0 and pytest-cov 7.1.0. Four local workers, no delegated agents, one coordinated coverage-producing job in this checkout. Requested permission up front for the established synthetic localhost-binding restriction; the permitted run passed. This review had no failed sandbox attempt. The coder's recorded baseline/acceptance outcomes are historical and do not replace these fresh results.

| Command | Fresh result |
|---|---|
| `.venv/bin/python scripts/check.py --first core,mcp,web,cli --workers 4` | exit 0; selected-first `3093 passed in 75.21s`; full `4514 passed in 108.01s (0:01:48)`; no failures, skips, xfails or warnings summary; final `All checks passed.` |
| `.venv/bin/python -m coverage report --include="*/finances/domain/proposals.py,*/finances/db/time.py" --fail-under=100` | immediately after check, exit 0; time.py `3 0 0 0 100%`; domain/proposals.py `104 0 30 0 100%`; `TOTAL 107 0 30 0 100%`; no missing locations |
| `.venv/bin/python -m pytest tests/unit/test_proposal_helpers.py --no-cov` | exit 0; exactly `9 passed in 0.05s` |
| Status/diff/scope/given inspection | isolated status and tracked diff empty (implementation is committed); baseline-to-delivery diff contains exactly the 45 Scope paths; all earlier tests equal supplied diff and given bytes equal block |

Overall coverage is 99.98%, above the configured 85%; every mandatory critical-module gate passes. Both targeted helper files and TOTAL are 100% with no missing line/branch. Synthetic data only; no real samples, real database, real Keychain, aggregator or dependency installation. No new search gate or independent probe is specified. Full output retained at `/tmp/phase47d-review-check.log`.

Full-run section table:

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           198 passed    0 failed    0 skipped
  parsers       853 passed    0 failed    0 skipped
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
  tests (core,mcp,web,cli): passed
  tests: passed
  critical coverage: passed
All checks passed.
```

## Requirement and coder-case evidence

| Requirement | Deciding tests and observations |
|---|---|
| R1 | Given `test_clean_reason_accepts_cleaned_text[one/collapse/limit/cleaned-limit]` and `test_clean_reason_refuses_without_echo[empty/blank/long]` assert full normalized values and exact refusal across Unicode whitespace and 1/200/201 limits. Source calls existing collapse_ws before cleaned-length validation, with no truncation or extra rule. Domain imports remain inside domain. |
| R2 | `test_writer_matrix_covers_all_ten_public_entries` pins complete inventory. `test_every_writer_delegates_original_reason_first` uses a distinct ValueError subclass instance at the actual helper binding, original raw reason, invalid surrounding inputs, one helper call, identity propagation and zero session/clock calls. `test_invalid_reason_precedes_other_refusals` covers blank/long reasons and edit/delete plus rename/delete forms; `test_valid_reason_preserves_next_refusal` checks exact historical next errors and no write/clock. `test_creation_sites_store_shared_reason_and_timestamp` uses valid migrated entities and helper-return markers stored verbatim at every creation site. All nine inline copies are removed. |
| R3 | Given `test_utc_now_reads_aware_utc_each_time` patches datetime.now with two distinct microsecond timestamps and asserts returned identity plus both explicit UTC arguments. db/time.py returns datetime.now(UTC) directly on every call; no cache, DB or local-calendar dependency. |
| R4 | Given `test_audit_reads_shared_clock_per_event`, full creation/event matrix, `test_all_fifteen_repository_clock_sites_use_module_lookup`, and source diff cover all fifteen call sites across nine modules. Every call resolves db_time.utc_now dynamically; all eight private _now definitions and transfers' lazy clock import are removed. No function capture, compatibility wrapper, import-time read or operation-wide timestamp reuse. |
| R5 | Strict persisted event tests below prove distinct reads, event order, literal audit content and aware UTC/microseconds after fresh-session conversion. Production diff changes clock lookups at original positions only; no transaction management or surrounding validation changes. |
| R6 | Exact thirty-file diff/given-byte equality and assertion AST comparison, preserved notes semantics, unchanged inventories and passing full suite/facade/privacy/permission tests. All previous identities and assertion expectations remain intact. |

Caller tests contain 49 cases (12 sentinel variants, 24 invalid-reason variants, 12 valid-reason next-refusal variants and inventory). Creation/event/inventory tests contain 30 cases (24 creation variants, five event sequences and clock inventory). With nine given cases: 4426 + 49 + 30 + 9 = 4514, matching progress and the fresh run. New test files remain core under the unchanged section fallback.

Creation matrix reaches ten public writers and all nine creation sites, including transfer and not-transfer, rule edit/delete and category rename/delete. Each runs with valid synthetic bases and resets the shared clock after setup. Cleaned reasons and distinct helper-return marker cases are checked in returned objects and freshly loaded proposals with exact UTC microsecond timestamps. Category-change dry runs retain their existing rolled-back audit read; the creation test explicitly expects two clock calls there rather than hiding or removing it.

All fifteen timestamp sites are accounted for: proposals six (three proposal creation sites, acceptance, decline and advice creation); transfers one; new_categories two; rule_changes one; category_changes one; finding_proposals one; audit one; advice dismissal one; findings one. Source inspection complements runtime persistence assertions rather than replacing them.

Strict event tests install their controlled clocks after fixture/setup writes:

- `test_category_acceptance_keeps_three_distinct_clock_reads`: changed assignment audit at T1, decided_at at T2, acceptance audit at T3; exactly three reads; literal before/after text and aware freshly loaded values.
- `test_decline_keeps_two_distinct_clock_reads`: decided_at T1, decline audit T2; exactly two reads and exact stored text/status.
- `test_advice_creation_and_dismissal_read_once_each_without_audits`: creation T1, dismissal T2, unchanged audit inventory; repeated-dismissal refusal consumes no third read; returned and reloaded UTC values checked.
- `test_direct_finding_status_reads_for_status_then_audit`: set_at T1, finding_handled audit T2; exactly two reads and literal finding text.
- `test_accept_finding_status_keeps_four_event_times`: set_at T1, finding audit T2, decided_at T3, proposal audit T4; exactly four reads, fresh-session UTC conversion and literal audit action/text sequence.

The strict side-effect clocks reject excess reads; distinct values detect timestamp reuse and reordered events. Assertions check useful behavior and persisted output, not merely line execution.

## Fresh scratch-only spot checks

Copied reviewed source/tests/config into a fresh disposable directory outside both checkouts, confirmed finances import provenance in scratch src, and applied each exact mutation independently. Restored each scratch file before the next check; reviewed source was never mutated. Every named given case was run with `--no-cov` and failed as required:

| Mutation | Deciding given case | Fresh broken observation |
|---|---|---|
| clean_reason uses reason.strip() | `test_clean_reason_accepts_cleaned_text[collapse]` | exit 1; normalized-value assertion fails on interior whitespace |
| validate raw length before cleaning | `test_clean_reason_accepts_cleaned_text[cleaned-limit]` | exit 1; incorrect ValueError on padded 200-character input |
| upper bound excludes 200 | `test_clean_reason_accepts_cleaned_text[limit]` | exit 1; incorrect ValueError on exactly 200 characters |
| utc_now calls datetime.now() without UTC | `test_utc_now_reads_aware_utc_each_time` | exit 1; explicit UTC call-argument assertion fails despite mock returning aware values |
| audit event reads datetime.now(UTC) directly | `test_audit_reads_shared_clock_per_event` | exit 1; returned event timestamp fails controlled identity assertion |

Unmodified given cases pass in the fresh nine-case gate. No extra defense masks these mutations and no test input or assertion was changed. Scratch directory cleaned up; logs retained as `/tmp/phase47d-review-spot-{collapse,raw-length,inclusive,utc,audit}.log`.

## Progress and result

Progress accurately records N/final/given counts, both public helper names, 45 scoped paths, thirty exact earlier-test migrations, all nine reason and fifteen timestamp sites, and no deviations. Its acceptance timing (94.05s) is coder history; fresh independent full-suite time is 108.01s. No baseline, environment, specification/test or implementation blocker remains.

PASS for the exact reviewed commit and bytes identified above. Only this report is written in the original repository. No implementation, progress, phase document or unrelated work was changed; no commit, push or later-phase implementation was performed.
