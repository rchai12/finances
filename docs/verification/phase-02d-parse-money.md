# Verify Phase 2d: `parse_money`

Spec: `docs/phases/phase-02d-parse-money.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote the body of `parse_money`. The test file and the function's `def` line and docstring were given. The spec's "Suggested approach" is optional: judge the body by behavior and by the rules, not by whether it follows that approach.

`domain/money.py` is a critical module (`docs/testing.md`), so 100% coverage and a clean probe run are both required.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `18 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `89 passed`, 0 skipped, 0 xfailed, `Required test coverage of 85.0% reached`, and the row for `src/finances/domain/money.py` at `100%` with nothing under `Missing` |

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, ` M src/finances/domain/money.py`, ` M tests/unit/test_money.py`. Report every other path.
- `git diff HEAD -- src/finances/domain/money.py` shows `format_cents` unchanged: no removed or changed line inside it.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test file untouched | compare `tests/unit/test_money.py` with the block in step 1 of the spec | identical apart from trailing whitespace; the file ends with a newline |
| given | signature kept | read `money.py` | the `def parse_money(text: str) -> int:` line and the docstring match the block in step 3 |
| R1, R2 | accepted inputs | probe script in section 4 | every `valid` line ends in `ok` |
| R3 | rejected inputs and message | probe script | every `invalid` and `message` line ends in `ok` |
| R3 | constant message | read every `raise` in `money.py` | each raised `ValueError` carries the constant string `invalid money text`: no f-string, no `%` or `.format`, and no exception chaining that carries the input (`from None` is fine) |
| R4 | no float | run the search below this table | no output |
| R4 | `Decimal` used | read `money.py` | the cents value comes from `decimal.Decimal` |
| R5 | ASCII digits only | probe script; `git grep -n -F "\d" -- src/finances/domain/money.py` | every `ascii` line ends in `ok`; the search prints nothing |
| scope | nothing extra | read `money.py` | no `print`, no logging, no `# pragma: no cover`; helper functions are allowed only if their names start with `_` |

`git grep -n -E "float|round\(| / |/ 100" -- src/finances/domain/money.py`

## 4. Independent probes

None of these inputs are in the given tests. They catch a body that special-cases the listed examples, goes through `float` (`0.57` and `8.20` each come out one cent low that way), or leans on `Decimal` to reject bad text (`Decimal` accepts `1__0`, `inf`, `1E2`, and non-ASCII digits).

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
from finances.domain.money import format_cents, parse_money

D = "$"
failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


VALID = {
    "0.57": 57,
    "8.20": 820,
    "(1,000)": -100000,
    "999,999.99-": -99999999,
    "0012.30": 1230,
    " \t" + D + "3\n": 300,
    D + "1,234,567,890.12": 123456789012,
    "-.05": -5,
    "(0)": 0,
    "1,234": 123400,
    "(.5)": -50,
    D + ".99": 99,
    "(" + D + "2.00)": -200,
}
for text, want in VALID.items():
    try:
        got = parse_money(text)
    except Exception as exc:  # noqa: BLE001
        got = repr(exc)
    check(f"valid {text!r} -> {want} (got {got!r})", got == want and type(got) is int)

INVALID = [
    "(",
    ")",
    "inf",
    "nan",
    "1__0",
    "1E2",
    "0b1",
    "12.3.4",
    D + "(5)",
    ")5(",
    "5" + D,
    "1,,000",
    ",123",
    "1,0000",
    "1.",
    ".",
    "- " + D + "5",
    "5 -",
    "((5))",
    "5--",
    "1.234,56",
]
for text in INVALID:
    try:
        got = parse_money(text)
        check(f"invalid {text!r} (returned {got!r})", False)
    except ValueError as exc:
        check(f"invalid {text!r}", True)
        check(f"message {text!r}", str(exc) == "invalid money text")
    except Exception as exc:  # noqa: BLE001
        check(f"invalid {text!r} (raised {type(exc).__name__})", False)

for text in ["٣", "５", "१.२३", "1٠"]:
    try:
        parse_money(text)
        check(f"ascii {text!r}", False)
    except ValueError:
        check(f"ascii {text!r}", True)
    except Exception:  # noqa: BLE001
        check(f"ascii {text!r} (wrong exception type)", False)

check("roundtrip", all(parse_money(format_cents(n)) == n for n in range(-25000, 25001, 7)))
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
- "Replace the whole content of `tests/unit/test_money.py` with the block in step 1."
- For the function body: "`parse_money(<input>)` returned `<got>`; it must return `<want>`" or "... must raise `ValueError(\"invalid money text\")`". Then: "Change only the body of `parse_money`, then run steps 6 to 15 again." One line per failing input, at most three; if more fail, also say "the Suggested approach in the spec passes all of these".
- For a rule: "Line N of `money.py` uses `<thing>`, which R<n> forbids. Rewrite that line, then run steps 6 to 15 again."
