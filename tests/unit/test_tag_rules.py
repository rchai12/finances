import pytest

from finances.domain.tags import clean_note, normalize_tag
from finances.domain.text import NOTE_LIMIT, TAG_LIMIT


def test_a_tag_at_the_limit_is_kept() -> None:
    assert TAG_LIMIT == 30
    assert normalize_tag("x" * 30) == "x" * 30
    with pytest.raises(ValueError, match="a tag must be 1 to 30 characters"):
        normalize_tag("x" * 31)


def test_a_note_at_the_limit_is_kept() -> None:
    assert NOTE_LIMIT == 500
    assert clean_note("x" * 500) == "x" * 500
    assert clean_note("   ") == ""
