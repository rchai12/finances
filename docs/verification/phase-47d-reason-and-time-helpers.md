# Verify Phase 47d: shared proposal reasons and repository UTC time

Spec: `docs/phases/phase-47d-reason-and-time-helpers.md`.
Read AGENTS.md and docs/phase-conventions.md. Independently judge the current diff;
write only `docs/reviews/phase-47d-reason-and-time-helpers.md`.

Two shared helpers replace nine reason validators and eight private clocks plus
the borrowed transfer clock. Given artifacts: one nine-case unit file and an
exact diff to thirty earlier clock-patched test files. All other tests are
coder-owned. No migration, dependency, new permission or reference build.

## Starting baseline

Confirm predecessor 47c PASS at 4426 tests and committed implementation/review
69294ab. Confirm finalized spec/guide are committed and match HEAD in the coder's
isolated planning-baseline checkout; read status/diff and progress before writing
this report. Missing implementation is a baseline blocker, not a functional FAIL.
Confirm finances.__file__ resolves to the reviewed src. Preserve unrelated editor
settings in the original workspace. Before transporting a verdict, compare the
reviewed source/tests with the delivered bytes; do not approve stale code.

## 1. Gates

Run the four Acceptance steps in the spec exactly and in order. First:
`.venv/bin/python scripts/check.py --first core,mcp,web,cli --workers 4`.
Require at least 4435 full-suite passes plus coder cases, clean section table,
mandatory critical coverage and final `All checks passed.`. Immediately run the
specified helper coverage report, requiring both files and TOTAL at 100% with no
missing line/branch. Then nine given passes, given bytes/diff equality and scope.
A serial override requires the recorded resource reason. Keep one coverage run
per checkout. Resolve localhost sandbox failures through execution permission;
preserve failed and permitted outcomes without weakening tests. No real samples.

## 2. Scope

Only explicit Scope paths and this report. Existing-test changes equal the
embedded thirty-file diff. Compare assertions and test identities, not just
counts. Fixtures outside that diff, ORM defaults, migrations, domain inventory,
web/auth clocks and application adapters remain unchanged. No _now compatibility
wrapper or direct captured utc_now function import in the scoped repositories.
No reason truncation, validation reordering or timestamp precision changes.

## 3. Requirement checklist

| Id | Evidence and deciding observation |
|---|---|
| R1 | Given accepted/refused reason cases cover 1/200/201, blank Unicode whitespace and collapse before length; full cleaned value returned with exact refusal text. |
| R2 | All ten public writers in sentinel/precedence matrix actually call the helper once with original reason before DB/clock; nine creation-site marker cases store helper result. No copied reason validator remains. |
| R3 | Given test_utc_now_reads_aware_utc_each_time checks UTC argument, distinct reads, identity and microseconds. No local calendar dependency/cache. |
| R4 | Given shared audit clock case; creation and event matrices reach all fifteen call sites in all nine modules; source inventory shows no private clocks/captured function aliases. |
| R5 | Persisted strict event sequences: category acceptance three reads, decline two, advice creation/dismissal one each, finding set two, finding acceptance four. Fresh loaded data is aware UTC and exact; before/after actions/text unchanged. |
| R6 | Exact thirty-file diff and nine-case given block; all prior test identities/assertions preserved, full suite and facade pins pass. Notes creation times and dismissal semantics retain expected values. |

Require a named test for every Tests to write bullet. Fixtures must reset the
clock after setup and use valid synthetic entities: an invalid reason/target
case alone cannot prove successful persistence or use of the helper result.

## 4. Probe

None. Helper boundary tests, complete caller matrices, and strict persisted event
sequences provide independent kinds of evidence without another validator/clock
implementation. No new search gate is specified; manually inspect named sources.

## 5. Spot checks

Mutate only a fresh disposable copy of reviewed source/tests; verify import
provenance, restore each scratch mutation before the next, never the reviewed
checkout. Full given ids below start with
`tests/unit/test_proposal_helpers.py::`.

| Exact mutation | Deciding given test and input | Correct | Broken |
|---|---|---|---|
| clean_reason: use reason.strip() in place of collapse_ws | test_clean_reason_accepts_cleaned_text[collapse], embedded tabs/newline/NBSP | ACME reason here | interior whitespace remains |
| clean_reason: validate raw length before cleaning | test_clean_reason_accepts_cleaned_text[cleaned-limit], 200 x with outer whitespace | 200 x accepted | ValueError |
| clean_reason: upper bound <200 instead of <=200 | test_clean_reason_accepts_cleaned_text[limit] | 200 x accepted | ValueError |
| utc_now: call datetime.now() without UTC | test_utc_now_reads_aware_utc_each_time, controlled datetime.now | two calls with UTC | call argument assertion fails even on a UTC host |
| audit.record_change: restore datetime.now(UTC) at the event call site | test_audit_reads_shared_clock_per_event, two controlled microsecond timestamps | first then second, two clock reads | actual timestamp, identity mismatch |

Trace each mutation through the final code. The reason inputs isolate their
named rules; the 200-x cleaned input passes a correct bound and the unpadded
limit case isolates inclusivity. The datetime mock returns fixed aware values
even when the wrong argument is used, so its argument assertion is essential.
The audit test patches conversion only, leaving real AuditRow construction and
two actual record_change calls; a private timestamp cannot satisfy identity.
These are rule checks, not permission to change given tests or a reference build.

## 6. Reasonable variations and exclusions

Reason imports/aliases and private local names are coder choices. Module alias
for db.time may differ, but all calls must resolve its utc_now attribute at call
time. Equal constant test patches may be deduplicated only as supplied in the
given diff. A shared timestamp captured for a whole operation is incorrect even
when equal-time fixtures let it pass. Do not demand fixture caching, new clocks
for other layers, broader date cleanup, a new facade export, or new permissions.

## 7. Progress and verdict

Report standard verdict, passed count, findings and approved deviations; distinguish
baseline, environment, spec/test and implementation defects. Preserve fresh gate
output, section table and final ten lines. Record exact diff equality, module/site
coverage and spot results. Check progress public names/count/scope and deviations.
On FAIL send requirement, observation and required result to coder; do not repair
implementation or relax the spec. No commit, push or later-phase implementation.
