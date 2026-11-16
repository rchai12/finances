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
