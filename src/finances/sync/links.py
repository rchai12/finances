"""Link names, and the access URL of each link kept in the system keychain."""

import re

import keyring
import keyring.errors

from finances.sync.simplefin import SyncError

KEYCHAIN_SERVICE = "finances-simplefin"

_NAME = re.compile(r"[a-z][a-z0-9-]{0,29}")


def validate_link_name(name: str) -> str:
    """Return the name when it can name a link, otherwise raise ValueError."""
    if _NAME.fullmatch(name) is None:
        raise ValueError(
            "a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter"
        )
    return name


def save_access_url(link: str, access_url: str) -> None:
    """Keep the link's access URL in the keychain, replacing an earlier one."""
    validate_link_name(link)
    try:
        keyring.set_password(KEYCHAIN_SERVICE, link, access_url)
    except keyring.errors.KeyringError:
        raise SyncError("could not use the system keychain") from None


def load_access_url(link: str) -> str | None:
    """Return the link's access URL, or None when the link is not set up."""
    validate_link_name(link)
    try:
        return keyring.get_password(KEYCHAIN_SERVICE, link)
    except keyring.errors.KeyringError:
        raise SyncError("could not use the system keychain") from None


def keychain_state(link: str) -> str:
    try:
        return "no" if load_access_url(link) is None else "yes"
    except SyncError:
        return "unknown"


def delete_access_url(link: str) -> bool:
    """Forget the link's access URL. Return False when there was none."""
    validate_link_name(link)
    try:
        if keyring.get_password(KEYCHAIN_SERVICE, link) is None:
            return False
        keyring.delete_password(KEYCHAIN_SERVICE, link)
    except keyring.errors.KeyringError:
        raise SyncError("could not use the system keychain") from None
    return True
