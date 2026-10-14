import base64
import json
from datetime import date

import keyring
import keyring.backend
import keyring.errors
from sqlalchemy import Engine

from finances.sync.runner import (
    AGGREGATOR_FAILED,
    KEYCHAIN_FAILED,
    NOT_SET_UP,
    LinkRun,
    SyncReport,
    run_links,
)

TODAY = date(2026, 5, 20)
SERVICE = "finances-simplefin"
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"


def key(access: str) -> str:
    user, password = access.split("//")[1].split("@")[0].split(":")
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringError("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.KeyringError("locked")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.KeyringError("locked")


def test_the_kinds_of_failure() -> None:
    assert (KEYCHAIN_FAILED, NOT_SET_UP, AGGREGATOR_FAILED) == (
        "keychain",
        "not set up",
        "aggregator",
    )


def test_a_failure_and_its_cause_do_not_change_equality() -> None:
    assert LinkRun("alex", None, "link alex is not set up") == LinkRun(
        "alex", None, "link alex is not set up", NOT_SET_UP, None
    )
    assert LinkRun("alex", None, "x", KEYCHAIN_FAILED, "a") == LinkRun(
        "alex", None, "x", AGGREGATOR_FAILED, "b"
    )


def test_each_failure_says_what_kind_it_is(db_engine: Engine, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    empty = {"errlist": [], "connections": [], "accounts": []}

    def bridge(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        if headers["Authorization"] == key(ALEX):
            return 403, b""
        return 200, json.dumps(empty).encode()

    alex, bob = run_links(db_engine, ["alex", "bob"], today=TODAY, transport=bridge)
    assert (alex.error, alex.failure, alex.cause) == (
        "link alex: aggregator access was revoked or is wrong",
        AGGREGATOR_FAILED,
        "aggregator access was revoked or is wrong",
    )
    assert (bob.error, bob.failure, bob.cause) == ("link bob is not set up", NOT_SET_UP, None)
    keychain.passwords[(SERVICE, "sam")] = "https://sam-user:sam-pass@bridge.simplefin.org/x"
    (sam,) = run_links(db_engine, ["sam"], today=TODAY, transport=bridge)
    assert (sam.report, sam.error, sam.failure, sam.cause) == (SyncReport([], []), None, None, None)


def test_a_keychain_failure(db_engine: Engine) -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        (alex,) = run_links(db_engine, ["alex"], today=TODAY, transport=lambda *_: (500, b""))
    finally:
        keyring.set_keyring(previous)
    assert (alex.error, alex.failure, alex.cause) == (
        "link alex: could not use the system keychain",
        KEYCHAIN_FAILED,
        "could not use the system keychain",
    )
