# Review: Phase 47a

- Verdict: PASS
- Passed: 4337
- Findings: 0
- Approved deviations: Owner-approved mixed scope in commit 9f2e5c83346ab7affd517648a62fa3e99a6629e0 and preserved untracked .vscode/settings.json (2026-11-15); unrelated work does not itself block approval.
- For the architect: Phase 47b's predecessor approval requirement is satisfied once this reassessment is committed; do not treat the historical FAIL below as the current verdict.

## Findings

None.

Parts that needed a repair: None in the implementation. The owner resolved the sole outstanding mixed-scope finding by explicit exception.

Built beyond the spec: Unrelated process/documentation changes, approved as a scope deviation; no additional application behavior.

## Reassessment (2026-11-15): authority and baseline

The owner explicitly authorized reassessment of the committed implementation, approved the unrelated process/documentation changes in `9f2e5c83346ab7affd517648a62fa3e99a6629e0` and preserved untracked `.vscode/settings.json`, and authorized updates to this report and `docs/progress.md`. This overrides the verifier's normal report-only write restriction for these two documents. It resolves only the mixed-scope gate; functional requirements remain unchanged. No unrelated work was deleted, reverted, or modified. No commit or push was made; Phase 47b was not implemented.

Inspected HEAD `9f2e5c83346ab7affd517648a62fa3e99a6629e0` against finalized spec baseline `39c11337f032c8f8da7ea9da9283c71f54693df7`, including intervening process/planning commits `77281971854fb808a86e259a8c3866df228439a7` and `5a300c9d010d648c7d8a9fbc8392b3891d809955`. The Phase 47a spec and guide still match their committed baseline. At entry, `git diff HEAD` was empty and `git status --short --untracked-files=all` listed only `.vscode/settings.json`. The implementation and review are now committed, unlike the original review's working-tree condition.

The existing review explicitly had one finding, Scope, and stated that no functional repair was identified. Fresh inspection confirms the application diff consists only of the six scoped production modules and four new test files. No earlier test, migration, dependency declaration, test configuration, matching rule, or MCP module changed. The given test file matches the spec's Python block byte-for-byte. The progress addition is the scoped phase entry. The unrelated paths in the implementation commit are `.claude/hooks/no_reference_build.py`, `.claude/skills/phase-architect/SKILL.md`, `.claude/skills/phase-architect/templates/guide.md`, `.claude/skills/phase-architect/templates/spec.md`, `.claude/skills/phase-implementer-verifier/SKILL.md`, `docs/codebase-audit.md`, and `docs/handoffs/finances.md`. They and the editor setting are accounted for by the owner exception, rather than attributed to Phase 47a or silently treated as in scope. Earlier process and Phase 47b planning commits were inspected separately and left untouched.

## Historical evidence reuse decision

The prior review explicitly records 4,337 passing tests, 100% service coverage, seven passing given cases, and three successful mutation detections. Those observations remain preserved below. Its requirement-to-test mapping was checked against the current source and assertions and remains applicable to the same named cases.

The prior review does not include a source/test byte manifest or an installed-dependency and relevant-environment fingerprint. A clean current tracked tree and unchanged dependency declarations cannot prove that the earlier tested uncommitted bytes, installed packages, interpreter, and relevant environment all still match. Consequently the conditional authorization for document-only evidence reuse was insufficient to establish every required condition. The prior 4,337-test result is historical corroboration, not the basis for the current functional verdict: all applicable executable gates and scratch mutation checks were run afresh.

## Fresh verification evidence

Ran from the repository root with its existing `.venv/bin/python`, Python 3.12.16 on macOS; `finances.__file__` resolves to this workspace's `src/finances/__init__.py`. Fingerprinted 630 tracked source/test/script/config/spec/guide files and inventoried 61 installed distributions before verification; all fingerprints and installed version entries still matched afterward. Source, tests, configuration and dependencies were not changed during this reassessment. Synthetic tests only; no real statements, real database, real Keychain or aggregator were accessed.

