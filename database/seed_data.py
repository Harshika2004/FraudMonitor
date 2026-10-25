"""
Synthetic Sample Banking Data Generator
Populates customers, accounts, and realistic transaction streams with both
ordinary activity and deliberate fraud indicator patterns.
Completely synthetic - no real personal or banking data.
"""

import sys
import os
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Add project root to sys.path so imports work cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.database.connection import SessionLocal, engine
from backend.app.models.customer import Customer
from backend.app.models.account import Account
from backend.app.models.transaction import Transaction
from backend.app.models.rule import FraudRule
from backend.app.models.risk_config import RiskScoreConfiguration
from backend.app.models.alert import Alert, AlertRuleTrigger
from backend.app.models.investigation_note import InvestigationNote
from backend.app.rules.engine import rule_engine

# Seed for reproducible synthetic data
random.seed(42)

# Synthetic Reference Data
SYNTHETIC_CUSTOMERS = [
    {"ref": "CUST-1001", "first": "Alexander", "last": "Wright", "email": "a.wright@synthetic-mail.test", "phone": "+1-555-0101", "segment": "STANDARD"},
    {"ref": "CUST-1002", "first": "Sophia", "last": "Chen", "email": "s.chen@synthetic-mail.test", "phone": "+1-555-0102", "segment": "HIGH_NET_WORTH"},
    {"ref": "CUST-1003", "first": "Marcus", "last": "Patel", "email": "m.patel@synthetic-mail.test", "phone": "+1-555-0103", "segment": "STANDARD"},
    {"ref": "CUST-1004", "first": "Elena", "last": "Rostova", "email": "e.rostova@synthetic-mail.test", "phone": "+1-555-0104", "segment": "STANDARD"},
    {"ref": "CUST-1005", "first": "David", "last": "Kim", "email": "d.kim@synthetic-mail.test", "phone": "+1-555-0105", "segment": "LOW_RISK"},
    {"ref": "CUST-1006", "first": "Olivia", "last": "Johnson", "email": "o.johnson@synthetic-mail.test", "phone": "+1-555-0106", "segment": "STANDARD"},
    {"ref": "CUST-1007", "first": "James", "last": "Miller", "email": "j.miller@synthetic-mail.test", "phone": "+1-555-0107", "segment": "HIGH_NET_WORTH"},
    {"ref": "CUST-1008", "first": "Amara", "last": "Okafor", "email": "a.okafor@synthetic-mail.test", "phone": "+1-555-0108", "segment": "STANDARD"},
    {"ref": "CUST-1009", "first": "Lucas", "last": "Santos", "email": "l.santos@synthetic-mail.test", "phone": "+1-555-0109", "segment": "LOW_RISK"},
    {"ref": "CUST-1010", "first": "Zara", "last": "Al-Mansoor", "email": "z.almansoor@synthetic-mail.test", "phone": "+1-555-0110", "segment": "HIGH_NET_WORTH"},
]

