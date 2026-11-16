"""
Test script for verifying Scenarios A, B, C, and D of the Customer / Account Directory logic.
"""
import sys
import os
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database.connection import SessionLocal
from backend.app.models.dataset import Dataset
from backend.app.models.customer import Customer
from backend.app.models.account import Account
from backend.app.models.transaction import Transaction
from backend.app.models.alert import Alert
from backend.app.services.dataset_service import DatasetService, PREVIEW_CACHE
from backend.app.rules.engine import rule_engine

def run_tests():
    db = SessionLocal()
    print("=" * 70)
    print("STARTING DIRECTORY DATA LOGIC VERIFICATION SUITE")
    print("=" * 70)

    try:
        # -------------------------------------------------------------
        # SCENARIO A: CSV containing account_id only (no customer identity, no balance)
        # -------------------------------------------------------------
        print("\n--- Testing Scenario A: account_id only ---")
        csv_a = (
            "account_id,amount,transaction_type,timestamp,location_city\n"
            "ACC-A101,150.00,PURCHASE,2026-03-01T10:00:00Z,New York\n"
            "ACC-A101,12000.00,TRANSFER,2026-03-01T11:00:00Z,New York\n"
            "ACC-A102,80.00,PURCHASE,2026-03-01T12:00:00Z,Chicago\n"
        )
        token_a = "token_scenario_a"
        PREVIEW_CACHE[token_a] = {
            "filename": "scenario_a.csv",
            "file_size": len(csv_a),
            "content": csv_a,
            "validation": {}
        }
        ds_a = DatasetService.confirm_and_import(db, token_a, "scenario_a.csv", len(csv_a))
        eval_res_a = DatasetService.run_analysis(db, ds_a.dataset_id)
        print(f"Scenario A imported: dataset_id={ds_a.dataset_id}, eval={eval_res_a}")

        # Query directory logic (import route logic directly or simulate)
        from backend.app.api.routes_customers import list_customers
        res_a = list_customers(dataset_id=ds_a.dataset_id, db=db)
        
        assert res_a["mode"] == "ACCOUNT", f"Expected mode 'ACCOUNT', got {res_a['mode']}"
        assert res_a["title"] == "Account Directory", f"Expected title 'Account Directory', got {res_a['title']}"
        assert res_a["has_balance"] == False, f"Expected has_balance False, got {res_a['has_balance']}"
        assert len(res_a["items"]) == 2, f"Expected 2 accounts, got {len(res_a['items'])}"

        # Check account ACC-A101
        acc_a101 = next(item for item in res_a["items"] if item["identifier"] == "ACC-A101")
        assert acc_a101["account_count"] is None, f"Expected account_count None, got {acc_a101['account_count']}"
        assert acc_a101["name"] == "Not provided", f"Expected name 'Not provided', got {acc_a101['name']}"
        assert acc_a101["email"] == "Not provided", f"Expected email 'Not provided', got {acc_a101['email']}"
        assert acc_a101["total_balance"] is None, f"Expected total_balance None, got {acc_a101['total_balance']}"
        assert acc_a101["transaction_count"] == 2, f"Expected 2 txns for ACC-A101, got {acc_a101['transaction_count']}"
        assert acc_a101["alert_count"] >= 1, f"Expected >= 1 alert for ACC-A101, got {acc_a101['alert_count']}"
        assert acc_a101["risk_segment"] in ("MEDIUM", "HIGH", "CRITICAL"), f"Expected MEDIUM/HIGH/CRITICAL, got {acc_a101['risk_segment']}"

        # Check account ACC-A102
        acc_a102 = next(item for item in res_a["items"] if item["identifier"] == "ACC-A102")
        assert acc_a102["transaction_count"] == 1, f"Expected 1 txn for ACC-A102, got {acc_a102['transaction_count']}"
        assert acc_a102["alert_count"] == 0, f"Expected 0 alerts for ACC-A102, got {acc_a102['alert_count']}"
        assert acc_a102["risk_segment"] == "LOW", f"Expected LOW, got {acc_a102['risk_segment']}"
        print("PASS: Scenario A verified (Account Directory, no Accounts col, no fake customer, no fake balance).")

        # -------------------------------------------------------------
        # SCENARIO B: CSV containing account_id, customer_name, email (no customer_id, no balance)
        # -------------------------------------------------------------
        print("\n--- Testing Scenario B: account_id, customer_name, email ---")
        csv_b = (
            "account_id,amount,transaction_type,timestamp,location_city,customer_name,email\n"
            "ACC-B201,300.00,PURCHASE,2026-03-02T09:00:00Z,Boston,Alice Smith,alice@example.com\n"
            "ACC-B201,250.00,PURCHASE,2026-03-02T10:00:00Z,Boston,Alice Smith,alice@example.com\n"
            "ACC-B202,500.00,PURCHASE,2026-03-02T11:00:00Z,Boston,Bob Jones,bob@example.com\n"
        )
        token_b = "token_scenario_b"
        PREVIEW_CACHE[token_b] = {
            "filename": "scenario_b.csv",
            "file_size": len(csv_b),
            "content": csv_b,
            "validation": {}
        }
        ds_b = DatasetService.confirm_and_import(db, token_b, "scenario_b.csv", len(csv_b))
        eval_res_b = DatasetService.run_analysis(db, ds_b.dataset_id)
        print(f"Scenario B imported: dataset_id={ds_b.dataset_id}, eval={eval_res_b}")

        res_b = list_customers(dataset_id=ds_b.dataset_id, db=db)
        assert res_b["mode"] == "ACCOUNT", f"Expected mode 'ACCOUNT', got {res_b['mode']}"
        assert res_b["title"] == "Account Directory", f"Expected title 'Account Directory', got {res_b['title']}"
        assert res_b["has_balance"] == False, f"Expected has_balance False, got {res_b['has_balance']}"
        assert len(res_b["items"]) == 2, f"Expected 2 accounts, got {len(res_b['items'])}"

        # Check account ACC-B201
        acc_b201 = next(item for item in res_b["items"] if item["identifier"] == "ACC-B201")
        assert acc_b201["name"] == "Alice Smith", f"Expected 'Alice Smith', got {acc_b201['name']}"
        assert acc_b201["email"] == "alice@example.com", f"Expected 'alice@example.com', got {acc_b201['email']}"
        assert acc_b201["account_count"] is None, f"Expected account_count None, got {acc_b201['account_count']}"
        assert acc_b201["transaction_count"] == 2, f"Expected 2 txns, got {acc_b201['transaction_count']}"

        # Verify no Customer records exist for dataset B
        cust_cnt_b = db.query(Customer).filter(Customer.dataset_id == ds_b.dataset_id).count()
        assert cust_cnt_b == 0, f"Expected 0 Customer records, got {cust_cnt_b}"
        print("PASS: Scenario B verified (Account Directory with actual names & emails, no fake Customer IDs).")

        # -------------------------------------------------------------
        # SCENARIO C: CSV containing customer_id, customer_name, email, multiple accounts, balance
        # -------------------------------------------------------------
        print("\n--- Testing Scenario C: customer_id, customer_name, email, multi-account, balance ---")
        csv_c = (
            "customer_id,account_id,amount,transaction_type,timestamp,location_city,customer_name,email,account_balance\n"
            "CUST-C01,ACC-C1,50.00,PURCHASE,2026-03-03T10:00:00Z,Seattle,Charlie Brown,charlie@bank.com,4500.50\n"
            "CUST-C01,ACC-C1,60.00,PURCHASE,2026-03-03T11:00:00Z,Seattle,Charlie Brown,charlie@bank.com,4500.50\n"
            "CUST-C01,ACC-C2,15000.00,TRANSFER,2026-03-03T12:00:00Z,Seattle,Charlie Brown,charlie@bank.com,18000.00\n"
            "CUST-C02,ACC-C3,120.00,PURCHASE,2026-03-03T13:00:00Z,Portland,Dana White,dana@bank.com,1200.00\n"
        )
        token_c = "token_scenario_c"
        PREVIEW_CACHE[token_c] = {
            "filename": "scenario_c.csv",
            "file_size": len(csv_c),
            "content": csv_c,
            "validation": {}
        }
        ds_c = DatasetService.confirm_and_import(db, token_c, "scenario_c.csv", len(csv_c))
        eval_res_c = DatasetService.run_analysis(db, ds_c.dataset_id)
        print(f"Scenario C imported: dataset_id={ds_c.dataset_id}, eval={eval_res_c}")

        res_c = list_customers(dataset_id=ds_c.dataset_id, db=db)
        assert res_c["mode"] == "CUSTOMER", f"Expected mode 'CUSTOMER', got {res_c['mode']}"
        assert res_c["title"] == "Customer Directory", f"Expected title 'Customer Directory', got {res_c['title']}"
        assert res_c["has_balance"] == True, f"Expected has_balance True, got {res_c['has_balance']}"
        assert len(res_c["items"]) == 2, f"Expected 2 customers, got {len(res_c['items'])}"

        # Check Charlie Brown (CUST-C01)
        c01 = next(item for item in res_c["items"] if item["identifier"] == "CUST-C01")
        assert c01["name"] == "Charlie Brown", f"Expected 'Charlie Brown', got {c01['name']}"
        assert c01["email"] == "charlie@bank.com", f"Expected 'charlie@bank.com', got {c01['email']}"
        # CRUCIAL: Charlie has 2 distinct accounts (ACC-C1, ACC-C2), NOT 3 rows!
        assert c01["account_count"] == 2, f"Expected 2 distinct accounts, got {c01['account_count']}"
        # Transaction count is 3
        assert c01["transaction_count"] == 3, f"Expected 3 txns, got {c01['transaction_count']}"
        # Total balance = 4500.50 + 18000.00 = 22500.50
        assert abs(c01["total_balance"] - 22500.50) < 0.01, f"Expected total_balance ~22500.50, got {c01['total_balance']}"
        # Risk score and alert
        assert c01["alert_count"] >= 1, f"Expected >= 1 alert, got {c01['alert_count']}"
        assert c01["risk_segment"] in ("MEDIUM", "HIGH", "CRITICAL"), f"Expected MEDIUM/HIGH/CRITICAL, got {c01['risk_segment']}"

        # Check Dana White (CUST-C02)
        c02 = next(item for item in res_c["items"] if item["identifier"] == "CUST-C02")
        assert c02["name"] == "Dana White", f"Expected 'Dana White', got {c02['name']}"
        assert c02["account_count"] == 1, f"Expected 1 account, got {c02['account_count']}"
        assert c02["transaction_count"] == 1, f"Expected 1 txn, got {c02['transaction_count']}"
        assert abs(c02["total_balance"] - 1200.00) < 0.01, f"Expected balance ~1200.00, got {c02['total_balance']}"
        print("PASS: Scenario C verified (Customer Directory, distinct account counts, accurate balances, dynamic risk).")

        # -------------------------------------------------------------
        # SCENARIO D: Switching from one dataset to another
        # -------------------------------------------------------------
        print("\n--- Testing Scenario D: Switching datasets ---")
        # Switch active back to dataset A
        db.query(Dataset).update({Dataset.is_active: False})
        active_a = db.query(Dataset).filter(Dataset.dataset_id == ds_a.dataset_id).first()
        active_a.is_active = True
        db.commit()

        # Query directory without passing dataset_id (should resolve active dataset A)
        res_d_a = list_customers(db=db)
        assert res_d_a["mode"] == "ACCOUNT", f"Expected mode 'ACCOUNT' for active A, got {res_d_a['mode']}"
        assert len(res_d_a["items"]) == 2, f"Expected 2 accounts, got {len(res_d_a['items'])}"
        identifiers_a = [item["identifier"] for item in res_d_a["items"]]
        assert "ACC-A101" in identifiers_a and "ACC-A102" in identifiers_a
        assert "CUST-C01" not in identifiers_a
        assert "ACC-C1" not in identifiers_a

        # Switch active to dataset C
        db.query(Dataset).update({Dataset.is_active: False})
        active_c = db.query(Dataset).filter(Dataset.dataset_id == ds_c.dataset_id).first()
        active_c.is_active = True
        db.commit()

        res_d_c = list_customers(db=db)
        assert res_d_c["mode"] == "CUSTOMER", f"Expected mode 'CUSTOMER' for active C, got {res_d_c['mode']}"
        assert len(res_d_c["items"]) == 2, f"Expected 2 customers, got {len(res_d_c['items'])}"
        identifiers_c = [item["identifier"] for item in res_d_c["items"]]
        assert "CUST-C01" in identifiers_c and "CUST-C02" in identifiers_c
        assert "ACC-A101" not in identifiers_c
        print("PASS: Scenario D verified (No cross-contamination, clean switching, no stale records).")

        print("\n" + "=" * 70)
        print("ALL VERIFICATION SUITE TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