The initial sandboxed check exited 1: its section-first stage passed 2,752 cases; its full run reported `4327 passed, 10 errors in 281.35s`, all ten errors being `PermissionError: [Errno 1] Operation not permitted` at synthetic transport fixtures binding localhost. The section table identified sync as `274 passed, 10 failed` and supplied `.venv/bin/python scripts/check.py --section sync`; critical coverage did not run. Requested execution permission and reran the exact required full gate with localhost binding permitted. No test was weakened or skipped.

| Fresh command | Observation |
|---|---|
| `.venv/bin/python scripts/check.py --first web,cli,core` (permitted rerun) | Section-first `2752 passed in 139.10s`; full `4337 passed in 278.12s (0:04:38)`; no failures, skips, xfails or warnings summary; `All checks passed.`; exit 0 |
| `.venv/bin/python -m coverage report --include="*/finances/categorize/service.py" --fail-under=100` | Immediately after successful check: `TOTAL 88 0 22 0 100%`; exit 0 |
| `.venv/bin/python -m pytest tests/integration/test_web_pair_after_rules.py --no-cov` | `7 passed in 1.91s`; exit 0 |
| `git grep -n -F 'categorize(session)' -- src/finances/web/routes/categories.py src/finances/web/routes/transactions.py src/finances/web/routes/statements.py src/finances/web/routes/sync.py` | No output; exit 1 (expected no matches) |
| Scope and given-file inspection | Given bytes identical; only authorized reassessment documents modified, preserved `.vscode/settings.json` untracked; owner exception resolves mixed scope |

Fresh full-run section table:

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts        66 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           198 passed    0 failed    0 skipped
  parsers       853 passed    0 failed    0 skipped
  sync          284 passed    0 failed    0 skipped
  core         1404 passed    0 failed    0 skipped
```

Fresh check's last ten lines:

```text
  core         1404 passed    0 failed    0 skipped
== critical coverage

Summary:
  lint: passed
  format: passed
  tests (web,cli,core): passed
  tests: passed
  critical coverage: passed
