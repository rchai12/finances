# Review: Phase 36a

- Verdict: PASS
- Passed: 3273
- Findings: 0
- Approved deviations: none
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3273 passed`, `All checks passed.`, `critical coverage: passed` (N + 14 = 3273)
- Given tests plus `test_check_script.py`: `29 passed`
- `git diff --stat HEAD -- tests`: only `tests/unit/test_check_script.py`
- `git diff --stat HEAD -- src`: only `src/finances/db/repositories.py`, deleted
- Given files match the spec blocks; the critical-modules diff equals the spec's
- Scope paths match the guide's list

## Requirement checklist

- R1: probe `FAILURES 0` (102 definitions moved unchanged)
- R2: `test_the_facade_offers_every_name_and_only_those`; `test_the_facade_only_imports`
- R3: `test_no_area_imports_the_facade`
- R4: `test_the_package_holds_one_module_per_area`; `test_no_module_is_longer_than_400_lines`
- R5: `test_check_script.py`; `scripts/check.py` critical coverage passed

## Probe

`FAILURES 0`. One `ok` line per definition of `HEAD:src/finances/db/repositories.py`.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Define one function in `__init__.py` instead of its area: `test_the_facade_only_imports` fails (`FunctionDef` is not `__all__`).
2. Put `list_budgets` in `categories.py`: `test_each_name_lives_in_its_area[budgets]` fails (`__module__` is `categories`).
3. An area imports from `finances.db.repositories`: `test_no_area_imports_the_facade` fails (`statements.py`).
4. Edit a body while moving it (rename a local in `list_budgets`): the probe fails (`FAIL list_budgets`).

## Out of scope

Absent: a changed function body or signature; a change to any other source file; a change to `views` or the CLI.
