import base64
import json
import re
from datetime import UTC, datetime

import keyring
import keyring.backend
import keyring.errors
import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.sync import transport
from finances.sync.feed import AccountFeed
from finances.sync.service import apply_feed

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"
CLAIM = "https://bridge.simplefin.org/simplefin/claim/DEMO-1"
TOKEN = base64.b64encode(CLAIM.encode()).decode()
ACCOUNT_HEADINGS = ["SimpleFIN account", "Institution", "Name", "Currency", "Mapped to"]
RUN_HEADINGS = [
    "Link",
    "Account",
    "SimpleFIN account",
    "New",
    "Changed",
    "Removed",
    "Same",
    "Drift",
    "Problem",
]
STATUS_HEADINGS = [
    "Link",
    "Account",
    "SimpleFIN account",
    "Keychain",
    "Last pull",
    "Balance date",
    "Drift",
]


def run(*args: object, input: str | None = None):
    return runner.invoke(app, [str(arg) for arg in args], input=input)


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


def stamp(day: int) -> int:
    today = datetime.now(UTC).date()
    return int(datetime(today.year, today.month, today.day, 12, tzinfo=UTC).timestamp()) - (
        day * 86400
    )


def account(account_id: str, name: str, balance: str, *moves: tuple[str, int, str]) -> dict:
    return {
        "id": account_id,
        "name": name,
        "conn_id": "C-1",
        "currency": "USD",
        "balance": balance,
        "balance-date": stamp(0),
        "transactions": [
            {"id": feed_id, "posted": stamp(days_ago), "amount": amount, "description": "PROBE"}
            for feed_id, days_ago, amount in moves
        ],
    }


