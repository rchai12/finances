"""Data-health problems as plain text for the terminal."""

from dataclasses import dataclass

from finances.domain.health import Problem


@dataclass(frozen=True)
class HealthRow:
    kind: str
    account: str
    problem: str
    action: str


def health_rows(problems: list[Problem]) -> list[HealthRow]:
    """Each problem's four texts."""
    return [
        HealthRow(problem.kind, problem.account, problem.detail, problem.action)
        for problem in problems
    ]


def health_summary(problems: list[Problem]) -> str:
    """How many problems, or that there are none."""
    if not problems:
        return "No problems found."
    return f"Problems: {len(problems)}."
