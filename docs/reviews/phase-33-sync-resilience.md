# Review: Phase 33

- Verdict: PASS
- Passed: 2932
- Findings: 0
- Approved deviations: failure-message width uses `PROVIDER_ACCOUNT_ID_LIMIT` (200); one extra coverage test when `on_retry` is omitted
- For the architect: `docs/roadmap.md` also has uncommitted Phase 34 outline notes, not part of this phase

## Findings

None

Parts that needed a repair: ORM `String(200)` literal failed `test_the_orm_names_its_widths_by_constant`; two retry branches needed a missing-link remember and a no-`on_retry` retry test

Built beyond the spec: `test_retries_without_an_on_retry`

## Gates

- `scripts/check.py`: `2932 passed`, `All checks passed.` (N + 15 = 2926; extra coder tests)
- Given tests: `15 passed`
- `bash -n` on both schedule scripts: nothing
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Network-call search: only `src/finances/sync/transport.py`

## Requirement checklist

- R1: `AggregatorUnreachable` from `OSError`; `simplefin.py` 100% covered
- R2: given migration 0011 tests; `record_sync_failure` / `clear_sync_failure` / `list_sync_failures`
- R3: given retry tests; keychain and not-set-up in `test_sync_resilience_more.py`
- R4: `test_the_daily_sync_tries_again_then_remembers_the_failure`; web `git diff HEAD -- src/finances/web` empty; `test_sync_now_does_not_wait`
- R5: given CLI status line; `test_status_prints_failures_by_link`
- R6: `test_a_stored_failure_is_a_sync_problem`; `gather_health` passes `list_sync_failures`
- R7: schedule scripts match the spec blocks; `bash -n` clean

## Probe

None, as the guide says.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy.

1. `run_links` retries every `SyncError`: status 500 makes 4 calls and three waits.
2. `run_links` retries revoked access: status 403 makes 4 calls.
3. A good sync clears every link's failure: sam's stored failure is gone.
4. `record_sync_failure` keeps the first failure: the older message remains.
5. `health_problems` drops the failures: no `sync` problem naming link alex.

## Out of scope

Absent: retries of error answers in the unmutated code; a change to the web; syncing more than once a day.
