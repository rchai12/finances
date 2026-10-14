# Verify Phase 21: people and ownership

Spec: `docs/phases/phase-21-people-and-ownership.md`

Do not modify any file in the repository, and do not run `fin` against the real database in `data/`. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder added migration `0006` (people, account owners, cardholder aliases), a pure rule in `domain/people.py`, seven repository functions, a new package `src/finances/analysis/` with the attribution, the `fin people` commands, `fin accounts set-owner`, an `Owner` column, and a `Person` column with `--person` in `fin transactions list`. Four test files were given; the coder wrote one.

Judge the code by what it does, never by how it is written. These are correct and must not be reported: any private helpers; filtering by person in Python after reading the rows, as long as the limit applies after the filter; reading owners and aliases once per command.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it; it is `1454` when Phase 17d was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 74 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/integration/test_migration_0006.py tests/unit/test_people_rules.py tests/integration/test_people_attribution.py tests/e2e/test_cli_people.py --no-cov` | exactly `74 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with every module of `finances.analysis`, `finances.db`, `finances.domain`, and `finances.cli` at 100% |
| `.venv/bin/python -c "from finances.db.migrate import head_revision; print(head_revision())"` | `0006` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis --cov=finances.db --cov=finances.domain --cov=finances.cli --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/cli/accounts.py
 M src/finances/cli/listing.py
 M src/finances/cli/main.py
 M src/finances/db/orm.py
 M src/finances/db/repositories.py
 M src/finances/domain/models.py
?? src/finances/analysis/
?? src/finances/cli/people.py
?? src/finances/db/migrations/versions/0006_people.py
?? src/finances/domain/people.py
?? tests/e2e/test_cli_people.py
?? tests/integration/test_migration_0006.py
?? tests/integration/test_people_attribution.py
?? tests/integration/test_people_repositories.py
?? tests/unit/test_people_rules.py
```

- The four given test files are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- src/finances/domain/models.py src/finances/db/orm.py src/finances/db/repositories.py` only adds lines, apart from import lines that gained a name.
- In `git diff HEAD -- src/finances/cli/accounts.py src/finances/cli/listing.py`, the only changes to existing commands are the `Owner` and `Person` columns, the `--person` option, and listing through `list_transactions_with_people`; no heading, cell, or message of the existing commands changed.
- `src/finances/analysis/` holds exactly `__init__.py` (a docstring) and `people.py`.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1, R2 | tables | gate 4; read `0006_people.py` | `down_revision = "0005"`; no import from `finances`; no `server_default`; every constraint named; `downgrade` drops the three tables |
| R3 to R5 | the rule | probe script | every line starting `rules:` |
| R6 to R12 | repositories | the coder's tests (section 5); probe script | `cli: add Kim`, `cli: a second Kim in another case is refused`, `cli: people list` |
| R13 to R15 | attribution | probe script | `cli: transactions show their person`, the four lines starting `cli: --person`, `cli: the limit counts only the person's rows`, `cli: an unknown person`, `cli: moving an alias moves the attribution` |
| R16 to R19 | people and owner commands | probe script | `cli: add ...`, `cli: Lee owns the Visa`, `cli: the checking account is joint`, `cli: KIM PROBE on statements is Kim` |
| R20, R21 | the new columns | probe script | `cli: accounts list shows each owner`, `cli: transactions show their person` |
| R22 | registration | read `main.py` | the `people` group after `sync` |
| layering | pure rule, thin commands | the searches below | no output |

Run each of these searches. Each must print nothing.

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/analysis src/finances/domain/people.py src/finances/cli/people.py`

`git grep -n --untracked -E "^ *(import|from) +finances" -- src/finances/domain/people.py`

`git grep -n --untracked -E "finances\.(cli|ingest|sync)" -- src/finances/analysis`

`git grep -n --untracked -E "select\(|finances\.db\.orm|session\.(add|execute)" -- src/finances/analysis src/finances/cli/people.py src/finances/cli/accounts.py src/finances/cli/listing.py`

## 4. Independent probes

The script checks the rule directly, then tells a household story with its own names through the commands, on a temporary data folder that it removes: three accounts, two people, one owner, one Joint account, one cardholder alias, five transactions, every `--person` filter, and an alias moved to the other person. It writes nothing outside that folder.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`. A line that says a section `ran to the end (stopped by ...)` and ends in `FAIL` means the code raised where it should not have; report it with the exception named on that line.

