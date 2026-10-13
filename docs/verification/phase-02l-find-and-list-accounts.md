# Verify Phase 2l: `find_accounts_by_last4` and `list_accounts`

Spec: `docs/phases/phase-02l-find-and-list-accounts.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote the bodies of `find_accounts_by_last4` and `list_accounts`, and possibly private helpers (names starting with `_`). The test file and the two `def` lines with their docstrings were given. Judge the code by behavior and by the rules.

Every requirement in this spec is checked by a given test, and the spec has its own step for 100% coverage of `repositories.py`. If a gate fails, the most useful thing to report is which step the coder skipped.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `32 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `282 passed`, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| the coverage command below this table | `Required test coverage of 100% reached` |

`.venv/bin/python -m pytest tests/integration/test_repositories.py -o addopts="" --import-mode=importlib --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, ` M src/finances/db/repositories.py`, ` M tests/integration/test_repositories.py`. Report every other path.
- `git diff HEAD -- src/finances/db/repositories.py` only adds lines: the two new functions at the end, and at most new import lines at the top. `AccountExistsError`, `get_account_by_name`, and `create_account` have no changed or removed line.
- `git diff HEAD -- tests/integration/test_repositories.py` changes the import line and adds tests at the end. No Phase 2k test is changed or removed.
- `git status --short --ignored` shows no `.db` or `.sqlite` file and no `data/` folder in the repository.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test file untouched | compare `tests/integration/test_repositories.py` with the block in step 1 of the spec | identical apart from trailing whitespace; the file ends with a newline |
| given | signatures kept | compare the two new functions with the block in step 3 | both `def` lines and both docstrings are unchanged |
| R1 | find | probe script | `find: all three`, `find: ids`, `find: a list of Account`, and `find: other digits` end in `ok` |
| R2 | no match | probe script | `empty database: find` and `find: no match` end in `ok` |
| R3 | bad input | probe script | the six `find: rejects` lines end in `ok` |
| R4 | active filter | probe script | `list: active only`, `list: everything`, `list: flags`, and `list: positional False` end in `ok` |
| R5 | order and type | probe script | the two `sorted without regard to case` lines and `list: a list of Account` end in `ok` |
| R6 | empty | probe script | `empty database: list` and `empty database: list all` end in `ok` |
| rules | read-only | probe script; search below | `functions changed nothing` ends in `ok`; the search prints nothing |
| scope | nothing extra | probe script | `nothing extra is public` ends in `ok` |

`git grep -n -E "commit\(|rollback\(|close\(|print\(|logging|== True|== False" -- src/finances/db/repositories.py`

## 4. Independent probes

None of these names or digits are in the given tests. The script mixes active and inactive accounts that share the same last four digits, uses names whose order differs between case-sensitive and case-insensitive sorting, and checks that neither function changes the database.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It works inside its own temporary folder. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import tempfile
from pathlib import Path

from finances.db import repositories
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AccountRow
from finances.db.repositories import create_account, find_accounts_by_last4, list_accounts
from finances.domain.models import Account

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def names(accounts):
    return [account.name for account in accounts]


def rejects(session, text):
    try:
        find_accounts_by_last4(session, text)
    except ValueError as exc:
        return str(exc) == "last4 must be exactly 4 digits"
    except Exception:  # noqa: BLE001
        return False
    return False


try:
    with tempfile.TemporaryDirectory() as folder:
        url = f"sqlite:///{(Path(folder).resolve() / 'probe.db').as_posix()}"
        upgrade_to_head(url)
        engine = get_engine(url)

        with session_scope(engine) as session:
            check("empty database: find", find_accounts_by_last4(session, "7777") == [])
            check("empty database: list", list_accounts(session) == [])
            check("empty database: list all", list_accounts(session, True) == [])

        rows = [
            ("mango Card", "7777", True),
            ("Zucchini Savings", None, True),
            ("apricot Checking", "0001", False),
            ("Lemon Card", "7777", False),
            ("banana Card", "7777", True),
            ("Kiwi", "0001", True),
        ]
        with session_scope(engine) as session:
            for name, last4, _active in rows:
                create_account(session, name, "Probe Bank", "other", last4=last4)
            for name, _last4, active in rows:
                if not active:
                    session.query(AccountRow).filter_by(name=name).one().is_active = False

        with session_scope(engine) as session:
            found = find_accounts_by_last4(session, "7777")
            check("find: all three, inactive included, id order", names(found) == ["mango Card", "Lemon Card", "banana Card"])
            check("find: ids", [account.id for account in found] == [1, 4, 5])
            check("find: a list of Account", type(found) is list and all(type(a) is Account for a in found))
            check("find: other digits", names(find_accounts_by_last4(session, "0001")) == ["apricot Checking", "Kiwi"])
            check("find: no match", find_accounts_by_last4(session, "9999") == [])
            for text in ["77777", "777", "7 77", "77.7", "\u0667\u0667\u0667\u0667", "7777\n"]:
                check(f"find: rejects {text!r}", rejects(session, text))

            active = list_accounts(session)
            check("list: active only, sorted without regard to case", names(active) == ["banana Card", "Kiwi", "mango Card", "Zucchini Savings"])
            check("list: a list of Account", type(active) is list and all(type(a) is Account for a in active))
            everything = list_accounts(session, include_inactive=True)
            check(
                "list: everything, sorted without regard to case",
                names(everything) == ["apricot Checking", "banana Card", "Kiwi", "Lemon Card", "mango Card", "Zucchini Savings"],
            )
            check("list: flags", [a.is_active for a in everything] == [False, True, True, False, True, True])
            check("list: positional False equals the default", list_accounts(session, False) == active)
            check("list: calling twice gives equal lists", list_accounts(session) == active)
            check("functions changed nothing", session.query(AccountRow).count() == 6 and not session.dirty and not session.new)
        engine.dispose()
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)

public = sorted(
    name
    for name, value in vars(repositories).items()
    if getattr(value, "__module__", "") == repositories.__name__ and not name.startswith("_")
)
expected = ["AccountExistsError", "create_account", "find_accounts_by_last4", "get_account_by_name", "list_accounts"]
check(f"nothing extra is public {public}", public == expected)
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
- "Replace the whole content of `tests/integration/test_repositories.py` with the block in step 1."
- For a function: "R<n> is not met: `<call>` gave `<got>`; it must give `<want>`. Change only the body of `<function>`, then run steps 10 to 21 again." At most three.
- For code no test reaches: "Delete lines N to M of `repositories.py`: no requirement asks for them. Then run steps 10 to 21 again."
- For a rule: "Line N of `repositories.py` has `<thing>`, which the Rules section forbids. Rewrite that line, then run steps 10 to 21 again."
