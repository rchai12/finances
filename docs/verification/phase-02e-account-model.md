# Verify Phase 2e: `AccountType` and `Account`

Spec: `docs/phases/phase-02e-account-model.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote the members of `AccountType` and the fields of `Account`. The test file and the class shells (imports, class lines, docstrings) were given.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `20 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `102 passed`, 0 skipped, 0 xfailed, `Required test coverage of 85.0% reached`, and the row for `src/finances/domain/models.py` at `100%` |

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, `?? src/finances/domain/models.py`, `?? tests/unit/test_models.py`. Report every other path.
- `git diff HEAD -- src` is empty (`money.py` and everything else tracked is untouched).

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test file untouched | compare `tests/unit/test_models.py` with the block in step 1 of the spec | identical apart from trailing whitespace; the file ends with a newline |
| given | shells kept | compare `models.py` with the block in step 3 | the module docstring, the three imports, both class lines, the `@dataclass(frozen=True)` line, and both class docstrings are unchanged |
| R1 | enum | read `models.py`; probe script | four members with the values in the spec, in order; probe lines `enum ...` end in `ok` |
| R2 | fields | read `models.py`; probe script | eight annotated fields in the spec's order with the spec's types; probe lines `field ...` end in `ok` |
| R3 | no defaults | read `models.py` | no field has `=` or `field(...)` |
| R4 | standard library only | run the search below this table | no output |
| scope | nothing extra | probe script | the two `nothing extra` and `no methods` lines end in `ok` |

`git grep -n --untracked -E "^(from|import) finances" -- src/finances/domain`

## 4. Independent probes

These checks are not in the given tests. They look at the declared types, at behavior the tests do not exercise, and at anything added beyond the two classes.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import dataclasses
import typing
from datetime import UTC, datetime
from enum import StrEnum

from finances.domain import models
from finances.domain.models import Account, AccountType

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


check("enum base", AccountType.__mro__[1] is StrEnum)
check(
    "enum members",
    {name: member.value for name, member in AccountType.__members__.items()}
    == {"CHECKING": "checking", "SAVINGS": "savings", "CREDIT_CARD": "credit_card", "OTHER": "other"},
)
check("enum formats as its value", f"{AccountType.SAVINGS}" == "savings")
check("enum equals its value", AccountType.OTHER == "other")

hints = typing.get_type_hints(Account)
check(
    "field types",
    hints
    == {
        "id": int,
        "name": str,
        "institution": str,
        "type": AccountType,
        "currency": str,
        "last4": str | None,
        "is_active": bool,
        "created_at": datetime,
    },
)
check("field order", list(hints) == [field.name for field in dataclasses.fields(Account)])
check("frozen", Account.__dataclass_params__.frozen is True)
check("compares by value", Account.__dataclass_params__.eq is True)

when = datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)
saver = Account(7, "Rainy Day", "Example Savings Bank", AccountType.SAVINGS, "USD", None, False, when)
check("positional construction", (saver.id, saver.type, saver.last4, saver.is_active) == (7, "savings", None, False))
check("replace makes a new object", dataclasses.replace(saver, name="Other").name == "Other" and saver.name == "Rainy Day")
check("usable in a set", len({saver, dataclasses.replace(saver)}) == 1)
try:
    Account(id=1, name="Only Two Fields")
    check("missing fields are an error", False)
except TypeError:
    check("missing fields are an error", True)
try:
    Account(1, "A", "B", AccountType.OTHER, "USD", None, True, when, "extra")
    check("a ninth value is an error", False)
except TypeError:
    check("a ninth value is an error", True)

public = sorted(name for name in vars(models) if not name.startswith("_"))
check(f"nothing extra in the module {public}", public == ["Account", "AccountType", "StrEnum", "dataclass", "datetime"])
extra = sorted(set(vars(Account)) - set(vars(dataclasses.make_dataclass("X", [], frozen=True))) - set(hints))
check(f"no methods or properties on Account {extra}", extra in ([], ["__match_args__"]))
print("FAILURES", failures)
```

## 5. Progress log

`docs/progress.md` ends with the entry given in step 11 of the spec, with a real date in place of `YYYY-MM-DD`. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

## If the verdict is FAIL

Send each repair in one of these forms, and no other:

- "Run step N of the spec again."
- "Replace the whole content of `tests/unit/test_models.py` with the block in step 1."
- For the coder's own code: "`<probe or test name>` fails: expected `<want>`, found `<got>`. Change only the members of `AccountType` (or only the fields of `Account`), then run steps 9 to 17 again." At most three.
- For a rule: "Line N of `models.py` has `<thing>`, which R3 or R4 (or the rule against extra code) forbids. Remove or rewrite that line, then run steps 9 to 17 again."
