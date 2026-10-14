# Verify Phase 23: one home for text rules, limits, and input checks

Spec: `docs/phases/phase-23-shared-rules.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

This phase must change **no behaviour**. It moves text cutting and column widths into `finances.domain.text`, moves typed-input checks into the repository and the domain validators, and replaces small copied helpers. The risk is a changed message or a changed order of messages when a form has two mistakes; the probe compares the last commit with the work under review on exactly those cases.

Judge the code by what it does. These are correct and must not be reported: `NAME_LIMIT` imported into `domain/people.py` rather than assigned; `TEXT_LIMIT = NAME_LIMIT` in `feed_setup.py`; the order of imports.

## 1. Gates

Run each command on its own line from the repository root. Do not activate the virtual environment.

**N** is the passed count before the phase; the coder's entry in `docs/progress.md` states it. It is `2007` when Phase 22 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 53 passed in the `tests` step, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_text.py tests/unit/test_shared_helpers.py tests/integration/test_repository_rules.py --no-cov` | exactly `53 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| `git diff HEAD --stat -- tests src/finances/web/templates src/finances/db/migrations scripts` | nothing |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain --cov=finances.db --cov=finances.ingest --cov=finances.sync --cov=finances.cli --cov=finances.web --cov=finances.views --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` shows only paths of the spec's Scope table, plus the three new test files and `docs/progress.md`. Report every other one.
- The three given test files are identical to the blocks in the spec. No existing test, template, migration, or script changed (gate 4).
- `git diff HEAD -- AGENTS.md` adds exactly the sentence of R15.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 to R4 | text and widths | gate 2; the searches | passes; no output |
| R5 to R9 | input checks | gate 2 | passes |
| R10 to R12 | same order, same messages | probe | every line starting `same:`, in particular `same: map: unknown account and a blank id` and `same: web add: empty name and a bad type` |
| R13, R14 | shared helpers | the first search | no output |
| R15 | the document | section 2 | the one sentence |

Run each of these searches. Each must print nothing.

`git grep -n -E 'def (_tidy|_feed_text|_description|_squeezed|_fail|_feed_id|_owner_id)\(|(^|[^A-Z])_FEED_ID_LIMIT|ACCOUNT_TEXT_LIMIT|(^|[^A-Z])_ID_LIMIT|(^|[^A-Z])_DESCRIPTION_LIMIT|join\(text\.split\(\)\)\[:' -- src/finances ':!src/finances/domain/text.py'`

`git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views)" -- src/finances/domain`

## 4. Independent probe

The script extracts the last commit's `src/` into a temporary folder with `git archive` (it does not touch the repository), then runs one scenario twice in fresh interpreters: on that copy and on the work under review. The scenario uses a temporary data folder, an in-memory keychain, and a fake SimpleFIN; it contacts nothing. Besides the listings, syncs, and pages, it runs every refusal this phase moved, with one mistake and with two: `fin sync map` with an unknown account and a blank id, `fin accounts set-owner` with an unknown account and an unknown person, `fin accounts add` with a long name, and the web's Add account, owner, map, and create-and-map forms with mixed mistakes. It compares each output after replacing form tokens and clock times.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It takes about fifteen seconds. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

