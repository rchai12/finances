# Verify Phase 2c: Money helpers

Spec: `docs/phases/phase-02c-money-helpers.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

## 1. Gates

Activate the virtual environment first, then run each command on its own line.

| Command | Expected |
|---|---|
| `python -m ruff check .` | `All checks passed!` |
| `python -m ruff format --check .` | `18 files already formatted` |
| `python -m pytest` | exit code 0, exactly `72 passed`, 0 skipped, 0 xfailed, and the line `Required test coverage of 85.0% reached. Total coverage: 98.77%` |

In the coverage table, the row for `src/finances/domain/money.py` must show 100% and an empty `Missing` column. Anything less is a FAIL, because this is a critical module (`docs/testing.md`).

## 2. Scope audit

- `git status --short` lists exactly: `docs/progress.md`, `src/finances/domain/`, `tests/unit/test_money.py`. Report every other path as a finding.
- `src/finances/domain/` contains exactly `__init__.py` and `money.py` (ignore `__pycache__`).
- `git diff HEAD -- pyproject.toml tests/conftest.py tests/unit/test_config.py tests/unit/test_diagnostics.py tests/unit/test_log.py tests/e2e` is empty.

## 3. Requirement checklist

The spec gives both files verbatim, so these rows are comparisons.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | package marker | read `src/finances/domain/__init__.py` | the file is empty |
| R2 | `money.py` | compare the file with the R2 block in the spec | identical apart from trailing whitespace |
| R3 | `test_money.py` | compare the file with the R3 block | identical apart from trailing whitespace |
| R4 | nothing bent to fit | read both files | no `try`, `except`, `skip`, `xfail`, `assert True`, or `# pragma: no cover` |
| R5 | counts | gate output from section 1; `python -m pytest tests/unit/test_money.py --no-cov` | exactly `72 passed` overall, exactly `56 passed` for the file, `money.py` at 100% |
| behavior | independent of the copy | probe script, section 4 | last line is `FAILURES 0` |

For each comparison, report every differing line with its line number.

## 4. Independent probes

Run this even when the file comparison passes. Most of these inputs are **not** in the spec's tables. They catch an implementation that special-cases the listed examples or uses `float` (`0.29`, `4.35`, and `1.15` each come out one cent low when multiplied as floats).

Save the script below in a temporary directory **outside the repository**, run it with `python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
from finances.domain.money import format_cents, parse_money

D = "$"
failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


VALID = {
    "0.29": 29, "4.35": 435, "1.15": 115, D + "0.07": 7, "(1,000)": -100000,
    "999,999.99-": -99999999, "0012.30": 1230, " \t" + D + "3\n": 300,
    D + "1,234,567,890.12": 123456789012, "-.05": -5, "(0)": 0, "1,234": 123400,
    "-" + D + "12.34": -1234, "(" + D + "1,234.56)": -123456, "-0.00": 0,
}
for text, want in VALID.items():
    try:
        got = parse_money(text)
    except Exception as exc:  # noqa: BLE001
        got = repr(exc)
    check(f"valid {text!r} -> {want}", got == want)

INVALID = [
    "", "   ", "(", ")", "()", "12,34", "1.2.3", "-(5)", "Infinity", "0x10", "1_000",
    "12.345", "1,23.45", "1234,567", "--5", "(-5)", "-5-", D + "-5", D + D + "5",
    "+5", "1 000", D + " 5", "- 5", "1e3", "NaN", "12.",
]
for text in INVALID:
    try:
        parse_money(text)
        check(f"invalid {text!r}", False)
    except ValueError as exc:
        check(f"invalid {text!r}", True)
        check(f"message {text!r}", str(exc) == "invalid money text")
    except Exception:  # noqa: BLE001
        check(f"invalid {text!r} (wrong exception type)", False)

for text in ["١٢", "５", "१.२३"]:
    try:
        parse_money(text)
        check(f"ascii {text!r}", False)
    except ValueError:
        check(f"ascii {text!r}", True)

check("type", type(parse_money("7")) is int and type(parse_money("(1.50)")) is int)

FORMAT = {
    -100000000: "-" + D + "1,000,000.00", 99: D + "0.99", -1: "-" + D + "0.01",
    123456789012: D + "1,234,567,890.12", 10: D + "0.10", -100: "-" + D + "1.00",
    0: D + "0.00", 123456: D + "1,234.56",
}
for cents, want in FORMAT.items():
    check(f"format {cents}", format_cents(cents) == want)

check("roundtrip", all(parse_money(format_cents(n)) == n for n in range(-25000, 25001, 7)))
print("FAILURES", failures)
```

## 5. Project rules that apply to this phase

- **No float for money.** `git grep -n -E "float|round\(| / |/ 100" -- src/finances/domain/money.py` returns no matches.
- **`domain` imports nothing from the project.** `git grep -n -E "^(from|import) " -- src/finances/domain` shows only `decimal` and `re`.
- **No logging of amounts.** `git grep -n -E "logging|print\(" -- src/finances/domain` returns no matches.
- **Input never echoed in errors.** Every `raise` in `money.py` is `ValueError("invalid money text")` with a constant string: no f-string, and no exception chaining that carries the input.
- **Synthetic data only.** The test file contains amounts only: no merchant names, account numbers, or personal names.

## 6. Progress log

`docs/progress.md` ends with the entry given in step 5 of the spec's work order, with a real date in place of `YYYY-MM-DD`. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

## If the verdict is FAIL

A repair sent back to the coder is either the instruction to replace a whole file with a block from the spec, or a single command to run. Do not describe an edit in a sentence.
