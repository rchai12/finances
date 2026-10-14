# Verify Phase 17b: syncing from SimpleFIN

Spec: `docs/phases/phase-17b-simplefin-sync.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote one migration, a domain class, an ORM class, three repository functions, and three new modules in `src/finances/sync/`: the SimpleFIN client, the transport (the project's only network code), and `run_sync`. Four test files were given; the coder wrote one.

**Do not contact SimpleFIN or any other host.** Nothing in this guide needs the network. The probe script replaces `urllib.request.urlopen` while it checks the transport, and every other check uses a fake transport.

Judge the code by what it sends and returns and by the rules, never by how it is written. These are all correct and must not be reported:

- any way of decoding the token, building the URL, or reading the JSON that gives the specified results;
- private helpers and constants;
- `transport.py` importing `SyncError` from `simplefin.py`, or the other way round through a private module, as long as R16 holds.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it; it is `1291` when Phase 8 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 84 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/integration/test_migration_0004.py tests/unit/test_simplefin.py tests/unit/test_transport.py tests/integration/test_sync_runner.py --no-cov` | exactly `84 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with every module of `finances.sync`, `finances.db`, and `finances.domain` at 100% |
| `.venv/bin/python -c "from finances.db.migrate import head_revision; print(head_revision())"` | `0004` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov=finances.db --cov=finances.domain --cov-branch --cov-report=term-missing --cov-fail-under=100`

If you can, run the third command once more with the machine's network switched off. The result must be the same.

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/db/orm.py
 M src/finances/db/repositories.py
 M src/finances/domain/models.py
?? src/finances/db/migrations/versions/0004_feed_accounts.py
?? src/finances/sync/runner.py
?? src/finances/sync/simplefin.py
?? src/finances/sync/transport.py
?? tests/integration/test_feed_account_repositories.py
?? tests/integration/test_migration_0004.py
?? tests/integration/test_sync_runner.py
?? tests/unit/test_simplefin.py
?? tests/unit/test_transport.py
```

- The four given test files are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- src/finances/domain/models.py src/finances/db/orm.py src/finances/db/repositories.py` only adds lines, apart from import lines that gained a name.
- `git diff HEAD --stat -- src/finances/sync/feed.py src/finances/sync/service.py src/finances/ingest src/finances/cli src/finances/config.py tests/conftest.py tests/fixtures pyproject.toml` is empty, and no existing test file or migration is changed. No dependency was added.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | migration and ORM | gate 4; read `0004_feed_accounts.py` | `down_revision = "0003"`; no import from `finances`; no `server_default`; every constraint named; `downgrade` drops one table |
| R2, R3 | mapping | probe script; the coder's tests | every line starting `mapping:` |
| R4 | pending feed ids | probe script | `repositories: pending feed ids of one account, from a day on` |
| R6 | claiming | probe script | every line starting `client: a setup token` and `client: a used token` |
| R7 | fetching | probe script | `client: one GET to /accounts ...`, `client: credentials go in a Basic header, never in the URL`, the three lines starting `client: status`, and `client: an answer that is not JSON` |
| R8 to R12 | reading the answer | probe script | `client: the answer is read`, the two lines starting `client: a hold`, and `client: messages from both versions, printable and at most 200 characters` |
| R13 to R15 | the transport | probe script | every line starting `transport:` |
| R16 | one place for the network | the first two searches below | no output |
| R17 to R22 | a sync | probe script | every line starting `story`, `isolation:`, and `mapping: another currency is reported, and the window follows days` |
| secrets | nothing leaks | read every `raise` in `sync/`; search below | the only messages are the thirteen listed in the spec (R2, R6, R7, R15, R18, R20); none is an f-string; no exception, log, or print carries a URL, a token, or answer text |
| scope | nothing extra | probe script | `client: public names ...` and `client: the answer types are frozen` |

Run each of these searches. Each must print nothing.

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "^ *(import|from) +(urllib\.request|urllib\.error|socket|http\.client|ssl)" -- src/finances ':!src/finances/sync/transport.py'`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/sync`

`git grep -n --untracked -E "finances\.(ingest|cli)" -- src/finances/sync src/finances/db src/finances/domain`

