import keyring
import keyring.backend
import keyring.errors
import pytest

from finances.domain.models import DEFAULT_LINK, FeedAccount
from finances.sync.links import (
    KEYCHAIN_SERVICE,
    delete_access_url,
    load_access_url,
    save_access_url,
    validate_link_name,
)
from finances.sync.simplefin import SyncError

ACCESS = "https://user:pass@bridge.simplefin.org/simplefin"
NAME_RULE = "a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter"


class BrokenKeyring(keyring.backend.KeyringBackend):
    """A keychain that is locked or missing: every call fails."""

    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringLocked("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.PasswordSetError("refused")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.PasswordDeleteError("refused")


def test_the_names() -> None:
    assert (KEYCHAIN_SERVICE, DEFAULT_LINK) == ("finances-simplefin", "default")


def test_a_feed_account_has_the_default_link_unless_given() -> None:
    assert FeedAccount(1, 2, "ACT-1").link == "default"
    assert FeedAccount(1, 2, "ACT-1", "alex").link == "alex"


@pytest.mark.parametrize("name", ["a", "alex", "sam-2", "x" * 30, "default", "a-b-c", "z9"])
def test_usable_link_names(name: str) -> None:
    assert validate_link_name(name) == name


@pytest.mark.parametrize(
    "name", ["", "Alex", "1alex", "-alex", "al ex", "alex_", "x" * 31, "ålex", "alex\n", " alex"]
)
def test_unusable_link_names(name: str) -> None:
    with pytest.raises(ValueError) as caught:
        validate_link_name(name)
    assert str(caught.value) == NAME_RULE


def test_save_load_and_delete(keychain) -> None:
    assert load_access_url("alex") is None
    save_access_url("alex", ACCESS)
    save_access_url("sam", ACCESS + "2")
    assert keychain.passwords == {
        ("finances-simplefin", "alex"): ACCESS,
        ("finances-simplefin", "sam"): ACCESS + "2",
    }
    assert load_access_url("alex") == ACCESS
    save_access_url("alex", ACCESS + "3")
    assert load_access_url("alex") == ACCESS + "3"
    assert delete_access_url("alex") is True
    assert delete_access_url("alex") is False
    assert load_access_url("alex") is None
    assert load_access_url("sam") == ACCESS + "2"


@pytest.mark.parametrize("call", [load_access_url, delete_access_url])
def test_a_bad_name_never_reaches_the_keychain(keychain, call) -> None:
    with pytest.raises(ValueError):
        call("Bad Name")
    with pytest.raises(ValueError):
        save_access_url("Bad Name", ACCESS)
    assert keychain.passwords == {}


def test_a_keychain_that_fails_is_one_constant_error() -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        for call, args in (
            (save_access_url, ("alex", ACCESS)),
            (load_access_url, ("alex",)),
            (delete_access_url, ("alex",)),
        ):
            with pytest.raises(SyncError) as caught:
                call(*args)
            assert str(caught.value) == "could not use the system keychain"
            assert caught.value.__suppress_context__ is True
    finally:
        keyring.set_keyring(previous)
