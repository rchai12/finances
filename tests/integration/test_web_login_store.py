import re
from datetime import UTC, datetime, timedelta

import pytest

from finances.web.login import Attempt, attempt, has_password, session_key, set_password, unlock

RIGHT = "correct horse battery"
T0 = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def test_no_password_at_first() -> None:
    assert (has_password(), session_key()) == (False, None)


def test_the_first_password_and_a_change() -> None:
    set_password(RIGHT, None)
    first = session_key()
    assert has_password() and re.fullmatch(r"[0-9a-f]{64}", first or "")
    for current in (None, "not the password"):
        with pytest.raises(ValueError) as raised:
            set_password("another long password", current)
        assert str(raised.value) == "the current password is wrong"
    set_password("another long password", RIGHT)
    assert session_key() != first
    assert attempt("another long password", T0) == Attempt(True, None)


def test_a_short_password_stores_nothing() -> None:
    with pytest.raises(ValueError) as raised:
        set_password("too short", None)
    assert str(raised.value) == "a password is 12 to 200 characters"
    assert has_password() is False


def test_the_lockout() -> None:
    set_password(RIGHT, None)
    for _ in range(4):
        assert attempt("wrong", T0) == Attempt(False, None)
    one_hour = T0 + timedelta(hours=1)
    assert attempt("wrong", T0) == Attempt(False, one_hour)
    for _ in range(3):
        assert attempt("wrong", T0 + timedelta(minutes=30)) == Attempt(False, one_hour)
    assert attempt(RIGHT, T0 + timedelta(minutes=59)) == Attempt(False, one_hour)
    later = T0 + timedelta(minutes=61)
    for _ in range(4):
        assert attempt("wrong", later) == Attempt(False, None)
    one_day = later + timedelta(days=1)
    assert attempt("wrong", later) == Attempt(False, one_day)
    after = one_day + timedelta(minutes=1)
    for _ in range(2):
        assert attempt("wrong", after) == Attempt(False, None)
    assert attempt("wrong", after) == Attempt(False, after + timedelta(days=3))
    free = after + timedelta(days=3, minutes=1)
    assert attempt(RIGHT, free) == Attempt(True, None)
    for _ in range(4):
        assert attempt("wrong", free) == Attempt(False, None)


def test_unlock_needs_the_password() -> None:
    with pytest.raises(ValueError) as raised:
        unlock(RIGHT)
    assert str(raised.value) == "no password is set; run fin web password"
    set_password(RIGHT, None)
    for _ in range(5):
        attempt("wrong", T0)
    with pytest.raises(ValueError) as raised:
        unlock("wrong")
    assert str(raised.value) == "wrong password"
    assert attempt(RIGHT, T0) == Attempt(False, T0 + timedelta(hours=1))
    unlock(RIGHT)
    assert attempt(RIGHT, T0) == Attempt(True, None)
    for _ in range(4):
        assert attempt("wrong", T0) == Attempt(False, None)


def test_a_new_password_clears_the_lockout() -> None:
    set_password(RIGHT, None)
    for _ in range(5):
        attempt("wrong", T0)
    set_password("another long password", RIGHT)
    assert attempt("another long password", T0) == Attempt(True, None)
