# Review: Phase 16j

- Verdict: PASS
- Passed: 2728
- Findings: 0
- Approved deviations: None
- For the architect: a web test that posts more than 1000 `id` fields must raise Starlette's `Request.form` `max_fields` (default 1000), or the framework answers before the app's "at most 1000" message.

## Findings

None

Parts that needed a repair: coverage miss on `rename_account` / `set_account_active` when the account id is missing; two coder tests added.

Built beyond the spec: none.

## Gates

- `scripts/check.py`: `2728 passed`, `All checks passed.` (N + 29 = 2721; 7 more are the coder's)
- Given tests: `29 passed`
- Earlier page tests: `tests/integration/test_web_pages.py tests/integration/test_web_search.py tests/integration/test_web_forms.py tests/e2e/test_cli_categories.py`, `184 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists the guide's 10 paths, plus this review
- Given files: `accounts.html`, `transactions.html`, `tests/e2e/test_cli_accounts_and_bulk.py`, and `tests/integration/test_web_accounts_and_bulk.py` match the spec's blocks

## Requirement checklist

- R1: `rename_account` (`repositories.py:1108`) strips, checks empty/length/another name ignoring case, allows its own case change. Tests: given rename tests; `test_renaming_keeps_a_change_of_its_own_case`, `test_rename_account_refuses_a_missing_id`.
- R2: `set_account_active` (`repositories.py:1128`) sets `is_active`. Tests: given close/reopen; `test_set_account_active_refuses_a_missing_id`; closed account left out of balances and still in spending.
- R3: bulk set/clear (`repositories.py:1151` and `1165`) take distinct ids in order, refuse empty and more than 1000, require every transaction (and the category for set) before any write. Tests: given bulk tests; coder 1001 / repeated-id / web 1001 tests.
- R4, R5: the given CLI tests pass; one distinct id still prints the single-transaction line (`test_a_category_set_by_hand_is_kept`).
- R6 to R8: the given web tests pass. `_back_filters` keeps only `_FILTER_FIELDS`. Bulk clear runs `categorize` in the same session.
- R9: the given templates are used as shown; checkboxes sit in the date cell.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the named tests run, and the file restored.

1. The bulk redirect keeps an unknown field from `back`: `test_set_and_clear_several_transactions` fails.
2. One distinct id prints the several-transactions line: `test_a_category_set_by_hand_is_kept` fails.
3. A closed account still shows on the Accounts page by default: `test_rename_close_and_reopen_an_account` fails.
4. `select=all` does not check the boxes: `test_every_row_has_a_checkbox_and_select_all_checks_them` fails.
5. Renaming an account to another account's name in another case is allowed: `test_a_refused_account_change` (CLI and web "already exists" cases) fails.

## Out of scope

Absent: a migration; deleting an account; changing an account's type or institution; JavaScript.