class Bridge:
    """A fake SimpleFIN Bridge: claims give an access URL; each access URL has its answer."""

    def __init__(self) -> None:
        self.claim = (200, ALEX.encode())
        self.answers: dict[str, tuple[int, dict | None]] = {}
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, url, dict(headers)))
        if method == "POST":
            return self.claim
        status, body = self.answers[headers["Authorization"]]
        return status, json.dumps(body).encode()

    def answer(self, access: str, *accounts: dict, status: int = 200, messages=()) -> None:
        user, password = access.split("//")[1].split("@")[0].split(":")
        key = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        body = {
            "errlist": [{"code": "con.auth", "msg": text} for text in messages],
            "connections": [
                {"conn_id": "C-1", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}
            ],
            "accounts": list(accounts),
        }
        self.answers[key] = (status, body)


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringLocked("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.PasswordSetError("refused")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.PasswordDeleteError("refused")


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> Bridge:
    fake = Bridge()
    monkeypatch.setattr(transport, "urllib_transport", fake)
    return fake


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    for name, kind, last4 in (
        ("Test Card", "credit_card", "1111"),
        ("Test Checking", "checking", "2222"),
        ("Test Other Card", "credit_card", "3333"),
    ):
        details = ["--institution", "Probe Bank", "--type", kind, "--last4", last4]
        made = run("accounts", "add", "--name", name, *details)
        assert made.exit_code == 0
    return tmp_settings


@pytest.fixture
def broken_keychain():
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    yield
    keyring.set_keyring(previous)


# ----- link and unlink -----


def test_link_claims_the_token_and_keeps_the_access_in_the_keychain(
    bridge: Bridge, keychain
) -> None:
    result = run("sync", "link", "--link", "alex", input=TOKEN + "\n")
    assert result.exit_code == 0
    assert result.stdout == "SimpleFIN setup token: \nLinked alex.\n"
    assert TOKEN not in result.output and "alex-pass" not in result.output
    assert keychain.passwords == {("finances-simplefin", "alex"): ALEX}
    assert [(method, url) for method, url, _ in bridge.calls] == [("POST", CLAIM)]


def test_link_without_a_name_uses_the_default_link(bridge: Bridge, keychain) -> None:
    assert run("sync", "link", input=TOKEN + "\n").stdout.endswith("Linked default.\n")
    assert keychain.passwords == {("finances-simplefin", "default"): ALEX}


def test_a_link_is_not_replaced_unless_asked(bridge: Bridge, keychain) -> None:
    keychain.passwords[("finances-simplefin", "alex")] = SAM
    result = run("sync", "link", "--link", "alex", input=TOKEN + "\n")
    assert failed_cleanly(result, "link alex is already set up; use --replace to set it up again")
    assert bridge.calls == []
    result = run("sync", "link", "--link", "alex", "--replace", input=TOKEN + "\n")
    assert result.exit_code == 0
    assert keychain.passwords == {("finances-simplefin", "alex"): ALEX}


def test_a_refused_token_stores_nothing(bridge: Bridge, keychain) -> None:
    bridge.claim = (403, b"")
    result = run("sync", "link", "--link", "alex", input=TOKEN + "\n")
    assert result.exit_code == 1
    assert result.stderr == "Error: setup token was already used or does not exist\n"
    assert keychain.passwords == {}


def test_a_token_that_is_not_simplefin_is_not_sent(bridge: Bridge, keychain) -> None:
    bad = base64.b64encode(b"https://example.com/claim").decode()
    result = run("sync", "link", "--link", "alex", input=bad + "\n")
    assert result.stderr == "Error: setup token is not valid\n"
    assert bridge.calls == [] and keychain.passwords == {}


@pytest.mark.parametrize("command", ["link", "unlink"])
def test_a_bad_link_name(bridge: Bridge, keychain, command: str) -> None:
    result = run("sync", command, "--link", "Alex Smith", input=TOKEN + "\n")
    message = "a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter"
    assert failed_cleanly(result, message)
    assert bridge.calls == []


def test_unlink(keychain) -> None:
    keychain.passwords[("finances-simplefin", "sam")] = SAM
    result = run("sync", "unlink", "--link", "sam")
    assert (result.exit_code, result.stdout) == (0, "Unlinked sam.\n")
    assert keychain.passwords == {}
    assert failed_cleanly(run("sync", "unlink", "--link", "sam"), "link sam is not set up")


def test_a_keychain_that_fails(bridge: Bridge, broken_keychain) -> None:
    assert failed_cleanly(
        run("sync", "link", input=TOKEN + "\n"), "could not use the system keychain"
    )
    assert failed_cleanly(run("sync", "unlink"), "could not use the system keychain")


# ----- map and accounts -----


def test_map_and_list_accounts(migrated: Settings, bridge: Bridge, keychain) -> None:
    keychain.passwords[("finances-simplefin", "alex")] = ALEX
    bridge.answer(
        ALEX,
        account("ACT-1", "Probe Rewards Card", "-10.00"),
        account("ACT-2", "Probe Checking", "100.00"),
        messages=("Probe Bank\\nneeds attention",),
    )
    result = run(
        "sync", "map", "--account", "test card", "--feed-account", " ACT-1 ", "--link", "alex"
    )
    assert (result.exit_code, result.stdout) == (
        0,
        'Mapped ACT-1 to "Test Card" under link alex.\n',
    )
    result = run("sync", "accounts", "--link", "alex")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        ACCOUNT_HEADINGS,
        ["ACT-1", "Probe Bank", "Probe Rewards Card", "USD", "Test Card"],
        ["ACT-2", "Probe Bank", "Probe Checking", "USD", ""],
    ]
    assert result.stdout.endswith("SimpleFIN: Probe Bank\\nneeds attention\n")
    assert "alex-pass" not in result.output
    method, url, headers = bridge.calls[0]
    assert (method, headers["Authorization"].startswith("Basic ")) == ("GET", True)
    assert url.startswith("https://bridge.simplefin.org/simplefin/accounts?start-date=")


def test_accounts_lists_only_this_links_mappings(
    migrated: Settings, bridge: Bridge, keychain
) -> None:
    keychain.passwords[("finances-simplefin", "sam")] = SAM
    bridge.answer(SAM, account("ACT-1", "Probe Card", "0"))
    assert (
        run(
            "sync", "map", "--account", "Test Card", "--feed-account", "ACT-1", "--link", "alex"
        ).exit_code
        == 0
    )
    result = run("sync", "accounts", "--link", "sam")
    assert table_rows(result.stdout)[1] == ["ACT-1", "Probe Bank", "Probe Card", "USD", ""]


def test_accounts_with_none_and_with_an_error(migrated: Settings, bridge: Bridge, keychain) -> None:
    keychain.passwords[("finances-simplefin", "default")] = ALEX
    bridge.answer(ALEX)
    assert run("sync", "accounts").stdout == "No accounts.\n"
    bridge.answer(ALEX, status=402)
    assert failed_cleanly(run("sync", "accounts"), "aggregator subscription needs payment")


