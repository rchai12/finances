from datetime import timedelta

import pytest

from finances.domain.login import (
    PASSWORD_MAX,
    PASSWORD_MIN,
    check_new_password,
    hash_password,
    lock_for,
    verify_password,
)

SALT = bytes(range(16))
STORED = (
    "scrypt$16384$8$1$000102030405060708090a0b0c0d0e0f$"
    "e96ec6ba8c63a23698220f37c7fc042925d430c7feadec9ceb04af03cabb9f2f"
)
LENGTH = "a password is 12 to 200 characters"


def test_the_limits() -> None:
    assert (PASSWORD_MIN, PASSWORD_MAX) == (12, 200)


@pytest.mark.parametrize("text", ["x" * 12, "  ünïcödé kept  "])
def test_a_new_password_that_is_kept(text: str) -> None:
    assert check_new_password(text) == text


@pytest.mark.parametrize("text", ["", "x" * 11, "x" * 201])
def test_a_new_password_that_is_refused(text: str) -> None:
    with pytest.raises(ValueError) as raised:
        check_new_password(text)
    assert str(raised.value) == LENGTH


def test_the_hash() -> None:
    assert hash_password("correct horse battery", SALT) == STORED


@pytest.mark.parametrize(
    ("password", "stored", "right"),
    [
        ("correct horse battery", STORED, True),
        ("correct horse batterY", STORED, False),
        ("correct horse battery", "", False),
        ("correct horse battery", "md5$abc", False),
        ("correct horse battery", "scrypt$16384$8$1$zz$00", False),
        ("correct horse battery", STORED.replace("$8$", "$9$"), False),
    ],
)
def test_verifying(password: str, stored: str, right: bool) -> None:
    assert verify_password(password, stored) is right


@pytest.mark.parametrize(
    ("failures", "lock"),
    [
        (0, None),
        (4, None),
        (5, timedelta(hours=1)),
        (6, None),
        (10, timedelta(days=1)),
        (11, None),
        (13, timedelta(days=3)),
        (14, None),
        (16, timedelta(days=3)),
    ],
)
def test_the_lockout_schedule(failures: int, lock: timedelta | None) -> None:
    assert lock_for(failures) == lock
