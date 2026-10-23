"""The audit trail as the `fin audit` table shows it."""

from dataclasses import dataclass

from finances.domain.audit import Change


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


def change_link(change: Change) -> str:
    if change.kind == "transaction":
        return f"/transactions/{change.record_id}"
    return {
        "account": "/accounts",
        "person": "/people",
        "category": "/categories",
        "rule": "/categories",
        "transfer": "/transfers",
        "statement": "/statements",
        "backup": "/backups",
    }[change.kind]
