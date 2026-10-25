# Automated Testing & Verification Documentation

## 1. Overview of Test Architecture

The automated test suite is built with `pytest` and FastAPI's `TestClient` (backed by `httpx`).

To guarantee fast, deterministic, and isolated execution, the test suite uses an in-memory SQLite database configured with `StaticPool` and dynamic schema generation:
- Runs in **under 1 second**.
- Requires **zero external network access**.
- Does not modify or rely on the local MySQL database.
- Completely wipes and regenerates tables between tests to guarantee zero test pollution.

---

## 2. Test Execution Command

From PowerShell:

```powershell
$env:PYTHONPATH="c:\Users\harsh\OneDrive\Desktop\Banking-Fraud-Monitoring"
& "c:\Users\harsh\OneDrive\Desktop\Banking-Fraud-Monitoring\backend\venv\Scripts\python.exe" -m pytest "backend/tests" -v
```

---

## 3. Test Suites & Coverage Breakdown

### 3.1 `test_rules.py` (Rule Engine Unit Tests)
- `test_high_value_rule_triggers_above_threshold`: Verifies transaction > $10,000 flags and awards 35 points.
- `test_high_value_rule_does_not_trigger_below_threshold`: Verifies ordinary amount ($250) passes cleanly.
- `test_velocity_rule_triggers_on_rapid_transactions`: Verifies 4 rapid transactions within 30 minutes trigger velocity rule.
- `test_unusual_timing_rule_identifies_off_hours`: Verifies 03:30 AM flags while 14:30 PM passes.
- `test_geographic_anomaly_detects_impossible_speed`: Verifies NYC to London in 45 mins (>7,000 km/h) triggers impossible speed rule.
- `test_geographic_anomaly_does_not_flag_plausible_travel`: Verifies NYC to Philadelphia in 3 hours (50 km/h) passes without false alert.
- `test_unusual_spending_insufficient_history`: Verifies that having only 2 historical transactions returns `insufficient_data` instead of a fabricated baseline.
- `test_unusual_spending_triggers_when_exceeding_baseline`: Verifies that a transaction > 3x the 6-transaction baseline triggers correctly.

### 3.2 `test_scoring.py` (Scoring Engine & Idempotency)
- `test_risk_band_mapping`: Tests boundary conditions (0, 29, 30, 59, 60, 79, 80, 100).
- `test_risk_bands_no_gaps_or_overlaps`: Mathematical continuity validation for score band definitions.
- `test_score_capped_at_max`: Ensures compound score sums are strictly capped at 100.
- `test_duplicate_alert_prevention_idempotency`: Verifies re-evaluating an existing transaction updates or retains the existing alert rather than generating duplicate alert records.
- `test_disabled_rule_does_not_fire`: Confirms that setting `is_enabled = False` in database completely prevents that rule from awarding points.

### 3.3 `test_api.py` (FastAPI REST Endpoints)
- `test_health_endpoint`: Validates HTTP 200 health response and database health reporting.
- `test_create_and_list_transactions`: Tests POST `/api/transactions` and GET `/api/transactions` with pagination.
- `test_invalid_transaction_amount_rejected`: Verifies Pydantic rejects negative amounts with HTTP 422.
- `test_evaluate_single_transaction_api`: Validates the single-transaction evaluation endpoint.
- `test_alert_status_workflow_and_notes`: End-to-end investigation workflow test: OPEN -> UNDER_INVESTIGATION -> Add Note -> RESOLVED.
- `test_invalid_alert_status_rejected`: Verifies invalid status strings return HTTP 422.
- `test_analytics_dashboard_endpoint`: Validates structure of `/api/analytics/dashboard`.

### 3.4 `test_frontend_routes.py` (Static Route Verification)
- Verifies all 5 HTML views (`/`, `/transactions`, `/alerts`, `/rules`, `/customers`) serve HTTP 200 with HTML content.
- Verifies static CSS (`/static/css/style.css`) and JS (`/static/js/api.js`) are served properly.