failures = 0
ROOT = Path.cwd()
# Runs in a fresh interpreter against one copy of the code. Prints each section as
# "@@ NAME" followed by its output. Uses a temporary data folder, an in-memory keychain,
# and a fake SimpleFIN; it contacts nothing.
SCENARIO = r"""
import base64, json, os, sys, tempfile
from datetime import UTC, date, datetime, timedelta
import keyring, keyring.backend, keyring.errors

class Memory(keyring.backend.KeyringBackend):
    priority = 1
    def __init__(self):
        super().__init__(); self.p = {}
    def get_password(self, s, u): return self.p.get((s, u))
    def set_password(self, s, u, v): self.p[(s, u)] = v
    def delete_password(self, s, u): del self.p[(s, u)]

class Broken(keyring.backend.KeyringBackend):
    priority = 1
    def get_password(self, s, u): raise keyring.errors.KeyringError("locked")
    def set_password(self, s, u, v): raise keyring.errors.KeyringError("locked")
    def delete_password(self, s, u): raise keyring.errors.KeyringError("locked")

memory = Memory(); keyring.set_keyring(memory)
os.environ["FIN_DATA_DIR"] = tempfile.mkdtemp()
os.environ["COLUMNS"] = "220"
from typer.testing import CliRunner
from fastapi.testclient import TestClient
from finances.cli.main import app as cli
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, TransactionRow
from finances.db.repositories import create_account, create_person, set_account_owner, set_cardholder_alias, map_feed_account
from finances.sync import transport
from finances.web.app import create_app

runner = CliRunner(env={"COLUMNS": "220"})
def show(name, text):
    print("@@ " + name); print(text)
def cli_run(name, *args):
    result = runner.invoke(cli, list(args))
    show(name, f"exit={result.exit_code}\n--stdout--\n{result.stdout}--stderr--\n{result.stderr}")

ALEX = "https://alex-u:alex-p@bridge.simplefin.org/simplefin"
SAM = "https://sam-u:sam-p@bridge.simplefin.org/simplefin"
def key(access):
    user, password = access.split("//")[1].split("@")[0].split(":")
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
noon = int(datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0).timestamp())
def acct(feed_id, name, balance, *moves):
    return {"id": feed_id, "name": name, "conn_id": "C", "currency": "USD", "balance": balance, "balance-date": noon,
            "transactions": [{"id": t, "posted": noon - days * 86400, "amount": amount, "description": "PROBE " + t} for t, days, amount in moves]}
answers = {
    key(ALEX): [200, [acct("A-1", "Probe Card", "-12.50", ("T1", 2, "-12.50")), acct("A-7", "Rewards Visa 2468", "0.00")], ["Probe note"]],
    key(SAM): [200, [acct("S-1", "Sam Savings 9999", "40.00", ("T2", 1, "40.00"))], []],
}
def bridge(method, url, headers):
    status, accounts, notes = answers[headers["Authorization"]]
    body = {"errlist": [{"code": "x", "msg": n} for n in notes], "connections": [{"conn_id": "C", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}], "accounts": accounts}
    return status, json.dumps(body).encode()
transport.urllib_transport = bridge

cli_run("db upgrade", "db", "upgrade")
with session_scope(get_engine()) as s:
    card = create_account(s, "Probe Card", "Probe Bank", "credit_card", last4="1111")
    checking = create_account(s, "Probe Checking", "Probe Bank", "checking")
    old = create_account(s, "Probe Old", "Probe Bank", "savings", last4="9999")
    kim = create_person(s, "Kim"); lee = create_person(s, "Lee")
    set_account_owner(s, card.id, kim.id); set_account_owner(s, checking.id, None); set_account_owner(s, old.id, lee.id)
    set_cardholder_alias(s, "LEE PROBE", lee.id)
    s.get(AccountRow, old.id).is_active = False
    for i, (acc, cents, card4, holder) in enumerate(((card.id, -1875, "2222", "LEE PROBE"), (checking.id, 90000, None, None))):
        s.add(TransactionRow(account_id=acc, posted_date=date(2026, 4, 10 + i), amount_cents=cents, description=f"PROBE <b>{i}</b>",
                             section="purchases", card_last4=card4, cardholder=holder, source="statement", fingerprint=f"p{i}".ljust(64, "0")))
    map_feed_account(s, card.id, "A-1", "alex"); map_feed_account(s, checking.id, "B-1", "bob"); map_feed_account(s, old.id, "S-1", "sam")
memory.p[("finances-simplefin", "alex")] = ALEX
memory.p[("finances-simplefin", "sam")] = SAM

cli_run("accounts list", "accounts", "list")
cli_run("accounts list --all", "accounts", "list", "--all")
cli_run("people list", "people", "list")
cli_run("transactions list", "transactions", "list")
cli_run("statements list", "statements", "list")
cli_run("sync run", "sync", "run")
cli_run("sync run --link sam", "sync", "run", "--link", "sam")
answers[key(ALEX)][0] = 403
cli_run("sync run with a refused link", "sync", "run")
answers[key(ALEX)][0] = 200
cli_run("sync status", "sync", "status")

client = TestClient(create_app(8765), base_url="http://127.0.0.1:8765")
for path in ("/accounts", "/accounts?closed=true", "/people", "/transactions", "/transactions?person=lee", "/sync"):
    show("page " + path, client.get(path).text)
show("page sync run", client.post("/sync/run", data={"csrf": client.cookies["fin_csrf"]}).text)

cli_run("map: unknown account and a blank id", "sync", "map", "--account", "Nope", "--feed-account", "  ", "--link", "alex")
cli_run("map: unknown account", "sync", "map", "--account", "Nope", "--feed-account", "ACT-5", "--link", "alex")
cli_run("map: id too long", "sync", "map", "--account", "Probe Checking", "--feed-account", "X" * 201, "--link", "alex")
cli_run("map: id with spaces", "sync", "map", "--account", "Probe Checking", "--feed-account", "  B-2 ", "--link", "bob")
cli_run("set-owner: unknown person", "accounts", "set-owner", "--account", "Probe Card", "--owner", "Nobody")
cli_run("set-owner: unknown account and person", "accounts", "set-owner", "--account", "Nope", "--owner", "Nobody")
cli_run("set-owner: joint", "accounts", "set-owner", "--account", "Probe Card", "--owner", "  JOINT ")
cli_run("set-owner: a person", "accounts", "set-owner", "--account", "Probe Card", "--owner", " kim ")
cli_run("accounts add: name too long", "accounts", "add", "--name", "N" * 101, "--institution", "Probe Bank", "--type", "other")
def form(label, path, **fields):
    response = client.post(path, data={"csrf": client.cookies["fin_csrf"], **fields}, follow_redirects=False)
    show(label, f"status={response.status_code} location={response.headers.get('location')}\n{response.text}")
form("web add: empty name and a bad type", "/accounts/add", name="", institution="", type="loan", last4="12")
form("web add: long institution", "/accounts/add", name="Probe New", institution="I" * 101, type="other")
form("web owner: unknown account and person", "/accounts/owner", account="Nope", owner="Nobody")
form("web owner: unknown person", "/accounts/owner", account="Probe Checking", owner="Nobody")
form("web owner: a person with spaces", "/accounts/owner", account="Probe Checking", owner=" kim ")
form("web map: unknown account and a blank id", "/sync/map", link="alex", feed_account="  ", account="Nope")
form("web map: blank id", "/sync/map", link="alex", feed_account="  ", account="Probe Checking")
form("web map: id with spaces", "/sync/map", link="alex", feed_account=" A-9 ", account="Probe Checking", next="sync")
form("web create: bad type and blank id", "/sync/create", link="alex", feed_account="", account="", institution="", type="loan")
form("web create: unknown owner", "/sync/create", link="alex", feed_account="A-7", account="Probe Rewards", institution="Probe Bank", type="credit_card", owner="Nobody")
form("web create: blank id", "/sync/create", link="alex", feed_account=" ", account="Probe Rewards", institution="Probe Bank", type="credit_card")
show("page /accounts after the forms", client.get("/accounts?closed=true").text)
show("page /sync after the forms", client.get("/sync").text)
keyring.set_keyring(Broken())
cli_run("sync run with a broken keychain", "sync", "run")
cli_run("sync status with a broken keychain", "sync", "status")
show("page /sync with a broken keychain", client.get("/sync").text)
"""


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def sections(src: Path) -> dict[str, str]:
    env = {**os.environ, "PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(
        [sys.executable, "-c", SCENARIO], capture_output=True, text=True, env=env, check=False
    )
    if done.returncode != 0:
        return {"scenario": "crashed: " + done.stderr.strip().splitlines()[-1]}
    text = re.sub(r'name="csrf" value="[^"]*"', 'name="csrf" value="TOKEN"', done.stdout)
    text = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", "TIME UTC", text)
    found = {}
    for part in text.split("@@ ")[1:]:
        name, _, body = part.partition("\n")
        found[name] = body
    return found


