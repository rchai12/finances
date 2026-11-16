from datetime import date
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from finances.analysis.spending import spending_report
from finances.categorize import service
from finances.cli.categories import categorize_all
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    create_rule,
    create_transfer_pair,
    list_category_assignments,
    list_changes,
    list_rules,
    list_transfer_pairs,
    reject_transfer,
    set_category_by_hand,
    set_split,
    share_transaction,
)
from finances.domain.models import CONFIRMED, MANUAL
from finances.ingest.service import ImportStatus, StatementImportResult
from finances.sync.runner import LinkRun, SyncReport
from finances.web.app import create_app
from tests.support import WEB_PORT, post, run

DAY = date(2026, 5, 10)


def add_pair(session: Session) -> None:
    for number, cents in enumerate((-12345, 12345), start=1):
        account = create_account(session, f"Test Account {number}", "Test Bank", "checking")
        session.add(
            TransactionRow(
                account_id=account.id,
                posted_date=DAY,
                amount_cents=cents,
                description="SYNTHETIC TRANSFER",
                source="statement",
                fingerprint=f"t{number:02d}".ljust(64, "0"),
            )
        )
    session.flush()


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        add_pair(session)
    engine.dispose()
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    found.get("/categories")
    return found


def snapshot() -> tuple:
    engine = get_engine()
    with session_scope(engine) as session:
        found = (
            list_rules(session),
            list_category_assignments(session),
            list_transfer_pairs(session),
            list_changes(session),
        )
    engine.dispose()
    return found


def test_pair_failure_rolls_back_rule_categories_pairs_and_audit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = snapshot()
    real_pair = service.pair_transfers

    def fail(session: Session) -> None:
        assert list_rules(session)
        assert list_category_assignments(session)
        assert real_pair(session).paired == 1
        assert len(list_changes(session)) > len(before[3])
        raise RuntimeError("synthetic pairing failure")

    monkeypatch.setattr(service, "pair_transfers", fail)
    with pytest.raises(RuntimeError, match="synthetic pairing failure"):
        post(
            client,
            "/categories/rules/add",
            pattern="SYNTHETIC",
            category="Groceries",
            match="contains",
            priority="0",
        )
    assert snapshot() == before


@pytest.mark.parametrize(
    "exclusion", ["none", "rejected", "confirmed", "split", "shared", "manual"]
)
def test_repeated_clear_preserves_pairing_rules_and_report(
    client: TestClient, exclusion: str
) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        if exclusion == "rejected":
            reject_transfer(session, 1, 2)
        elif exclusion == "confirmed":
            create_transfer_pair(session, 1, 2, CONFIRMED)
        elif exclusion == "split":
            set_split(session, 2, [(10000, "Groceries"), (2345, "Dining")])
        elif exclusion == "shared":
            create_person(session, "Example Person")
            create_person(session, "Example Payer")
            share_transaction(session, 2, "Example Person", payer="Example Payer")
        elif exclusion == "manual":
            set_category_by_hand(session, 2, "Groceries")
    for _ in range(2):
        response = post(client, "/transactions/1/category/clear")
        assert (response.status_code, response.headers["location"]) == (
            303,
            "/transactions/1?notice=category-cleared",
        )
    with session_scope(engine) as session:
        pairs = list_transfer_pairs(session)
        assert len(pairs) == (1 if exclusion in ("none", "confirmed", "manual") else 0)
        if exclusion == "confirmed":
            assert pairs[0].status == CONFIRMED
        if exclusion == "manual":
            assert list_category_assignments(session)[2].source == MANUAL
        if exclusion == "none":
            report = spending_report(session, DAY, DAY)
            assert report.summary.spent_cents == 0
            assert report.summary.transfers == 2
            assert report.lines == []
    engine.dispose()


@pytest.mark.parametrize("action", ["import", "sync", "split"])
def test_existing_web_operations_pair_once(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    pairing = Mock(wraps=service.pair_transfers)
    monkeypatch.setattr(service, "pair_transfers", pairing)
    if action == "import":
        monkeypatch.setattr(
            "finances.web.routes.statements.import_statement",
            lambda *args, **kwargs: StatementImportResult("test.pdf", ImportStatus.IMPORTED, "ok"),
        )
        response = client.post(
            "/statements/upload",
            data={"csrf": client.cookies["fin_csrf"]},
            files={"file": ("test.pdf", b"%PDF-synthetic", "application/pdf")},
        )
        assert response.status_code == 200
    elif action == "sync":
        monkeypatch.setattr(
            "finances.web.routes.sync.run_links",
            lambda *args, **kwargs: [LinkRun("example", SyncReport([], []), None)],
        )
        response = post(client, "/sync/run")
        assert response.status_code == 200
    else:
        engine = get_engine()
        with session_scope(engine) as session:
            set_split(session, 1, [(-10000, "Groceries"), (-2345, "Dining")])
        engine.dispose()
        response = post(client, "/transactions/1/split/clear")
        assert (response.status_code, response.headers["location"]) == (
            303,
            "/transactions/1?notice=split-removed",
        )
    assert pairing.call_count == 1
    assert len(snapshot()[2]) == 1


def test_cli_adapter_result_and_text(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    result = service.CategorizeResult(2, 1, 1)
    operation = Mock(return_value=result)
    monkeypatch.setattr("finances.cli.categories.categorize_and_pair", operation)
    assert categorize_all() is result
    assert operation.call_count == 1
    output = run("categorize")
    assert output.exit_code == 0
    assert output.stdout == "Categorized 2 transactions: 1 changed, 1 without a category.\n"


def test_standalone_categorize_leaves_pair_waiting(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_rule(session, "SYNTHETIC", "Groceries")
        assert service.categorize(session) == service.CategorizeResult(2, 2, 0)
        assert list_transfer_pairs(session) == []
    engine.dispose()
