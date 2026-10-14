import pytest

from finances.domain.merchants import clean_merchant


@pytest.mark.parametrize(
    ("description", "merchant"),
    [
        ("FOOBAR CHICKEN #123TUCKERGA", "FOOBAR CHICKEN"),
        ("ACME GROCERY #123 DECATUR GA", "ACME GROCERY"),
        ("acme  gas #1234 allen tx", "ACME GAS"),
        ("  ACME COFFEE  ", "ACME COFFEE"),
        ("DEBIT CARD PURCHASE ACME*Terminal3 08-15 Lisboa", "ACME"),
        ("DEBIT CARD RECURRING PYMT STREAMCO.COM 08-19 866-555-0100", "STREAMCO.COM"),
        ("EXAMPLESTREAM.COM 08-01 SURREY BC 1234 DEBIT CARD PURCHASE", "EXAMPLESTREAM.COM"),
        ("POS PURCHASE FOOBAR DINER", "FOOBAR DINER"),
        ("DEBIT CARD PURCHASE SQ *ACME COFFEE 08-15 DECATUR", "ACME COFFEE"),
        ("SQ *ACME COFFEE", "ACME COFFEE"),
        ("SQ*ACME COFFEE", "ACME COFFEE"),
        ("TST* FOOBAR DINER 0042", "FOOBAR DINER 0042"),
        ("TST*FOOBAR DINER", "FOOBAR DINER"),
        ("PAYPAL *STREAMCO", "STREAMCO"),
        ("GOOGLE *FOOBAR GAMES", "FOOBAR GAMES"),
        ("PP*ACME STORE", "ACME STORE"),
        ("SP ACME OUTDOORS", "ACME OUTDOORS"),
        ("AMAZON MKTPL*AB12CD34E", "AMAZON MKTPL"),
        ("PAYMENT FROM CHK 9999 CONF#M00000000", "PAYMENT FROM CHK 9999"),
        ("EXAMPLE BANK MOBILE PYMT", "EXAMPLE BANK MOBILE PYMT"),
        ("ONLINE PAYMENT, THANK YOU", "ONLINE PAYMENT, THANK YOU"),
        ("INCOMING WIRE TRANSFER WIRE REF# 20260814-00000000", "INCOMING WIRE TRANSFER WIRE"),
        (
            "Probe Person PAYMENT ID ABC000000000 ZELLE PAYMENT TO",
            "PROBE PERSON PAYMENT ID ABC ZELLE PAYMENT TO",
        ),
        (
            "ACHDepositInternettransferfromEXAMPLE BANKDDAaccount",
            "ACHDEPOSITINTERNETTRANSFERFROMEXAMPLE BANKDDAACCOUNT",
        ),
        ("STREAMCO.COM 866-555-0100", "STREAMCO.COM"),
        ("ACME MARKET 08-15", "ACME MARKET"),
        ("ACME 12-PACK STORE", "ACME 12-PACK STORE"),
        ("ACME #١٢٣", "ACME"),
        ("INTEREST CHARGE ON PURCHASES", "INTEREST CHARGE ON PURCHASES"),
    ],
)
def test_clean_merchant(description: str, merchant: str) -> None:
    assert clean_merchant(description) == merchant


@pytest.mark.parametrize(
    ("description", "merchant"),
    [("#1234", "#1234"), ("12345678", "12345678"), ("  *  ", "*"), ("sq *", "SQ *")],
)
def test_when_nothing_is_left_the_description_is_kept(description: str, merchant: str) -> None:
    assert clean_merchant(description) == merchant


def test_cleaning_twice_changes_nothing() -> None:
    for description in ("SQ *ACME COFFEE", "ACME GROCERY #123 DECATUR GA", "STREAMCO.COM"):
        once = clean_merchant(description)
        assert clean_merchant(once) == once