```python
import os
import tempfile
from datetime import date

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def outcome(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, str(exc))


def section(name, function):
    try:
        function()
    except Exception as exc:  # noqa: BLE001
        check(f"{name}: ran to the end (stopped by {type(exc).__name__}: {exc})", False)


def cells(output):
    return [[cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]] for line in output.splitlines() if line.startswith(("│", "┃"))]


def rule_checks():
    from finances.domain.people import JOINT, normalize_cardholder, person_for, validate_person_name

    aliases = {"KIM PROBE": "Kim", "LEE O'PROBE": "Lee"}
    check("rules: cardholder names are compared in upper case with single spaces", normalize_cardholder("  kim\t probe ") == "KIM PROBE")
    check("rules: the cardholder's person comes first", person_for("Kim  Probe", "Lee", aliases) == "Kim")
    check("rules: then the account's owner", person_for("SOMEONE ELSE", "Lee", aliases) == "Lee" and person_for(None, JOINT, aliases) == JOINT)
    check("rules: no owner and no known cardholder is unassigned", person_for("SOMEONE ELSE", None, aliases) is None)
    check("rules: reserved names", outcome(validate_person_name, " UNASSIGNED ") == ("ValueError", "joint and unassigned are reserved names"))


def cli_checks():
    from typer.testing import CliRunner

    from finances.cli.main import app
    from finances.config import get_settings
    from finances.db.engine import get_engine, session_scope
    from finances.db.orm import TransactionRow

    saved = os.environ.get("FIN_DATA_DIR")
    folder = tempfile.TemporaryDirectory()
    os.environ["FIN_DATA_DIR"] = folder.name
    get_settings.cache_clear()
    runner = CliRunner(env={"COLUMNS": "200"})

    def fin(*args):
        return runner.invoke(app, list(args))

    try:
        check("cli: db upgrade to 0006", fin("db", "upgrade").exit_code == 0)
        from finances.db.migrate import head_revision
        check("cli: the newest revision is 0006", head_revision() == "0006")
        for name, kind in (("Probe Visa", "credit_card"), ("Probe Joint Checking", "checking"), ("Probe Brokerage", "other")):
            fin("accounts", "add", "--name", name, "--institution", "Probe Bank", "--type", kind)
        check("cli: add Kim", fin("people", "add", "--name", "Kim").stdout == 'Added person "Kim" (id 1)\n')
        check("cli: add Lee", fin("people", "add", "--name", "Lee").stdout == 'Added person "Lee" (id 2)\n')
        check("cli: a second Kim in another case is refused", fin("people", "add", "--name", "KIM").stderr == "Error: a person with this name already exists\n")
        check("cli: Lee owns the Visa", fin("accounts", "set-owner", "--account", "probe visa", "--owner", "lee").stdout == 'Owner of "Probe Visa" is Lee.\n')
        check("cli: the checking account is joint", fin("accounts", "set-owner", "--account", "Probe Joint Checking", "--owner", "Joint").stdout == 'Owner of "Probe Joint Checking" is Joint.\n')
        check("cli: KIM PROBE on statements is Kim", fin("people", "alias", "--person", "kim", "--cardholder", "kim   probe").stdout == 'Cardholder "KIM PROBE" is Kim.\n')
        listed = cells(fin("accounts", "list").stdout)
        check("cli: accounts list shows each owner", [row[0::5] for row in listed] == [["Name", "Owner"], ["Probe Brokerage", ""], ["Probe Joint Checking", "Joint"], ["Probe Visa", "Lee"]])
        engine = get_engine(get_settings().effective_database_url)
        with session_scope(engine) as session:
            for account_id, day, cents, cardholder in ((1, 20, -1875, "KIM PROBE"), (1, 19, -5230, "LEE PROBE"), (1, 18, -999, None), (2, 17, 250000, None), (3, 16, 4100, None)):
                session.add(TransactionRow(account_id=account_id, posted_date=date(2027, 3, day), amount_cents=cents, description=f"PROBE {day}", cardholder=cardholder, source="statement", fingerprint=f"p{day}".ljust(64, "0")))
        engine.dispose()
        rows = cells(fin("transactions", "list").stdout)
        check("cli: transactions show their person", rows[0][-1] == "Person" and [(row[2], row[-1]) for row in rows[1:]] == [("PROBE 20", "Kim"), ("PROBE 19", "Lee"), ("PROBE 18", "Lee"), ("PROBE 17", "Joint"), ("PROBE 16", "")])
        for person, wanted in (("kim", ["PROBE 20"]), ("LEE", ["PROBE 19", "PROBE 18"]), ("joint", ["PROBE 17"]), ("unassigned", ["PROBE 16"])):
            got = [row[2] for row in cells(fin("transactions", "list", "--person", person).stdout)[1:]]
            check(f"cli: --person {person}", got == wanted)
        check("cli: the limit counts only the person's rows", [row[2] for row in cells(fin("transactions", "list", "--person", "lee", "--limit", "1").stdout)[1:]] == ["PROBE 19"])
        check("cli: an unknown person", fin("transactions", "list", "--person", "Nobody").stderr == "Error: person not found\n")
        people = cells(fin("people", "list").stdout)
        check("cli: people list", people == [["Name", "Owns", "Cardholder names"], ["Kim", "", "KIM PROBE"], ["Lee", "Probe Visa", ""]])
        fin("people", "alias", "--person", "Lee", "--cardholder", "Kim Probe")
        moved = [row[-1] for row in cells(fin("transactions", "list", "--limit", "1").stdout)[1:]]
        check("cli: moving an alias moves the attribution", moved == ["Lee"])
    finally:
        if saved is None:
            os.environ.pop("FIN_DATA_DIR", None)
        else:
            os.environ["FIN_DATA_DIR"] = saved
        get_settings.cache_clear()
        folder.cleanup()


section("rules", rule_checks)
section("cli", cli_checks)
print("FAILURES", failures)
```

