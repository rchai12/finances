# Verify Phase 25: data health

Spec: `docs/phases/phase-25-data-health.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added the data-health rules (pure), a gathering function, rows, and `fin health`. Two test files were given; no migration.

These are correct and must not be reported: the texts as module constants; one query per account in `account_facts`; `sorted` with a tuple key.

## 1. Gates

N is `2763` when Phase 16g was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 22 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_health.py tests/e2e/test_cli_health.py --no-cov` | exactly `22 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.health --cov=finances.analysis.health --cov=finances.views.health --cov=finances.cli.health --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|timedelta|health_problems\(" -- src/finances/cli/health.py` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/cli/main.py
?? src/finances/analysis/health.py
?? src/finances/cli/health.py
?? src/finances/domain/health.py
?? src/finances/views/health.py
?? tests/e2e/test_cli_health.py
?? tests/integration/test_health_facts.py
?? tests/unit/test_health.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R4, R6, R7 | gate 2 | passes |
| R5 | the coder's `tests/integration/test_health_facts.py` | each item of the spec's "Tests to write" has a test |
| R5 | read `account_facts` | active accounts only; `with_balance=True` for drift; UTC date of `pulled_at` |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. Closed accounts are checked too.
2. A drift of zero is reported.
3. A threshold uses "at least" instead of "more than".
4. An account on SimpleFIN also gets `statements` problems.
5. Problems come in the order the accounts were listed.

## 6. Out of scope

Each must be absent: a web page; a change to `fin doctor`; a migration; stored sync failures.
