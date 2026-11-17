# Review: Phase 47j

- Verdict: PASS
- Passed: 4855
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Phase 47j: bounded SQLite lock waiting (2026-11-17)

Reviewed committed delivery `ad5749bff07b62d07ffeb3c51254e116cb6a1212` against finalized planning baseline `47c7ac30e41cb99cf88d111bc9e2478af0497861`. Predecessor 47i implementation c0cb517 and PASS review 67c8e7e are committed; N=4828. Spec and guide match committed planning bytes. Read project instructions, architecture, conventions, testing strategy, handoff, spec/guide, progress, scoped diff and all new tests and documentation.

The committed diff is exactly ten Scope paths. Both given files match their spec blocks byte-for-byte. Independent AST comparison confirms the only semantic edit in each earlier test file is the added environment key; test_config's tuple was reformatted. `session_scope` AST and engine public signature are unchanged. No other application source, tests, dependency, migration, configuration or section changes. Source inspection confirms backend validation remains before timeout-specific work; no retry/replay, WAL, pool, isolation or check_same_thread changes.

Fresh clean clone `/tmp/47j-independent` used the existing linked venv and explicit clone/src PYTHONPATH; `finances.__file__` resolved inside clone src. All tracked files matched the original delivered workspace byte-for-byte before and after gates. Original untracked `.vscode/settings.json` was preserved. Only this review report is written in the workspace.

## Fresh independent acceptance

All five acceptance steps ran sequentially with `.venv/bin/python`, Python 3.12.16, pytest 9.1.1 and four workers. Existing synthetic localhost fixtures received execution permission; no failed sandbox attempt, weakened test or dependency installation. The contention databases were migrated synthetic temporary files; no real data, Keychain or aggregator access. Coder receipts remain historical and were not reused.

| Gate | Fresh observation |
|---|---|
| `scripts/check.py --first core --workers 4` | exit 0; selected core 1675 passed in 31.08s; full 4855 passed in 97.99s; all sections zero failures/skips; no xfails/warnings summary; lint, format, overall and critical gates passed; final `All checks passed.` |
| Immediate specified config/engine coverage | exit 0; config 61 statements/16 branches, engine 35/8; zero missing/partial; both modules and TOTAL 100% |
| Two given files, `--no-cov` | exit 0; exactly 15 passed in 0.05s |
| `test_db_lock_wait_behavior.py --no-cov -v` | exit 0; 12 passed in 0.75s, including all contention and preservation cases below |
| Scope/given audit | exact ten paths; given bytes, older env-list ASTs, session_scope and tracked delivery bytes match |

Overall coverage was 99.98%. Full check output: `/tmp/47j-independent-check.log`. No separate probe is specified; driver PRAGMAs and real contention/state tests are independent evidence.

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           361 passed    0 failed    0 skipped
  parsers       903 passed    0 failed    0 skipped
  sync          284 passed    0 failed    0 skipped
  core         1675 passed    0 failed    0 skipped
```

Final ten check lines:

```text
  core         1675 passed    0 failed    0 skipped
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
| R1 | `test_default`, `test_valid_bounds`, `test_invalid_bounds`, `test_environment`, `test_shared_fixture_clears_timeout_environment` and `test_tmp_settings_clears_poisoned_environment` pin 30000 ms default, inclusive 0..120000, validation location, environment and isolation. The new public setting is `Settings.db_busy_timeout_ms`. |
| R2 | Six `test_every_connection_timeout` cases observe 137 ms on two connections and after disposal across memory/file/configured and read/write engines, plus PRAGMAs. `test_setting_overrides_url_timeout` observes 211 despite URL timeout=0. Six `test_timeout_boundaries_on_reopened_connections` cover zero/default/max and sqlite:// and memory; `test_cache_clear_and_file_parent` checks changed settings and relative parent creation. Source passes configured milliseconds divided by 1000 via native driver connect_args. |
| R3 | `test_waiting_writer_commits_once_after_release` holds a real file-backed writer, waits for a pre-execute marker, confirms worker remains pending, releases holder, surfaces worker exceptions, counts exactly one write and asserts exact stored names. Worker owns its session; cleanup closes holder and joins pool. |
| R4 | `test_blocked_writer_rolls_back_and_later_succeeds[held-lock-timeout]` and `[zero-wait]` hold the lock through refusal, assert SQLAlchemy OperationalError wrapping sqlite3 OperationalError with SQLITE_BUSY, one attempted write, no worker row, holder commit and later successful transaction. The worker performs a safe read and stages its ORM row before flush. Finally blocks release and join; bounds are generous rather than elapsed-time guarantees. No replay occurs. |
| R5 | Given connection cases assert foreign_keys and query_only on each connection. `test_foreign_keys_readonly_and_unsupported` verifies actual FK IntegrityError, read-only DML OperationalError with unchanged contents and existing unsupported-backend message. `test_cache_clear_and_file_parent` covers parent creation; existing engine suite passes and session_scope is unchanged. |
| R6 | `.env.example` records default, units and range. `docs/database-locks.md` covers cache/restart, URL precedence, zero/default/max, native busy handling, non-deadline and early-refusal limits, rollback/no replay and restore/concurrent-writer limits. |

Fifteen given and twelve coder cases explain 4828 -> 4855. No test waits the production 30-second default. The setting governs SQLite's native busy handler, not total operation duration; some lock upgrades can refuse immediately.

## Scratch-only spot checks

Each mutation ran independently in a disposable clone with confirmed clone import provenance and unchanged given tests. Each designated case failed with exit 1 on its intended behavior; reviewed source was never mutated.

| Mutation | Given case | Broken observation |
|---|---|---|
| Remove lower bound | `test_invalid_bounds[-1]` | no ValidationError |
| Remove upper bound | `test_invalid_bounds[120001]` | no ValidationError |
| Omit milliseconds-to-seconds conversion | `test_every_connection_timeout[write-memory]` | driver reports 137000 ms instead of 137 |
| Skip setting for explicit URL timeout=0 | `test_setting_overrides_url_timeout` | driver reports 0 instead of 211 |
| Remove query_only | `test_every_connection_timeout[read-file]` | PRAGMA reports 0 instead of 1 |

Logs: `/tmp/47j-spot-{lower,upper,conversion,url,readonly}.log`; scratch clones removed. The initial scratch harness had a quoting SyntaxError and was corrected before these runs; it did not touch reviewed files or acceptance evidence. No baseline, environment, specification/test or implementation blocker remains. PASS applies to the exact reviewed delivery commit. No implementation, progress or phase documents were edited; no commit or push performed.
