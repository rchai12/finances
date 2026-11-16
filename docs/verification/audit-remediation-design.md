# Verification plan: audit remediation design

Design: [audit-remediation-design.md](../audit-remediation-design.md).

This is the acceptance plan for staged implementation, not a PASS report or an
executable phase guide. The findings are accepted; do not repeat the audit.

## Before each part is handed to the coder

1. Confirm the predecessor's review and actual test count. Phase 46 supplies
   4,310 only for the initial baseline; never reuse that count for later parts.
2. Produce a single numbered spec and same-named verification guide. List exact
   source/test/doc paths and all changes to prior test pins. Confirm only explicitly authorized new
   dependencies or schema changes are being smuggled into a refactor.
3. Embed given tests, migrations if any, and prior-test diffs through `gen_spec.py`.
   Count collected cases and run given tests against the predecessor in a scratch
   clone. Behavior repairs must fail for their intended missing behavior;
   characterization guards may already pass. Do not implement a reference feature.
4. Give complete tests for touched critical modules, including parser helpers
   and existing pairing/spending logic if altered. Leave other explicit behavior
   cases to the coder, using descriptive filenames rather than mandatory `_more`.
5. Trace spot checks through validation and persistence. For 47c, distinguish
   schema refusal from safe dispatch; for 47f, distinguish display attribution
   from joint ownership; for 47j, distinguish lock waiting from transaction replay.
6. Validate searches with planted violations in scratch work. A grep that always
   prints nothing is not evidence. Keep probes lean and self-checked, and execute
   them outside the repository as finances conventions require.
7. Commit the intended baseline through the owner's normal process before a
   coder starts. An uncommitted baseline is a workflow defect, not a product defect.

## Required evidence per part

| Part | Deciding evidence |
|---|---|
| 47a | Each affected user action produces the eligible pair immediately; request rollback removes both initiating change and downstream effects; proposal submission remains inert |
| 47b | Serial/2/4-worker identity and coverage parity, actual timings, unchanged failure gates |
| 47c | Unknown and registered-but-unhandled kinds both refuse with no writes; explicit category/transfer paths and all existing kinds retain results |
| 47d | Cleaned-length boundaries and each writer's validation order; one substituted UTC source controls all targeted event timestamps |
| 47e | Exact line preservation including blanks/page boundaries; synthetic parser records and reconciliation unchanged |
| 47f | Complete JSON ownership matrix including a name colliding with the joint label; no duplicated tool ownership loading |
| 47g | CLI/web/MCP compatibility matrix for valid/invalid/default input and report/export parity, including error precedence |
| 47h | Complete tool/signature/schema inventory and proposal serialization matrix; access-policy tests; import-direction and size gates |
| 47i | All moved tests accounted for and assigned to correct sections; forbidden dependency rejected by the tightened guard |
| 47j | Event-coordinated two-connection lock success and exhaustion, no partial writes, settings isolation, foreign keys and read-only enforcement |

## Implementation gates

Use the exact commands in the part's executable spec. Phase 47b explicitly
permits worker/duration options and has scripts-only coverage and benchmark
evidence rules; its spec takes precedence over the generic commands below. Its first gate is
`.venv/bin/python scripts/check.py --first <sections>` with the sections in the
design table, refined to the actual change. It must finish `All checks passed.`;
every section must show zero failures, and the run must have no skips, xfails,
or warnings summary. Run the specified coverage report immediately on that
coverage data, before another coverage-producing run. Critical modules retain
100% line and branch coverage and the full suite retains its configured threshold.

Then verify exact given-file contents/counts, named searches, scope, and the
progress entry. A pure move retains test cases and assertions, not merely a
passing total. A test rename maps old node ids to new ids. Do not infer correctness
from unchanged test counts alone.

The verifier reads `git status --short` and `git diff HEAD` before writing its
report and edits only that report. Any mutation checks run in a scratch copy.
Report under `docs/reviews/<phase-spec-name>` using `phase-conventions.md`, with
requirements, observed behavior, and required result for each finding. A bad
probe/oracle or wrong given expectation returns to the architect.

## Design validation performed

The source audit was accepted as requested. Existing signatures, ownership
representation, categorization callers, period adapters, engine construction,
and test-section names were read to scope the design. No production code,
tests, live data, or services were changed or executed for this design. No
implementation gate, failing-first test, or performance claim is reported as run.
