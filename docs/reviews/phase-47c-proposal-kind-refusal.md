# Review: Phase 47c

- Verdict: PASS
- Passed: 4426
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Baseline, isolation and provenance (2026-11-16)

Independently reviewed the uncommitted delivery against planning baseline `cbcfeea8850dd49c307b6f7184d7ed58960ba569`. Phase 47b is approved and committed: implementation `2d476ac1f925a64600f44b6ebdffb5256b7e2b99`, PASS review `3edb1821d90fd09404432e795f116183c2618ece`, N = 4371. The finalized Phase 47c spec and guide match their committed versions. Read the required project rules, architecture, conventions, spec, guide, handoff procedure, testing strategy, remediation design section 47c, progress entry, production diff and all three new test files, plus existing proposal rules/refusal assertions.

Confirmed the actual original checkout is `/Users/richardxiaohuachai/Desktop/Projects/finances` at `cbcfeea`. Entry status contained the two modified scoped files (`docs/progress.md`, `src/finances/db/repositories/proposals.py`), three new scoped test files, and unrelated untracked `.vscode/settings.json`. Read `git diff HEAD` before writing. Preserved unrelated editor work.

Created a fresh local clone of the committed baseline at `/var/folders/2d/386g2_8d69915k8_pvkhdq3c0000gn/T/finances-47c-review-4ao_wohl/checkout`, then copied only the five explicit Scope paths. Linked the existing project venv and excluded only that symlink in the clone's local Git exclude. Isolated status contains exactly the five Scope paths; no missing or extra implementation paths. Every isolated Python command used `PYTHONPATH` pointing at this clone's src. Explicit import check resolved `finances.__file__` to that clone's `src/finances/__init__.py` before the guide gates.

After verification and before transporting this verdict, compared all 1,002 tracked and new delivery files byte-for-byte between the original and isolated checkout: all match. The production file SHA-256 is `8d7339d72ed497a5575295cbe18570d8f1ef8584111eb07c2f5df0a00a2729db`; full per-file manifest is `/tmp/phase47c-review-manifest.json`. The given test file is byte-for-byte identical to the spec's Python block. No earlier test, fixture, domain inventory/text helper, migration, dependency, adapter, configuration or script changed. The production module remains below its 400-line cap (372 lines). All three new tests belong to core via the unchanged fallback.

## Fresh independent acceptance

Ran the guide's acceptance steps sequentially from the isolated root, with its existing `.venv/bin/python` and explicit clone PYTHONPATH. Python 3.12.16; pytest 9.1.1; pytest-xdist 3.8.0; pytest-cov 7.1.0. Used four local workers, with only one coverage-producing run in this checkout and no delegated agents or concurrent coverage jobs from this review.

Requested execution permission for the established localhost-binding restriction before the full check. The permitted check succeeded; this review had no failed sandbox attempt. The progress entry's coder sandbox failure (ten transport-fixture bind errors) and successful permitted baseline are historical environment evidence, not fresh failures or implementation defects. No dependency installation, real statements, real database, real Keychain or aggregator was used. These results are independent runs, not reuse of coder acceptance evidence.

| Command | Fresh observation |
|---|---|
| `.venv/bin/python scripts/check.py --first core,mcp,web,cli --workers 4` | exit 0; selected-first 3005 passed; full `4426 passed in 93.75s (0:01:33)`; no failures, skips, xfails or warnings summary; `All checks passed.` |
| `.venv/bin/python -m coverage report --include="*/finances/db/repositories/proposals.py"` | immediately after successful check; exit 0; `TOTAL 205 0 104 0 100%`; no missing locations |
| `.venv/bin/python -m pytest tests/unit/test_proposal_dispatch.py --no-cov` | exit 0; `4 passed in 0.03s` |
| `git status --short --untracked-files=all` and `git diff HEAD` | isolated tree contains exactly the five scoped paths; original additionally retains unrelated editor setting; reviewed bytes equal delivery |

All new guard and terminal fallback lines/branches are covered. There are no uncovered new refusal branches to explain. Overall configured coverage is 99.98% (above 85%), and all mandatory critical modules pass. No artificial 100% target was required for this noncritical module; the measured result happens to be 100%. No search gate, migration check or independent probe is specified.

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
  core         1459 passed    0 failed    0 skipped
```

Last ten lines:

```text
  core         1459 passed    0 failed    0 skipped
== critical coverage

Summary:
  lint: passed
  format: passed
  tests (core,mcp,web,cli): passed
  tests: passed
  critical coverage: passed
