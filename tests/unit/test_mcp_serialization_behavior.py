import ast
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from finances.analysis.search import FoundTransaction
from finances.domain.models import DataSource, Transaction
from finances.domain.spending import Flow
from finances.mcp_server import helpers, proposals, tools
from finances.mcp_server import serialization as ser
from tests.unit.test_mcp_serialization import CASES, proposal


def transaction():
    return Transaction(
        7,
        2,
        None,
        date(2026, 1, 3),
        date(2026, 1, 2),
        -123,
        "ACME COFFEE",
        None,
        None,
        None,
        None,
        DataSource.STATEMENT,
        False,
        "synthetic",
        datetime(2026, 1, 4, tzinfo=UTC),
    )


@pytest.mark.parametrize("assigned", [False, True])
@pytest.mark.parametrize("refund", [False, True])
def test_complete_transaction_rows(assigned, refund):
    item = replace(
        transaction(),
        amount_cents=123 if refund else -123,
        card_last4="1111" if assigned else None,
        is_pending=assigned,
    )
    flow = Flow(
        item.amount_cents,
        item.transaction_date,
        "spending",
        "Coffee" if assigned else "Uncategorized",
        "Food",
        "ACME",
        "Pat Example" if assigned else "Unassigned",
        "Test Card",
        "Test Bank",
        "",
    )
    assert ser.transaction_item(FoundTransaction(item, flow), {2: "Test Card"}) == {
        "id": 7,
        "day": "2026-01-02",
        "posted": "2026-01-03",
        "account": "Test Card",
        "description": "ACME COFFEE",
        "merchant": "ACME",
        "amount_cents": item.amount_cents,
        "kind": "spending",
        "refund": refund,
        "category": "Coffee" if assigned else None,
        "group": "Food" if assigned else None,
        "person": "Pat Example" if assigned else None,
        "card": "1111" if assigned else None,
        "pending": assigned,
    }


def test_brief_named_and_absent(monkeypatch):
    session = Mock()
    item = transaction()
    expected = {
        "id": 7,
        "posted": "2026-01-03",
        "account": "Test Card",
        "description": "ACME COFFEE",
        "amount_cents": -123,
    }
    assert ser.brief(item, {2: "Test Card"}) == expected
    lookup = Mock(return_value=item)
    monkeypatch.setattr(ser, "get_transaction", lookup)
    assert ser.named(session, 7, {2: "Test Card"}) == expected
    lookup.assert_called_once_with(session, 7)
    lookup.return_value = None
    with pytest.raises(AssertionError):
        ser.named(session, 7, {})
    assert session.mock_calls == []


@pytest.mark.parametrize(
    "kind,changes,new_fields",
    [
        (
            "group",
            {"transfer": False, "income": True},
            {
                "new": {
                    "name": "Synthetic value",
                    "group": None,
                    "kind": "income",
                    "sensitive": True,
                    "tax": None,
                }
            },
        ),
        (
            "group",
            {"transfer": False, "income": False},
            {
                "new": {
                    "name": "Synthetic value",
                    "group": None,
                    "kind": "spending",
                    "sensitive": True,
                    "tax": None,
                }
            },
        ),
        (
            "finding_status",
            {"finding_month": None, "finding_subject": None},
            {"finding": {"type": "fee", "about": "", "month": "", "status": "handled"}},
        ),
        (
            "category_delete",
            {"value": None},
            {
                "category_change": {
                    "name": "Synthetic before",
                    "rename_to": None,
                    "delete": True,
                    "move_to": None,
                }
            },
        ),
        ("future", {}, {"kind": "future", "category": None}),
    ],
)
@pytest.mark.parametrize("status", ["accepted", "declined"])
def test_proposal_variants(monkeypatch, kind, changes, new_fields, status):
    item = replace(
        proposal(kind),
        **changes,
        status=status,
        decided_at=datetime(2026, 1, 3, 4, 5, 6, 123456, tzinfo=UTC),
    )
    expected = dict(
        next(value for name, value in CASES if name == (kind if kind != "future" else "category"))
    )
    expected.update(
        new_fields,
        status=status,
        decided_at="2026-01-03T04:05:06.123456+00:00",
        waits_for=42,
        out_of_date=True,
    )
    session = Mock()
    waiting = Mock(return_value=42)
    stale = Mock(return_value=True)
    monkeypatch.setattr(ser, "waits_for", waiting)
    monkeypatch.setattr(ser, "proposal_out_of_date", stale)
    assert ser.proposal_item(session, item) == expected
    waiting.assert_called_once_with(session, item)
    stale.assert_called_once_with(session, item)
    assert session.mock_calls == []


