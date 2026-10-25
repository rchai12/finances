# Verify Phase 38: pairing after unsplit and unshare, and the links that can be unlinked

Spec: `docs/phases/phase-38-pairing-gaps.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder made removing a split on the web, and removing a share on the web and in the terminal, pair transfers in the same session, made the SimpleFIN page take its links from the database instead of a test Keychain's private dict, and gave a link's accounts page an Unlink button whenever the Keychain has access for it. A template diff, a diff to one earlier test, and one test file were given.

These are correct and must not be reported: `list_feed_links` called inside `_sync_page`'s existing session; the union written as a set or a sorted merge.

## 1. Gates

N is `3998` when Phase 37 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 7 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_pairing_gaps.py --no-cov` | exactly `7 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web.routes.sync --cov=finances.web.routes.transactions --cov=finances.web.routes.shared --cov=finances.cli.shared --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/integration/test_web_recheck.py` |
| `git grep -n -e "passwords" -e "keyring" -- src/finances/web/routes` | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the four source files and the template of the spec's Scope, `tests/integration/test_web_recheck.py`, and two new test files. The given test file, the template, and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_clearing_a_split_on_the_web_pairs_the_transfer`); the coder's no-partner case | pass |
| R2 | gate 2 (`test_unsharing_on_the_web_pairs_the_transfer`, `test_unsharing_in_the_terminal_pairs_the_transfer`); the coder's missing-id case | pass |
| R3 | gate 2 (`test_unlink_is_offered_for_the_links_the_database_knows`); gate 5; the coder's two-link and no-link cases | pass |
| R4 | gate 4 | only that file |
| R5 | gate 2 (`test_the_accounts_page_offers_unlink_right_after_linking`, `test_the_accounts_page_offers_unlink_when_simplefin_refuses`, `test_no_unlink_for_a_link_that_is_not_set_up`); the coder's bad-name case | pass |

## 4. Probe

None.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `remove_split`: no `pair_transfers` | given `test_clearing_a_split_on_the_web_pairs_the_transfer` | paired | not paired |
| 2. `clear_share`: no `pair_transfers` | given `test_unsharing_on_the_web_pairs_the_transfer` | paired | not paired |
| 3. `remove_command`: no `pair_transfers` | given `test_unsharing_in_the_terminal_pairs_the_transfer` | paired | not paired |
| 4. `_sync_page`: `_keychain_links` kept | given `test_unlink_is_offered_for_the_links_the_database_knows` (`alex` only in the Keychain) | `bea` | `alex`, `bea` |
| 5. `_sync_page`: mapping rows only | the same test (`bea` only seen) | `bea` | none |
| 6. `sync_accounts`: `unlinkable` never set | given `test_the_accounts_page_offers_unlink_right_after_linking` | one Unlink form | none |
| 7. `sync_accounts`: `unlinkable` only on the 200 page | given `test_the_accounts_page_offers_unlink_when_simplefin_refuses` (access `not an access url`) | one Unlink form on the 502 | none |
| 8. `sync_accounts`: `unlinkable` always true | given `test_no_unlink_for_a_link_that_is_not_set_up` (`bea` not in the Keychain) | none on the 400 | one |

## 6. Out of scope

Each must be absent: pairing added after rules, aliases, or clearing categories; another way of listing Keychain links; a migration storing link names; changes to `fin sync`; any other audit finding.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