def test_accounts_of_a_link_that_is_not_set_up(migrated: Settings, bridge: Bridge) -> None:
    result = run("sync", "accounts", "--link", "sam")
    assert failed_cleanly(result, "link sam is not set up (run: fin sync link --link sam)")
    assert bridge.calls == []


def test_map_refusals(migrated: Settings) -> None:
    assert failed_cleanly(
        run("sync", "map", "--account", "Nope", "--feed-account", "ACT-1"), "account not found"
    )
    assert failed_cleanly(
        run("sync", "map", "--account", "Test Card", "--feed-account", "  "),
        "feed account id must be 1 to 200 characters",
    )
    assert failed_cleanly(
        run("sync", "map", "--account", "Test Card", "--feed-account", "X" * 201),
        "feed account id must be 1 to 200 characters",
    )
    assert run("sync", "map", "--account", "Test Card", "--feed-account", "ACT-1").exit_code == 0
    assert failed_cleanly(
        run("sync", "map", "--account", "Test Checking", "--feed-account", "ACT-1"),
        "feed account is already mapped to another account",
    )
    result = run(
        "sync", "map", "--account", "Test Checking", "--feed-account", "ACT-1", "--link", "sam"
    )
    assert result.exit_code == 0


# ----- run and status -----


def test_run_pulls_every_link_and_prints_one_row_per_account(
    migrated: Settings, bridge: Bridge, keychain
) -> None:
    keychain.passwords[("finances-simplefin", "alex")] = ALEX
    keychain.passwords[("finances-simplefin", "sam")] = SAM
    for name, feed, link in (
        ("Test Card", "ACT-1", "alex"),
        ("Test Checking", "ACT-2", "alex"),
        ("Test Other Card", "ACT-1", "sam"),
    ):
        assert (
            run("sync", "map", "--account", name, "--feed-account", feed, "--link", link).exit_code
            == 0
        )
    bridge.answer(
        ALEX,
        account("ACT-1", "Probe Card", "-12.50", ("A-1", 3, "-12.50")),
        account("ACT-9", "Probe Unmapped", "1.00"),
    )
    bridge.answer(
        SAM,
        account("ACT-1", "Probe Other", "-4.00", ("S-1", 2, "-4.00")),
        messages=("Sam bank note",),
    )
    result = run("sync", "run")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        RUN_HEADINGS,
        ["alex", "Test Card", "ACT-1", "1", "0", "0", "0", "", ""],
        ["alex", "", "ACT-9", "", "", "", "", "", "not mapped"],
        ["alex", "Test Checking", "ACT-2", "", "", "", "", "", "not in the aggregator's answer"],
        ["sam", "Test Other Card", "ACT-1", "1", "0", "0", "0", "", ""],
    ]
    assert result.stdout.endswith("SimpleFIN (sam): Sam bank note\n")
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-15.00", ("A-1", 3, "-12.50")))
    result = run("sync", "run", "--link", "alex")
    assert table_rows(result.stdout)[1] == [
        "alex",
        "Test Card",
        "ACT-1",
        "0",
        "0",
        "0",
        "1",
        "-$2.50",
        "",
    ]
    assert len(table_rows(result.stdout)) == 3


def test_one_link_failing_does_not_stop_the_others(
    migrated: Settings, bridge: Bridge, keychain
) -> None:
    keychain.passwords[("finances-simplefin", "alex")] = ALEX
    keychain.passwords[("finances-simplefin", "sam")] = SAM
    mapped = (("Test Card", "alex"), ("Test Checking", "bob"), ("Test Other Card", "sam"))
    for name, link in mapped:
        made = run("sync", "map", "--account", name, "--feed-account", "ACT-1", "--link", link)
        assert made.exit_code == 0
    bridge.answer(ALEX, status=403)
    bridge.answer(SAM, account("ACT-1", "Probe Other", "-4.00", ("S-1", 2, "-4.00")))
    result = run("sync", "run")
    assert result.exit_code == 1
    assert result.stderr == (
        "Error: link alex: aggregator access was revoked or is wrong\n"
        "Error: link bob is not set up (run: fin sync link --link bob)\n"
    )
    assert table_rows(result.stdout) == [
        RUN_HEADINGS,
        ["sam", "Test Other Card", "ACT-1", "1", "0", "0", "0", "", ""],
    ]


