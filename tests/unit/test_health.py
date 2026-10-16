from datetime import date

import pytest

from finances.domain.health import (
    BACKUP_STALE_DAYS,
    KINDS,
    STATEMENT_STALE_DAYS,
    SYNC_STALE_DAYS,
    AccountFacts,
    Problem,
    health_problems,
)

AS_OF = date(2026, 5, 20)
BACKUP = "Run fin backup run, or press Back up now on the Backups page."
SYNC = "Run fin sync run; if it fails, link SimpleFIN again (docs/sync-setup.md)."
DRIFT = "Look for a missing or extra transaction, or import the statement for that period."
STATEMENTS = "Upload the newest statement on the Statements page, or run fin import statement."
GAP = "Upload the statement for those days."


def facts(name: str = "Test Card", **changes) -> AccountFacts:
    values = {
        "name": name,
        "mapped": False,
        "last_pull": None,
        "drift_cents": None,
        "drift_date": None,
        "newest_statement_end": date(2026, 5, 1),
        "has_data": True,
        "gaps": (),
    }
    values.update(changes)
    return AccountFacts(**values)


def test_the_limits_and_kinds() -> None:
    assert (BACKUP_STALE_DAYS, SYNC_STALE_DAYS, STATEMENT_STALE_DAYS) == (2, 3, 45)
    assert KINDS == ("backup", "sync", "drift", "statements", "gap")


def test_nothing_wrong() -> None:
    assert health_problems([facts()], date(2026, 5, 19), AS_OF) == []
    assert health_problems([], date(2026, 5, 18), AS_OF) == []


@pytest.mark.parametrize(
    ("newest", "problems"),
    [
        (None, [Problem("backup", "", "No backup yet.", BACKUP)]),
        (date(2026, 5, 18), []),
        (
            date(2026, 5, 17),
            [Problem("backup", "", "The newest backup is 3 days old (taken 2026-05-17).", BACKUP)],
        ),
    ],
)
def test_backups(newest: date | None, problems: list[Problem]) -> None:
    assert health_problems([], newest, AS_OF) == problems


@pytest.mark.parametrize(
    ("changes", "problems"),
    [
        (
            {"mapped": True},
            [Problem("sync", "Test Card", "Mapped to SimpleFIN but never synced.", SYNC)],
        ),
        ({"mapped": True, "last_pull": date(2026, 5, 17)}, []),
        (
            {"mapped": True, "last_pull": date(2026, 5, 16)},
            [
                Problem(
                    "sync", "Test Card", "No SimpleFIN pull for 4 days (last on 2026-05-16).", SYNC
                )
            ],
        ),
        (
            {"mapped": True, "last_pull": AS_OF, "drift_cents": -1234, "drift_date": AS_OF},
            [
                Problem(
                    "drift",
                    "Test Card",
                    "The balance differs from SimpleFIN's by -$12.34 on 2026-05-20.",
                    DRIFT,
                )
            ],
        ),
        ({"mapped": True, "last_pull": AS_OF, "drift_cents": 0, "drift_date": AS_OF}, []),
        ({"mapped": True, "last_pull": AS_OF, "newest_statement_end": None}, []),
    ],
    ids=["never-synced", "three-days", "four-days", "drift", "no-drift", "no-statements-needed"],
)
def test_accounts_on_simplefin(changes: dict, problems: list[Problem]) -> None:
    assert health_problems([facts(**changes)], AS_OF, AS_OF) == problems


@pytest.mark.parametrize(
    ("changes", "problems"),
    [
        ({"newest_statement_end": date(2026, 4, 5)}, []),
        (
            {"newest_statement_end": date(2026, 4, 4)},
            [
                Problem(
                    "statements",
                    "Test Card",
                    "The newest statement ends 2026-04-04 (46 days ago).",
                    STATEMENTS,
                )
            ],
        ),
        (
            {"newest_statement_end": None, "has_data": False},
            [Problem("statements", "Test Card", "No statements yet.", STATEMENTS)],
        ),
        ({"newest_statement_end": None, "has_data": True}, []),
        (
            {"gaps": ((date(2026, 2, 1), date(2026, 2, 28)),)},
            [Problem("gap", "Test Card", "No statement covers 2026-02-01 to 2026-02-28.", GAP)],
        ),
    ],
    ids=["45-days", "46-days", "no-data", "data-without-statements", "a-gap"],
)
def test_accounts_on_statements(changes: dict, problems: list[Problem]) -> None:
    assert health_problems([facts(**changes)], AS_OF, AS_OF) == problems


def test_problems_come_by_kind_then_account_then_detail() -> None:
    found = health_problems(
        [
            facts(
                "beta",
                gaps=((date(2026, 3, 1), date(2026, 3, 5)), (date(2026, 1, 1), date(2026, 1, 9))),
            ),
            facts("Alpha", newest_statement_end=None, has_data=False),
            facts(
                "Card",
                mapped=True,
                last_pull=date(2026, 5, 1),
                drift_cents=500,
                drift_date=date(2026, 5, 1),
            ),
        ],
        None,
        AS_OF,
    )
    assert [(problem.kind, problem.account, problem.detail) for problem in found] == [
        ("backup", "", "No backup yet."),
        ("sync", "Card", "No SimpleFIN pull for 19 days (last on 2026-05-01)."),
        ("drift", "Card", "The balance differs from SimpleFIN's by $5.00 on 2026-05-01."),
        ("statements", "Alpha", "No statements yet."),
        ("gap", "beta", "No statement covers 2026-01-01 to 2026-01-09."),
        ("gap", "beta", "No statement covers 2026-03-01 to 2026-03-05."),
    ]
