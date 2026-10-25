import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from backend.app.models.transaction import Transaction
from backend.app.models.account import Account
from backend.app.rules.high_value import HighValueTransactionRule
from backend.app.rules.velocity import TransactionVelocityRule
from backend.app.rules.unusual_timing import UnusualTransactionTimingRule
from backend.app.rules.geographic_anomaly import GeographicAnomalyRule
from backend.app.rules.unusual_spending import UnusualSpendingRule

def test_high_value_rule_triggers_above_threshold(db_session):
    rule = HighValueTransactionRule()
    txn = Transaction(
        transaction_ref="TXN-HIGH-01",
        account_id=1,
        amount=Decimal("15000.00"),
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        location_city="New York"
    )
    result = rule.evaluate(txn, db_session, parameters={"threshold": 10000.00}, configured_points=35)
    assert result.triggered is True
    assert result.points == 35
    assert "exceeds the configured threshold" in result.reason

def test_high_value_rule_does_not_trigger_below_threshold(db_session):
    rule = HighValueTransactionRule()
    txn = Transaction(
        transaction_ref="TXN-LOW-01",
        account_id=1,
        amount=Decimal("250.00"),
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        location_city="New York"
    )
    result = rule.evaluate(txn, db_session, parameters={"threshold": 10000.00}, configured_points=35)
    assert result.triggered is False
    assert result.points == 0

def test_velocity_rule_triggers_on_rapid_transactions(db_session):
    rule = TransactionVelocityRule()
    now = datetime(2026, 10, 24, 14, 0, 0)

    # Insert 3 prior transactions within 30 minutes
    for i in [5, 10, 15]:
        t = Transaction(
            transaction_ref=f"TXN-VELO-PRIOR-{i}",
            account_id=1,
            amount=Decimal("100.00"),
            timestamp=now - timedelta(minutes=i),
            location_city="Chicago"
        )
        db_session.add(t)
    db_session.commit()

    # Current 4th transaction at `now`
    current_txn = Transaction(
        transaction_ref="TXN-VELO-CURR",
        account_id=1,
        amount=Decimal("120.00"),
        timestamp=now,
        location_city="Chicago"
    )
    db_session.add(current_txn)
    db_session.commit()

    result = rule.evaluate(
        current_txn,
        db_session,
        parameters={"time_window_minutes": 60, "transaction_count_threshold": 3},
        configured_points=30
    )
    assert result.triggered is True
    assert result.points == 30
    assert result.context["transaction_count_in_window"] >= 4

def test_unusual_timing_rule_identifies_off_hours(db_session):
    rule = UnusualTransactionTimingRule()

    # Off-hours: 03:30 AM
    txn_night = Transaction(
        transaction_ref="TXN-NIGHT-01",
        account_id=1,
        amount=Decimal("100.00"),
        timestamp=datetime(2026, 10, 24, 3, 30, 0),
        location_city="Seattle"
    )
    res_night = rule.evaluate(txn_night, db_session, parameters={"start_hour": 1, "end_hour": 5}, configured_points=20)
    assert res_night.triggered is True
    assert res_night.points == 20

    # Normal daytime: 14:30 PM
    txn_day = Transaction(
        transaction_ref="TXN-DAY-01",
        account_id=1,
        amount=Decimal("100.00"),
        timestamp=datetime(2026, 10, 24, 14, 30, 0),
        location_city="Seattle"
    )
    res_day = rule.evaluate(txn_day, db_session, parameters={"start_hour": 1, "end_hour": 5}, configured_points=20)
    assert res_day.triggered is False
    assert res_day.points == 0

