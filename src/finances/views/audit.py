"""The audit trail as the `fin audit` table shows it."""

import re
from dataclasses import dataclass

from finances.domain.audit import Change

_FINDING_MONTH = re.compile(r" in (\d{4}-\d{2})$")

_LINKS = {
    "account": "/accounts",
    "person": "/people",
    "category": "/categories",
    "rule": "/categories",
    "transfer": "/transfers",
    "statement": "/statements",
    "backup": "/backups",
    "proposal": "/review",
    "alias": "/categories",
    "settlement": "/shared",
}


@dataclass(frozen=True)
class ChangeRow:
    when: str
    who: str
    action: str
    record: str
    before: str
    after: str


def change_rows(changes: list[Change]) -> list[ChangeRow]:
    return [
        ChangeRow(
            when=item.at.strftime("%Y-%m-%d %H:%M"),
            who=item.who,
            action=item.action,
            record=item.kind if item.record_id is None else f"{item.kind} {item.record_id}",
            before="" if item.before is None else item.before,
            after="" if item.after is None else item.after,
        )
        for item in changes
    ]


def change_link(change: Change) -> str | None:
    if change.kind == "transaction":
        return f"/transactions/{change.record_id}"
    if change.kind == "finding":
        text = change.after if change.after is not None else change.before
        found = _FINDING_MONTH.search(text or "")
        if found is not None:
            return f"/insights?month={found.group(1)}"
        return "/insights"
    return _LINKS.get(change.kind)
