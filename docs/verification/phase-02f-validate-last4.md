# Verify Phase 2f: `validate_last4`

Spec: `docs/phases/phase-02f-validate-last4.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote the body of `validate_last4`. The test file and the function's `def` line and docstring were given. The spec's "Suggested approach" is optional: judge the body by behavior and by the rules.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `20 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `122 passed`, 0 skipped, 0 xfailed, `Required test coverage of 85.0% reached`, and the row for `src/finances/domain/models.py` at `100%` |

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, ` M src/finances/domain/models.py`, ` M tests/unit/test_models.py`. Report every other path.
- `git diff HEAD -- src/finances/domain/models.py` shows `AccountType` and `Account` unchanged: the only changes are the new function and, at most, new import lines at the top.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test file untouched | compare `tests/unit/test_models.py` with the block in step 1 of the spec | identical apart from trailing whitespace; the file ends with a newline |
| given | signature kept | read `models.py` | the `def validate_last4(last4: str \| None) -> str \| None:` line and the docstring match the block in step 3 |
| R1, R2 | accepted inputs | probe script in section 4 | the `None` line and every `valid` line end in `ok` |
| R3, R5 | rejected inputs | probe script | every `invalid` line ends in `ok` |
| R4 | constant message | probe script; read every `raise` in the function | every `message` line ends in `ok`; the raised `ValueError` carries a constant string, with no f-string, `%`, or `.format` |
| rules | imports | read `models.py` | every import is at the top of the file and comes from the standard library |
| rules | no output | run the search below this table | no output |

`git grep -n -E "^(from|import) finances|print\(|logging" -- src/finances/domain/models.py`

## 4. Independent probes

None of these inputs are in the given tests. They catch a body that special-cases the listed examples, trusts `str.isdigit()` or `\\d` (both accept digits from other alphabets), or uses `$` or `re.match` in a way that lets a trailing newline through.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
from finances.domain import models
from finances.domain.models import validate_last4

MESSAGE = "last4 must be exactly 4 digits"
failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


check("None", validate_last4(None) is None)
for text in ["5678", "0001", "1000", "0909"]:
    try:
        got = validate_last4(text)
    except Exception as exc:  # noqa: BLE001
        got = repr(exc)
    check(f"valid {text!r} (got {got!r})", got == text and type(got) is str)

INVALID = [
    "5678\n",
    "\n5678",
    "5678\r",
    "\t5678",
    "5 678",
    "56789",
    "567",
    "5",
    "56.8",
    "5e10",
    "0x12",
    "1_23",
    "\u0664\u0664\u0664\u0664",
    "\u0967\u0968\u0969\u096a",
    "12\uff13\uff14",
    "\u00b2\u00b2\u00b2\u00b2",
    "four",
    "None",
]
for text in INVALID:
    try:
        got = validate_last4(text)
        check(f"invalid {text!r} (returned {got!r})", False)
    except ValueError as exc:
        check(f"invalid {text!r}", True)
        check(f"message {text!r}", str(exc) == MESSAGE)
    except Exception as exc:  # noqa: BLE001
        check(f"invalid {text!r} (raised {type(exc).__name__})", False)

public = sorted(name for name in vars(models) if not name.startswith("_") and name not in {"re"})
expected = ["Account", "AccountType", "StrEnum", "dataclass", "datetime", "validate_last4"]
check(f"nothing extra in the module {public}", public == expected)
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
- "Replace the whole content of `tests/unit/test_models.py` with the block in step 1."
- For the coder's own code: "`validate_last4(<input>)` returned `<got>`; it must raise `ValueError("last4 must be exactly 4 digits")`" (or "... must return `<want>`"). Then: "Change only the body of `validate_last4`, then run steps 6 to 15 again." One line per failing input, at most three.
- For a rule: "Line N of `models.py` has `<thing>`, which the spec's Rules section forbids. Remove or rewrite that line, then run steps 6 to 15 again."
