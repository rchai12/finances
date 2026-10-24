"""The household password and lockout, kept in the system keychain."""

import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Final

import keyring
import keyring.errors

from finances.domain.login import check_new_password, hash_password, lock_for, verify_password

KEYCHAIN_SERVICE: Final = "finances-web"
_PASSWORD = "password"
_SESSION = "session-key"
_LOCKOUT = "lockout"
_KEYCHAIN = "could not use the system keychain"


@dataclass(frozen=True)
class Attempt:
    ok: bool
    locked_until: datetime | None


def has_password() -> bool:
    return _get(_PASSWORD) is not None


def check_password(password: str) -> bool:
    return verify_password(password, _get(_PASSWORD) or "")


def set_password(new: str, current: str | None) -> None:
    stored = _get(_PASSWORD)
    if stored is not None and (current is None or not verify_password(current, stored)):
        raise ValueError("the current password is wrong")
    checked = check_new_password(new)
    _set(_PASSWORD, hash_password(checked, secrets.token_bytes(16)))
    _set(_SESSION, secrets.token_hex(32))
    _save_lock(0, None)


def attempt(password: str, now: datetime) -> Attempt:
    count, until = _load_lock()
    if until is not None and until > now:
        return Attempt(False, until)
    if verify_password(password, _get(_PASSWORD) or ""):
        _save_lock(0, None)
        return Attempt(True, None)
    count += 1
    length = lock_for(count)
    end = None if length is None else now + length
    _save_lock(count, end)
    return Attempt(False, end)


def unlock(password: str) -> None:
    stored = _get(_PASSWORD)
    if stored is None:
        raise ValueError("no password is set; run fin web password")
    if not verify_password(password, stored):
        raise ValueError("wrong password")
    _save_lock(0, None)


def session_key() -> str | None:
    return _get(_SESSION)


def _get(name: str) -> str | None:
    try:
        return keyring.get_password(KEYCHAIN_SERVICE, name)
    except keyring.errors.KeyringError:
        raise ValueError(_KEYCHAIN) from None


def _set(name: str, value: str) -> None:
    try:
        keyring.set_password(KEYCHAIN_SERVICE, name, value)
    except keyring.errors.KeyringError:
        raise ValueError(_KEYCHAIN) from None


def _load_lock() -> tuple[int, datetime | None]:
    text = _get(_LOCKOUT) or "0"
    parts = text.split(" ", 1)
    until = datetime.fromisoformat(parts[1]) if len(parts) == 2 else None
    return int(parts[0]), until


def _save_lock(count: int, until: datetime | None) -> None:
    text = str(count) if until is None else f"{count} {until.isoformat()}"
    _set(_LOCKOUT, text)