@pytest.mark.parametrize("seam", ["waits_for", "proposal_out_of_date", "get_transaction"])
def test_read_errors_propagate_without_writes(monkeypatch, seam):
    session = Mock()
    monkeypatch.setattr(ser, "waits_for", Mock(return_value=None))
    monkeypatch.setattr(ser, seam, Mock(side_effect=LookupError("synthetic refusal")))
    with pytest.raises(LookupError, match="synthetic refusal"):
        if seam == "get_transaction":
            ser.named(session, 7, {})
        else:
            ser.proposal_item(session, proposal("category"))
    assert session.mock_calls == []


@pytest.mark.parametrize(
    "name,seam,args",
    [
        ("propose_category", "store_category_proposal", (7, "Coffee", "Reason")),
        ("propose_transfer", "store_transfer", (7, 8, "Reason")),
        ("propose_not_transfer", "store_not_transfer", (7, 8, "Reason")),
        ("propose_rule", "store_rule", (7, "ACME", "Coffee", "Reason")),
        ("propose_merchant_alias", "store_alias", (7, "ACME", "Reason")),
        ("propose_group", "store_group", ("Synthetic", 7, "Reason")),
        ("propose_new_category", "store_new_category", ("Synthetic", "Food", 7, "Reason")),
        ("propose_rule_change", "store_rule_change", (7, "Reason")),
        ("propose_category_change", "store_category_change", ("Coffee", "Reason")),
        ("propose_finding_status", "store_finding_status", ("fee", "handled", "Reason")),
    ],
)
def test_all_writer_serializer_wiring(monkeypatch, name, seam, args):
    session = Mock()
    item = proposal("category")
    marker = {"synthetic": "marker"}
    monkeypatch.setattr(proposals, "writing", lambda: nullcontext(session))
    monkeypatch.setattr(proposals, seam, Mock(return_value=item))
    monkeypatch.setattr(proposals, "find_finding", Mock(return_value=object()))
    serializer = Mock(return_value=marker)
    monkeypatch.setattr(ser, "proposal_item", serializer)
    assert getattr(tools, name)(*args) == {"proposal": marker}
    serializer.assert_called_once_with(session, item)
    assert session.mock_calls == []


def test_listing_and_queue_wiring(monkeypatch):
    session = Mock()
    item = proposal("category")
    marker = {"synthetic": "marker"}
    monkeypatch.setattr(tools, "reading", lambda: nullcontext(session))
    monkeypatch.setattr(proposals, "reading", lambda: nullcontext(session))
    monkeypatch.setattr(proposals, "load_proposals", Mock(return_value=[item]))
    serializer = Mock(return_value=marker)
    monkeypatch.setattr(ser, "proposal_item", serializer)
    assert tools.list_proposals() == {"proposals": [marker]}
    serializer.assert_called_once_with(session, item)
    monkeypatch.setattr(tools, "account_names", Mock(return_value={2: "Test Card"}))
    monkeypatch.setattr(tools, "load_uncategorized", Mock(return_value=[transaction()]))
    monkeypatch.setattr(tools, "count_uncategorized", Mock(return_value=1))
    brief = Mock(return_value=marker)
    monkeypatch.setattr(ser, "brief", brief)
    assert tools.list_uncategorized() == {
        "total": 1,
        "transactions": [dict(marker, merchant="ACME COFFEE")],
    }
    brief.assert_called_once()


def test_source_structure_and_limits():
    folder = Path(tools.__file__).parent
    source = (folder / "tools.py").read_text()
    serialization = (folder / "serialization.py").read_text()
    assert len(source.splitlines()) <= 861
    assert len(serialization.splitlines()) <= 400
    former = {"_transaction_item", "_brief", "_named", "_iso", "_proposal_item"}
    assert not any(isinstance(n, ast.Name) and n.id in former for n in ast.walk(ast.parse(source)))
    assert not any(
        isinstance(n, ast.FunctionDef) and n.name in former for n in ast.walk(ast.parse(source))
    )
    assert "mcp_server.tools" not in serialization and "mcp_server.server" not in serialization
    from finances.mcp_server.server import _TOOLS

    assert all(fn.__module__ == tools.__name__ for fn, _ in _TOOLS)


