# Verify Phase 14e: data coverage and finding merchants

Spec: `docs/phases/phase-14e-coverage-and-names.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added `joined_periods` and the name-matching rules in `domain`, `coverage_report` and `find_names` in `analysis`, and the `data_coverage` and `find_merchants` tools. Two test files and a diff to five earlier test files were given; no migration.

These are correct and must not be reported: `statement_gaps` rewritten to use `joined_periods` (if its earlier tests pass unchanged); a private normalizing helper; candidates built as a list or a generator.

## 1. Gates

N is `3226` when Phase 14d was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 28 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_name_matching.py tests/integration/test_mcp_coverage.py --no-cov` | exactly `28 passed` |
| `.venv/bin/python -m pytest tests/integration/test_mcp_accounts.py tests/integration/test_mcp_more.py tests/integration/test_mcp_spending.py tests/integration/test_mcp_outlook.py tests/integration/test_mcp_queues.py tests/integration/test_health_facts.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.mcp_server --cov=finances.domain.periods --cov=finances.domain.merchants --cov=finances.analysis.coverage --cov=finances.analysis.names --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(views|web|cli)" -- src/finances/mcp_server` | no output |
| `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py` | no output |
| `git diff --stat HEAD -- tests` | the five files of the given diff |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `src/finances/domain/periods.py`, `src/finances/domain/merchants.py`, the two new `analysis` modules, `src/finances/mcp_server/tools.py` and `server.py`, the five earlier MCP test files, and the three new test files. The earlier-test diff equals the spec's; the two descriptions equal the spec's text.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R9 | gates 1 to 8 | pass |
| R4 to R7 (edges) | the coder's `tests/integration/test_mcp_coverage_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `closest_names` keeps scores above the threshold only (`>`) | `test_best_first_merchants_before_categories_on_a_tie` (groceries) | FOOBAR GROCERY at 75 | missing |
| 2. Categories before merchants on a tie | the same (cofee) | ACME COFFEE first | Coffee & Dessert first |
| 3. The similarity rounds down (`200 * M // T`) | `test_the_score[that coffee place-ACME UTILITY-67]` | 67 | 66 |
| 4. `joined_periods` joins only overlapping periods | `test_joined_periods[next day joins]` | one run | two |
| 5. `joined_periods` joins periods one day apart | `test_joined_periods[one day apart stays]` | two runs | one |
| 6. `data_coverage` keeps an empty account as `""` | `test_data_coverage` (the backup problem) | `None` | `""` |

## 6. Out of scope

Each must be absent: a new dependency; an embedding or index; a page or command; a write.
