from datetime import date

from finances.domain.shared import Owed, Settlement, Share
from finances.views.shared import (
    SettlementRow,
    ShareRow,
    owed_text,
    settlement_rows,
    settlement_text,
    share_rows,
    share_text,
)

DAY = date(2026, 5, 20)


def test_share_text_of_zero_names_the_debtor() -> None:
    assert share_text(Share(1, "Sam", "Alex", 0)) == "Transaction 1: Alex owes Sam $0.00."


def test_share_text_of_a_negative_share_names_the_payer() -> None:
    assert share_text(Share(2, "Sam", "Alex", -200)) == "Transaction 2: Sam owes Alex $2.00."


def test_owed_text() -> None:
    assert owed_text(Owed("Alex", "Sam", 600)) == "Alex owes Sam $6.00."


def test_settlement_text() -> None:
    found = Settlement(1, "Alex", "Sam", 400, DAY)
    assert settlement_text(found) == "Alex paid Sam $4.00 on 2026-05-20."


def test_share_rows_every_field() -> None:
    rows = share_rows([Share(1, "Sam", "Alex", 1000), Share(2, "Sam", "Alex", -200)])
    assert rows == [
        ShareRow(id="1", paid_by="Sam", owes="Alex", owed="$10.00"),
        ShareRow(id="2", paid_by="Sam", owes="Alex", owed="-$2.00"),
    ]


def test_settlement_rows_every_field() -> None:
    rows = settlement_rows([Settlement(1, "Alex", "Sam", 400, DAY)])
    assert rows == [
        SettlementRow(id="1", date="2026-05-20", payer="Alex", payee="Sam", amount="$4.00"),
    ]