def test_read_tool_helper_markers(monkeypatch):
    from types import SimpleNamespace as NS

    session = Mock()
    names = {2: "Test Card"}
    marker = {"synthetic": "moved"}
    monkeypatch.setattr(tools, "reading", lambda: nullcontext(session))
    monkeypatch.setattr(tools, "account_names", Mock(return_value=names))
    found = object()
    monkeypatch.setattr(tools, "search_transactions", Mock(return_value=[found]))
    tx = Mock(return_value=marker)
    monkeypatch.setattr(ser, "transaction_item", tx)
    assert tools.list_transactions() == {"transactions": [marker], "next_offset": None}
    tx.assert_called_once_with(found, names)
    named = Mock(return_value=marker)
    monkeypatch.setattr(ser, "named", named)
    monkeypatch.setattr(
        tools,
        "list_transfer_pairs",
        Mock(return_value=[NS(id=3, status="auto", out_transaction_id=7, in_transaction_id=8)]),
    )
    assert tools.list_transfers() == {
        "total": 1,
        "pairs": [{"pair": 3, "status": "auto", "out": marker, "in": marker}],
    }
    from unittest.mock import call

    assert named.call_args_list == [call(session, 7, names), call(session, 8, names)]
    named.reset_mock()
    monkeypatch.setattr(tools, "transfer_suggestions", Mock(return_value=[(7, 8)]))
    assert tools.list_transfer_suggestions() == {"suggestions": [{"out": marker, "in": marker}]}
    assert named.call_args_list == [call(session, 7, names), call(session, 8, names)]
    iso = Mock(return_value="moved-date")
    monkeypatch.setattr(ser, "iso", iso)
    facts = NS(
        name="Test Card",
        gaps=[],
        newest_statement_end=None,
        mapped=False,
        last_pull=None,
        drift_cents=None,
        drift_date=None,
    )
    monkeypatch.setattr(
        tools,
        "coverage_report",
        Mock(
            return_value=NS(
                as_of=date(2026, 1, 2),
                accounts=[NS(facts=facts, type="credit_card", span=None, audited=[])],
                problems=[],
            )
        ),
    )
    result = tools.data_coverage()
    assert [
        result["accounts"][0][key] for key in ["newest_statement_end", "last_pull", "drift_date"]
    ] == ["moved-date"] * 3
    assert iso.call_args_list == [call(None)] * 3
    item = NS(
        id=1,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        subject="Synthetic",
        text="Synthetic note",
        dismissed_at=None,
    )
    monkeypatch.setattr(proposals, "writing", lambda: nullcontext(session))
    monkeypatch.setattr(proposals, "keep_advice", Mock(return_value=item))
    monkeypatch.setattr(proposals, "reading", lambda: nullcontext(session))
    monkeypatch.setattr(proposals, "load_advice", Mock(return_value=[item]))
    expected = {
        "id": 1,
        "created_at": "2026-01-02T00:00:00+00:00",
        "subject": "Synthetic",
        "text": "Synthetic note",
        "dismissed_at": "moved-date",
    }
    assert tools.log_advice("Synthetic note") == {"advice": expected}
    assert tools.list_advice() == {"advice": [expected]}
    assert session.mock_calls == []


