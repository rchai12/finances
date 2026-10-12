# Verify Phase 2k: `get_account_by_name` and `create_account`

Spec: `docs/phases/phase-02k-create-and-get-account.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote the bodies of `get_account_by_name` and `create_account`, and possibly private helpers (names starting with `_`). The test file and the rest of `repositories.py` were given. Judge the code by behavior and by the rules.

Every requirement in this spec is checked by a given test, and the spec has its own step for 100% coverage of `repositories.py`. So a failure here should be rare; if a gate fails, the most useful thing to report is which step the coder skipped.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `32 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `267 passed`, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| the coverage command below this table | `Required test coverage of 100% reached` |

`.venv/bin/python -m pytest tests/integration/test_repositories.py -o addopts="" --import-mode=importlib --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, `?? src/finances/db/repositories.py`, `?? tests/integration/test_repositories.py`. Report every other path.
- `git diff HEAD -- src tests/unit tests/e2e tests/conftest.py tests/integration/test_engine.py tests/integration/test_migrations.py tests/integration/test_migrate.py pyproject.toml` is empty.
- `git status --short --ignored` shows no `.db` or `.sqlite` file and no `data/` folder in the repository.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test file untouched | compare `tests/integration/test_repositories.py` with the block in step 3 of the spec | identical apart from trailing whitespace; the file ends with a newline |
| given | given parts kept | compare `repositories.py` with the block in step 1 | the module docstring, the `AccountExistsError` class, both `def` signatures, and both docstrings are unchanged. Import lines may differ |
| R1, R2 | lookup | probe script | `found before the commit`, `found after the commit`, `inner spaces must match`, and the two `wildcard` lines end in `ok` |
| R3 | create | probe script | `created account`, `outer spaces removed`, `type, currency, last4`, and `created_at is aware UTC` end in `ok` |
| R4 | empty text | probe script | `empty name` and `empty institution` end in `ok` |
| R5 | duplicates | probe script; search below | `duplicate, other case` and `session usable after five errors` end in `ok`; the search prints nothing (no `IntegrityError`) |
| R6 | last4 | probe script | `bad last4` and `non-ASCII last4` end in `ok` |
| R7 | type | probe script | `capitalised type text` ends in `ok` |
| R8 | flush, no commit | probe script; search below | `ids assigned before any commit`, `nothing committed by the function`, `only the two good rows exist`, and `rolled-back name is free again` end in `ok`; the search prints nothing |
| scope | nothing extra | probe script | `nothing extra is public` ends in `ok` |

`git grep -n --untracked -E "commit\(|rollback\(|close\(|print\(|logging|IntegrityError" -- src/finances/db/repositories.py`

## 4. Independent probes

None of these names or inputs are in the given tests. The script uses names with tabs and doubled inner spaces, lookups containing `%` and `_` (which a pattern match would treat as wildcards), several errors in a row inside one session, and a rollback after two creations.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It works inside its own temporary folder. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import tempfile
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finances.db import repositories
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AccountRow
from finances.db.repositories import AccountExistsError, create_account, get_account_by_name
from finances.domain.models import Account, AccountType

EXISTS = "an account with this name already exists"
failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def raises(kind, message, function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return type(exc) is kind and (message is None or str(exc) == message)
    return False


def count(engine):
    with session_scope(engine) as session:
        return session.scalar(select(func.count()).select_from(AccountRow))


try:
    with tempfile.TemporaryDirectory() as folder:
        url = f"sqlite:///{(Path(folder).resolve() / 'probe.db').as_posix()}"
        upgrade_to_head(url)
        engine = get_engine(url)

        with session_scope(engine) as session:
            made = create_account(session, "\tJoint  Savings ", "  Probe Credit Union", "savings", last4="0000")
            same = get_account_by_name(session, "JOINT  SAVINGS")
        check("created account", type(made) is Account and made.id == 1)
        check("outer spaces removed, inner spaces kept", (made.name, made.institution) == ("Joint  Savings", "Probe Credit Union"))
        check("type, currency, last4", (made.type, made.currency, made.last4) == (AccountType.SAVINGS, "USD", "0000"))
        check("created_at is aware UTC", made.created_at.tzinfo is not None and made.created_at.utcoffset() == timedelta(0))
        check("found before the commit, same values", same == made)

        with session_scope(engine) as session:
            check("found after the commit", get_account_by_name(session, " joint  savings\n") == made)
            check("inner spaces must match", get_account_by_name(session, "Joint Savings") is None)
            check("a pattern character is not a wildcard", get_account_by_name(session, "Joint%") is None)
            check("an underscore is not a wildcard", get_account_by_name(session, "Joint _Savings") is None)

        with session_scope(engine) as session:
            check("duplicate, other case", raises(AccountExistsError, EXISTS, create_account, session, "joint  SAVINGS", "X", "other"))
            check("empty name", raises(ValueError, "account name must not be empty", create_account, session, " \t ", "X", "other"))
            check("empty institution", raises(ValueError, "institution must not be empty", create_account, session, "New", "\n", "other"))
            check("capitalised type text", raises(ValueError, None, create_account, session, "New", "X", "Savings"))
            check("bad last4", raises(ValueError, "last4 must be exactly 4 digits", create_account, session, "New", "X", "other", last4="12345"))
            check("non-ASCII last4", raises(ValueError, "last4 must be exactly 4 digits", create_account, session, "New", "X", "other", last4="\u0661\u0662\u0663\u0664"))
            second = create_account(session, "New", "X", AccountType.CREDIT_CARD, currency="EUR")
            check("session usable after five errors", second.id == 2 and second.currency == "EUR")
        check("only the two good rows exist", count(engine) == 2)

        session = Session(engine)
        third = create_account(session, "Temporary", "X", "checking")
        fourth = create_account(session, "Temporary Two", "X", "checking")
        check("ids assigned before any commit", (third.id, fourth.id) == (3, 4))
        session.rollback()
        session.close()
        check("nothing committed by the function", count(engine) == 2)

        with session_scope(engine) as session:
            check("rolled-back name is free again", create_account(session, "temporary", "X", "other").name == "temporary")
        engine.dispose()
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)

public = sorted(
    name
    for name, value in vars(repositories).items()
    if getattr(value, "__module__", "") == repositories.__name__ and not name.startswith("_")
)
check(f"nothing extra is public {public}", public == ["AccountExistsError", "create_account", "get_account_by_name"])
print("FAILURES", failures)
```

## 5. Progress log

`docs/progress.md` ends with the entry given in step 14 of the spec, with a real date in place of `YYYY-MM-DD`. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then one line: `Steps skipped or out of order: <none, or the step numbers>`.

## If the verdict is FAIL

Send each repair in one of these forms, and no other:

- "Run step N of the spec again."
- "Replace the whole content of `tests/integration/test_repositories.py` with the block in step 3."
- For a function: "R<n> is not met: `<call>` gave `<got>`; it must give `<want>`. Change only the body of `<function>`, then run steps 10 to 21 again." At most three.
- For code no test reaches: "Delete lines N to M of `repositories.py`: no requirement asks for them. Then run steps 10 to 21 again."
- For a rule: "Line N of `repositories.py` has `<thing>`, which the Rules section forbids. Rewrite that line, then run steps 10 to 21 again."
