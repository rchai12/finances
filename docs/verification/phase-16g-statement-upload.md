# Verify Phase 16g: statement upload

Spec: `docs/phases/phase-16g-statement-upload.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder fixed the bulk form's field limit, and added a Statements page that uploads a PDF statement through the existing import, lists the statements, and shows the gaps between them. Two templates and three test files were given; no migration.

These are correct and must not be reported: an `async` bulk route with `run_in_threadpool`; `rpartition` or a regular expression for the file name; reading the upload with `file.file.read(limit + 1)`.

## 1. Gates

N is `2728` when Phase 16j was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 23 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_statement_gaps.py tests/integration/test_web_statements.py tests/integration/test_web_bulk_limit.py --no-cov` | exactly `23 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_accounts_and_bulk.py tests/e2e/test_cli_import.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.analysis --cov=finances.domain.periods --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|timedelta" -- src/finances/web` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |
| `git grep -n --untracked -E "write_bytes|NamedTemporaryFile|mkstemp|open\(" -- src/finances/web/app.py` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/domain/periods.py
 M src/finances/web/app.py
 M src/finances/web/templates/layout.html
?? src/finances/analysis/statements.py
?? src/finances/views/statements.py
?? src/finances/web/templates/statements.html
?? tests/integration/test_statements_more.py
?? tests/integration/test_web_bulk_limit.py
?? tests/integration/test_web_statements.py
?? tests/unit/test_statement_gaps.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1, R2, R5 to R8 | gate 2 | passes |
| R3, R4, R7 (name cut, nothing written) | the coder's `tests/integration/test_statements_more.py` | each item of the spec's "Tests to write" has a test |
| R1 | read the bulk route | the form is read with `max_fields=1100`; the rest of the route is unchanged |
| R8 | read the upload route | no `open`, `write_bytes`, or temporary file; nothing logged at INFO or above |

## 4. Probe

None: the given tests upload real PDFs through the fake bank parser. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. The stored name keeps the folders the browser sent.
2. The rules do not run after an upload.
3. A dry run writes the statement.
4. Two back-to-back statements are reported as a gap of no days.
5. The bulk route reads its form with the framework's default limit again.

## 6. Out of scope

Each must be absent: keeping the uploaded file; several files at once; a change to `ingest/` or `fin import`; JavaScript.
