"""Stable fingerprints for statement lines, so the same line is stored once."""

import hashlib

from finances.ingest.parsers.helpers import collapse_ws
from finances.ingest.statement import StatementLine


def fingerprint_lines(account_id: int, lines: list[StatementLine]) -> list[str]:
    seen: dict[str, int] = {}
    fingerprints: list[str] = []
    for item in lines:
        key = "\n".join(
            (
                str(account_id),
                item.posted_date.isoformat(),
                str(item.amount_cents),
                collapse_ws(item.description).upper(),
                "" if item.card_last4 is None else item.card_last4,
                "" if item.external_ref is None else item.external_ref,
            )
        )
        occurrence = seen.get(key, 0)
        seen[key] = occurrence + 1
        payload = f"{key}\n{occurrence}"
        fingerprints.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())
    return fingerprints
