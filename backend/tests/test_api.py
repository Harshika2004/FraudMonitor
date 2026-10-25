import pytest
from datetime import datetime
from decimal import Decimal
from backend.app.models.transaction import Transaction
from backend.app.models.alert import Alert

def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["ok", "degraded"]
    assert "database" in data

def test_create_and_list_transactions(client, db_session):
    # Create transaction
    payload = {
        "account_id": 1,
        "amount": "1250.00",
        "currency": "USD",
        "transaction_type": "TRANSFER",
        "channel": "ONLINE",
        "timestamp": datetime.utcnow().isoformat(),
        "location_city": "Austin",
        "location_country": "USA"
    }
    create_res = client.post("/api/transactions", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()
    txn_id = created["transaction_id"]

    # List transactions
    list_res = client.get("/api/transactions")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] >= 1
    assert any(item["transaction_id"] == txn_id for item in data["items"])

def test_invalid_transaction_amount_rejected(client):
    payload = {
        "account_id": 1,
        "amount": "-50.00",  # Invalid negative amount
        "currency": "USD",
        "transaction_type": "TRANSFER",
        "channel": "ONLINE",
        "timestamp": datetime.utcnow().isoformat(),
        "location_city": "Austin"
    }
    res = client.post("/api/transactions", json=payload)
    assert res.status_code == 422

def test_evaluate_single_transaction_api(client, db_session):
    # Insert high-value transaction
    txn = Transaction(
        transaction_ref="TXN-API-EVAL-01",
        account_id=1,
        amount=Decimal("18000.00"),
        timestamp=datetime.utcnow(),
        location_city="Atlanta"
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)

    res = client.post(f"/api/transactions/{txn.transaction_id}/evaluate")
    assert res.status_code == 200
    data = res.json()
    assert data["is_flagged"] is True
    assert data["risk_score"] >= 35
    assert len(data["triggered_rules"]) >= 1

def test_alert_status_workflow_and_notes(client, db_session):
    # Create transaction and alert
    txn = Transaction(
        transaction_ref="TXN-ALERT-TEST-01",
        account_id=1,
        amount=Decimal("25000.00"),
        timestamp=datetime.utcnow(),
        location_city="San Francisco"
    )
    db_session.add(txn)
    db_session.commit()

    alert = Alert(
        alert_ref="ALT-TEST-0001",
        transaction_id=txn.transaction_id,
        risk_score=75,
        risk_category="HIGH",
        status="OPEN"
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # 1. Update status to UNDER_INVESTIGATION
    patch_res = client.patch(
        f"/api/alerts/{alert.alert_id}/status",
        json={"status": "UNDER_INVESTIGATION", "assigned_to": "Analyst Alice", "note": "Reviewing KYC"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "UNDER_INVESTIGATION"

    # 2. Add an investigation note
    note_res = client.post(
        f"/api/alerts/{alert.alert_id}/notes",
        json={"author": "Analyst Alice", "note_text": "Verified with cardholder. Transaction authorized.", "action_taken": "Contacted Customer"}
    )
    assert note_res.status_code == 201

    # 3. Resolve alert
    resolve_res = client.patch(
        f"/api/alerts/{alert.alert_id}/status",
        json={"status": "RESOLVED", "resolution_reason": "CUSTOMER_VERIFIED", "note": "Closed after verification."}
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"

    # 4. Fetch details to verify notes
    detail_res = client.get(f"/api/alerts/{alert.alert_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["notes"]) >= 2

def test_invalid_alert_status_rejected(client, db_session):
    txn = Transaction(
        transaction_ref="TXN-INVALID-STATUS-TEST",
        account_id=1,
        amount=Decimal("100.00"),
        timestamp=datetime.utcnow(),
        location_city="Denver"
    )
    db_session.add(txn)
    db_session.commit()
    alert = Alert(
        alert_ref="ALT-TEST-0002",
        transaction_id=txn.transaction_id,
        risk_score=35,
        risk_category="MEDIUM",
        status="OPEN"
    )
    db_session.add(alert)
    db_session.commit()

    # Invalid status should return 422 validation error
    res = client.patch(f"/api/alerts/{alert.alert_id}/status", json={"status": "NON_EXISTENT_STATUS"})
    assert res.status_code == 422

def test_analytics_dashboard_endpoint(client, db_session):
    res = client.get("/api/analytics/dashboard?days=30")
    assert res.status_code == 200
    data = res.json()
    assert "kpi" in data
    assert "risk_distribution" in data
    assert "alert_status_distribution" in data
    assert "rule_frequency" in data