All checks passed.
```

Fresh scratch-only mutation checks copied source/tests/config outside the repository and confirmed import provenance inside that scratch source using `PYTHONPATH`. Independently omitting pairing after rule creation, bulk clear, and alias deletion caused the corresponding `[rule-add]`, `[bulk-clear]`, and `[alias-delete]` given cases to fail at `assert find_transfer_pair(session, 1) is not None` (each exit 1). The scratch copy was removed; the reviewed tree was never mutated. No independent probe is specified.

Fresh inspection and passing tests confirm R1–R7 using the actual test names in the historical requirement table below: operation order/session/result identity and error propagation; unchanged CLI result/text/session boundary; all seven web writes and redirects; inert submissions and the four accepted kinds; one pairing call on existing import/sync/split paths; persisted rollback of write/category/pair/audit state; repeated and excluded pairing behavior and spending exclusion. Acceptance ordering, pair-only unshare/explicit pairing, CLI import/sync boundaries, privacy, schema and capability surfaces remain unchanged. Existing import/sync operation boundaries are preserved as required by R5; no broader transaction redesign was introduced.

Full fresh logs are local temporary evidence: `/tmp/phase47a-reassessment-check.log`, `/tmp/phase47a-reassessment-check-permitted.log`, and `/tmp/phase47a-reassessment-spot-{rule-add,bulk-clear,alias-delete}.log`. The gate digest above remains in this report independently of temporary-log retention.

## Result and handoff

PASS: no functional finding remains, and the sole historical delivery finding is resolved by the owner's explicit scope exception. Phase 47b's predecessor approval requirement is satisfied once this reassessment is committed. This statement does not implement or verify Phase 47b. The owner retains control of committing this reassessment.

## Historical review retained verbatim

The following is the prior review, including its then-current FAIL, gate output, findings and handoff. These describe the earlier review state and are superseded only by the reassessment above.

# Review: Phase 47a

- Verdict: FAIL
- Passed: 4337
- Findings: 1
- Approved deviations: None
- For the architect: Baseline documents are now committed in 39c1133; resolve the remaining mixed-scope status gate before approval. No functional repair was identified.

## Findings

Scope | docs/phases/phase-47a-categorize-and-pair.md:34 | expected git status limited to the 11 Scope paths plus the authorized review artifact | found 21 status entries: the 11 phase paths, this report, and nine unrelated entries; the executable spec and guide are now committed in 39c1133, but the literal scope gate remains unmet and no owner-approved exception is evidenced.

Parts that needed a repair: None in the implementation; scope acceptance remains unresolved. The previous uncommitted-document condition is resolved.

Built beyond the spec: No additional application behavior; unrelated working-tree changes are present and cannot be attributed to the coder from this diff alone.

## Baseline and scope condition

Re-reviewed against HEAD `39c1133` (`Finalize Phase 47a spec and verification baseline`). The executable spec and guide now match their committed versions; the previous finding's uncommitted-document component is resolved. Read the current `git status --short`, `git diff HEAD`, required documents, and four new test files before writing this update.

The phase implementation contains exactly the six production files, four new tests, and appended phase entry listed in Scope. No earlier test, migration, dependency, matching rule, or MCP module changed. The given file is byte-for-byte identical to the spec's Python block. No implementation defect was found.

The nine remaining unrelated status entries are `.claude/hooks/no_reference_build.py`, `.claude/skills/phase-architect/SKILL.md`, `.claude/skills/phase-implementer-verifier/SKILL.md`, `.agents/`, `.claude/skills/phase-architect/history.md`, `.claude/skills/phase-architect/templates/`, `.vscode/`, `docs/codebase-audit.md`, and `docs/handoffs/`. They were also present at the previous review. Their presence does not establish that the coder changed them. They were preserved throughout review.

The current status has 21 entries, including this existing review artifact: 11 phase Scope entries, nine unrelated entries, and the report. The historical progress entry's count of 23 describes the coder's earlier tree, before the baseline commit, rather than the current review status. The guide requires this mixed-tree condition reported separately; it remains the sole delivery finding, not a functional failure.

## Gate evidence (2026-11-15)

Ran all gates afresh from the repository root in the guide's order, using loopback permission for the known existing transport-test restriction. The exact required check passed on this review run, with no warnings summary, skips, xfails, or failures. No real database, statement samples, Keychain, or aggregator was accessed. The prior review's sandbox failures are historical evidence, not results of this fresh run.

| Command | Observed |
|---|---|
| `.venv/bin/python scripts/check.py --first web,cli,core` | `4337 passed in 273.50s (0:04:33)`; `All checks passed.`; exit 0 |
| `.venv/bin/python -m coverage report --include="*/finances/categorize/service.py" --fail-under=100` | `TOTAL 88 0 22 0 100%`; exit 0; run immediately after the successful check |
| `.venv/bin/python -m pytest tests/integration/test_web_pair_after_rules.py --no-cov` | `7 passed in 0.84s`; exit 0 |
| `git grep -n -F 'categorize(session)' -- src/finances/web/routes/categories.py src/finances/web/routes/transactions.py src/finances/web/routes/statements.py src/finances/web/routes/sync.py` | No output; exit 1, as expected for no matches |
| `git status --short` | 21 entries including the existing review artifact; nine unrelated entries keep the literal scope gate unmet |

Full-run section table:

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts        66 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           198 passed    0 failed    0 skipped
  parsers       853 passed    0 failed    0 skipped
  sync          284 passed    0 failed    0 skipped
  core         1404 passed    0 failed    0 skipped
```

Last ten lines of the successful check:

```text
  core         1404 passed    0 failed    0 skipped
== critical coverage

Summary:
  lint: passed
  format: passed
  tests (web,cli,core): passed
  tests: passed
  critical coverage: passed
All checks passed.
```

## Requirement and coder-case evidence

Test names below are actual collected cases; all passed. Assertions check results or persisted behavior, rather than merely executing coverage lines.