Then read `transport.py`: it must not create an SSL context, set `check_hostname`, use `ssl._create_unverified_context`, or pass `context=` to `urlopen`.

## 4. Independent probes

The script builds its own SimpleFIN answers (an institution, accounts, holds, and messages that are not in the fixtures or the spec) and its own fake Bridge, and replaces `urllib.request.urlopen` only while it checks the transport, restoring it afterwards. It tells a three-sync story on a fresh database: a hold that posts under a new id, then an answer with a message from the aggregator.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Each database it uses is a file in a temporary directory that it removes. It opens no connection. Every line must end in `ok`; the last line must be `FAILURES 0`. A line that says a section `ran to the end (stopped by ...)` and ends in `FAIL` means the code raised where it should not have; report it with the exception named on that line.

```python
import base64
import dataclasses
import io
import json
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def outcome(function, *args, **kwargs):
    """Return the value, or the exception type name and message."""
    try:
        return function(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, str(exc))


def section(name, function):
    try:
        function()
    except Exception as exc:  # noqa: BLE001
        check(f"{name}: ran to the end (stopped by {type(exc).__name__}: {exc})", False)


def epoch(year, month, day, hour=12):
    return int(datetime(year, month, day, hour, tzinfo=UTC).timestamp())


ACCESS = "https://probe-user:probe-pass@bridge.simplefin.org/simplefin"


class Bridge:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, method, url, headers):
        self.calls.append((method, url, dict(headers)))
        status, body = self.replies.pop(0)
        return status, body if isinstance(body, bytes) else json.dumps(body).encode()


def card(balance, *transactions, account_id="P-CARD", currency="USD"):
    return {"id": account_id, "name": "Probe Card", "conn_id": "C-9", "currency": currency, "balance": balance,
            "balance-date": epoch(2027, 3, 1, 2), "transactions": list(transactions)}


def move(feed_id, day, amount, text, pending=False):
    return {"id": feed_id, "posted": 0 if pending else epoch(2027, 2, day), "amount": amount, "description": text,
            "transacted_at": epoch(2027, 2, day, 20), "pending": pending}


def answer(*accounts, errlist=(), errors=None):
    reply = {"errlist": [{"code": "gen.api", "msg": text} for text in errlist],
             "connections": [{"conn_id": "C-9", "name": "Probe Bank", "org_id": "O-9", "sfin_url": "https://bridge.simplefin.org/simplefin"}],
             "accounts": list(accounts)}
    if errors is not None:
        reply["errors"] = errors
    return reply


def client_checks():
    from finances.sync import simplefin
    from finances.sync.feed import FeedTransaction
    from finances.sync.simplefin import ProviderAccount, claim_access_url, fetch_accounts, parse_account_set

    claim = "https://bridge.simplefin.org/simplefin/claim/PROBE-77"
    bridge = Bridge((200, ACCESS.encode()))
    got = claim_access_url(base64.b64encode(claim.encode()).decode(), bridge)
    check("client: a setup token is claimed with one POST", got == ACCESS and [call[:2] for call in bridge.calls] == [("POST", claim)])
    for label, url in [("plain http", "http://bridge.simplefin.org/x"), ("another host", "https://probe.example/x"), ("a look-alike host", "https://notsimplefin.org/x"), ("credentials in the claim URL", "https://a:b@bridge.simplefin.org/x")]:
        bridge = Bridge((200, ACCESS.encode()))
        result = outcome(claim_access_url, base64.b64encode(url.encode()).decode(), bridge)
        check(f"client: a setup token with {label} is refused and nothing is sent", result == ("SyncError", "setup token is not valid") and bridge.calls == [])
    check("client: a used token", outcome(claim_access_url, base64.b64encode(claim.encode()).decode(), Bridge((403, b"")))  == ("SyncError", "setup token was already used or does not exist"))
    bridge = Bridge((200, answer(card("-61.75", move("T-1", 20, "-61.75", "PROBE  BAKERY")))))
    reply = fetch_accounts(ACCESS, date(2027, 2, 1), date(2027, 3, 1), bridge)
    method, url, headers = bridge.calls[0]
    check("client: one GET to /accounts for the dates asked, pending included, end day included", method == "GET" and url == f"https://bridge.simplefin.org/simplefin/accounts?start-date={epoch(2027, 2, 1, 0)}&end-date={epoch(2027, 3, 2, 0)}&pending=1")
    check("client: credentials go in a Basic header, never in the URL", headers == {"Authorization": "Basic " + base64.b64encode(b"probe-user:probe-pass").decode()} and "probe-pass" not in url)
    check("client: the answer is read", reply.accounts == [ProviderAccount("P-CARD", "Probe Card", "Probe Bank", "USD", -6175, date(2027, 3, 1), [FeedTransaction("T-1", date(2027, 2, 20), -6175, "PROBE BAKERY", False, date(2027, 2, 20))])] and reply.messages == [])
    for status, message in [(403, "aggregator access was revoked or is wrong"), (402, "aggregator subscription needs payment"), (503, "aggregator answered with an error")]:
        check(f"client: status {status}", outcome(fetch_accounts, ACCESS, date(2027, 2, 1), date(2027, 3, 1), Bridge((status, b""))) == ("SyncError", message))
    check("client: an answer that is not JSON", outcome(fetch_accounts, ACCESS, date(2027, 2, 1), date(2027, 3, 1), Bridge((200, b"<html>"))) == ("SyncError", "aggregator answer could not be read"))
    held = parse_account_set(answer(card("0", move("H-1", 27, "-12.00", "PROBE HOLD", pending=True), {"id": "H-2", "posted": 0, "amount": "-1", "description": "", "pending": True})))
    first, second = held.accounts[0].transactions
    check("client: a hold with no posted date takes the day it happened", (first.posted_date, first.transaction_date, first.is_pending) == (date(2027, 2, 27), date(2027, 2, 27), True))
    check("client: a hold with no dates at all takes the balance date, and an empty text the placeholder", (second.posted_date, second.transaction_date, second.description) == (date(2027, 3, 1), None, "(no description)"))
    messages = parse_account_set(answer(errlist=["Probe Bank\nneeds a new sign-in\u0007", "  \u0007 "], errors=["older " + "z" * 300])).messages
    check("client: messages from both versions, printable and at most 200 characters", messages == ["Probe Bank needs a new sign-in", "older " + "z" * 194])
    public = sorted(name for name, value in vars(simplefin).items() if getattr(value, "__module__", "") == simplefin.__name__ and not name.startswith("_"))
    check(f"client: public names {public}", public == ["ProviderAccount", "ProviderAnswer", "SyncError", "claim_access_url", "fetch_accounts", "parse_account_set"])
    check("client: the answer types are frozen", dataclasses.is_dataclass(ProviderAccount) and ProviderAccount.__dataclass_params__.frozen)


def transport_checks():
    from finances.sync.transport import urllib_transport

    real = urllib.request.urlopen
    seen = []

    class Reply(io.BytesIO):
        status = 200

    try:
        urllib.request.urlopen = lambda request, timeout: (seen.append((request.get_method(), request.data, timeout)), Reply(b"PROBE"))[1]
        check("transport: a request is sent through urllib with a 60 second timeout", urllib_transport("GET", "https://bridge.simplefin.org/x", {}) == (200, b"PROBE") and seen == [("GET", None, 60)])

        def refuse(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 403, "no", {}, io.BytesIO(b"PROBE SECRET"))

        urllib.request.urlopen = refuse
        check("transport: an HTTP error status comes back without its body", urllib_transport("GET", "https://bridge.simplefin.org/x", {}) == (403, b""))

        def unreachable(request, timeout):
            raise urllib.error.URLError("probe host unreachable")

        urllib.request.urlopen = unreachable
        check("transport: an unreachable host is one constant error", outcome(urllib_transport, "GET", "https://bridge.simplefin.org/x", {}) == ("SyncError", "could not reach the aggregator"))
    finally:
        urllib.request.urlopen = real


def run(body):
    from finances.db.engine import get_engine, session_scope
    from finances.db.migrate import upgrade_to_head
    from finances.db.repositories import create_account

    with tempfile.TemporaryDirectory() as folder:
        url = f"sqlite:///{(Path(folder) / 'probe.db').as_posix()}"
        upgrade_to_head(url)
        engine = get_engine(url)
        try:
            with session_scope(engine) as session:
                create_account(session, "Probe Card", "Probe Bank", "credit_card", last4="8080")
                create_account(session, "Probe Checking", "Probe Bank", "checking", last4="9191")
                body(session)
        finally:
            engine.dispose()


def runner_checks():
    from finances.db.repositories import latest_balance, list_transactions, map_feed_account
    from finances.sync.runner import AccountSync, run_sync

    def story(session):
        map_feed_account(session, 1, "P-CARD")
        bridge = Bridge(
            (200, answer(card("-61.75", move("T-1", 20, "-61.75", "PROBE BAKERY"), move("H-1", 27, "-90.00", "PROBE HOTEL HOLD", True), move("H-2", 28, "-7.00", "PROBE GAS HOLD", True)), card("5.00", account_id="P-UNKNOWN"))),
            (200, answer(card("-153.25", move("T-1", 20, "-61.75", "PROBE BAKERY"), move("T-2", 28, "-91.50", "PROBE HOTEL"), move("H-2", 28, "-7.00", "PROBE GAS HOLD", True)))),
            (200, answer(card("-153.25", move("T-2", 28, "-91.50", "PROBE HOTEL")), errlist=["Probe Bank: partial listing"])),
        )
        first = run_sync(session, ACCESS, today=date(2027, 3, 1), transport=bridge)
        check("story 1: the card is applied, the unknown account is reported", [(item.provider_account_id, item.account_id, item.problem) for item in first.accounts] == [("P-CARD", 1, None), ("P-UNKNOWN", None, "not mapped")])
        check("story 1: three rows, two of them holds", first.accounts[0].pull.inserted == 3 and sorted(t.is_pending for t in list_transactions(session, 1)) == [False, True, True])
        second = run_sync(session, ACCESS, today=date(2027, 3, 1), transport=bridge)
        pull = second.accounts[0].pull
        check("story 2: the hotel posted under a new id and its hold is removed", (pull.inserted, pull.removed, pull.unchanged) == (1, 1, 2) and pull.drift_cents == 0)
        third = run_sync(session, ACCESS, today=date(2027, 3, 1), transport=bridge)
        check("story 3: with a message from the aggregator, nothing is removed", third.messages == ["Probe Bank: partial listing"] and third.accounts[0].pull.removed == 0)
        rows = sorted((t.description, t.is_pending) for t in list_transactions(session, 1))
        check("story 3: the posted row no longer delivered and the hold are both kept", rows == [("PROBE BAKERY", False), ("PROBE GAS HOLD", True), ("PROBE HOTEL", False)])
        check("story: the balance is the aggregator's", latest_balance(session, 1).balance_cents == -15325)
        check("story: three requests, one per sync", len(bridge.calls) == 3)

    def mapping(session):
        first = map_feed_account(session, 1, "P-A")
        again = map_feed_account(session, 1, "P-B")
        check("mapping: a new aggregator account replaces the old one for the same account", (first.id, again.id, again.provider_account_id) == (1, 1, "P-B"))
        check("mapping: the same aggregator account again is accepted", map_feed_account(session, 1, "P-B").provider_account_id == "P-B")
        check("mapping: another account cannot take it", outcome(map_feed_account, session, 2, "P-B") == ("ValueError", "feed account is already mapped to another account"))
        bridge = Bridge((200, answer(card("1.00", move("X-1", 20, "1.00", "PROBE"), currency="CAD", account_id="P-B"), card("0", account_id="P-GONE-NOT"))))
        report = run_sync(session, ACCESS, today=date(2027, 3, 1), transport=bridge, days=10)
        check("mapping: another currency is reported, and the window follows days", report.accounts[0] == AccountSync("P-B", 1, None, "currency is not USD") and f"start-date={epoch(2027, 2, 19, 0)}&" in bridge.calls[0][1])

    def pending_ids(session):
        from finances.db.repositories import list_pending_feed_ids
        from finances.sync.feed import AccountFeed, FeedTransaction
        from finances.sync.service import apply_feed

        apply_feed(session, 1, AccountFeed([FeedTransaction("A", date(2027, 2, 1), -1, "PROBE", True), FeedTransaction("B", date(2027, 2, 9), -1, "PROBE", True), FeedTransaction("C", date(2027, 2, 9), -1, "PROBE")]))
        apply_feed(session, 2, AccountFeed([FeedTransaction("D", date(2027, 2, 9), -1, "PROBE", True)]))
        check("repositories: pending feed ids of one account, from a day on", list_pending_feed_ids(session, 1, date(2027, 2, 2)) == ["B"] and list_pending_feed_ids(session, 1, date(2027, 2, 1)) == ["A", "B"])

    def isolation(session):
        map_feed_account(session, 1, "P-CARD")
        map_feed_account(session, 2, "P-CHK")
        bridge = Bridge(
            (200, answer(card("-1.00", move("Q" * 101, 20, "-1.00", "PROBE")), card("4.00", move("K-1", 21, "4.00", "PROBE DEPOSIT"), account_id="P-CHK"))),
            (200, answer(card("0.00", move("OLD", 1, "-1.00", "PROBE OLD HOLD", True)))),
            (200, answer(card("0.00"))),
        )
        report = run_sync(session, ACCESS, today=date(2027, 3, 1), transport=bridge)
        check("isolation: one account's unusable feed does not stop another's", report.accounts[0] == AccountSync("P-CARD", 1, None, "feed has an unusable transaction id") and report.accounts[1].pull.inserted == 1)
        report = run_sync(session, ACCESS, today=date(2027, 3, 1), transport=bridge, days=40)
        check("isolation: a mapped account missing from the answer is reported", report.accounts[-1] == AccountSync("P-CHK", 2, None, "not in the aggregator's answer"))
        report = run_sync(session, ACCESS, today=date(2027, 3, 5), transport=bridge)
        check("isolation: a hold older than the window is not removed", report.accounts[0].pull.removed == 0 and [t.description for t in list_transactions(session, 1)] == ["PROBE OLD HOLD"])

    run(story)
    run(isolation)
    run(mapping)
    run(pending_ids)


section("client", client_checks)
section("transport", transport_checks)
section("runner", runner_checks)
print("FAILURES", failures)
```

