import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.sync import transport

runner = CliRunner(env={"COLUMNS": "200"})
MERCHANT = "QUUXLY BAKERY"
AMOUNT = "-73.19"
CENTS = "7319"
DIGITS = "4826"
PASSWORD = "hush-quux-pass"
ACCESS = f"https://probe-user:{PASSWORD}@bridge.simplefin.org/simplefin"
SECRETS = (MERCHANT, AMOUNT, AMOUNT.lstrip("-"), CENTS, DIGITS, PASSWORD)


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def fake_bridge(posted: datetime):
    user, password = ACCESS.split("//")[1].split("@")[0].split(":")
    key = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
    body = {
        "errlist": [],
        "connections": [{"conn_id": "C-1", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": "ACT-1",
                "name": "Probe Card",
                "conn_id": "C-1",
                "currency": "USD",
                "balance": AMOUNT,
                "balance-date": int(posted.timestamp()),
                "transactions": [
                    {
                        "id": "F-1",
                        "posted": int(posted.timestamp()),
                        "amount": AMOUNT,
                        "description": MERCHANT,
                    }
                ],
            }
        ],
    }

    def answer(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        assert method == "GET" and headers["Authorization"] == key
        return 200, json.dumps(body).encode()

    return answer


def test_no_command_writes_private_values_to_stderr(
    tmp_settings: Settings,
    tmp_path: Path,
    fake_bank,
    fake_statement_pdf,
    keychain,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIN_LOG_LEVEL", "INFO")
    today = datetime.now(UTC).date()
    day = today - timedelta(days=3)
    posted = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    statement = tmp_path / "statement.pdf"
    statement.write_bytes(
        fake_statement_pdf(
            last4=DIGITS,
            start=(today - timedelta(days=20)).isoformat(),
            end=(today - timedelta(days=1)).isoformat(),
            opening="0.00",
            closing=AMOUNT,
            rows=(f"{day.isoformat()}|-|purchases|{AMOUNT}|-|-|{MERCHANT}",),
        )
    )
    keychain.passwords[("finances-simplefin", "default")] = ACCESS
    monkeypatch.setattr(transport, "urllib_transport", fake_bridge(posted))
    card = ["--name", "Probe Card", "--institution", "Fake Bank", "--type", "credit_card"]

    results = [
        (0, run("db", "upgrade")),
        (0, run("accounts", "add", *card, "--last4", DIGITS)),
        (0, run("import", "statement", statement)),
        (0, run("import", "statement", statement)),
    ]
    listing = run("transactions", "list")
    results += [
        (0, listing),
        (0, run("sync", "map", "--account", "Probe Card", "--feed-account", "ACT-1")),
        (0, run("sync", "run")),
        (0, run("sync", "status")),
        (1, run("accounts", "add", *card)),
    ]

    assert MERCHANT in listing.stdout
    for code, result in results:
        assert result.exit_code == code
        for secret in SECRETS:
            assert secret not in result.stderr