| Requirement / case | Deciding evidence |
|---|---|
| R1: order, same session, exactly once, result identity | `tests/unit/test_categorize_and_pair.py::test_order_session_and_result_identity` |
| R1: exception identity and no commit/rollback | `tests/unit/test_categorize_and_pair.py::test_errors_propagate_without_session_management[categorize]` and `[pair]` |
| R1: standalone categorization preserved | `tests/integration/test_web_pair_after_rules_more.py::test_standalone_categorize_leaves_pair_waiting` |
| R2: CLI result and unchanged displayed text | `tests/integration/test_web_pair_after_rules_more.py::test_cli_adapter_result_and_text`; inspected unchanged session boundary in `categorize_all` |
| R3: seven writes, stored pair, exact redirects | `tests/integration/test_web_pair_after_rules.py::test_action_pairs_waiting_transfer[rule-add]`, `[rule-edit]`, `[rule-delete]`, `[alias-add]`, `[alias-delete]`, `[bulk-clear]`, `[single-clear]` |
| R4: inert submission, conditional acceptance, categorization counts, stored pair | `tests/integration/test_pair_after_acceptance.py::test_submission_is_inert_acceptance_categorizes_and_pairs[rule]`, `[alias]`, `[rule_edit]`, `[rule_delete]` |
| R4: unrelated accepted kind performs neither operation | `tests/integration/test_pair_after_acceptance.py::test_other_acceptance_kind_does_not_categorize_or_pair` |
| R4: acceptance ordering and result shape | Existing `accepting_order` iteration and `Accepted` construction are unchanged; full previous suite passes |
| R5: import, sync, split clear pair once | `tests/integration/test_web_pair_after_rules_more.py::test_existing_web_operations_pair_once[import]`, `[sync]`, `[split]`; stubs avoid network and real Keychain |
| R5: pair-only operations preserved | Unchanged source; existing `tests/integration/test_pairing_gaps.py::test_unsharing_on_the_web_pairs_the_transfer` and `::test_unsharing_in_the_terminal_pairs_the_transfer` pass |
| R6: initiating write, categorization, pair and audits roll back | `tests/integration/test_web_pair_after_rules_more.py::test_pair_failure_rolls_back_rule_categories_pairs_and_audit`; callback creates a pair before raising, and fresh-session snapshot equals pre-write state |
| R6: CLI import/sync boundaries preserved | No diff to their modules; CLI adapter retains its existing `session_scope` |
| R7: repetition, rejected/confirmed pairs, splits, shared movement and manual decision | `tests/integration/test_web_pair_after_rules_more.py::test_repeated_clear_preserves_pairing_rules_and_report[none]`, `[rejected]`, `[confirmed]`, `[split]`, `[shared]`, `[manual]` |
| R7: automatically paired transfers excluded from spending | Same test `[none]` asserts spent cents 0, transfers 2, and no report lines |
| R7: previous behavior, privacy and unchanged capability/schema surface | Full 4337-test run and production diff inspection; no network/logging/schema/money/matching/MCP changes |

Manual categories remain protected from recategorization; the manual-case test correctly retains the existing pairing behavior, which may pair manually categorized movements. No new exclusion rule was invented.

## Scratch-only spot checks

Copied source/tests into a disposable directory outside the repository and selected that source using `PYTHONPATH`. For each mutation independently, replaced only the named route's shared operation with standalone categorization, retaining the initiating write. Each named given case failed at `assert find_transfer_pair(session, 1) is not None` because the pair was absent; each unmodified case passed in the seven-case gate.

| Mutation | Deciding given case | Result |
|---|---|---|
| Omit pairing after rule creation | `test_action_pairs_waiting_transfer[rule-add]` | Failed for absent pair; exit 1 |
| Omit pairing after bulk category clear | `test_action_pairs_waiting_transfer[bulk-clear]` | Failed for absent pair; exit 1 |
| Omit pairing after alias deletion | `test_action_pairs_waiting_transfer[alias-delete]` | Failed for absent pair; exit 1 |

Deleted the scratch copy afterwards. No independent probe was specified. This report is the sole repository artifact written during review.

## Handoff to coder / architect

Scope requirement: status must contain only phase Scope paths, with the authorized review artifact accounted for separately. Observed: nine unrelated entries remain alongside the phase paths and report. Required: establish a reviewable tree satisfying the scope gate, or obtain an explicit owner-approved exception for those preserved entries. Do not discard unrelated work. The baseline documents are now committed; no application-code repair is requested.