## 5. The coder's tests

Read `tests/integration/test_people_repositories.py`.

- **Coverage of requirements.** For each of R1 to R22, name a test, given or the coder's, that would fail if the requirement were broken. A requirement with no such test is a finding.
- **Repository tests go through the functions**, each of R6 to R12 called directly and its result or what it stored compared with literals.
- **Assertions are exact.** No `assert True`, no `pytest.raises(Exception)`, no `skip` or `xfail`.
- **Synthetic names only.**
- **Spot checks.** For each change below, say which test, given or the coder's, would fail, by reading the test. If none would, that is a finding.
  1. `list_people` returns people in id order.
  2. `set_account_owner` adds a second row for the same account.
  3. `set_cardholder_alias` stores the name without normalizing it.
  4. `create_person` accepts `ALEX` when `Alex` exists.
  5. `list_account_owners` includes accounts that have no owner row.
  6. `--person JOINT` (capitals) is treated as a person's name.
  7. `fin people list` leaves out closed accounts from `Owns`.

## 6. Project rules that apply to this phase

- **Layering.** `domain/people.py` imports nothing from the project; `analysis/` reads through `db` repositories and writes nothing; the commands hold no attribution logic and no query.
- **Messages.** Only the messages written in the spec; the only varying parts are names.
- **Schema.** One new migration; nothing shipped is edited; `accounts` and `transactions` are unchanged.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- Totals or reports by person, or any change to `fin statements list`.
- Removing or renaming people, or clearing an owner.
- Splitting a transaction between people.
- Any change to links, the feed, or statements.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 21: people and ownership (YYYY-MM-DD)` with a real date. "Built" gives N and the passed count. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 to Part 5 / tests>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code.
