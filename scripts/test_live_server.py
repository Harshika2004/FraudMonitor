import os
import sys
import time
import json
import urllib.request
import urllib.parse
import subprocess
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

def test_http_endpoint(method, path, body=None, headers=None):
    url = f"{BASE_URL}{path}"
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    
    data = None
    if body is not None:
        if isinstance(body, dict):
            data = json.dumps(body).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(body, bytes):
            data = body
        elif isinstance(body, str):
            data = body.encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return resp.status, json.loads(content.decode("utf-8"))
            return resp.status, content.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(err_content)
        except Exception:
            return e.code, err_content
    except Exception as e:
        return 0, str(e)

def run_tests():
    print("=" * 65)
    print("  RUNNING COMPREHENSIVE END-TO-END SYSTEM TEST")
    print("=" * 65)

    # 1. Test HTML views
    pages = ["/", "/transactions", "/alerts", "/rules", "/customers"]
    for page in pages:
        status, content = test_http_endpoint("GET", page, headers={"Accept": "text/html"})
        assert status == 200, f"Page {page} returned status {status}"
        print(f"  [PASS] HTML Page {page:15} -> Status 200 OK ({len(content):,} bytes)")

    # 2. Test API Health
    status, health = test_http_endpoint("GET", "/api/health")
    assert status == 200 and health.get("status") == "healthy", f"Health check failed: {health}"
    print(f"  [PASS] API Health Check        -> {health['status']} (DB: {health.get('database')})")

    # 3. Test Active Dataset API
    status, active_ds = test_http_endpoint("GET", "/api/datasets/active")
    assert status == 200, f"Active dataset check failed: {status}"
    ds = active_ds.get("dataset")
    print(f"  [PASS] Active Dataset API      -> ID={ds['dataset_id'] if ds else 'None'}, Name={ds['filename'] if ds else 'None'}, Status={ds['status'] if ds else 'None'}")

    # 4. Test Preview with Sample CSV
    csv_path = Path("C:/Users/harsh/.gemini/antigravity/brain/4f497fdb-ab08-4f30-9c5d-40fbad4448e5/.user_uploaded/media_1793699065769_0256e41f.csv")
    if not csv_path.exists():
        csv_path = Path("test_sample.csv")
        csv_path.write_text("account_id,amount,transaction_type,timestamp,location_city\nACC100155,1000.0,WITHDRAWAL,2026-11-01 10:00:00,New York\n")

    csv_bytes = csv_path.read_bytes()
    boundary = "----WebKitFormBoundaryE2ETest7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="sample_transactions.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + csv_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    status, preview = test_http_endpoint(
        "POST",
        "/api/datasets/preview",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    assert status == 200, f"Preview failed: {status} {preview}"
    assert preview["validation_passed"] is True, f"Validation failed: {preview}"
    print(f"  [PASS] CSV Preview & Validate  -> {preview['total_rows']:,} rows, {preview['total_columns']} cols (Valid: {preview['validation_passed']})")

    # 5. Confirm and Import
    token = preview["temp_file_token"]
    status, confirmed = test_http_endpoint("POST", "/api/datasets/confirm", body={
        "temp_file_token": token,
        "filename": "sample_transactions.csv",
        "file_size_bytes": len(csv_bytes),
        "column_mapping": {}
    })
    assert status == 200 and confirmed.get("status") == "UPLOADED", f"Confirm failed: {confirmed}"
    new_dataset_id = confirmed["dataset_id"]
    print(f"  [PASS] Confirm & Import CSV   -> Dataset ID {new_dataset_id} created in 'UPLOADED' status")

    # 6. Run Fraud Risk Analysis
    status, analyzed = test_http_endpoint("POST", f"/api/datasets/{new_dataset_id}/analyze")
    assert status == 200 and analyzed.get("status") == "ANALYSED", f"Analysis failed: {analyzed}"
    print(f"  [PASS] Run Fraud Analysis     -> Evaluated {analyzed['evaluated_transactions']:,} txns, Clean: {analyzed['clean_transactions']:,}, Flagged: {analyzed['flagged_transactions']:,}, Alerts: {analyzed['open_alerts']:,}")

    # 7. Verify Dashboard Analytics (Scoped to new dataset)
    status, dash = test_http_endpoint("GET", "/api/analytics/dashboard")
    assert status == 200, f"Dashboard failed: {status}"
    kpi = dash["kpi"]
    assert kpi["total_transactions"] == analyzed["total_transactions"], "KPI mismatch on total txns"
    print(f"  [PASS] Dashboard Analytics     -> Monitored Vol: ${kpi['total_monitored_volume']:,.2f}, Flagged Vol: ${kpi['flagged_volume']:,.2f}, Flag Rate: {kpi['flag_rate_percentage']}%")

    # 8. Verify Transactions Queue (Scoped to new dataset)
    status, txns = test_http_endpoint("GET", "/api/transactions?page=1&page_size=10")
    assert status == 200, f"Transactions failed: {status}"
    print(f"  [PASS] Transactions Stream     -> Retrieved {len(txns['items'])} items (Total in active dataset: {txns['total']:,})")

    # 9. Verify Alerts Queue (Scoped to new dataset)
    status, alerts = test_http_endpoint("GET", "/api/alerts?page=1&page_size=10")
    assert status == 200, f"Alerts failed: {status}"
    print(f"  [PASS] Alerts Investigation    -> Retrieved {len(alerts['items'])} items (Total open alerts: {alerts['total']:,})")

    # 10. Test Dataset Switching (Switch back to Dataset 1)
    status, switched = test_http_endpoint("POST", "/api/datasets/switch/1")
    assert status == 200 and switched.get("dataset_id") == 1, f"Switch failed: {switched}"
    status, dash1 = test_http_endpoint("GET", "/api/analytics/dashboard")
    assert status == 200, f"Dashboard after switch failed: {status}"
    print(f"  [PASS] Dataset Switcher API    -> Switched back to Dataset 1 ({dash1['kpi']['total_transactions']:,} transactions restored)")

    print("=" * 65)
    print("  ALL END-TO-END TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