## 5. The coder's tests

Read `tests/integration/test_feed_account_repositories.py`.

- **Coverage of requirements.** For each of R1 to R22, name a test, given or the coder's, that would fail if the requirement were broken. A requirement with no such test is a finding. The coder's final message lists its own mapping; check it, do not trust it.
- **No network.** No test opens a connection, reads a real setup token or access URL, or names a real institution.
- **Assertions are exact.** No `assert True`, no `pytest.raises(Exception)`, no `skip` or `xfail`, and no expected value produced by calling the code under test.
- **Spot checks.** For each change below, say which test, given or the coder's, would fail, by reading the test. If none would, that is a finding.
  1. `map_feed_account` refuses to give an account a different aggregator account.
  2. `map_feed_account` adds a second row for an account instead of changing the first.
  3. `map_feed_account` changes the mapping before raising the `ValueError`.
  4. `list_feed_accounts` returns the mappings in another order.
  5. `list_pending_feed_ids` returns posted rows.
  6. `list_pending_feed_ids` leaves out a row dated `since`.
  7. `list_pending_feed_ids` returns another account's holds.

## 6. Project rules that apply to this phase

- **Privacy rule 1.** The only network code is `transport.py`, inside `src/finances/sync/`, and the client sends only to HTTPS hosts under `simplefin.org`. The probe lines starting `client: a setup token with` show that nothing is sent for any other host.
- **Privacy rule 4.** Nothing is logged at any level in `src/finances/sync/` (third search).
- **Money.** Integer cents through `parse_money`; no `float` (third search).
- **Layering.** `sync` does not import `ingest` or `cli` (fourth search).

## 7. Out of scope

Each of these must be absent. Report any that is present.

- A command, printed output, `keyring`, or the Keychain.
- An HTTP library other than the standard library, or any new dependency.
- Retries, sleeping, back-off, or caching.
- Support for another aggregator, or an abstraction over several.
- Use of `available-balance`, `balances-only`, `account`, `version`, `/info`, or `extra`.
- Any request to a real host, in code or in tests.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 17b: syncing from SimpleFIN (YYYY-MM-DD)` with a real date. "Built" gives N and the passed count. It reports nothing about a real SimpleFIN account. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 to Part 4 / tests>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code.
