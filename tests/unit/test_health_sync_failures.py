from datetime import UTC, date, datetime

from finances.domain.health import Problem, health_problems
from finances.domain.models import SyncFailure

AS_OF = date(2026, 10, 20)
SYNC = "Run fin sync run; if it fails, link SimpleFIN again (docs/sync-setup.md)."


def test_a_stored_failure_is_a_sync_problem() -> None:
    found = health_problems(
        [],
        AS_OF,
        AS_OF,
        failures=[
            SyncFailure(
                "sam",
                datetime(2026, 10, 19, 23, 30, tzinfo=UTC),
                "aggregator answered with an error",
            ),
            SyncFailure(
                "alex", datetime(2026, 10, 20, 11, 0, tzinfo=UTC), "could not reach the aggregator"
            ),
        ],
    )
    assert found == [
        Problem(
            "sync",
            "",
            "The last sync of link alex failed on 2026-10-20: could not reach the aggregator.",
            SYNC,
        ),
        Problem(
            "sync",
            "",
            "The last sync of link sam failed on 2026-10-19: aggregator answered with an error.",
            SYNC,
        ),
    ]


def test_no_failures_by_default() -> None:
    assert health_problems([], AS_OF, AS_OF) == []