def test_geographic_anomaly_detects_impossible_speed(db_session):
    rule = GeographicAnomalyRule()
    now = datetime(2026, 10, 24, 12, 0, 0)

    # 1st transaction in New York at 12:00
    t1 = Transaction(
        transaction_ref="TXN-GEO-NYC",
        account_id=1,
        amount=Decimal("50.00"),
        timestamp=now,
        location_city="New York",
        location_country="USA",
        latitude=Decimal("40.7128"),
        longitude=Decimal("-74.0060")
    )
    db_session.add(t1)
    db_session.commit()

    # 2nd transaction in London 45 minutes later (5,570 km away -> implied speed ~ 7400 km/h)
    t2 = Transaction(
        transaction_ref="TXN-GEO-LON",
        account_id=1,
        amount=Decimal("150.00"),
        timestamp=now + timedelta(minutes=45),
        location_city="London",
        location_country="UK",
        latitude=Decimal("51.5074"),
        longitude=Decimal("-0.1278")
    )
    db_session.add(t2)
    db_session.commit()

    result = rule.evaluate(t2, db_session, parameters={"speed_threshold_kmh": 800.0, "time_window_hours": 12}, configured_points=40)
    assert result.triggered is True
    assert result.points == 40
    assert result.context["implied_speed_kmh"] > 800.0

def test_geographic_anomaly_does_not_flag_plausible_travel(db_session):
    rule = GeographicAnomalyRule()
    now = datetime(2026, 10, 24, 10, 0, 0)

    # 1st transaction in New York at 10:00 AM
    t1 = Transaction(
        transaction_ref="TXN-GEO-NYC-NORMAL",
        account_id=1,
        amount=Decimal("30.00"),
        timestamp=now,
        location_city="New York",
        latitude=Decimal("40.7128"),
        longitude=Decimal("-74.0060")
    )
    db_session.add(t1)
    db_session.commit()

    # 2nd transaction in Philadelphia (150 km) 3 hours later (Implied speed = 50 km/h, perfectly plausible)
    t2 = Transaction(
        transaction_ref="TXN-GEO-PHL-NORMAL",
        account_id=1,
        amount=Decimal("40.00"),
        timestamp=now + timedelta(hours=3),
        location_city="Philadelphia",
        latitude=Decimal("39.9526"),
        longitude=Decimal("-75.1652")
    )
    db_session.add(t2)
    db_session.commit()

    result = rule.evaluate(t2, db_session, parameters={"speed_threshold_kmh": 800.0, "time_window_hours": 12})
    assert result.triggered is False
    assert result.points == 0

def test_unusual_spending_insufficient_history(db_session):
    rule = UnusualSpendingRule()
    now = datetime(2026, 10, 24, 15, 0, 0)

    # Only 2 prior transactions (minimum required is 5)
    for i in range(2):
        t = Transaction(
            transaction_ref=f"TXN-SPEND-PRIOR-{i}",
            account_id=1,
            amount=Decimal("50.00"),
            timestamp=now - timedelta(days=i + 1),
            location_city="Boston",
            status="COMPLETED"
        )
        db_session.add(t)
    db_session.commit()

    curr = Transaction(
        transaction_ref="TXN-SPEND-CURR",
        account_id=1,
        amount=Decimal("500.00"),
        timestamp=now,
        location_city="Boston",
        status="COMPLETED"
    )
    db_session.add(curr)
    db_session.commit()

    result = rule.evaluate(curr, db_session, parameters={"min_historical_txns": 5, "baseline_multiplier": 3.0})
    assert result.triggered is False
    assert result.insufficient_data is True
    assert "Insufficient historical data" in result.reason

def test_unusual_spending_triggers_when_exceeding_baseline(db_session):
    rule = UnusualSpendingRule()
    now = datetime(2026, 10, 24, 15, 0, 0)

    # Insert 6 prior transactions with mean around $50
    for i in range(6):
        t = Transaction(
            transaction_ref=f"TXN-SPEND-BASE-{i}",
            account_id=1,
            amount=Decimal("50.00"),
            timestamp=now - timedelta(days=i + 1),
            location_city="Boston",
            status="COMPLETED"
        )
        db_session.add(t)
    db_session.commit()

    # Current transaction of $350 (exceeds 3.0 * $50 = $150)
    curr = Transaction(
        transaction_ref="TXN-SPEND-DEVIANT",
        account_id=1,
        amount=Decimal("350.00"),
        timestamp=now,
        location_city="Boston",
        status="COMPLETED"
    )
    db_session.add(curr)
    db_session.commit()

    result = rule.evaluate(curr, db_session, parameters={"min_historical_txns": 5, "baseline_multiplier": 3.0}, configured_points=25)
    assert result.triggered is True
    assert result.points == 25
    assert result.insufficient_data is False
    assert result.context["historical_count"] == 6