CITIES = [
    {"city": "New York", "country": "USA", "lat": 40.7128, "lon": -74.0060},
    {"city": "Los Angeles", "country": "USA", "lat": 34.0522, "lon": -118.2437},
    {"city": "Chicago", "country": "USA", "lat": 41.8781, "lon": -87.6298},
    {"city": "Houston", "country": "USA", "lat": 29.7604, "lon": -95.3698},
    {"city": "Miami", "country": "USA", "lat": 25.7617, "lon": -80.1918},
    {"city": "Seattle", "country": "USA", "lat": 47.6062, "lon": -122.3321},
    {"city": "London", "country": "UK", "lat": 51.5074, "lon": -0.1278},
    {"city": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
]

MERCHANTS = [
    ("Amazon Retail", "ONLINE_RETAIL"),
    ("Target Superstore", "GROCERY"),
    ("Shell Petroleum", "GAS_STATION"),
    ("Apple Store", "ELECTRONICS"),
    ("Starbucks Coffee", "DINING"),
    ("Uber Technologies", "TRANSPORTATION"),
    ("Delta Air Lines", "TRAVEL"),
    ("Best Buy Electronics", "ELECTRONICS"),
    ("Rolex Luxury Jeweler", "LUXURY_GOODS"),
    ("CryptoExchange Global", "CRYPTO_CURRENCY"),
]

def seed_rules_and_bands(db):
    """Seed fraud rules and risk bands if not already present."""
    default_rules = [
        {
            "rule_code": "RULE_HIGH_VALUE",
            "rule_name": "High-Value Transaction Threshold",
            "description": "Flags single transactions exceeding a configured monetary threshold.",
            "rule_type": "THRESHOLD",
            "parameters_json": {"threshold": 10000.00, "currency": "USD"},
            "risk_points": 35,
            "is_enabled": True
        },
        {
            "rule_code": "RULE_VELOCITY",
            "rule_name": "High Transaction Velocity",
            "description": "Detects rapid repeated transactions on the same account within a configured time window.",
            "rule_type": "FREQUENCY",
            "parameters_json": {"time_window_minutes": 60, "transaction_count_threshold": 3},
            "risk_points": 30,
            "is_enabled": True
        },
        {
            "rule_code": "RULE_UNUSUAL_TIMING",
            "rule_name": "Unusual Transaction Timing",
            "description": "Identifies transactions processed during atypical off-hours (default: 01:00 to 05:00 AM local time).",
            "rule_type": "TEMPORAL",
            "parameters_json": {"start_hour": 1, "end_hour": 5},
            "risk_points": 20,
            "is_enabled": True
        },
        {
            "rule_code": "RULE_GEO_ANOMALY",
            "rule_name": "Geographic Implausibility (Impossible Speed)",
            "description": "Detects consecutive transactions across distant locations at physically implausible travel speeds (> 800 km/h).",
            "rule_type": "GEOGRAPHIC",
            "parameters_json": {"speed_threshold_kmh": 800.0, "time_window_hours": 12},
            "risk_points": 40,
            "is_enabled": True
        },
        {
            "rule_code": "RULE_UNUSUAL_SPENDING",
            "rule_name": "Deviant Spending vs Historical Baseline",
            "description": "Compares transaction amount against customer 30-day baseline; flags amounts > 3x mean (requires min 5 txns).",
            "rule_type": "STATISTICAL",
            "parameters_json": {"baseline_multiplier": 3.0, "min_historical_txns": 5, "lookback_days": 30},
            "risk_points": 25,
            "is_enabled": True
        }
    ]

    for r in default_rules:
        exists = db.query(FraudRule).filter(FraudRule.rule_code == r["rule_code"]).first()
        if not exists:
            db.add(FraudRule(**r))

    default_bands = [
        {"category_name": "LOW", "min_score": 0, "max_score": 29, "color_hex": "#10b981", "description": "Low risk indicator - routine activity with minor anomalies"},
        {"category_name": "MEDIUM", "min_score": 30, "max_score": 59, "color_hex": "#f59e0b", "description": "Medium risk indicator - requires review if repeated"},
        {"category_name": "HIGH", "min_score": 60, "max_score": 79, "color_hex": "#f97316", "description": "High risk indicator - priority investigation required"},
        {"category_name": "CRITICAL", "min_score": 80, "max_score": 100, "color_hex": "#ef4444", "description": "Critical risk indicator - immediate operational hold recommended"}
    ]

    for b in default_bands:
        exists = db.query(RiskScoreConfiguration).filter(RiskScoreConfiguration.category_name == b["category_name"]).first()
        if not exists:
            db.add(RiskScoreConfiguration(**b))

    db.commit()

def seed_database(evaluate_alerts: bool = True):
    """Populates database with complete synthetic customer, account, and transaction datasets."""
    print("=" * 70)
    print("  Banking Transaction Monitoring - Synthetic Seed Generator")
    print("=" * 70)

    db = SessionLocal()
    try:
        # 1. Seed rules & configurations
        seed_rules_and_bands(db)

        # 2. Check if customers already exist
        existing_cust_count = db.query(Customer).count()
        if existing_cust_count > 0:
            print(f"[INFO] Database already contains {existing_cust_count} customers. Skipping duplicate insertion.")
            print("[INFO] If you want a fresh dataset, run with recreate option.")
            return

        print("[1/5] Seeding synthetic customers...")
        created_customers = []
        for c_data in SYNTHETIC_CUSTOMERS:
            cust = Customer(
                customer_ref=c_data["ref"],
                first_name=c_data["first"],
                last_name=c_data["last"],
                email=c_data["email"],
                phone=c_data["phone"],
                risk_segment=c_data["segment"],
                account_status="ACTIVE"
            )
            db.add(cust)
            created_customers.append(cust)
        db.commit()

        print(f"[2/5] Seeding accounts for {len(created_customers)} customers...")
        created_accounts = []
        acct_types = ["CHECKING", "SAVINGS", "CREDIT", "BUSINESS"]
        for cust in created_customers:
            # Create 1 checking account
            acct_chk = Account(
                account_number=f"ACCT-{random.randint(1000, 9999)}-{cust.customer_id:04d}",
                customer_id=cust.customer_id,
                account_type="CHECKING",
                currency="USD",
                current_balance=Decimal(str(round(random.uniform(2500, 45000), 2))),
                average_monthly_balance=Decimal(str(round(random.uniform(2000, 30000), 2))),
                status="ACTIVE"
            )
            db.add(acct_chk)
            created_accounts.append(acct_chk)

            # Create secondary savings account for some
            if random.random() > 0.3:
                acct_sav = Account(
                    account_number=f"ACCT-{random.randint(5000, 9999)}-SAV-{cust.customer_id:04d}",
                    customer_id=cust.customer_id,
                    account_type="SAVINGS",
                    currency="USD",
                    current_balance=Decimal(str(round(random.uniform(5000, 120000), 2))),
                    average_monthly_balance=Decimal(str(round(random.uniform(4000, 100000), 2))),
                    status="ACTIVE"
                )
                db.add(acct_sav)
                created_accounts.append(acct_sav)

        db.commit()

        print(f"[3/5] Generating ~400 realistic synthetic transactions across past 30 days...")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        base_time = now - timedelta(days=28)
        created_transactions = []
        tx_counter = 1

        channels = ["ONLINE", "MOBILE_APP", "POS", "ATM", "BRANCH"]
        types = ["CARD_PAYMENT", "ONLINE_PURCHASE", "TRANSFER", "WITHDRAWAL", "DEPOSIT"]

        # A. Generate regular baseline transactions for all accounts
        for day in range(28):
            day_time = base_time + timedelta(days=day)
            for acct in created_accounts:
                # 1 to 3 normal transactions per account per day
                num_daily = random.choice([0, 1, 1, 2])
                for _ in range(num_daily):
                    merchant, m_cat = random.choice(MERCHANTS[:7])
                    city_data = CITIES[0] if acct.customer_id % 2 == 0 else CITIES[1]
                    tx_hour = random.randint(8, 21)  # Normal daytime hours
                    tx_time = day_time.replace(hour=tx_hour, minute=random.randint(0, 59), second=random.randint(0, 59))
                    
                    # Normal transaction amount between $8 and $220
                    amount = Decimal(str(round(random.uniform(8.50, 220.00), 2)))

                    txn = Transaction(
                        transaction_ref=f"TXN-{tx_time.strftime('%Y%m')}-{tx_counter:05d}",
                        account_id=acct.account_id,
                        amount=amount,
                        currency="USD",
                        transaction_type=random.choice(types),
                        channel=random.choice(channels),
                        timestamp=tx_time,
                        location_city=city_data["city"],
                        location_country=city_data["country"],
                        latitude=Decimal(str(city_data["lat"] + random.uniform(-0.02, 0.02))),
                        longitude=Decimal(str(city_data["lon"] + random.uniform(-0.02, 0.02))),
                        device_id=f"DEV-APP-{acct.customer_id}-{random.randint(100, 999)}",
                        ip_address=f"198.51.100.{random.randint(10, 250)}",  # RFC 5737 doc IP
                        merchant_name=merchant,
                        merchant_category=m_cat,
                        status="COMPLETED",
                        is_evaluated=False
                    )
                    db.add(txn)
                    created_transactions.append(txn)
                    tx_counter += 1

        # B. Inject deliberate suspicious test scenarios:
        print("[4/5] Injecting curated fraud detection test scenarios...")

        # Test Scenario 1: High-Value Transactions (RULE_HIGH_VALUE)
        # Account 1 & 2 execute large sums
        for acct_idx, high_amt in [(0, 14500.00), (1, 28000.00), (2, 75000.00)]:
            t_time = now - timedelta(days=2, hours=random.randint(10, 16))
            txn = Transaction(
                transaction_ref=f"TXN-{t_time.strftime('%Y%m')}-{tx_counter:05d}",
                account_id=created_accounts[acct_idx].account_id,
                amount=Decimal(str(high_amt)),
                currency="USD",
                transaction_type="TRANSFER",
                channel="ONLINE",
                timestamp=t_time,
                location_city="New York",
                location_country="USA",
                latitude=Decimal("40.7128"),
                longitude=Decimal("-74.0060"),
                device_id="DEV-WEB-SEC-101",
                ip_address="198.51.100.88",
                merchant_name="Wire Transfer Escrow",
                merchant_category="WIRE_TRANSFER",
                status="COMPLETED",
                is_evaluated=False
            )
            db.add(txn)
            created_transactions.append(txn)
            tx_counter += 1

        # Test Scenario 2: Transaction Velocity (RULE_VELOCITY)
        # Account 3 executes 4 transactions within 25 minutes
        velo_base_time = now - timedelta(days=1, hours=14)
        for offset_mins in [0, 6, 14, 22]:
            t_time = velo_base_time + timedelta(minutes=offset_mins)
            txn = Transaction(
                transaction_ref=f"TXN-{t_time.strftime('%Y%m')}-{tx_counter:05d}",
                account_id=created_accounts[3].account_id,
                amount=Decimal(str(round(random.uniform(150, 400), 2))),
                currency="USD",
                transaction_type="CARD_PAYMENT",
                channel="POS",
                timestamp=t_time,
                location_city="Chicago",
                location_country="USA",
                latitude=Decimal("41.8781"),
                longitude=Decimal("-87.6298"),
                device_id="POS-TERMINAL-902",
                ip_address="198.51.100.99",
                merchant_name="Best Buy Electronics",
                merchant_category="ELECTRONICS",
                status="COMPLETED",
                is_evaluated=False
            )
            db.add(txn)
            created_transactions.append(txn)
            tx_counter += 1

        # Test Scenario 3: Unusual Timing (RULE_UNUSUAL_TIMING)
        # Transactions between 01:00 AM and 05:00 AM
        for acct_idx in [4, 5]:
            t_time = (now - timedelta(days=3)).replace(hour=2, minute=random.randint(15, 45))
            txn = Transaction(
                transaction_ref=f"TXN-{t_time.strftime('%Y%m')}-{tx_counter:05d}",
                account_id=created_accounts[acct_idx].account_id,
                amount=Decimal("380.00"),
                currency="USD",
                transaction_type="ATM",
                channel="ATM",
                timestamp=t_time,
                location_city="Miami",
                location_country="USA",
                latitude=Decimal("25.7617"),
                longitude=Decimal("-80.1918"),
                device_id="ATM-DRIVE-THRU-404",
                ip_address="198.51.100.111",
                merchant_name="Downtown ATM #4",
                merchant_category="CASH_DISBURSEMENT",
                status="COMPLETED",
                is_evaluated=False
            )
            db.add(txn)
            created_transactions.append(txn)
            tx_counter += 1

        # Test Scenario 4: Geographic Implausibility (RULE_GEO_ANOMALY)
        # Account 6 transacts in New York at 10:00 AM, then in London at 10:40 AM (5,500 km in 40 mins!)
        geo_time_1 = (now - timedelta(days=4)).replace(hour=10, minute=0)
        geo_time_2 = (now - timedelta(days=4)).replace(hour=10, minute=40)

        txn_geo_1 = Transaction(
            transaction_ref=f"TXN-{geo_time_1.strftime('%Y%m')}-{tx_counter:05d}",
            account_id=created_accounts[6].account_id,
            amount=Decimal("45.00"),
            currency="USD",
            transaction_type="CARD_PAYMENT",
            channel="POS",
            timestamp=geo_time_1,
            location_city="New York",
            location_country="USA",
            latitude=Decimal("40.7128"),
            longitude=Decimal("-74.0060"),
            device_id="POS-CAFE-NYC-1",
            ip_address="198.51.100.120",
            merchant_name="Starbucks Coffee",
            merchant_category="DINING",
            status="COMPLETED",
            is_evaluated=False
        )
        db.add(txn_geo_1)
        created_transactions.append(txn_geo_1)
        tx_counter += 1

        txn_geo_2 = Transaction(
            transaction_ref=f"TXN-{geo_time_2.strftime('%Y%m')}-{tx_counter:05d}",
            account_id=created_accounts[6].account_id,
            amount=Decimal("1850.00"),
            currency="USD",
            transaction_type="CARD_PAYMENT",
            channel="POS",
            timestamp=geo_time_2,
            location_city="London",
            location_country="UK",
            latitude=Decimal("51.5074"),
            longitude=Decimal("-0.1278"),
            device_id="POS-JEWELRY-LON-8",
            ip_address="198.51.100.121",
            merchant_name="Rolex Luxury Jeweler",
            merchant_category="LUXURY_GOODS",
            status="COMPLETED",
            is_evaluated=False
        )
        db.add(txn_geo_2)
        created_transactions.append(txn_geo_2)
        tx_counter += 1

        # Test Scenario 5: Deviant Spending vs Baseline (RULE_UNUSUAL_SPENDING)
        # Account 7 (which has dozens of $20-$80 transactions) suddenly executes an $1,850 online purchase
        spend_time = now - timedelta(days=1, hours=16)
        txn_spend = Transaction(
            transaction_ref=f"TXN-{spend_time.strftime('%Y%m')}-{tx_counter:05d}",
            account_id=created_accounts[7].account_id,
            amount=Decimal("2450.00"),
            currency="USD",
            transaction_type="ONLINE_PURCHASE",
            channel="ONLINE",
            timestamp=spend_time,
            location_city="Seattle",
            location_country="USA",
            latitude=Decimal("47.6062"),
            longitude=Decimal("-122.3321"),
            device_id="DEV-SAFARI-MAC-44",
            ip_address="198.51.100.133",
            merchant_name="CryptoExchange Global",
            merchant_category="CRYPTO_CURRENCY",
            status="COMPLETED",
            is_evaluated=False
        )
        db.add(txn_spend)
        created_transactions.append(txn_spend)
        tx_counter += 1

        # Test Scenario 6: Multi-Rule Compound Trigger (Critical Risk: High Value + Off-Hours + Crypto)
        multi_time = (now - timedelta(hours=14)).replace(hour=3, minute=20)
        txn_multi = Transaction(
            transaction_ref=f"TXN-{multi_time.strftime('%Y%m')}-{tx_counter:05d}",
            account_id=created_accounts[8].account_id,
            amount=Decimal("18900.00"),
            currency="USD",
            transaction_type="TRANSFER",
            channel="ONLINE",
            timestamp=multi_time,
            location_city="Houston",
            location_country="USA",
            latitude=Decimal("29.7604"),
            longitude=Decimal("-95.3698"),
            device_id="DEV-UNKNOWN-TOR-01",
            ip_address="198.51.100.200",
            merchant_name="CryptoExchange Global",
            merchant_category="CRYPTO_CURRENCY",
            status="COMPLETED",
            is_evaluated=False
        )
        db.add(txn_multi)
        created_transactions.append(txn_multi)
        tx_counter += 1

        db.commit()
        print(f"[SUCCESS] Successfully seeded {len(created_transactions)} synthetic transactions.")

        # 5. Evaluate transactions through Rule Engine to create baseline alerts
        if evaluate_alerts:
            print("[5/5] Evaluating transactions with Rule Engine to generate initial alert queue...")
            db.commit()
            
            # Sort transactions chronologically for evaluation
            all_txns = db.query(Transaction).order_by(Transaction.timestamp.asc()).all()
            alert_count = 0
            for tx in all_txns:
                score, cat, results, alert = rule_engine.evaluate_transaction(tx, db)
                if alert:
                    alert_count += 1

            # Seed a sample investigation note on the top critical alert
            top_alert = db.query(Alert).filter(Alert.risk_category == "CRITICAL").first()
            if top_alert:
                top_alert.status = "UNDER_INVESTIGATION"
                top_alert.assigned_to = "Senior Risk Officer"
                note = InvestigationNote(
                    alert_id=top_alert.alert_id,
                    author="Senior Risk Officer",
                    note_text="High priority investigation opened: compounding indicators of high monetary value, off-hours execution, and crypto merchant category. Account contacted for verification.",
                    action_taken="Customer Contacted"
                )
                db.add(note)
                db.commit()

            print(f"[SUCCESS] Rule engine evaluated {len(all_txns)} transactions. Generated {alert_count} explainable alerts.")

        print("=" * 70)
        print("  Database seeding complete! System is fully operational.")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Database seeding failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