# Captured planning-baseline function ASTs, with only serializer names normalized.
BASELINE_ASTS = {
    "list_accounts": "94b263ae062fdecaa2b8f538cf16bf8fedfafc3ae81978a5905ca168ef48d3ac",
    "get_balances": "aabecb62c80577a94f09fcddcd9a8136457ee18f78190405bf2a8d2d7ff95da9",
    "get_net_worth": "99f8710492e6c7e8bd4f90bf97cc2aa2f5c94054d8206d977296e8e7424211bf",
    "list_transactions": "d2e9334cdc89af3218d91c6a6462002dc1c65b344d1dd780ef71878b4d30299d",
    "get_spending": "1a9fbea7c509455c78db31f25733009570977cc8d8fa66759a79f13697f7b3c3",
    "month_over_month": "49c549261a1c70bd74c453e2290359650d9b3e3c673aec3497244c28fb51cc27",
    "_month_start": "c6acb4647fc1ad957dfba13a9fea36a7b0e0ed85b2d886400470b79174d1b1dd",
    "get_insights": "7b429a9759f7c95c9568ebce1e8934979c6d804da44a799012e9900b08a2a6cf",
    "get_recurring": "0f18ae03cf1a71af3997bb4098ae651fe6fd2c5e349a5acf72f7297acf81acc9",
    "get_upcoming": "05cbf7983b624c29d310e6d24a6081caf9f3f648a6de2eb35afea2107bbd5be4",
    "get_forecast": "dea460f8c65babdb378cc5cc2305d6ee00022277ba45f4149584a56031e3db69",
    "get_budgets": "1187183990582a4928503b5a391316d17340f30935baf6039229cb8b1b083818",
    "list_uncategorized": "f89bad8ae852c6f202994cd7b05d7564d6c2b5ab2b69c684d6e30c0d992837c7",
    "list_categories": "3e6caf70f6b084aa7be5d08e3b427af998d5ef936293b55ab20fb5c892ff82b8",
    "list_rules": "5491a1d5579ac2c34d0bb02e708d06272d62ef307ac0a7f4fa049de1843e98f3",
    "list_transfers": "11a5440fe7ac49834a11489c59c68c87edd193465a1db2a4a2480207634e0c39",
    "list_transfer_suggestions": "c770ae983a1631180a3e0c4c86901dec696a3500d130e621be3e4fea14159472",
    "data_coverage": "b1e09fbd414a4cdd65b53c21b3c13d62051e6bb5d341dc58a97c39efd57343ef",
    "find_merchants": "dbd65cb75f2c2de917f7f4969e81bf5cabb5b896bb5cdcc0cf6acfe0072e2546",
    "_as_tool": "d4020e3bff9ca68806f7a5c74070b8318948bc47f0bb04fde819e897bcbcbb1a",
    "propose_category": "12a407e59f83a9077fe6ed28a16f175c13664bf43067526e683cd6153559a6f9",
    "propose_transfer": "fdd158e14cdd9742ddd2340ff5bda9e91de065e15def0cc0dc3d63eaa0b8b15f",
    "propose_not_transfer": "8e1ceb3f82304e3be63c1cba8309c69b499aa5bd5291d7aaf5cc729baff97c49",
    "propose_rule": "9f4832366e0bb1fe6f2eb997cdfb0e31e3f97317e893b393c708135ef9ca3d05",
    "propose_merchant_alias": "6198a80903609bd0edd9a93ad7ba261035865b40ece1733634e9686c7b081d13",
    "propose_group": "06845c6a88b70803cde39af05a4206b37f993309e147c0ed363f550cb8117427",
    "propose_new_category": "b0d12d751c3d83f1711f3468733686aab17123f228da0c88b048ddb263df9442",
    "propose_rule_change": "fcb77583a79268ec2ee5753982ede4da660afb7fa114b17488062e5abffe61ff",
    "propose_category_change": "8db028cd7f84c929c62439cd2052328207b4e413ac36eacab80f846b99c6ddea",
    "propose_finding_status": "4300cb8b7bfecd8c8d65607cad71e3458b58c695723a7b5eed92fe3c3975f8b5",
    "list_proposals": "d80d6e8e95517af30b2b54881694c04cefdcb2c650b226126c22086254678739",
    "log_advice": "87b056094d26721f01fd32f2d0e4e35c1018391ec88bfa0f1ea1d4f72c91fad9",
    "list_advice": "5fb3411421b9fbeed23c6ea914716387fafce2c440312fac3c22e9e200734b94",
}


def test_tool_bodies_match_planning_baseline():
    import hashlib

    nodes = []
    for module in (tools, proposals, helpers):
        tree = ast.parse(Path(module.__file__).read_text())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                if module is helpers and node.name == "month_start":
                    node.name = "_month_start"
                nodes.append(node)
    actual = {
        node.name: hashlib.sha256(ast.dump(node).encode()).hexdigest()
        for node in nodes
        if isinstance(node, ast.FunctionDef)
    }
    assert actual == BASELINE_ASTS
