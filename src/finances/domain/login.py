"""The household password's limits, hash, and lockout schedule."""

import hashlib
import hmac
from datetime import timedelta

PASSWORD_MIN = 12
PASSWORD_MAX = 200

_N = 16384
_R = 8
_P = 1
_DKLEN = 32
_LENGTH = "a password is 12 to 200 characters"


def check_new_password(text: str) -> str:
    if not PASSWORD_MIN <= len(text) <= PASSWORD_MAX:
        raise ValueError(_LENGTH)
    return text


def hash_password(password: str, salt: bytes) -> str:
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) != 6:
        return False
    scheme, n_text, r_text, p_text, salt_hex, _unused = parts
    if (scheme, n_text, r_text, p_text) != ("scrypt", str(_N), str(_R), str(_P)):
        return False
    try:
        hashed = hash_password(password, bytes.fromhex(salt_hex))
    except ValueError:
        return False
    return hmac.compare_digest(hashed, stored)


def lock_for(failures: int) -> timedelta | None:
    if failures == 5:
        return timedelta(hours=1)
    if failures == 10:
        return timedelta(days=1)
    if failures >= 13 and (failures - 13) % 3 == 0:
        return timedelta(days=3)
    return None