with tempfile.TemporaryDirectory() as folder:
    archive = subprocess.run(
        ["git", "archive", "HEAD", "src"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", folder], input=archive, check=True)
    before = sections(Path(folder) / "src")
after = sections(ROOT / "src")
check("scenario: runs on the last commit", "scenario" not in before and len(before) == 42)
check("scenario: runs on the work under review", "scenario" not in after)
for name in before:
    if name != "scenario":
        check(f"same: {name}", after.get(name) == before[name])
check("same: no section added or lost", set(after) == set(before))
print("FAILURES", failures)
```

## 5. The coder's tests

There are none to review. Confirm that the coder added no test file other than the three given ones and changed no existing test (gate 4). Then, for each change below, say which test would fail, by reading the tests. If none would, that is a finding.

1. `fit` does not trim trailing spaces after cutting.
2. `map_feed_account` stores the id with its outer spaces.
3. `create_account` checks the name before the type.
4. `fin sync map` looks up the account before checking the id. (The probe's `same: map: unknown account and a blank id`.)

## 6. Out of scope

Each of these must be absent. Report any that is present.

- A change to any output or message (the probe).
- A change to `ingest/service`'s cut-only `_fit` or to `sync/simplefin._clean`.
- A change to a migration or to `scripts/critical_modules.txt`.

## 7. Progress log

`docs/progress.md` ends with an entry headed `## Phase 23: one home for text rules, limits, and input checks (YYYY-MM-DD)` with a real date, N, and the passed count.

## Verdict

`PASS`, or `FAIL` followed by one line per finding:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then: `Total passed: <the count from the tests step>`

## If the verdict is FAIL

Send the coder each finding as: the requirement, what was observed, and what is required. Do not prescribe the code.
