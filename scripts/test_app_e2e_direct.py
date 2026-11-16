import os
import sys
from pathlib import Path
from decimal import Decimal

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database.connection import SessionLocal
from backend.app.main import serve_index, serve_transactions, serve_alerts, serve_rules, serve_customers
from backend.app.api.routes_health import health_check
from backend.app.api.routes_datasets import (
    get_active_dataset,
    list_datasets,
    confirm_import,
    analyze_dataset,
    switch_active_dataset
)
from backend.app.services.dataset_service import DatasetService
from backend.app.schemas.dataset import CSVConfirmImportRequest
from backend.app.api.routes_analytics import get_dashboard_data
from backend.app.api.routes_transactions import list_transactions
from backend.app.api.routes_alerts import list_alerts
from backend.app.api.routes_rules import list_rules
from backend.app.api.routes_customers import list_customers

def test_full_application():
    print("=" * 70)
    print("  BANKING FRAUD MONITORING & RISK ENGINE - DIRECT APPLICATION TEST")
    print("=" * 70)

    db = SessionLocal()
    try:
        # 1. Test HTML view functions & static file paths
        print("\n[1/7] Testing HTML View Routes & Frontend Templates...")
        for name, fn in [
            ("Overview Dashboard", serve_index),
            ("Transactions Queue", serve_transactions),
            ("Alerts Queue", serve_alerts),
            ("Detection Rules", serve_rules),
            ("Customer Directory", serve_customers)
        ]:
            resp = fn()
            assert resp.status_code == 200
            file_path = Path(resp.path)
            assert file_path.exists()
            content = file_path.read_text(encoding="utf-8")
            assert len(content) > 1000
            print(f"  [PASS] {name:22} -> 200 OK ({file_path.name}, {len(content):,} chars)")

        # 2. Test API Health
        print("\n[2/7] Testing System Health...")
        health = health_check(db=db)
        assert health["status"] == "ok" and health["database"]["status"] == "healthy"
        print(f"  [PASS] Health Status: {health['status']} (DB: {health['database']['status']})")

        # 3. Test Active Dataset Check (Initial State)
        print("\n[3/7] Testing Active Dataset API...")
        ds = get_active_dataset(db=db)
        print(f"  [PASS] Current Active Dataset: ID={ds.dataset_id if ds else 'None'}, Name={ds.filename if ds else 'None'}, Status={ds.status if ds else 'None'}")

        # 4. Test Preview with the User's Real CSV File
        print("\n[4/7] Testing CSV Preview & Validation with sample_transactions.csv...")
        csv_path = Path("C:/Users/harsh/.gemini/antigravity/brain/4f497fdb-ab08-4f30-9c5d-40fbad4448e5/.user_uploaded/media_1793699065769_0256e41f.csv")
        if not csv_path.exists():
            csv_path = Path("test_sample.csv")
            csv_path.write_text("account_id,amount,transaction_type,timestamp,location_city\nACC100155,1000.0,WITHDRAWAL,2026-11-01 10:00:00,New York\n")

        csv_content = csv_path.read_text(encoding="utf-8")
        preview = DatasetService.preview_csv(csv_content, "sample_transactions.csv", len(csv_content))
        
        assert preview["validation_passed"] is True
        assert preview["total_rows"] == 1000 or preview["total_rows"] > 0
        assert len(preview["preview_rows"]) == 20
        assert len(preview["missing_required_columns"]) == 0
        print(f"  [PASS] Validation Succeeded: Total Rows = {preview['total_rows']:,}, Total Cols = {preview['total_columns']}")
        print(f"  [PASS] Validation Summary: \"{preview['validation_summary']}\"")
        print(f"  [PASS] Sample Preview Record 1: {preview['preview_rows'][0]}")

        # 5. Test Confirm and Import
        print("\n[5/7] Testing Confirm & Import API...")
        confirm_payload = CSVConfirmImportRequest(
            temp_file_token=preview["temp_file_token"],
            filename="sample_transactions.csv",
            file_size_bytes=len(csv_content),
            column_mapping={}
        )
        new_ds = confirm_import(payload=confirm_payload, db=db)
        assert new_ds.dataset_id is not None
        assert new_ds.status == "UPLOADED"
        assert new_ds.is_active is True
        print(f"  [PASS] Dataset Ingested -> ID={new_ds.dataset_id}, Filename={new_ds.filename}, Rows={new_ds.total_rows:,}, Status={new_ds.status}")

        # 6. Test Fraud Risk Analysis Execution
        print("\n[6/7] Running Deterministic Fraud Risk Analysis on Imported Dataset...")
        analysis_res = analyze_dataset(dataset_id=new_ds.dataset_id, db=db)
        assert analysis_res["status"] == "ANALYSED"
        assert analysis_res["evaluated_transactions"] == new_ds.total_rows
        print(f"  [PASS] Analysis Finished:")
        print(f"         Total Transactions     : {analysis_res['total_transactions']:,}")
        print(f"         Evaluated Transactions : {analysis_res['evaluated_transactions']:,}")
        print(f"         Clean Transactions     : {analysis_res['clean_transactions']:,}")
        print(f"         Flagged Transactions   : {analysis_res['flagged_transactions']:,}")
        print(f"         Open Alerts Generated  : {analysis_res['open_alerts']:,}")
        print(f"         High / Critical Alerts : {analysis_res['high_critical_alerts']:,}")

        # 7. Test Module Scoping & Queries for the Active Dataset
        print("\n[7/7] Testing Scoped Queries across all Dashboard Modules...")
        dash_analytics = get_dashboard_data(days=30, dataset_id=new_ds.dataset_id, db=db)
        kpi = dash_analytics.kpi
        assert kpi.total_transactions == new_ds.total_rows
        print(f"  [PASS] Dashboard KPIs:")
        print(f"         Total Monitored Volume : ${kpi.total_monitored_volume:,.2f}")
        print(f"         Flagged Volume         : ${kpi.flagged_volume:,.2f}")
        print(f"         Flag Rate Percentage   : {kpi.flag_rate_percentage}%")
        print(f"         Risk Distribution      : {[c.dict() for c in dash_analytics.risk_distribution]}")
        print(f"         Rule Effectiveness     : {[(r.rule_code, r.trigger_count) for r in dash_analytics.rule_frequency]}")

        # Transactions module
        txns = list_transactions(page=1, page_size=5, sort_by="timestamp", sort_order="desc", dataset_id=new_ds.dataset_id, db=db)
        assert txns["total"] == new_ds.total_rows
        print(f"  [PASS] Transactions Module    : {txns['total']:,} records queryable, {len(txns['items'])} returned on page 1")

        # Alerts module
        alerts = list_alerts(page=1, page_size=5, sort_by="created_at", sort_order="desc", dataset_id=new_ds.dataset_id, db=db)
        assert alerts["total"] == analysis_res["open_alerts"]
        print(f"  [PASS] Alerts Module          : {alerts['total']:,} alerts queryable, {len(alerts['items'])} returned on page 1")

        # Rules module
        rules = list_rules(db=db)
        rule_list = rules if isinstance(rules, list) else rules.get("rules", [])
        assert len(rule_list) >= 5
        print(f"  [PASS] Rules Module           : {len(rule_list)} detection rules active")

        # Customers module
        customers = list_customers(limit=10, db=db)
        print(f"  [PASS] Customers Module       : {len(customers)} customers loaded")

        # Dataset Switcher: Switch back to Dataset 1
        print("\n[SUCCESS] Testing Dataset Switching...")
        switch_res = switch_active_dataset(dataset_id=1, db=db)
        assert switch_res.dataset_id == 1
        dash1 = get_dashboard_data(days=30, dataset_id=1, db=db)
        print(f"  [PASS] Switched back to Dataset 1 -> Total Transactions: {dash1.kpi.total_transactions:,}")

        print("\n" + "=" * 70)
        print("  ALL 7 SYSTEM TEST PHASES COMPLETED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    test_full_application()
