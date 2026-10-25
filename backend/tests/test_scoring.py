import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from backend.app.models.transaction import Transaction
from backend.app.models.rule import FraudRule
from backend.app.models.alert import Alert
from backend.app.rules.engine import rule_engine

def test_risk_band_mapping(db_session):
    # Test boundary conditions
    assert rule_engine.determine_risk_category(0, db_session) == "LOW"
    assert rule_engine.determine_risk_category(29, db_session) == "LOW"
    assert rule_engine.determine_risk_category(30, db_session) == "MEDIUM"
    assert rule_engine.determine_risk_category(59, db_session) == "MEDIUM"
    assert rule_engine.determine_risk_category(60, db_session) == "HIGH"
    assert rule_engine.determine_risk_category(79, db_session) == "HIGH"
    assert rule_engine.determine_risk_category(80, db_session) == "CRITICAL"
    assert rule_engine.determine_risk_category(100, db_session) == "CRITICAL"

def test_risk_bands_no_gaps_or_overlaps():
    bands = [
        ("LOW", 0, 29),
        ("MEDIUM", 30, 59),
        ("HIGH", 60, 79),
        ("CRITICAL", 80, 100)
    ]
    assert rule_engine.validate_risk_bands(bands) is True

    # Bad bands with gap
    gap_bands = [
        ("LOW", 0, 25),
        ("MEDIUM", 30, 59),  # Gap between 25 and 30
        ("HIGH", 60, 79),
        ("CRITICAL", 80, 100)
    ]
    assert rule_engine.validate_risk_bands(gap_bands) is False

def test_score_capped_at_max(db_session):
    # Construct transaction triggering multiple rules
    txn = Transaction(
        transaction_ref="TXN-COMPOUND-01",
        account_id=1,
        amount=Decimal("50000.00"),  # High value (+35)
        timestamp=datetime(2026, 10, 24, 3, 0, 0),  # Off hours (+20)
        location_city="New York",
        latitude=Decimal("40.7128"),
        longitude=Decimal("-74.0060")
    )
    db_session.add(txn)
    db_session.commit()

    score, category, results, alert = rule_engine.evaluate_transaction(txn, db_session)
    assert score <= 100
    assert alert is not None
    assert alert.risk_score == score

def test_duplicate_alert_prevention_idempotency(db_session):
    txn = Transaction(
        transaction_ref="TXN-IDEMP-01",
        account_id=1,
        amount=Decimal("25000.00"),
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        location_city="Houston"
    )
    db_session.add(txn)
    db_session.commit()

    # First evaluation creates 1 alert
    score1, cat1, results1, alert1 = rule_engine.evaluate_transaction(txn, db_session, force_reevaluate=False)
    alerts_count1 = db_session.query(Alert).filter(Alert.transaction_id == txn.transaction_id).count()
    assert alerts_count1 == 1

    # Second evaluation without force_reevaluate does not duplicate
    score2, cat2, results2, alert2 = rule_engine.evaluate_transaction(txn, db_session, force_reevaluate=False)
    alerts_count2 = db_session.query(Alert).filter(Alert.transaction_id == txn.transaction_id).count()
    assert alerts_count2 == 1
    assert alert1.alert_id == alert2.alert_id

def test_disabled_rule_does_not_fire(db_session):
    # Disable high value rule in database
    hv_rule = db_session.query(FraudRule).filter(FraudRule.rule_code == "RULE_HIGH_VALUE").first()
    hv_rule.is_enabled = False
    db_session.commit()

    txn = Transaction(
        transaction_ref="TXN-DISABLED-TEST",
        account_id=1,
        amount=Decimal("50000.00"),
        timestamp=datetime(2026, 10, 24, 12, 0, 0),
        location_city="Dallas"
    )
    db_session.add(txn)
    db_session.commit()

    score, category, results, alert = rule_engine.evaluate_transaction(txn, db_session)
    triggered_codes = [r.rule_code for r in results if r.triggered]
    assert "RULE_HIGH_VALUE" not in triggered_codes
