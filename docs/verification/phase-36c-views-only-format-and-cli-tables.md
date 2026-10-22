# Verify Phase 36c: views that only format (sync, transfers, backups), and the CLI tables

Spec: `docs/phases/phase-36c-views-only-format-and-cli-tables.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder moved the loading out of the sync, transfers, and backups views into three new `analysis` modules, moved the Keychain check to `sync/links.py`, switched seven CLI tables to `print_rows`, and merged the two `_change` helpers. Nothing a person sees may change. One test file and a diff to three earlier test files were given; no migration.

These are correct and must not be reported: a `TYPE_CHECKING` import of `LinkRun` in `analysis/simplefin.py`; the Keychain states kept in a dict; list comprehensions where the spec's wording says "loop".

## 1. Gates

N is `3286` when Phase 36b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 8 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_views_only_format.py tests/unit/test_views_take_data.py tests/integration/test_views.py tests/integration/test_transfer_views.py tests/integration/test_transfer_store.py --no-cov` | all passed |
| `.venv/bin/python -m pytest tests/e2e tests/integration/test_web_sync_setup.py tests/integration/test_web_transfers.py tests/integration/test_web_backups.py --no-cov -q` | all passed (output unchanged) |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.simplefin --cov=finances.analysis.transfers --cov=finances.analysis.backups --cov=finances.views --cov=finances.sync.links --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +(finances\.db|sqlalchemy|keyring|finances\.sync\.(links|simplefin|service|transport|keychain))" -- src/finances/views` | no output |
| `git diff --stat HEAD -- tests` | the three files of the given diff |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, the three earlier test files, and new `analysis/simplefin.py`, `analysis/transfers.py`, `analysis/backups.py`, `tests/unit/test_views_only_format.py`, and `tests/integration/test_listings_more_36c.py`. No template changes.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R11 | gates 1 to 6 | pass |
| R1 to R3 (edges) | the coder's `tests/integration/test_listings_more_36c.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None: the earlier command and page tests pin every output these views and tables make.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `views/sync.py` imports `finances.sync.links` again | `test_no_view_loads_data` | pass | fail |
| 2. Leave a `_change` in `views/insights.py` | `test_one_change_text` | pass | fail |
| 3. `transfer_lines` keeps the listing's order | `test_transfer_lines_sort_and_suggestions` | pair 2 first | pair 1 first |
| 4. `fin health` builds its table by hand again | `test_the_cli_tables_go_through_print_rows` | pass | `health.py: 1` |

## 6. Out of scope

Each must be absent: a template change; a change to output; a change to the three tables built from other cells.
