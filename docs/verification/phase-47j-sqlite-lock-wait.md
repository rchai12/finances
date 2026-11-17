# Verify Phase 47j: bounded SQLite lock waiting

Spec: docs/phases/phase-47j-sqlite-lock-wait.md. Read AGENTS.md and conventions.
Write only docs/reviews/phase-47j-sqlite-lock-wait.md.

## Baseline

47i committed/PASS67c8e7e at4828, implementationc0cb517. Finalized planning docs
committed and unchanged; expected implementation exists. Missing implementation
is baseline blocker. Inspect whole status/diff before report, record full planning
SHA and exact scoped delivery. Fresh isolated clone, linked venv, clone/src
PYTHONPATH and provenance. Preserve editor settings and compare delivery bytes
before transporting verdict. Do not reuse coder test receipts.

## 1. Gates

Run five spec acceptance steps fresh sequentially: first core selected-first full
check >=4843 plus coder, immediately config/engine coverage100, given-only15,
coder contention file and scope. All eight sections clean, critical/overall
coverage pass, no skips/xfails/warnings summary, final All checks passed.
Record full section table, final ten lines and exits. Resolve existing localhost
fixture permission failures as environment issues; never weaken tests.

## 2. Scope and requirements

Ten scope paths plus review. Given files identical. Earlier conftest/test_config
change only one new env key each; all other old tests unchanged. session_scope
and engine public signatures unchanged. Config uses established Pydantic bounds;
driver timeout obtained via get_settings even explicit URL/read_only. No retry,
replay, WAL, pool/isolation/check_same_thread or schema/dependency changes.

| Id | Evidence |
|---|---|
| R1 | default/valid/invalid/environment/isolation given and poisoned-env coder case |
| R2 | six per-connection scenarios and URL precedence, coder zero/default/max/sqlite:// and cache-change cases |
| R3 | held-writer plus pending worker, release then bounded completion, exact once-only DB result |
| R4 | held-lock50ms and zero timeout refusals, rollback/no partial rows, subsequent recovery |
| R5 | PRAGMA foreign_keys/query_only, actual FK/read-only DML refusal, existing engine tests and unchanged session_scope |
| R6 | .env and docs/database-locks.md accurate units/ranges/lifetime/limits; scope |

Name meaningful test for every Tests to write input. Assert actual SQLAlchemy/
sqlite busy error and stored contents, not only thread completion or elapsed time.
One worker failure must surface in main test. Verify finally releases holder and
joins worker even on failures. No test waits production30s or assumes exact sleep.

## 3. Probe

None separate: independently execute the actual connection/lock tests. PRAGMA
inspection plus file contention/state supply different evidence. Never run tests
against real DB or inspect real financial data. Timing used only for generous
hard completion bounds and bounded pending observation, not a performance claim.

## 4. Scratch-only spot checks

Given ids use file prefix below. No reviewed-file mutations.

| Mutation | Deciding test/input | Correct | Broken |
|---|---|---|---|
| remove lower bound | tests/unit/test_db_timeout_settings.py::test_invalid_bounds[-1] |ValidationError|accepted|
| remove upper bound | tests/unit/test_db_timeout_settings.py::test_invalid_bounds[120001] |ValidationError|accepted|
| omit ms-to-seconds conversion | tests/integration/test_db_busy_timeout.py::test_every_connection_timeout[write-memory],137ms |137|137000|
| skip config when explicit URL | tests/integration/test_db_busy_timeout.py::test_setting_overrides_url_timeout,URL timeout0 |211|0|
| remove query_only | test_every_connection_timeout[read-file] |query_only1|0|

Bounds input is otherwise valid, PRAGMA reads no data and cannot itself acquire
a writer lock. Unit conversions change no money. Trace each case through native
driver and assertion; investigate different failure mechanisms rather than
accepting any red test as sound mutation evidence.

## 5. Variations and verdict

Pydantic import style and private locals may vary; fixed field/range/default,
get_settings source and connect_args native behavior are mandatory. No requirement
for exact SQLite error prose or elapsed milliseconds. Timeout does not guarantee
whole-operation deadlines or delayed refusal for every deadlock/upgrade.
Docs must state this and existing rollback/no automatic replay. Check progress
matches all gates; no production public function changes. Standard report header
and findings, distinguish baseline/spec/environment/implementation. FAIL handoff
requirement/observation/required result; no code repair, commit, push or later work.
