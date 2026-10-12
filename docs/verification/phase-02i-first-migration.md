# Verify Phase 2i: the first migration

Spec: `docs/phases/phase-02i-first-migration.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote the bodies of `upgrade` and `downgrade` in the migration file. `pyproject.toml`, `env.py`, the test file, and the rest of the migration file were given. Judge the two bodies by the database they produce and by the rules.

Two things that are correct and must not be reported:

- Constraints written without `name=`. `env.py` passes the ORM's naming convention to Alembic, so an unnamed primary key or unique constraint still comes out as `pk_accounts` or `uq_accounts_name`. R2 and R3 are about the name in the database.
- The migration files do not appear in the coverage table. Alembic loads them by file path, outside the `finances` package import, so coverage does not list them. The tests still execute both functions.

In your report, say which steps, if any, were skipped or done out of order.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -c "import alembic; print(alembic.__version__.split('.')[0])"` | `1` |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `28 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `208 passed`, 0 skipped, 0 xfailed, and `Required test coverage of 85.0% reached` |

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, ` M pyproject.toml`, `?? src/finances/db/migrations/`, `?? tests/integration/test_migrations.py`. Report every other path.
- `src/finances/db/migrations/` holds exactly `env.py` and `versions/0001_accounts.py` (ignore `__pycache__`). There is no `alembic.ini`, `script.py.mako`, or `README` anywhere in the repository.
- `git diff HEAD -- pyproject.toml` adds one line, `"alembic>=1.13",`, and changes nothing else. The file ends with a newline.
- `git diff HEAD -- src/finances/db/orm.py src/finances/db/engine.py src/finances/domain tests/unit tests/e2e tests/conftest.py tests/integration/test_engine.py` is empty.
- No database file was left behind: `git status --short --ignored` shows no `.db` or `.sqlite` file and no `data/` folder in the repository.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test file untouched | compare `tests/integration/test_migrations.py` with the block in step 7 of the spec | identical apart from trailing whitespace; the file ends with a newline |
| given | `env.py` untouched | compare with the block in step 5 | identical apart from trailing whitespace |
| R1 to R5 | the table | probe script | `migration and ORM build the same tables`, `revision recorded`, `row round trip`, and `time comes back as UTC` end in `ok` |
| R1 | time zone declared | read `upgrade` | the `created_at` column is `sa.DateTime(timezone=True)` |
| R4 | nothing extra | run the search below this table | no output |
| R6 | downgrade | probe script | the two `downgrade` lines, `second upgrade rebuilds the same table`, `the table was really dropped`, and `repeated cycles` end in `ok` |
| R7 | self-contained | probe script | the `imports` line ends in `ok` |
| R8 | revision lines kept | probe script | the four `kept:` lines end in `ok` |
| scope | nothing extra | probe script | `one migration file`, `only upgrade and downgrade are defined`, and `only the two database files exist` end in `ok` |

`git grep -n --untracked -E "finances|server_default|create_index|print\(" -- src/finances/db/migrations/versions`

## 4. Independent probes

The given tests check the migrated database against a list of expected columns. This script checks it against a second database built directly from the ORM class, so any difference between the two shows up without a list. It also checks that `downgrade` really drops the table (a row inserted before the downgrade is gone afterwards), runs the cycle several times, and reads the migration file for anything added.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It works inside its own temporary folder. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import tempfile
from datetime import timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, Base, to_account

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def shape(url):
    """Everything the database knows about its tables, in a comparable form."""
    engine = get_engine(url)
    inspector = inspect(engine)
    result = {}
    for table in sorted(inspector.get_table_names()):
        if table == "alembic_version":
            continue
        result[table] = {
            "columns": [
                (c["name"], str(c["type"]), c["nullable"], c["default"], c["primary_key"])
                for c in inspector.get_columns(table)
            ],
            "pk": (inspector.get_pk_constraint(table)["name"], inspector.get_pk_constraint(table)["constrained_columns"]),
            "unique": sorted((u["name"], tuple(u["column_names"])) for u in inspector.get_unique_constraints(table)),
            "indexes": inspector.get_indexes(table),
            "foreign_keys": inspector.get_foreign_keys(table),
            "checks": inspector.get_check_constraints(table),
        }
    engine.dispose()
    return result


def versions(url):
    engine = get_engine(url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    engine.dispose()
    return [row[0] for row in rows]


def count_accounts(url):
    engine = get_engine(url)
    with session_scope(engine) as session:
        total = session.query(AccountRow).count()
    engine.dispose()
    return total


try:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder).resolve()
        migrated = f"sqlite:///{(root / 'migrated.db').as_posix()}"
        from_orm = f"sqlite:///{(root / 'from_orm.db').as_posix()}"
        config = Config()
        config.set_main_option("script_location", str(MIGRATIONS))
        config.set_main_option("sqlalchemy.url", migrated)

        command.upgrade(config, "0001")
        engine = get_engine(from_orm)
        Base.metadata.create_all(engine)
        engine.dispose()
        left, right = shape(migrated), shape(from_orm)
        check("migration and ORM build the same tables", left == right)
        if left != right:
            print("  migrated:", left)
            print("  from ORM:", right)
        check("revision recorded", versions(migrated) == ["0001"])

        engine = get_engine(migrated)
        with session_scope(engine) as session:
            session.add(AccountRow(name="Probe", institution="Probe Bank", type="savings", last4="0042"))
        with session_scope(engine) as session:
            account = to_account(session.query(AccountRow).one())
        engine.dispose()
        check("row round trip", (account.name, account.last4, account.currency) == ("Probe", "0042", "USD"))
        check("time comes back as UTC", account.created_at.utcoffset() == timedelta(0))

        command.downgrade(config, "base")
        check("downgrade leaves no application table", shape(migrated) == {})
        check("downgrade clears the revision", versions(migrated) == [])

        command.upgrade(config, "head")
        check("second upgrade rebuilds the same table", shape(migrated) == right)
        check("the table was really dropped (old row is gone)", count_accounts(migrated) == 0)

        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        check("repeated cycles end in the same place", shape(migrated) == right and versions(migrated) == ["0001"])
        names = sorted(path.name for path in root.iterdir())
        check(f"only the two database files exist {names}", names == ["from_orm.db", "migrated.db"])
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)

files = sorted(path.name for path in (MIGRATIONS / "versions").glob("*.py"))
check(f"one migration file {files}", files == ["0001_accounts.py"])
source = (MIGRATIONS / "versions" / "0001_accounts.py").read_text(encoding="utf-8")
for line in ['revision = "0001"', "down_revision = None", "branch_labels = None", "depends_on = None"]:
    check(f"kept: {line}", line in source)
defs = [line for line in source.splitlines() if line.startswith(("def ", "class "))]
check(f"only upgrade and downgrade are defined {defs}", defs == ["def upgrade() -> None:", "def downgrade() -> None:"])
imports = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
check(f"imports {imports}", sorted(imports) == ["from alembic import op", "import sqlalchemy as sa"])
print("FAILURES", failures)
```

## 5. Progress log

`docs/progress.md` ends with the entry given in step 18 of the spec, with a real date in place of `YYYY-MM-DD`. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then one line: `Steps skipped or out of order: <none, or the step numbers>`.

## If the verdict is FAIL

Send each repair in one of these forms, and no other:

- "Run step N of the spec again."
- "Replace the whole content of `<given file>` with the block in step N." (`pyproject.toml`, `env.py`, or the test file only)
- For `upgrade`: "The `<column or constraint>` must be `<what R1 to R4 say>`; the database has `<what was found>`. Change only the body of `upgrade`, then run steps 12 to 24 again." At most three.
- For `downgrade`: "After `downgrade`, `<what was found>`; R6 requires `<what is required>`. Change only the body of `downgrade`, then run steps 15 to 24 again."
- For a rule: "Line N of `0001_accounts.py` has `<thing>`, which R<n> forbids. Rewrite that line, then run steps 15 to 24 again."