All checks passed.
```

Full synthetic acceptance output is retained at `/tmp/phase47c-review-check.log`.

## Requirement and coder-case evidence

| Requirement | Deciding evidence and observation |
|---|---|
| R1 | Given `test_unsupported_kind_refuses_without_mutation[accept-unknown]` and `[stale-unknown]` assert the exact constant error, unchanged row and zero session/writer/delegate calls. `test_unknown_domain_proposal_refuses_without_queries` uses a genuine domain Proposal; `test_unknown_acceptance_refuses_before_dependency` makes waits_for return 99 and proves the unsupported error wins without calling it. `_open_row` remains before the new acceptance guard, preserving missing/non-open precedence. |
| R2 | Source has explicit CATEGORY acceptance and CATEGORY / TRANSFER / NOT_TRANSFER staleness branches, with constant terminal refusals. Given `[accept-future]` extends both inventory bindings and stubs staleness false, independently reaching acceptance's own terminal fallback; `[stale-future]` reaches the staleness terminal refusal. Neither falls through to category/pair behavior. |
| R3 | All four given cases assert unchanged status/time and no writer, audit or session calls. `test_refusal_caught_inside_transaction_leaves_persisted_state[accept/stale]` retains real downstream repository writers and real migrated sessions, catches inside a transaction that then commits, and compares assignments, pairs, rejections, audits and proposal rows in a fresh session. Rollback cannot hide mutations. No flush/commit/rollback was added to refusal paths; caller transaction ownership is preserved. |
| R4 | `test_matrix_inventory_is_complete` equates both matrix key sets to all twelve KINDS. `test_acceptance_dispatches_exactly_one_handler` covers all twelve: exact intended writer/arguments, no other writer, dependency-before-staleness order, result shape, accepted timestamp/status, one flush and exact audit call. Lazy handlers are patched at their defining modules. `test_staleness_delegates_without_writes` covers both booleans for all ten delegated kinds, exact arguments and no unintended delegate/write/session call. RULE and ALIAS are covered separately as below. Existing KINDS/proposal_text pins are unchanged and pass. |
| R5 | `test_supported_decisions_persist_with_audit[category/transfer/not_transfer]` verifies real manual category, confirmed pair or rejection, no unintended other decisions, persisted accepted status/timestamp and proposal_accepted audit. `test_missing_and_decided_refuse_before_dispatch[missing/accepted/declined]` checks exact historical refusal text and unchanged persisted snapshot. `test_open_dependency_refuses_before_staleness` checks exact parent refusal, zero staleness invocation and unchanged snapshot. Full previous suite and all boundary sections pass. |

The five RULE cases in `test_rule_staleness_preserves_category_and_dependency_checks` cover existing rule, missing category, group-only category, valid leaf with dependency false and valid leaf with dependency true. They assert category/rule arguments, short-circuit behavior, chain target_missing and no unintended delegates or writers. The two ALIAS cases in `test_alias_staleness_preserves_validation` check valid mapping and check_alias ValueError with exact mapping/source/target arguments and no unintended calls. Together with the twelve acceptance cases, twenty delegated staleness cases, inventory assertion and two unknown-seam cases, these comprise 42 coder unit cases. Nine coder integration cases complement the four given cases: 4371 + 42 + 9 + 4 = 4426.

Assertions validate outputs, arguments, mutation absence and real persisted state rather than merely exercising coverage. No unknown-kind test relies solely on a schema constraint. Existing supported validation, staleness refusal text and dependency behavior are preserved by the narrow production diff and passing previous suite. No reason/UTC cleanup, dispatch framework, new kind or permission was introduced.

## Fresh scratch-only spot checks

Copied reviewed source/tests/config into a fresh disposable directory outside both checkouts. Confirmed finances import provenance inside that scratch src. Independently applied each exact mutation, ran its named given case with `--no-cov`, and discarded the scratch directory afterward. No reviewed code was mutated.

| Exact mutation | Deciding given suffix | Fresh result |
|---|---|---|
| acceptance terminal refusal replaced with set_category_by_hand | `[accept-future]` | exit 1: required ValueError not raised |
| staleness terminal refusal replaced with pair_is_out_of_date | `[stale-future]` | exit 1: required ValueError not raised |
| unknown acceptance guard omitted, terminal refusal retained | `[accept-unknown]` | exit 1: waits_for unexpectedly called; the same terminal error alone does not satisfy the test |

The registered future input passes the inventory guard, and acceptance's given test stubs staleness false; no earlier defense masks the first two mutations. No redundant checks or ordinary validation needed removal. The third input keeps waits_for returning None and reaches terminal refusal, then fails the explicit no-dependency-call assertion. Unmodified given cases pass in the fresh four-case run. Logs are `/tmp/phase47c-review-spot-{accept-future,stale-future,accept-unknown}.log`.

## Progress accuracy and result

The coder entry accurately records baseline, isolation, scoped changes, N/final/given counts, 42 unit plus nine integration cases and no new public API. Its original acceptance timing (93.39s) is historical; this fresh run took 93.75s. Both report 4426 passes and full proposals coverage. No implementation repair is requested.

PASS for the exact reviewed bytes described above. Only `docs/reviews/phase-47c-proposal-kind-refusal.md` was written in the original repository. Implementation, phase documents, progress and unrelated work were preserved. No commit, push or later-phase implementation was performed.
