import pytest
import typer

from finances.cli.common import fail
from finances.domain.models import validate_provider_account_id
from finances.ingest.parsers.helpers import squeeze

BAD_ID = "feed account id must be 1 to 200 characters"


@pytest.mark.parametrize(
    ("text", "kept"),
    [("ACT-1", "ACT-1"), ("  ACT-1 \t", "ACT-1"), ("X" * 200, "X" * 200), (" a b ", "a b")],
)
def test_a_usable_provider_account_id(text: str, kept: str) -> None:
    assert validate_provider_account_id(text) == kept


@pytest.mark.parametrize("text", ["", "   ", "X" * 201, " " + "X" * 201])
def test_an_unusable_provider_account_id(text: str) -> None:
    with pytest.raises(ValueError, match=f"^{BAD_ID}$"):
        validate_provider_account_id(text)


def test_fail_prints_the_error_and_ends_the_command(capsys) -> None:
    with pytest.raises(typer.Exit) as stopped:
        fail("account not found")
    assert stopped.value.exit_code == 1
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "Error: account not found\n")


@pytest.mark.parametrize(
    ("text", "squeezed"),
    [("New  Balance", "NewBalance"), (" A \t B\nC ", "ABC"), ("", ""), (" x", "x")],
)
def test_squeeze_removes_every_space(text: str, squeezed: str) -> None:
    assert squeeze(text) == squeezed
