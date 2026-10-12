# Verify Phase 2c: `format_cents`

Spec: `docs/phases/phase-02c-format-cents.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote the body of `format_cents`. The test file and the function's `def` line and docstring were given. Judge the body by behavior and by the rules, not by whether it matches a particular implementation.

## 1. Gates

Activate the virtual environment first, then run each command on its own line.

| Command | Expected |
|---|---|
| `python -m ruff check .` | `All checks passed!` |
| `python -m ruff format --check .` | `18 files already formatted` |
| `python -m pytest` | exit code 0, exactly `30 passed`, 0 skipped, 0 xfailed, `Required test coverage of 85.0% reached`, and the row for `src/finances/domain/money.py` at `100%` |

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, `?? src/finances/domain/`, `?? tests/unit/test_money.py`. Report every other path.
- `src/finances/domain/` holds exactly `__init__.py` (empty) and `money.py` (ignore `__pycache__`).

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test file untouched | compare `tests/unit/test_money.py` with the block in step 2 of the spec | identical apart from trailing whitespace; the file ends with a newline |
| given | signature kept | read `money.py` | the `def format_cents(cents: int) -> str:` line and the docstring match the block in step 4 |
| R1 | behavior | probe script in section 4 | last line is `FAILURES 0` |
| R2 | integers only | run the search below this table | no output |
| R3 | no imports | read `money.py` | no `import` or `from` line |
| scope | nothing extra | read `money.py` | `format_cents` is the only function; no class, `print`, logging, `try`, or `# pragma: no cover` |

`git grep -n --untracked -E "float|round\(| / |/ 100" -- src/finances/domain/money.py`

## 4. Independent probes

None of these values are in the given tests. They catch a body that special-cases the listed examples or goes through `float`.

Save the script in a temporary directory **outside the repository**, run it with `python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
from finances.domain.money import format_cents

D = "$"
CASES = {
    7: D + "0.07",
    -99: "-" + D + "0.99",
    -1: "-" + D + "0.01",
    250: D + "2.50",
    1000: D + "10.00",
    99999: D + "999.99",
    100000: D + "1,000.00",
    -100001: "-" + D + "1,000.01",
    99999999999999: D + "999,999,999,999.99",
    -9007199254740993: "-" + D + "90,071,992,547,409.93",
    10**20 + 1: D + "1,000,000,000,000,000,000.01",
}
failures = 0
for cents, want in CASES.items():
    try:
        got = format_cents(cents)
    except Exception as exc:  # noqa: BLE001
        got = repr(exc)
    ok = got == want
    failures += 0 if ok else 1
    print(cents, "ok" if ok else f"FAIL got {got!r} want {want!r}")
print("FAILURES", failures)
```

## 5. Progress log

`docs/progress.md` ends with the entry given in step 9 of the spec, with a real date in place of `YYYY-MM-DD`. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

## If the verdict is FAIL

Send each repair in one of these forms, and no other:

- "Run step N of the spec again."
- "Replace the whole content of `<file>` with the block in step N." (given files only)
- For the function body: "`format_cents(<input>)` returned `<got>`; it must return `<want>`. Change only the body of `format_cents`, then run steps 7 to 14 again." One line per failing input, at most three.
- For a rule: "Line N of `money.py` uses `<thing>`, which R<n> forbids. Rewrite that line, then run steps 7 to 14 again."
