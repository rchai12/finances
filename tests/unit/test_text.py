from pathlib import Path

import pytest

import finances.db.orm as orm
import finances.domain.feed_setup as feed_setup
import finances.domain.people as people
import finances.ingest.parsers.helpers as helpers
import finances.ingest.service as ingest_service
from finances.db.orm import Base
from finances.domain.text import (
    DESCRIPTION_LIMIT,
    FEED_ID_LIMIT,
    NAME_LIMIT,
    PROVIDER_ACCOUNT_ID_LIMIT,
    collapse_ws,
    fit,
)


def test_the_limits() -> None:
    assert (NAME_LIMIT, DESCRIPTION_LIMIT, FEED_ID_LIMIT, PROVIDER_ACCOUNT_ID_LIMIT) == (
        100,
        500,
        100,
        200,
    )


def test_the_older_names_are_the_same_limits() -> None:
    assert people.NAME_LIMIT == feed_setup.TEXT_LIMIT == ingest_service.TEXT_LIMIT == NAME_LIMIT
    assert ingest_service.DESCRIPTION_LIMIT == DESCRIPTION_LIMIT


def test_collapse_ws_has_one_home() -> None:
    assert helpers.collapse_ws is collapse_ws
    assert collapse_ws("  ACME \t COFFEE\n#12  ") == "ACME COFFEE #12"
    assert collapse_ws("") == ""


@pytest.mark.parametrize(
    ("text", "limit", "fitted"),
    [
        ("  Probe   Visa  ", 100, "Probe Visa"),
        ("ABCDE", 5, "ABCDE"),
        ("ABCDEF", 5, "ABCDE"),
        ("ABCD EFGH", 5, "ABCD"),
        ("   ", 5, ""),
        ("A B", 5, "A B"),
    ],
)
def test_fit_collapses_cuts_and_trims(text: str, limit: int, fitted: str) -> None:
    assert fit(text, limit) == fitted


@pytest.mark.parametrize(
    ("table", "column", "limit"),
    [
        ("accounts", "name", NAME_LIMIT),
        ("accounts", "institution", NAME_LIMIT),
        ("people", "name", NAME_LIMIT),
        ("cardholder_aliases", "cardholder", NAME_LIMIT),
        ("transactions", "description", DESCRIPTION_LIMIT),
        ("transactions", "cardholder", NAME_LIMIT),
        ("transactions", "external_id", NAME_LIMIT),
        ("feed_items", "feed_id", FEED_ID_LIMIT),
        ("feed_accounts", "provider_account_id", PROVIDER_ACCOUNT_ID_LIMIT),
        ("feed_seen_accounts", "provider_account_id", PROVIDER_ACCOUNT_ID_LIMIT),
        ("feed_seen_accounts", "name", NAME_LIMIT),
        ("feed_seen_accounts", "institution", NAME_LIMIT),
    ],
)
def test_each_column_is_as_wide_as_its_limit(table: str, column: str, limit: int) -> None:
    assert Base.metadata.tables[table].columns[column].type.length == limit


def test_the_orm_names_its_widths_by_constant() -> None:
    source = Path(orm.__file__).read_text(encoding="utf-8")
    for literal in ("String(100)", "String(200)", "String(500)"):
        assert literal not in source
