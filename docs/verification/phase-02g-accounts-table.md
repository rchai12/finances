# Verify Phase 2g: `accounts` table and `to_account`

Spec: `docs/phases/phase-02g-accounts-table.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote seven columns of `AccountRow` and the body of `to_account`. Everything else in `orm.py`, the test file, and `pyproject.toml` were given. Judge the coder's code by behavior and by the rules, not by resemblance to a particular implementation. A private helper (a function whose name starts with `_`, for example one that returns the current UTC time) is allowed.

This phase was deliberately larger than the ones before it (two Code steps, a new dependency, four files). In your report, say which steps, if any, were skipped or done out of order: the architect uses that to size later phases.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -c "import sqlalchemy; print(sqlalchemy.__version__.split('.')[0])"` | `2` |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `23 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `170 passed`, 0 skipped, 0 xfailed, `Required test coverage of 85.0% reached`, and the row for `src/finances/db/orm.py` at `100%` |

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, ` M pyproject.toml`, `?? src/finances/db/`, `?? tests/unit/test_orm.py`. Report every other path.
- `src/finances/db/` holds exactly `__init__.py` (empty) and `orm.py` (ignore `__pycache__`).
- `git diff HEAD -- pyproject.toml` adds one line, `"sqlalchemy>=2.0",`, and changes nothing else. The file ends with a newline.
- `git diff HEAD -- src/finances/domain tests/unit/test_models.py tests/unit/test_money.py tests/conftest.py` is empty.
- No database file was created: `git status --short --ignored` shows no new `.db`, `.sqlite`, or `data/` entry.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test file untouched | compare `tests/unit/test_orm.py` with the block in step 6 of the spec | identical apart from trailing whitespace; the file ends with a newline |
| given | given parts kept | compare `orm.py` with the block in step 8 | the module docstring, `NAMING_CONVENTION`, `Base`, the `AccountRow` class line, its docstring, `__tablename__`, the `id` column, and the `def to_account` line with its docstring are unchanged. Import lines may differ |
| R1 | column style | read `orm.py` | each of the seven columns is `name: Mapped[...] = mapped_column(...)`, in the spec's order, with the spec's Python types |
| R2 | `type` is text | read `orm.py`; search below | `String(20)`; the search prints nothing |
| R3 | Python defaults | read `orm.py`; search below | `default=` on `currency`, `is_active`, `created_at` only; no `server_default` |
| R4 | aware default time | probe script | `default created_at is aware UTC` ends in `ok` |
| R5, R6 | conversion | probe script | every `round trip` line ends in `ok` |
| R7 | naive time becomes UTC | probe script | `round trip time is aware UTC` and `round trip time is unchanged` end in `ok` |
| R8 | imports | run the second search below | the only line printed is `from finances.domain.models import ...` |
| scope | nothing extra | probe script | the `no extra tables` and `no extra public functions` lines end in `ok` |

`git grep -n --untracked -E "server_default|utcnow|Enum|create_engine|create_all|Session" -- src/finances/db`

`git grep -n --untracked -E "^(from|import) finances" -- src/finances/db`

## 4. Independent probes

The given tests only inspect the table definition. This script builds the table in an in-memory SQLite database and uses it, which the tests never do: it checks the defaults as applied, the constraints as enforced, the constraint names, and a round trip through `to_account` with the naive time SQLite returns.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`. It creates no file.

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finances.db import orm
from finances.db.orm import AccountRow, Base, to_account
from finances.domain.models import Account, AccountType

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


engine = create_engine("sqlite://")
Base.metadata.create_all(engine)

inspector = inspect(engine)
check("only the accounts table", inspector.get_table_names() == ["accounts"])
check("primary key name", inspector.get_pk_constraint("accounts")["name"] == "pk_accounts")
uniques = inspector.get_unique_constraints("accounts")
check("unique constraint", [(u["name"], u["column_names"]) for u in uniques] == [("uq_accounts_name", ["name"])])
check("no indexes", inspector.get_indexes("accounts") == [])
check("no foreign keys", inspector.get_foreign_keys("accounts") == [])

with Session(engine) as session:
    row = AccountRow(name="Probe Savings", institution="Probe Bank", type="savings")
    session.add(row)
    session.flush()
    check("default currency", row.currency == "USD")
    check("default is_active", row.is_active is True)
    check("default last4", row.last4 is None)
    made = row.created_at
    aware = made.tzinfo is not None
    check("default created_at is aware UTC", aware and made.utcoffset() == timedelta(0))
    check("default created_at is now", aware and abs(datetime.now(UTC) - made) < timedelta(minutes=1))
    check("id assigned", isinstance(row.id, int))
    session.commit()

with Session(engine) as session:
    stored = session.get(AccountRow, 1)
    account = to_account(stored)
    check("round trip type", type(account) is Account and account.type is AccountType.SAVINGS)
    check("round trip values", (account.id, account.name, account.institution) == (1, "Probe Savings", "Probe Bank"))
    check("round trip defaults", (account.currency, account.last4, account.is_active) == ("USD", None, True))
    back = account.created_at
    check("round trip time is aware UTC", back.tzinfo is not None and back.utcoffset() == timedelta(0))
    both_aware = aware and back.tzinfo is not None
    check("round trip time is unchanged", both_aware and abs(back - made) < timedelta(seconds=1))

for label, values in [
    ("duplicate name", {"name": "Probe Savings", "institution": "Other Bank", "type": "other"}),
    ("missing name", {"institution": "Probe Bank", "type": "other"}),
    ("missing institution", {"name": "No Institution", "type": "other"}),
    ("missing type", {"name": "No Type", "institution": "Probe Bank"}),
]:
    with Session(engine) as session:
        session.add(AccountRow(**values))
        try:
            session.flush()
            check(f"{label} is rejected", False)
        except IntegrityError:
            check(f"{label} is rejected", True)

with Session(engine) as session:
    session.add(AccountRow(name="Second", institution="Probe Bank", type="checking", last4="0042", is_active=False))
    session.flush()
    second = to_account(session.get(AccountRow, 2))
    check("explicit values win over defaults", (second.last4, second.is_active) == ("0042", False))

mapped = sorted(name for name, value in vars(orm).items() if isinstance(value, type) and issubclass(value, Base))
check(f"no extra tables {mapped}", mapped == ["AccountRow", "Base"])
functions = sorted(name for name, value in vars(orm).items() if callable(value) and getattr(value, "__module__", "") == orm.__name__ and not isinstance(value, type) and not name.startswith("_"))
check(f"no extra public functions {functions}", functions == ["to_account"])
print("FAILURES", failures)
```

## 5. Progress log

`docs/progress.md` ends with the entry given in step 17 of the spec, with a real date in place of `YYYY-MM-DD`. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then one line: `Steps skipped or out of order: <none, or the step numbers>`.

## If the verdict is FAIL

Send each repair in one of these forms, and no other:

- "Run step N of the spec again."
- "Replace the whole content of `<given file>` with the block in step N." (`pyproject.toml` or `tests/unit/test_orm.py` only)
- For a column: "The `<name>` column must be `<what the Part 1 table says>`; it is `<what was found>`. Change only that column, then run steps 11 to 23 again."
- For the function: "`to_account` given `<input>` returned `<got>`; it must return `<want>`. Change only the body of `to_account`, then run steps 14 to 23 again." At most three.
- For a rule: "Line N of `orm.py` has `<thing>`, which R<n> forbids. Rewrite that line, then run steps 14 to 23 again."