def test_run_with_nothing_mapped_and_bad_options(migrated: Settings, bridge: Bridge) -> None:
    assert run("sync", "run").stdout == "No mapped accounts.\n"
    assert run("sync", "run", "--days", "0").exit_code == 2
    assert run("sync", "run", "--days", "91").exit_code == 2
    assert failed_cleanly(
        run("sync", "run", "--link", "Bad"),
        "a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter",
    )
    assert bridge.calls == []


def test_run_asks_for_the_days_given(migrated: Settings, bridge: Bridge, keychain) -> None:
    keychain.passwords[("finances-simplefin", "default")] = ALEX
    assert run("sync", "map", "--account", "Test Card", "--feed-account", "ACT-1").exit_code == 0
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "0"))
    assert run("sync", "run", "--days", "7").exit_code == 0
    today = datetime.now(UTC).date()
    start = int(datetime(today.year, today.month, today.day, tzinfo=UTC).timestamp()) - 7 * 86400
    assert re.search(rf"start-date={start}&", bridge.calls[0][1])


def test_status(migrated: Settings, bridge: Bridge, keychain) -> None:
    assert run("sync", "status").stdout == "No mapped accounts.\n"
    keychain.passwords[("finances-simplefin", "alex")] = ALEX
    assert (
        run(
            "sync", "map", "--account", "Test Card", "--feed-account", "ACT-1", "--link", "alex"
        ).exit_code
        == 0
    )
    assert (
        run(
            "sync",
            "map",
            "--account",
            "Test Other Card",
            "--feed-account",
            "ACT-1",
            "--link",
            "sam",
        ).exit_code
        == 0
    )
    result = run("sync", "status")
    assert table_rows(result.stdout) == [
        STATUS_HEADINGS,
        ["alex", "Test Card", "ACT-1", "yes", "never", "", ""],
        ["sam", "Test Other Card", "ACT-1", "no", "never", "", ""],
    ]
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-1.00", ("A-1", 1, "-1.00")))
    assert run("sync", "run", "--link", "alex").exit_code == 0
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-3.00", ("A-1", 1, "-1.00")))
    assert run("sync", "run", "--link", "alex").exit_code == 0
    row = table_rows(run("sync", "status").stdout)[1]
    assert row[:4] == ["alex", "Test Card", "ACT-1", "yes"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", row[4])
    assert row[5:] == [datetime.now(UTC).date().isoformat(), "-$2.00"]
    engine = get_engine()
    with session_scope(engine) as session:
        apply_feed(session, 1, AccountFeed())
    engine.dispose()
    row = table_rows(run("sync", "status").stdout)[1]
    assert row[5:] == [datetime.now(UTC).date().isoformat(), "-$2.00"]


def test_status_with_a_keychain_that_fails(migrated: Settings, broken_keychain) -> None:
    assert run("sync", "map", "--account", "Test Card", "--feed-account", "ACT-1").exit_code == 0
    assert table_rows(run("sync", "status").stdout)[1][3] == "unknown"


@pytest.mark.parametrize(
    "command", [["accounts"], ["map", "--account", "A", "--feed-account", "B"], ["run"], ["status"]]
)
def test_commands_that_read_the_database_need_it_migrated(
    tmp_settings: Settings, command: list[str]
) -> None:
    result = run("sync", *command)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


def test_sync_is_a_command_group() -> None:
    result = run("sync", "--help")
    assert result.exit_code == 0
    for name in ("link", "unlink", "accounts", "map", "run", "status"):
        assert re.search(rf"│ {name} ", result.stdout)


def test_reading_the_keychain_fails_for_accounts_and_run(
    migrated: Settings, bridge: Bridge, broken_keychain
) -> None:
    assert failed_cleanly(run("sync", "accounts"), "could not use the system keychain")
    assert run("sync", "map", "--account", "Test Card", "--feed-account", "ACT-1").exit_code == 0
    result = run("sync", "run")
    assert (result.exit_code, result.stderr) == (1, "Error: could not use the system keychain\n")
    assert bridge.calls == []
