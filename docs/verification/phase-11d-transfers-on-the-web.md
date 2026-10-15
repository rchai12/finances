# Verify Phase 11d: transfers on the web

Spec: `docs/phases/phase-11d-transfers-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a Transfers page with four forms, a transfer section on a transaction's page, `find_transfer_pair`, and `transfer_of`, on top of Phase 11c's functions. Three templates and one test file were given.

These are correct and must not be reported: helpers inside `web/app.py`; one session or several for a page's reads; `transfer_of` looking the pair up by `find_transfer_pair`.

## 1. Gates

N is `2311` when Phase 11c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 23 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_transfers.py --no-cov` | exactly `23 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.db --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|transfer_candidates|clear_pairs" -- src/finances/web` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/db/repositories.py
 M src/finances/views/transfers.py
 M src/finances/web/app.py
 M src/finances/web/templates/layout.html
 M src/finances/web/templates/transactions_one.html
?? src/finances/web/templates/transfers.html
?? tests/integration/test_transfer_views.py
?? tests/integration/test_web_transfers.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1, R2 | the coder's `tests/integration/test_transfer_views.py` | each item of the spec's "Tests to write" has a test |
| R2 | read `views/transfers.py` | `transfer_lines` and `transfer_of` build their lines with one shared helper |
| R3 to R7 | gate 2 | passes |

## 4. Probe

None: the given tests drive every route and form. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. Unpair with `back` ignores it and returns to `/transfers`.
2. Confirm stores the pair as `auto`.
3. A refused unpair with `back` answers the transaction's page instead of the Transfers page.
4. `transfer_of` finds only the out side of a pair.
5. The transaction page passes `transfer` even for a transaction in no pair, as an empty line.

## 6. Out of scope

Each must be absent: a change to `cli/`, `categorize/`, or `domain/`; JavaScript; a transfer count in the menu.
